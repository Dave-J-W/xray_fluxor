"""Install, or compare, one monitor lane (calc/lanes.py) on utilioc. It replaces the per-slot installers.

  --compare   read-only: diff every generated field against the live IOC, and write nothing
  --dry-run   list what would be written
  (default)   install the five slots in dependency order through calc/slotlib.install(). That is
              guarded: it refuses a slot owned by someone else, writes with readback, and verifies.

Hand-set values (pressure G on the pressure lane; background F/G/I) are written only to a fresh
slot (DESC not ours), or with --reset-values, so a re-run never overwrites the live pressure or
a tuned threshold.

Lane EStn (the E-station lane, calc/estation_lane.py) uses the same guarded installer, with a different commissioning
order for its flux slot (the TetrAMM links go in last) and a --remove that returns its four slots to their free defaults.

Usage: <bluesky venv>\\Scripts\\python.exe -X utf8 calc/install_lane.py --lane MonP|MonC|EStn [--compare|--dry-run] [--reset-values]
       <bluesky venv>\\Scripts\\python.exe -X utf8 calc/install_lane.py --lane EStn --remove [--dry-run]
"""
import argparse
import math
import sys
import time
from pathlib import Path

import epics

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lanes import LANES, build, rec  # noqa: E402
from slotlib import install, read_values, strings_match, _put_check, CALCOUT_FIELDS, TRANSFORM_FIELDS  # noqa: E402
from monp_transform import evaluate  # noqa: E402
from quality_slots import severity, bounds, flags, RHO0  # noqa: E402

_flux_of_bounds = {}


def v_flux(v):
    ref = evaluate(*(v[x] for x in "ABCDEFGH"))
    return [x for x in "IJKLMNOP" if abs(v[x] - ref[x]) > 1e-3 * max(abs(ref[x]), 1e-30)]


def v_bkg(v):
    bad = []
    e = v["A"] / v["B"] if v["B"] > 0 else -1
    if abs(v["E"] - e) > 1e-6 * max(1, abs(e)) + 1e-9:
        bad.append("E")
    if v["J"] != v["C"] + 10 * v["D"]:
        bad.append("J")
    if v["N"] != (1.0 if v["M"] != v["J"] else 0.0):
        bad.append("N")
    p = (1 + (int(v["C"]) % 3) ** 2) * 10 ** (math.floor(v["C"] / 3) + 3 * v["D"] - 17) * v["L"]
    if abs(v["P"] - p) > 1e-6 * max(abs(p), 1e-30):
        bad.append("P")
    return bad


def v_bounds(lane):
    return lambda v: _v_bounds(v, lane)


def _v_bounds(v, lane):
    # B is already E_eff in the slot. Check it against the flux slot's raw energy, then the rest.
    b = bounds(v["A"], v["B"], RHO0, lane)    # E already effective: no further scaling; the lane's own fit
    e_raw = float(epics.caget(_flux_of_bounds.get("rec") + ".E", timeout=3))
    want_b = e_raw * (RHO0 / v["I"]) ** .568
    bad = [k for k in "CDEFGL" if abs(v[k] - b[k]) > 1e-6 * max(abs(b[k]), 1e-30)]
    if abs(v["B"] - want_b) > 1e-4 * want_b:
        bad.append("B")
    print(f"  bounds: E {e_raw:.4f} keV, rho {v['I']:.6g} -> E_eff {v['B']:.4f} (want {want_b:.4f}); Lw {v['C']:.4f}")
    return bad


def v_flags(v):
    want = flags(v["A"], v["B"], v["C"], v["D"], v["E"], v["P"])
    bad = [k for k in "FGHIJKL" if v[k] != want[k]]
    print(f"  flags: E {v['A']:.3f} T {v['B']:.3f} bkg-stale {v['C']:.0f} P-age {v['D']:.0f} s no-beam {v['E']:.0f} s "
          f"-> code {v['L']:.0f} (want {want['L']:.0f})")
    return bad


def v_status(lane):
    def f(v):
        want = v["A"]
        sev = epics.caget(rec(lane, "status") + ".SEVR", as_string=True, timeout=3)
        print(f"  status: flags code {v['A']:.0f} -> VAL {v['VAL']:.0f} {sev} (want {want:.0f} {severity(want)})")
        return [] if (v["VAL"] == want and sev == severity(want)) else ["VAL/SEVR"]
    return f


def v_dark(v):
    return [] if abs(v["VAL"] - v["A"]) < 1e-9 else ["VAL"]


def compare(lane):
    return _compare_entries(lane, build(lane))


def _compare_entries(label, entries, extra=None, check_hand=False):
    """Read-only diff of generated fields against the live IOC. extra: {record: {field: wanted}} for fields the lane
    writes outside build() (the E-station TetrAMM links). check_hand: also compare the hand-set values, but only of a
    slot that is not ours (a slot that is ours keeps the operator's value, as the installer does)."""
    diffs = 0
    for r, desc, fields, hand, _ in entries:
        wanted = dict(fields)
        wanted.update((extra or {}).get(r, {}))
        if check_hand and hand and not _is_ours(r):
            wanted.update(hand)
        for k, want in wanted.items():
            if isinstance(want, (int, float)):
                got = epics.caget(f"{r}.{k}", timeout=3)
                same = got is not None and abs(float(got) - float(want)) < 1e-9
            else:
                got = epics.caget(f"{r}.{k}", as_string=True, timeout=3)
                same = got is not None and strings_match(got, want, k)
            if not same:
                diffs += 1
                print(f"  DIFF {r}.{k}: live {got!r}  generated {want!r}")
    print(f"{label}: {diffs} field(s) differ from the generated lane")
    return diffs


# ---------------------------------------------------------------------------------------------------------------------
# E-station lane (EStn): four slots, the guarded installer, a different commissioning order for the flux slot.
# estation_lane is imported lazily, so the MonP/MonC paths never load it (or fluxor).
# ---------------------------------------------------------------------------------------------------------------------
ESTN = "EStn"
OURS = "(xray_fluxor)"
UTIL = "15IDC:util:"
ESTN_ROLES = ["flags", "status", "flux", "bounds"]            # the order of estation_lane.build()
TEST_CURRENTS_NA = {"A": 2400.0, "B": 1600.0}                  # hand values the flux formula is commissioned on
ESTN_FOLLOW = ("A", "B")                                       # zeroed just before the TetrAMM links are written
RECOVERY = "fix the cause and re-run, or run --lane EStn --remove"
LIVE_FLOOR_NA = 5.0                                            # below this total current a live link check proves nothing


def _el():
    import estation_lane
    return estation_lane


def _targets():
    el = _el()
    return [el.rec(r) for r in ESTN_ROLES]


def _guard_write(pv):
    """Every EStn write goes through this: only the four target records (and their Enable) may be written."""
    r = pv[:-len("Enable")] if pv.endswith("Enable") else pv.split(".")[0]
    if not pv.startswith(UTIL) or r not in _targets():
        raise RuntimeError(f"refusing to write outside the four E-station records: {pv}")


def _put(pv, value, numeric=None):
    _guard_write(pv)
    _put_check(pv, value, numeric=isinstance(value, (int, float)) if numeric is None else numeric)


def _is_ours(r):
    return (epics.caget(f"{r}.DESC", as_string=True, timeout=3) or "").endswith(OURS)


def _close(a, b, rel=1e-3, guard=1e-30):
    return a == b or abs(a - b) <= rel * abs(b) + guard


def _check_letters(v, want, letters):
    return [x for x in letters if not _close(v[x], want[x])]


def v_estn_flux(v):
    """Every computed letter of the flux slot against evaluate_lane on the slot's own inputs A-F."""
    el = _el()
    ev = el.evaluate_lane(dict(current3_nA=v["A"], current4_nA=v["B"], energy_keV=v["C"], temp_F=v["D"],
                               pressure_kPa=v["E"], dark_nA=v["F"]))["flux"]
    bad = _check_letters(v, ev, sorted(el.EXPR["flux"]))
    print(f"  flux: A {v['A']:.4g} B {v['B']:.4g} nA, E {v['C']:.4f} keV, T {v['D']:.2f} degF, P {v['E']:.2f} kPa, "
          f"dark {v['F']:.3g} nA -> formula {v['P']:.6g} ph/s (want {ev['P']:.6g})")
    return bad


def v_estn_bounds(v):
    """Every computed letter of the bounds slot against its strings run on the slot's own inputs. B is E_eff in the
    slot (its link brings the raw energy each scan and CLCB replaces it), so the raw energy comes from the flux slot."""
    el = _el()
    e_raw = float(epics.caget(el.rec("flux") + ".C", timeout=3))
    ev = el.calc_eval.eval_transform(el.EXPR["bounds"], {"A": v["A"], "B": e_raw, "D": v["D"], "I": v["I"],
                                                         el.PLATES_LETTER: v[el.PLATES_LETTER]})
    bad = _check_letters(v, ev, sorted(el.EXPR["bounds"]))
    if v[el.PLATES_LETTER] != el.PLATE_CODES[el.G["plates"]]:
        bad.append(el.PLATES_LETTER)
    print(f"  bounds: RESULT {v['L']:.6g} (want {ev['L']:.6g}) low {v['K']:.6g} high {v['M']:.6g} ph/s, E_eff {v['B']:.4f} keV")
    return bad


def v_estn_flags(v):
    el = _el()
    ev = el.calc_eval.eval_transform(el.EXPR["flags"], {x: v[x] for x in "ABCDE"})
    bad = [x for x in sorted(el.EXPR["flags"]) if v[x] != ev[x]]
    print(f"  flags: code {v['L']:.0f} (want {ev['L']:.0f})")
    return bad


def v_estn_status(v):
    sev = epics.caget(_el().rec("status") + ".SEVR", as_string=True, timeout=3)
    print(f"  status: flags code {v['A']:.0f} -> VAL {v['VAL']:.0f} {sev} (want {v['A']:.0f} {severity(v['A'])})")
    return [] if (v["VAL"] == v["A"] and sev == severity(v["A"])) else ["VAL/SEVR"]


def _heartbeat_or_exit(code):
    if epics.caget(UTIL + "HEARTBEAT", timeout=3) is None:
        print("utilioc not reachable (HEARTBEAT): check EPICS_CA_ADDR_LIST. Nothing was written.")
        sys.exit(code)


def compare_estn():
    el = _el()
    _heartbeat_or_exit(2)
    return _compare_entries(ESTN, el.build(), extra={el.rec("flux"): el.input_links()}, check_hand=True)


def _default_desc(r):
    """The DESC of a free slot, as read from the live IOC: 'user Transform N', and for a calcout the bare record name."""
    return r[len(UTIL):] if "userCalcOut" in r else f"user Transform {r.rsplit('userTran', 1)[1]}"


def _set_fields(r):
    """The link and expression fields that are set in r. A free slot has none: INPx, CLCx and OUTx empty (and a calcout's
    CALC '0'). The comments (CMTx), values and PREC/COPT/EGU are not considered."""
    if "userCalcOut" in r:
        names = [f"INP{x}" for x in "ABCDEFGHIJKL"] + ["CALC", "OUT"]
        zero_ok = ("", "0")
    else:
        names = [f"{p}{x}" for p in ("INP", "CLC", "OUT") for x in "ABCDEFGHIJKLMNOP"]
        zero_ok = ("",)
    return [f for f in names if (epics.caget(f"{r}.{f}", as_string=True, timeout=3) or "").strip() not in zero_ok]


def _slot_state(r):
    """(state, DESC, set fields). ours: DESC ends '(xray_fluxor)'. free: DESC is exactly the real default AND no link or
    expression is set. Anything else (another DESC, an empty DESC, a default DESC with something set) is foreign."""
    cur = epics.caget(f"{r}.DESC", as_string=True, timeout=3)
    used = _set_fields(r)
    if (cur or "").endswith(OURS):
        return "ours", cur, used
    return ("free" if (cur == _default_desc(r) and not used) else "foreign"), cur, used


def _preflight(recs):
    """Read-only. Exit 1 if the utilioc is unreachable or any target slot is in use by someone else; nothing is written."""
    _heartbeat_or_exit(1)
    states, foreign = {}, []
    for r in recs:
        st, cur, used = _slot_state(r)
        states[r] = st
        print(f"{r}: {st}, DESC={cur!r}" + (f", fields set: {used}" if used else ""))
        if st == "foreign":
            foreign.append(r)
    if foreign:
        sys.exit(f"refusing: in use by someone else: {foreign}. Nothing was written.")
    return states


def _links_in_place(flux, links):
    """True when the flux slot already has both TetrAMM links (a re-run of a commissioned lane)."""
    return all((epics.caget(f"{flux}.{k}", as_string=True, timeout=3) or "").split()[:1] == v.split()[:1]
               for k, v in links.items())


def _commission_values(role, hand, state, reset_values, rerun):
    """Hand values written at commissioning. The flux slot gets the two test currents, except on a re-run of a lane whose
    links are in place (it is re-verified on the live currents); the dark (F) only in a fresh slot or with --reset-values,
    so a re-run never overwrites a dark that was entered by hand."""
    if role != "flux":
        return dict(hand)
    out = {} if rerun else dict(TEST_CURRENTS_NA)
    if state != "ours" or reset_values:
        out.update(hand)
    return out


def _slot_fields(role, fields, rerun):
    fields = dict(fields)
    if role == "flux":
        if rerun:
            for k in ("INPA", "INPB"):
                fields.pop(k, None)                         # the links stay as they are
        else:
            fields.update({"INPA": "", "INPB": ""})         # the TetrAMM links stay empty until the formula is verified
    return fields


def estn_sequence(entries, states, links, reset_values=False, rerun=False):
    """The complete ordered list of writes [(pv, value)], with ('verify', rec) where a verification runs. The dry-run
    prints exactly this and the install performs exactly this (the tests compare the two)."""
    flux = entries[ESTN_ROLES.index("flux")][0]
    seq = []
    if rerun:                    # a lane already running: disable all four, flux first, before rewriting anything
        seq += [(f"{r}Enable", 0) for r in [flux] + [e[0] for e in entries if e[0] != flux]]
    for role, (r, desc, fields, hand, kind) in zip(ESTN_ROLES, entries):
        seq.append((f"{r}Enable", 0))
        seq += [(f"{r}.{k}", v) for k, v in _slot_fields(role, fields, rerun).items()]
        seq += [(f"{r}.{k}", v) for k, v in _commission_values(role, hand, states[r], reset_values, rerun).items()]
        seq += [(f"{r}Enable", 1), ("verify", r)]
    if not rerun:
        seq += [(f"{flux}.{x}", 0.0) for x in ESTN_FOLLOW]
        seq += [(f"{flux}.{k}", v) for k, v in links.items()]
    return seq


def _write_links(flux, links):
    """Set the TetrAMM links on the commissioned flux slot, read each back and report the string. A and B are zeroed
    first, so that if the TetrAMM is not there the slot publishes 0 (INVALID), not the test currents."""
    ok = True
    for x in ESTN_FOLLOW:
        _put(f"{flux}.{x}", 0.0, numeric=True)
    for k, v in links.items():
        pv = f"{flux}.{k}"
        _guard_write(pv)
        if epics.caput(pv, v, wait=True, timeout=5) != 1:
            raise RuntimeError(f"caput failed: {pv}")
        back = epics.caget(pv, as_string=True, timeout=5)
        good = bool(back) and str(back).split()[0] == v.split()[0]
        print(f"  {pv}: wrote {v!r} ({len(v)} chars), reads back {back!r}" + ("" if good else "  MISMATCH"))
        ok &= good
    return ok


def _final_check(flux, cfg):
    """After the links are written. Returns (ok, warnings). The source PVs are read from THIS PC: if one does not answer,
    only the enable and the link strings are confirmed (WARNING). If both answer, the slot's A and B must agree with them
    (the utilioc may not see the TetrAMM even though this PC does); only then is the formula verified on live currents."""
    time.sleep(2.5)
    warnings = []
    enabled = epics.caget(f"{flux}Enable", timeout=3)
    sev = epics.caget(f"{flux}.SEVR", as_string=True, timeout=3)
    print(f"  {flux}: Enable={enabled}, SEVR={sev}")
    ok = enabled is not None and float(enabled) == 1
    src = {"A": cfg["current3"], "B": cfg["current4"]}

    def direct():
        return {k: epics.caget(pv, timeout=3) for k, pv in src.items()}

    d = direct()
    down = [k for k, v in d.items() if v is None]
    if down:
        warnings.append(f"TetrAMM link(s) {['INP' + k for k in down]} not connected from this PC (TetrAMM IOC down?): the slot is "
                        f"enabled with its links set; the flux is INVALID until they connect and the formula was NOT verified "
                        f"on live currents")
        return ok, warnings

    def agrees(vals, d):
        return all(abs(vals[k] - float(d[k])) <= 1e-3 * abs(float(d[k])) + 0.5 for k in d)

    vals = read_values(flux)
    if not agrees(vals, d):
        d = direct()                                        # allow one scan of drift
        vals = read_values(flux)
    if any(v is None for v in d.values()) or not agrees(vals, d):
        warnings.append(f"the utilioc does not see the TetrAMM (links INVALID or stale): slot A={vals['A']:.4g}, B={vals['B']:.4g} nA "
                        f"but this PC reads {d}; the formula was NOT verified on live currents")
        return ok, warnings
    bad = [x for x, v in vals.items() if not math.isfinite(v)] + v_estn_flux(vals)
    if bad:
        print(f"MISMATCH in {bad} with the live TetrAMM currents")
        return False, warnings
    total = sum(float(v) for v in d.values())
    if total <= LIVE_FLOOR_NA:
        warnings.append(f"beam off or currents below {LIVE_FLOOR_NA:g} nA: the live link check proves nothing (the slot agrees with "
                        f"this PC only because both are near 0); the formula was NOT verified on live currents")
    elif sev == "INVALID":
        warnings.append("flux slot SEVR is INVALID: a link is not answering. Suspects: the TetrAMM inputs (INPA, INPB), the energy, "
                        "hutch temperature or pressure links; the formula was NOT verified on live currents")
    else:
        print("  verified on live currents (the slot's A and B agree with the TetrAMM read directly)")
    return ok, warnings


def _fail_cleanup(touched, flux, test_currents):
    """After any failure, every step is attempted even if an earlier one fails. If test currents were put: zero A and B
    while the flux slot is still enabled, wait a scan so the flux (and through it the bounds) recomputes to 0. Then Enable 0
    on every touched slot: flux, one scan, bounds, flags, status. A disabled record keeps its last values, so they are made
    harmless first. The summary names anything that could not be done."""
    failed = []

    def put(pv, value, what):
        try:
            _guard_write(pv)
            ok = epics.caput(pv, value, wait=True, timeout=5) == 1
        except Exception as ex:
            ok = False
            print(f"  ERROR while {what}: {type(ex).__name__}: {ex}")
        print(f"  {pv} -> {value}: {'done' if ok else 'FAILED'}")
        if not ok:
            failed.append(pv)
        return ok

    if flux in touched and test_currents:
        for x in ESTN_FOLLOW:
            put(f"{flux}.{x}", 0.0, f"zeroing {x}")
        time.sleep(2.5)                                      # one scan: the flux recomputes from 0 nA
    el = _el()
    order = [r for r in (el.rec(x) for x in ('flux', 'bounds', 'flags', 'status')) if r in touched]
    for i, r in enumerate(order):
        put(f"{r}Enable", 0, f"disabling {r}")
        if i == 0 and r == flux and len(order) > 1:
            time.sleep(2.5)                                  # one scan: the bounds sees the zeroed flux before it is disabled
    if failed:
        print(f"LANE FAILED and the cleanup is INCOMPLETE: these writes failed: {failed}. Set those PVs by hand "
              f"(Enable 0, A and B 0). {RECOVERY}")
    else:
        print(f"LANE FAILED: the slots this run touched are disabled; {RECOVERY}")


def estn_install(dry_run=False, reset_values=False):
    """Returns (ok, warnings). Fresh install: flags, status, flux, bounds, each commissioned and verified (the flux slot
    with INPA/INPB empty and the test currents 2400/1600 nA as hand values); then A and B are zeroed and the TetrAMM links
    are written and read back; then the final check. A re-run of a commissioned lane (flux ours, both links in place)
    first disables all four slots, then rewrites them, re-enabling each as it verifies, with no test currents.
    On ANY failure every slot touched is disabled and no test current is left (see _fail_cleanup)."""
    el = _el()
    cfg = el.load_pvs()
    entries, links = el.build(cfg), el.input_links(cfg)
    flux = entries[ESTN_ROLES.index("flux")][0]
    states = _preflight([e[0] for e in entries])
    rerun = states[flux] == "ours" and _links_in_place(flux, links)
    if dry_run:
        print("re-run of a commissioned lane: all four slots are disabled first, no test currents" if rerun else
              "fresh commissioning: test currents on the flux slot, TetrAMM links last")
        print("would write, in order (nothing is written):")
        for pv, v in estn_sequence(entries, states, links, reset_values, rerun):
            print(f"  would verify {v}" if pv == "verify" else f"  would put {pv} = {v!r}")
        return True, []
    verifiers = {"flags": v_estn_flags, "status": v_estn_status, "flux": v_estn_flux, "bounds": v_estn_bounds}
    touched, test_currents, done = [], False, False
    try:
        if rerun:
            touched = [flux] + [e[0] for e in entries if e[0] != flux]
            for r in touched:
                _put(f"{r}Enable", 0, numeric=True)
        for role, (r, desc, fields, hand, kind) in zip(ESTN_ROLES, entries):
            if r not in touched:
                touched.append(r)
            if role == "flux" and not rerun:
                test_currents = True
            hv = _commission_values(role, hand, states[r], reset_values, rerun)
            if not install(None, desc, _slot_fields(role, fields, rerun), hv, verifiers[role], set_hand_values=bool(hv), rec=r):
                raise RuntimeError(f"{r} did not verify")
        if not rerun:
            print("commissioned and verified on the test currents; now the TetrAMM links")
            if not _write_links(flux, links):
                raise RuntimeError("a TetrAMM link did not read back as written")
        fin, warnings = _final_check(flux, cfg)
        if not fin:
            raise RuntimeError("final check failed")
        for w in warnings:
            print("WARNING:", w)
        done = True
        return True, warnings
    except (Exception, SystemExit) as ex:
        print(f"ERROR: {type(ex).__name__}: {ex}")
        return False, []
    finally:
        if not done:
            _fail_cleanup(touched, flux, test_currents)


# The real defaults of a free slot, read from the live IOC (2026-11-16). CMTA-P are the lower-case letters a-p.
FREE_TRANSFORM = {"SCAN": "Passive", "PREC": "3", "COPT": "Conditional", "EGU": ""}
FREE_CALCOUT = {"CALC": "0", "SCAN": "Passive", "PREC": "5", "EGU": "", "HIGH": 0.0, "HSV": "NO_ALARM", "HIHI": 0.0,
                "HHSV": "NO_ALARM", "HYST": 0.0, "OOPT": "Every Time", "DOPT": "Use CALC", "OCAL": "0", "OUT": ""}


def estn_free_writes(r):
    """[(pv, value, must)]: the writes that return one of our slots to its free default, ending with Enable 1 (a free
    slot is enabled, with empty expressions). must=False: the value is computed or an output (letters, VAL); a refused put
    is reported and ignored."""
    w = [(f"{r}Enable", 0, True)]
    if "userCalcOut" in r:
        w += [(f"{r}.INP{x}", "", True) for x in "ABCDEFGHIJKL"]
        w += [(f"{r}.{k}", v, True) for k, v in FREE_CALCOUT.items()]
        w += [(f"{r}.{x}", 0.0, False) for x in "ABCDEFGHIJKL"] + [(f"{r}.VAL", 0.0, False)]
    else:
        w += [(f"{r}.{k}", v, True) for k, v in FREE_TRANSFORM.items()]
        w += [(f"{r}.{p}{x}", "", True) for p in ("INP", "CLC") for x in "ABCDEFGHIJKLMNOP"]
        w += [(f"{r}.CMT{x}", x.lower(), True) for x in "ABCDEFGHIJKLMNOP"]
        w += [(f"{r}.{x}", 0.0, False) for x in "ABCDEFGHIJKLMNOP"]
    w.append((f"{r}.DESC", _default_desc(r), True))
    w.append((f"{r}Enable", 1, True))
    return w


def estn_remove(dry_run=False):
    """Return our four slots to their free defaults. Refuses (exit 1, nothing written) if any is in use by someone else;
    a slot that is already free is left alone; only slots whose DESC ends '(xray_fluxor)' are written."""
    recs = list(reversed(_targets()))
    states = _preflight(recs)
    mine = [r for r in recs if states[r] == "ours"]
    for r in recs:
        if states[r] == "free":
            print(f"{r}: already free, nothing to do")
    writes = [(f"{r}Enable", 0, True) for r in mine]               # everything off first, then restore
    for r in mine:
        writes += estn_free_writes(r)[1:]
    for pv, v, must in writes:
        if dry_run:
            print(f"  would put {pv} = {v!r}" + ("" if must else " (if the IOC allows)"))
            continue
        try:
            _put(pv, v)
        except Exception as ex:
            if not must:
                print(f"  {pv}: put refused or not read back ({ex}); ignored (computed field)")
                continue
            print(f"ERROR: {type(ex).__name__}: {ex}")
            print(f"REMOVE FAILED at {pv}: every slot that was ours is disabled, those before this one are restored (and enabled "
                  f"again), this one is partly restored, the rest are not restored yet; fix the cause and run --lane EStn --remove again")
            return False
    print("(dry run: nothing written)" if dry_run else f"REMOVED {len(mine)} slot(s)")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True, choices=sorted(LANES) + [ESTN])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--compare", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset-values", action="store_true")
    ap.add_argument("--remove", action="store_true", help="EStn only: return its four slots to their free defaults")
    a = ap.parse_args(argv)
    if a.remove and (a.lane != ESTN or a.compare):
        ap.error("--remove is for --lane EStn only (list it with --dry-run)")
    if a.lane == ESTN:
        if a.compare:
            sys.exit(0 if compare_estn() == 0 else 1)
        if a.remove:
            sys.exit(0 if estn_remove(dry_run=a.dry_run) else 1)
        ok, warnings = estn_install(dry_run=a.dry_run, reset_values=a.reset_values)
        if ok:                                   # a failure has already printed LANE FAILED and the recovery line
            print("LANE OK" + (f" (with {len(warnings)} WARNING)" if warnings else ""))
        sys.exit(0 if ok else 1)
    if a.compare:
        sys.exit(0 if compare(a.lane) == 0 else 1)
    verifiers = {"flags": v_flags, "status": v_status(a.lane), "dark": v_dark, "flux": v_flux, "bkg": v_bkg,
                 "bounds": v_bounds(a.lane)}
    roles = ["flags", "status", "dark", "flux", "bkg", "bounds"]   # same order as lanes.build()
    _flux_of_bounds["rec"] = rec(a.lane, "flux")
    ok = True
    for role, (r, desc, fields, hand, kind) in zip(roles, build(a.lane)):
        fresh = not (epics.caget(f"{r}.DESC", as_string=True, timeout=3) or "").endswith("(xray_fluxor)")
        ok &= install(None, desc, fields, hand, verifiers[role], dry_run=a.dry_run,
                      set_hand_values=bool(hand) and (fresh or a.reset_values), rec=r)
        if not ok:
            break
    print("LANE OK" if ok else "LANE FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
