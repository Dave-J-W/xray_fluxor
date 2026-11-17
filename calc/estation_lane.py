"""The E-station live lane: IC-500-50 read by the TetrAMM (channels 3 and 4), as utilioc slots. Definition, mirror, self-test.

Design: docs/superpowers/specs/2026-11-16-estation-live-lane-design.md. OFFLINE: nothing here talks to EPICS.

Slots on 15IDC:util: (free slots from the 2026-11-16 read-only discovery; transform 12 is reserved for a later dark estimator)
  flux   userTran9   formula photons/s at the exit of the collection region (not wall-loss or recombination corrected)
  bounds userTran10  RESULT and the stated low/high bounds (wall loss + recombination + the symmetric terms)
  flags  userTran11  one 0/1 per condition and their sum (the status code)
  status userCalcOut9 the status code carried as alarm severity (> 0.5 MINOR, > 15.5 MAJOR)

Every constant in the expressions is GENERATED from the fluxor registry (fluxor/parameters.toml) and the fluxor chamber and
chain code, never typed here, so the lane cannot drift from the offline package: change a row, rerun the self-test, reinstall.
The E-station source PV names are not in this file: they come from calc/estation_pvs.local.json (gitignored; template
calc/estation_pvs.template.json).

Letters (transform values A-P are evaluated in order; an expression may use only inputs and EARLIER letters)

flux (userTran9)
  inputs   A TetrAMM channel 3 mean current nA   B channel 4 mean current nA   C mono energy keV   D hutch air T degF
           E gas pressure kPa (link userTran1.G, the MonP updater's ambient pressure)   F dark nA, hand-set (0)
  computed G net current A = MAX(A+B-F,0)*1E-9   H T degC   I N2 density g/cm3   J ln(E)   K mu_en/rho   L mu/rho
           M absorbed fraction over l_eff   O 0/1: raw sum below -margin or a channel at/above the full-scale fraction, or NaN (feeds flag 32)
           P photons/s at the exit, the formula (N is unused)
bounds (userTran10)
  inputs   A formula flux (flux.P)   B energy keV (flux.C), replaced by E_eff   D net current A (flux.G)   I density (flux.I)
           P plate orientation constant (horizontal = 1)
  computed C wall-loss fraction (MC fit)   E/F/G recombination loss, central/low/high aspect ratio (capped 0.5)
           H low-bound denominator   J high-bound denominator   K LOW bound   L RESULT (best estimate)   M HIGH bound
           N up % (high vs RESULT)   O down % (low vs RESULT)
flags (userTran11)
  inputs   A energy keV (flux.C)   B raw-current fault (flux.O)   C s since the pressure update (userTran3.H)
           D net current A (flux.G)   E central recombination loss (bounds.E)
  computed F bit 1   G bit 2   H bit 4   I bit 8   J bit 16   K bit 32   L status code = F+2G+4H+8I+16J+32K
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import calc_eval  # noqa: E402
import monp_transform as mt  # noqa: E402
import quality_slots as qs  # noqa: E402
from fluxor import constants as fc  # noqa: E402
from fluxor import params  # noqa: E402
from fluxor.chains import tetramm  # noqa: E402
from fluxor.chambers.ic500_50 import Ic500_50  # noqa: E402

P = "15IDC:util:"
LETTERS = "ABCDEFGHIJKLMNOP"
SLOTS = {"flux": 9, "bounds": 10, "flags": 11, "status": 9}           # userTran9/10/11, userCalcOut9
PRESSURE = f"{P}userTran1.G NPP NMS"                                  # the MonP updater's ambient pressure, kPa
PRESSURE_AGE = f"{P}userTran3.H NPP NMS"                              # s since that update
PLATE_CODES = {"vertical": 0, "horizontal": 1}
PLATES_LETTER = "P"
PV_LOCAL = Path(__file__).resolve().parent / "estation_pvs.local.json"
PV_TEMPLATE = Path(__file__).resolve().parent / "estation_pvs.template.json"
PV_KEYS = ("current3", "current4", "energy", "hutch_temp_f")
LIMIT = 39
# Flag thresholds: one edit here changes the expression strings, the comments, FLAG_BITS and (by import) the tests.
RAW_NEG_MARGIN_NA = 5.0        # bit 32: raw sum A+B below -this (nA) is a fault; noise around zero is not
RECOMB_FLAG_FRACTION = 0.05    # bit 2: central recombination loss above this fraction
LOW_CURRENT_NA = 50.0          # bit 8: net current below this (nA): the stated bounds understate the uncertainty
FULL_SCALE_FRACTION = 0.99     # bit 32: a channel at or above this fraction of the TetrAMM full scale


def _sci(x, sig=6):
    """Number in calc form, always with an exponent when it has one: 2.17205E17, 3.369272E-3, 1E-9."""
    m, e = f"{x:.{sig - 1}E}".split("E")
    m = m.rstrip("0").rstrip(".") if "." in m else m
    return f"{m}E{int(e)}"


def _n(x, sig=6):
    """Shortest calc form: no leading zero, exponent only when needed (quality_slots._n, with a significant-figure limit)."""
    t = f"{x:.{sig}g}"
    if "e" in t:
        m, e = t.split("e")
        t = f"{m}E{int(e)}"
    return t[1:] if t.startswith("0.") else t


def _generate():
    """All constants of the lane, read from the registry and the fluxor chamber and chain. Returns a dict."""
    reg = params.default()
    ch = Ic500_50(reg)
    rng = reg.value("tetramm.range")
    unit_a = reg.value("tetramm.unit_a")
    l_cm = reg.value("ic500.l_eff_cm")
    e0, s, p = reg.value("ic500.wall_fit")
    # recombination is linear in the current: loss = k * I (first order), k from fluxor at 1 uA (central, low, high aspect)
    _, (r_lo, r_c, r_hi), _ = ch.extra_flags_and_high(1e-6, 10.0, reg.value("gas.p_kpa"), reg.value("gas.t_c"))
    k_per_a = (r_lo * 1e6, r_c * 1e6, r_hi * 1e6)
    # symmetric terms: the chamber's, the TetrAMM range gain, and the gas stand-in at the stand-in P and T
    terms = {n: v[0] for n, v in ch.symmetric_terms.items()}
    terms["TetrAMM range gain"] = reg.value("tetramm.gain_rel")
    p0, t0 = reg.value("gas.p_kpa"), reg.value("gas.t_c")
    terms["gas stand-in P,T"] = math.hypot(reg.param("gas.p_kpa").sigma / p0, reg.param("gas.t_c").sigma / (t0 + 273.15))
    sigma_s = math.sqrt(sum(v * v for v in terms.values()))
    # noise threshold (flag 8): the chain's own 3-sigma of the two-channel current, rounded up to 0.1 nA
    tet = tetramm.TetraMM(("Current3", "Current4"), rng=rng, darks={"Current3": 0.0, "Current4": 0.0}, dark_age_h=1.0, reg=reg)
    noise_na = math.ceil(3 * tet.current({"channels": {"Current3": 0.0, "Current4": 0.0}}).abs_sigma_a / 1e-9 * 10) / 10
    return dict(
        reg=reg, l_cm=l_cm, unit_a=unit_a, wall_fit=(e0, s, p), band=dict(ch.band), k_per_a=k_per_a, terms=terms,
        sigma_s=sigma_s, lf=math.floor((1 - sigma_s) * 1000) / 1000, hf=math.ceil((1 + sigma_s) * 1000) / 1000,
        k_flux=fc.W_EV / (fc.E_CHARGE * 1e3), k_dens=fc.M_N2 / fc.R_GAS / 1000,
        fs_na=FULL_SCALE_FRACTION * tetramm.FULL_SCALE_A[rng] / unit_a, noise_na=noise_na,
        e_range=ch.energy_range_kev, plates=reg.value("ic500.plate_orientation"))


G = _generate()
# the lane's constants are the registry's, and where the repo has other copies they must agree
assert _sci(G["k_flux"]) == "2.17205E17", _sci(G["k_flux"])
# MonP types 3.369272E-3 (a rounding of M/R); the lane generates the exact M_N2/R_GAS/1000 = 3.369238E-3 (1e-5 apart)
assert abs(G["k_dens"] / mt.M_OVER_R - 1) < 1e-12 and abs(G["k_dens"] / 3.369272e-3 - 1) < 2e-5
assert G["band"] == qs.BAND, (G["band"], qs.BAND)
assert (fc.RHO0_G_CM3, fc.RANGE_EXP) == (qs.RHO0, qs.RANGE_EXP)
assert G["e_range"] == (4.9, 30.5)


def _wall_expr():
    e0, s, p = G["wall_fit"]
    return "B>{0:g}?1-1/EXP(((B-{0:g})/{1:g})^{2:g}):0".format(e0, s, p)


def _expressions():
    l = G["l_cm"]
    b = G["band"]
    kl, kc, kh = (_n(x, 5) for x in G["k_per_a"])   # fluxor order: low, central, high aspect
    lo_e, hi_e = G["e_range"]
    flux = {
        "G": f"MAX(A+B-F,0)*{_sci(G['unit_a'])}",
        "H": "(D-32)/1.8",
        "I": f"E*{_sci(G['k_dens'], 7)}/(H+273.15)",
        "J": "LN(C)",
        "K": mt.MUEN.replace("L", "J"),
        "L": mt.MU.replace("L", "J"),
        "M": f"1-EXP(-{l:g}*K*I)",
        "O": f"A+B>=-{_n(RAW_NEG_MARGIN_NA)}&&A<{_n(round(G['fs_na'], 3))}&&B<{_n(round(G['fs_na'], 3))}?0:1",
        "P": f"G*{_sci(G['k_flux'])}/C/M*EXP(-{l:g}*L*I)",
    }
    bounds = {
        "B": qs.BOUNDS["expr"]["CLCB"],                                 # E_eff = E*(rho0/rho)^.568
        "C": _wall_expr(),
        "E": f"MIN(D*{kc},.5)",                                         # recombination, central aspect ratio
        "F": f"MIN(D*{kl},.5)",                                         # ... low
        "G": f"MIN(D*{kh},.5)",                                         # ... high
        "H": f"(1-MAX({_n(b['a'])}*C-{_n(b['b'])},0))*(1-F)",
        "J": f"1-C-MIN({_n(b['cap'])},{_n(b['k'])}*C+{_n(b['floor'])}*(B>{_n(b['e_widen'])}))",
        "K": f"A*{_n(G['lf'])}/H",
        "L": "A/(1-C)/(1-E)",
        "M": f"A*{_n(G['hf'])}/J/(1-G)",
        "N": "A>0?100*(M/L-1):0",
        "O": "A>0?100*(1-K/L):0",
    }
    flags = {
        "F": f"A>{_n(qs.FLAG1_E_KEV)}",
        "G": f"E>{_n(RECOMB_FLAG_FRACTION)}",
        "H": "C>7200",
        "I": f"D<{_sci(LOW_CURRENT_NA * 1e-9, 3)}",
        "J": f"A>={_n(lo_e)}&&A<={_n(hi_e)}?0:1",
        "K": "B>0",           # flux.O is 1 for a fault
        "L": "F+2*G+4*H+8*I+16*J+32*K",
    }
    return {"flux": flux, "bounds": bounds, "flags": flags}


EXPR = _expressions()
FLAG_BITS = [(1, "F", "E > 12.5 keV: wall-loss band in use"),
             (2, "G", f"recombination central loss above {100 * RECOMB_FLAG_FRACTION:g} %"),
             (4, "H", "pressure not updated for 2 h"),
             (8, "I", f"low current: net below {LOW_CURRENT_NA:g} nA, bounds understate"),
             (16, "J", "E outside 4.9-30.5 keV (MAJOR)"),
             (32, "K", f"raw sum below -{RAW_NEG_MARGIN_NA:g} nA, channel >= {100 * FULL_SCALE_FRACTION:g} % of full scale, or NaN (MAJOR)")]

LANE = {
    "name": "EStation",
    "slots": dict(SLOTS),
    "plates": G["plates"],
    "expr": EXPR,
    "constants": {"l_eff_cm": G["l_cm"], "wall_fit": G["wall_fit"], "k_recomb_per_A_low_central_high": G["k_per_a"], "LOW_FACTOR": G["lf"],
                  "HIGH_FACTOR": G["hf"], "sigma_symmetric": G["sigma_s"], "noise_nA": G["noise_na"], "full_scale_nA_99pct": G["fs_na"]},
    "terms": G["terms"],
}


def rec(role):
    n = SLOTS[role]
    return f"{P}{'userCalcOut' if role == 'status' else 'userTran'}{n}"


def _short(r):
    return r[len(P):]


_PV_NAME = re.compile(r"[A-Za-z0-9_:.\-]+")


def validate_pvs(cfg):
    """Every source PV must be a bare PV name: no whitespace (a trailing ' PP' or ' CPP' would change how the link behaves),
    no character outside [A-Za-z0-9_:.-], and not one of our own utilioc records (a link must not point at 15IDC:util:).
    The error names the key, never the value."""
    for k in PV_KEYS:
        v = cfg.get(k)
        if not isinstance(v, str):
            raise ValueError(f"PV config key {k!r} must be a string PV name (not null, a number or a list)")
        if not _PV_NAME.fullmatch(v) or v.startswith(P):
            raise ValueError(f"PV config key {k!r} is not a bare PV name (whitespace or a character outside [A-Za-z0-9_:.-], "
                             f"or a {P} record)")
    return cfg


def load_pvs(path=None):
    """The E-station source PV names, from the gitignored local file. A clear error names the template if it is missing."""
    path = Path(path or PV_LOCAL)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: copy {PV_TEMPLATE.name} to {path.name} and enter the real PV names "
                                f"(the file is gitignored; PV names must not be tracked)")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in PV_KEYS if not str(cfg.get(k, "")).strip()]
    if missing:
        raise ValueError(f"{path}: missing {missing} (see {PV_TEMPLATE.name})")
    return validate_pvs(cfg)


def _link(pv, tail=" NPP NMS"):
    """A read-only input link. A link that would be over 39 characters with its modifiers is written bare: NPP NMS are the
    defaults of a DB link, so 'PV' and 'PV NPP NMS' mean the same."""
    s = f"{pv}{tail}"
    if len(s) > LIMIT:
        s = pv
    if len(s) > LIMIT:
        raise ValueError(f"input link {pv!r} is longer than {LIMIT} characters")
    return s


def input_links(cfg=None):
    """The two TetrAMM links of the flux slot (INPA, INPB). The installer sets them LAST, after commissioning."""
    cfg = validate_pvs(cfg) if cfg else load_pvs()
    return {"INPA": _link(cfg["current3"]), "INPB": _link(cfg["current4"])}


def _transform(desc, links, expr, comments, egu, prec):
    f = {"DESC": desc, "SCAN": "1 second", "PREC": prec, "COPT": "Always", "EGU": egu}
    for x in LETTERS:
        f[f"INP{x}"] = links.get(f"INP{x}", "")
    for x in LETTERS:
        f[f"CLC{x}"] = expr.get(x, "")
    for x in LETTERS:
        f[f"CMT{x}"] = comments.get(x, "")
    return f


def build(cfg=None):
    """[(record, DESC, fields, hand_values, kind)] in install order: flags, status, flux, bounds (as calc/lanes.py:build).
    The flux slot's INPA/INPB (the TetrAMM links) are not included: input_links() returns them for the installer."""
    cfg = validate_pvs(cfg) if cfg else load_pvs()
    flux, bnd, fl, st = rec("flux"), rec("bounds"), rec("flags"), rec("status")
    out = []

    desc = "E-station status flags (xray_fluxor)"
    links = {"INPA": f"{flux}.C NPP NMS", "INPB": f"{flux}.O NPP NMS", "INPC": PRESSURE_AGE,
             "INPD": f"{flux}.G NPP NMS", "INPE": f"{bnd}.E NPP NMS"}
    cm = {"A": f"energy keV ({_short(flux)}.C)", "B": f"raw current fault ({_short(flux)}.O)",
          "C": f"s since P update ({_short(PRESSURE_AGE.split()[0])})", "D": f"net current A ({_short(flux)}.G)",
          "E": f"recomb loss central ({_short(bnd)}.E)",
          "F": "1: E>12.5 keV, wall-loss band", "G": f"2: recomb. loss above {100 * RECOMB_FLAG_FRACTION:g} %",
          "H": "4: pressure not updated 2 h", "I": f"8: net I below {LOW_CURRENT_NA:g} nA (low)",
          "J": "16: E outside 4.9-30.5 keV (MAJOR)", "K": f"32: raw sum<-{RAW_NEG_MARGIN_NA:g}nA/FS/NaN (MAJOR)",
          "L": "STATUS CODE = sum of the bits"}
    out.append((fl, desc, _transform(desc, links, EXPR["flags"], cm, "", "0"), {}, "transform"))

    desc = "E-station status code (xray_fluxor)"
    f = {"DESC": desc}
    for x in "ABCDEFGHIJKL":
        f[f"INP{x}"] = f"{fl}.L NPP NMS" if x == "A" else ""
    f.update({k: v for k, v in qs.STATUS["fields"].items() if not k.startswith("INP")})
    out.append((st, desc, f, {}, "calcout"))

    desc = "E-station flux ph/s (xray_fluxor)"
    links = {"INPC": _link(cfg["energy"]), "INPD": _link(cfg["hutch_temp_f"]), "INPE": PRESSURE}
    cm = {"A": "TetrAMM ch3 mean current nA", "B": "TetrAMM ch4 mean current nA", "C": "mono energy keV",
          "D": "hutch air T degF (posts on change)", "E": "N2 kPa (userTran1.G, ambient)", "F": "dark nA (hand-set)",
          "G": "net current A", "H": "hutch T degC", "I": "N2 density g/cm3", "J": "ln(E/keV)",
          "K": "mu_en/rho N cm2/g (fit)", "L": "mu/rho N cm2/g (fit)",
          "M": f"fraction absorbed in {G['l_cm']:g} cm (l_eff)", "O": f"1: raw sum<-{RAW_NEG_MARGIN_NA:g}nA, >=FS, or NaN",
          "P": f"formula, NOT result ({_short(bnd)}.L)"}
    out.append((flux, desc, _transform(desc, links, EXPR["flux"], cm, "ph/s", "4"), {"F": 0.0}, "transform"))

    desc = "E-station RESULT ph/s (xray_fluxor)"
    links = {"INPA": f"{flux}.P NPP MS", "INPB": f"{flux}.C NPP NMS", "INPD": f"{flux}.G NPP NMS", "INPI": f"{flux}.I NPP NMS"}
    cm = {"A": f"exit flux ph/s ({_short(flux)}.P)", "B": f"E_eff keV ({_short(flux)}.C density-scaled)",
          "C": "signal wall-loss fraction (MC fit)", "D": f"net current A ({_short(flux)}.G)",
          "E": "recombination loss, central", "F": "recombination loss, low aspect",
          "G": "recombination loss, high aspect", "H": "LOW denominator", "I": f"N2 density g/cm3 ({_short(flux)}.I)",
          "J": "HIGH denominator", "K": "flux LOW bound ph/s", "L": "RESULT: best flux ph/s",
          "M": "flux HIGH bound ph/s", "N": "uncertainty up %", "O": "uncertainty down %",
          PLATES_LETTER: "plates: 0 vertical, 1 horizontal"}
    f = _transform(desc, links, EXPR["bounds"], cm, "ph/s", "4")
    f[PLATES_LETTER] = PLATE_CODES[G["plates"]]          # a constant of the lane, re-asserted at every install
    out.append((bnd, desc, f, {}, "transform"))
    return out


def check_lengths(cfg=None):
    """Every DESC, expression, comment and link must fit 39 characters (autosave / CA string limit). Returns the offenders."""
    bad = []
    for r, desc, fields, _, _ in build(cfg):
        for k, v in fields.items():
            if len(str(v)) > LIMIT:
                bad.append((r, k, v))
    for k, v in input_links(cfg).items():
        if len(v) > LIMIT:
            bad.append((rec("flux"), k, v))
    return bad


def check_letter_order():
    """A computed letter may use only input letters and EARLIER computed letters (no state letters in this lane)."""
    problems = []
    cfg = {k: "X:" + k for k in PV_KEYS}
    built = {_short(r): (f, hv) for r, _, f, hv, kind in build(cfg) if kind == "transform"}
    for role, expr in EXPR.items():
        f, hv = built[_short(rec(role))]
        inputs = {x for x in LETTERS if f.get(f"INP{x}")} | set(hv) | ({"A", "B"} if role == "flux" else set())
        if role == "bounds":
            inputs.add(PLATES_LETTER)
        done = set()
        for x in LETTERS:
            if x in expr:
                bad = calc_eval.letters_used(expr[x]) - inputs - done
                if bad:
                    problems.append((role, x, expr[x], sorted(bad)))
                done.add(x)
    return problems


def evaluate_lane(inputs):
    """Run the actual slot strings through calc/calc_eval.py. inputs: current3_nA, current4_nA, energy_keV, temp_F,
    pressure_kPa; optional dark_nA (0), p_age_s (0). Returns {"flux": letters, "bounds": letters, "flags": letters,
    "status": code, "severity": ...}: this is the lane's mirror."""
    fx = calc_eval.eval_transform(EXPR["flux"], {"A": inputs["current3_nA"], "B": inputs["current4_nA"],
                                                  "C": inputs["energy_keV"], "D": inputs["temp_F"],
                                                  "E": inputs["pressure_kPa"], "F": inputs.get("dark_nA", 0.0)})
    bd = calc_eval.eval_transform(EXPR["bounds"], {"A": fx["P"], "B": fx["C"], "D": fx["G"], "I": fx["I"],
                                                    PLATES_LETTER: PLATE_CODES[G["plates"]]})
    fl = calc_eval.eval_transform(EXPR["flags"], {"A": fx["C"], "B": fx["O"], "C": inputs.get("p_age_s", 0.0),
                                                   "D": fx["G"], "E": bd["E"]})
    code = fl["L"]
    return {"flux": fx, "bounds": bd, "flags": fl, "status": code, "severity": qs.severity(code)}


def fluxor_reference(total_ua, e_kev, p_kpa, t_c, dark_na=0.0, split=0.6):
    """fluxor.core.evaluate for the same case (Ic500_50 + TetraMM channels 3 and 4); returns its Result."""
    from fluxor.core import evaluate
    tet = tetramm.TetraMM(("Current3", "Current4"), rng=G["reg"].value("tetramm.range"),
                          darks={"Current3": dark_na, "Current4": 0.0}, dark_age_h=1.0, reg=G["reg"])
    reading = {"channels": {"Current3": total_ua * 1e3 * split + dark_na, "Current4": total_ua * 1e3 * (1 - split)}}
    return evaluate(Ic500_50(G["reg"]), tet, reading, e_kev, p_kpa, t_c)


def compare_with_fluxor(currents_ua=(0.5, 3.0, 4.0, 100.0), energies=(8.0, 10.0, 20.0, 30.0),
                        gas=((98.99, 22.2), (101.325, 20.0), (97.0, 25.0)), darks=(0.0, 0.5)):
    """Worst relative differences lane vs fluxor over the grid: flux formula (5-20 keV, to 30 keV), RESULT, low, high."""
    worst = dict(formula_5_20=0.0, formula_30=0.0, best=0.0, low=0.0, high=0.0)
    for ua in currents_ua:
        for e in energies:
            for p, t in gas:
                for d in darks:
                    ref = fluxor_reference(ua, e, p, t, d)
                    lane = evaluate_lane(dict(current3_nA=ua * 1e3 * 0.6 + d, current4_nA=ua * 1e3 * 0.4,
                                              energy_keV=e, temp_F=t * 1.8 + 32, pressure_kPa=p, dark_nA=d))
                    rel = lambda a, b: abs(a / b - 1)
                    f = rel(lane["flux"]["P"], ref.flux_formula)
                    worst["formula_5_20" if e <= 20 else "formula_30"] = max(worst["formula_5_20" if e <= 20 else "formula_30"], f)
                    worst["best"] = max(worst["best"], rel(lane["bounds"]["L"], ref.flux_best))
                    worst["low"] = max(worst["low"], rel(lane["bounds"]["K"], ref.flux_low))
                    worst["high"] = max(worst["high"], rel(lane["bounds"]["M"], ref.flux_high))
    return worst


def main():
    ok = True
    try:
        cfg = load_pvs()
    except (FileNotFoundError, ValueError) as ex:
        print("local PV config:", ex)
        cfg = {k: "SOURCE:" + k for k in PV_KEYS}
        print("  using placeholder names for the length check only")
    print("expression lengths (limit 39):")
    for role, expr in EXPR.items():
        for x, s in expr.items():
            ok &= len(s) <= LIMIT
            print(f"  {role}.{x}: {len(s):2d} {'OK' if len(s) <= LIMIT else 'TOO LONG'}  {s}")
    bad = check_lengths(cfg)
    print("too long (all fields):", bad or "none")
    ok &= not bad
    order = check_letter_order()
    print("letter-order problems:", order or "none")
    ok &= not order
    print(f"constants: l_eff {G['l_cm']} cm, wall fit {G['wall_fit']}, recombination per A (low, central, high) "
          f"{tuple(round(x) for x in G['k_per_a'])}, sigma_s {100 * G['sigma_s']:.2f} % -> LOW {G['lf']} HIGH {G['hf']}, "
          f"noise {G['noise_na']} nA, full-scale 99 % {G['fs_na']:.0f} nA")
    # finite everywhere over the grid
    nonfinite = []
    for ua in (0.0, 0.0005, 0.5, 3, 4, 100, 120):
        for e in (5, 8, 10, 12.5, 13, 20, 30, 30.5):
            r = evaluate_lane(dict(current3_nA=ua * 600, current4_nA=ua * 400, energy_keV=e, temp_F=72.0, pressure_kPa=98.99))
            nonfinite += [(ua, e, role, x) for role in ("flux", "bounds", "flags") for x, v in r[role].items() if not math.isfinite(v)]
    print("non-finite values on the grid:", nonfinite or "none")
    ok &= not nonfinite
    w = compare_with_fluxor()
    print("lane vs fluxor.core.evaluate (0.5/3/4/100 uA, 8/10/20/30 keV, 3 gas states, 2 darks), worst |lane/fluxor - 1|:")
    for k_, v in w.items():
        print(f"  {k_:13s} {100 * v:.3f} %")
    ok &= w["formula_5_20"] < 0.01 and w["formula_30"] < 0.02 and max(w["best"], w["low"], w["high"]) < 0.02
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
