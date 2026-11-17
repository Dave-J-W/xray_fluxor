"""Shared, guarded installer for utilioc transform slots (15IDC:util:userTranN).

install() refuses an occupied slot (one whose DESC is not ours and that has links or expressions
set). It then: turns the slot's Enable off; writes and reads back every field; writes the
hand-set values; turns the Enable on; waits two scans; and calls `verify(values) -> list of bad
letters`. It writes only to the given 15IDC:util:userTranN record.
"""
import math
import sys
import time

import epics

LETTERS = "ABCDEFGHIJKLMNOP"


def strings_match(back, value, field=None):
    """True when a string field reads back as written. A bare DB link ('PV' with no spaces: the E-station lane writes
    its long links bare because 'PV NPP NMS' would exceed 39 characters) may read back with the default modifiers
    appended ('PV NPP NMS'), possibly cut at the 39-character limit; that is the same link, so it matches."""
    back, value = str(back).strip(), str(value).strip()
    if back == value:
        return True
    if not str(field or "").startswith(("INP", "OUT")):      # only link fields: every other comparison stays exact
        return False
    if not value or any(c.isspace() for c in value) or not back.startswith(value + " "):
        return False
    return all("NPP".startswith(t) or "NMS".startswith(t) for t in back[len(value):].split())


def _put_check(pv, value, numeric=False, tol=1e-9):
    if epics.caput(pv, value, wait=True, timeout=5) != 1:
        raise RuntimeError(f"caput failed: {pv}")
    back = epics.caget(pv, as_string=not numeric, timeout=5)
    if numeric:
        if back is None or abs(float(back) - float(value)) > tol * max(1.0, abs(float(value))):
            raise RuntimeError(f"readback mismatch {pv}: wrote {value}, read {back}")
    elif not strings_match(back, value, pv.rsplit(".", 1)[-1]):
        raise RuntimeError(f"readback mismatch {pv}: wrote {value!r}, read {back!r}")
    print(f"  {pv} = {back!r}")


def read_values(rec, letters=LETTERS, tries=10):
    """A consistent snapshot of a slot's values.

    CA gets of A-P are sequential, so a 1 s scan can process between them. Then, at low count
    rates, the inputs and the results come from different scans (±1 count = 1.7 % at 59 Hz).
    Read twice and accept only when both reads agree exactly. Retry up to `tries` times."""
    prev = None
    for _ in range(tries):
        cur = {x: float(epics.caget(f"{rec}.{x}", timeout=3)) for x in letters}
        if cur == prev:
            return cur
        prev = cur
    return cur


CALCOUT_FIELDS = [f"INP{x}" for x in "ABCDEFGHIJKL"] + ["CALC", "OCAL", "OUT"]
TRANSFORM_FIELDS = [p + x for p in ("INP", "CLC", "OUT") for x in LETTERS]


def install(slot, desc, fields, hand_values, verify, dry_run=False, set_hand_values=True, rec=None):
    """slot: transform slot number (userTranN), or pass rec= a full 15IDC:util: record name."""
    rec = rec or f"15IDC:util:userTran{slot}"
    kind_fields = CALCOUT_FIELDS if "userCalcOut" in rec else TRANSFORM_FIELDS
    if not rec.startswith("15IDC:util:"):
        sys.exit("refusing: target outside 15IDC:util:")
    if epics.caget("15IDC:util:HEARTBEAT", timeout=3) is None:
        sys.exit("utilioc not reachable (HEARTBEAT): check EPICS_CA_ADDR_LIST")
    cur = epics.caget(f"{rec}.DESC", as_string=True, timeout=3)
    used = [f for f in kind_fields
            if (epics.caget(f"{rec}.{f}", as_string=True, timeout=3) or "").strip() not in ("", "0")]
    if used and cur != desc and not (cur or "").endswith("(xray_fluxor)"):
        sys.exit(f"{rec} is in use by someone else (DESC={cur!r}, set: {used}). Refusing.")
    print(f"{rec}: DESC={cur!r}, fields set before: {used or 'none'}")
    for k, v in fields.items():
        if len(str(v)) > 39:
            sys.exit(f"{k} longer than 39 characters: {v!r}")
    if dry_run:
        for k, v in fields.items():
            print(f"  would set {rec}.{k} = {v!r}")
        print(f"  would set hand values {hand_values}" if set_hand_values else "  hand values kept")
        return True
    _put_check(f"{rec}Enable", 0, numeric=True)
    for k, v in fields.items():
        _put_check(f"{rec}.{k}", v, numeric=isinstance(v, (int, float)))
    if set_hand_values:
        for k, v in hand_values.items():
            _put_check(f"{rec}.{k}", v, numeric=True)
    _put_check(f"{rec}Enable", 1, numeric=True)
    time.sleep(2.5)
    vals = read_values(rec) if "userTran" in rec else read_values(rec, list("ABCDEFGHIJKL") + ["VAL"])
    print("  slot values:", {x: f"{v:.6g}" for x, v in vals.items()})
    # Any NaN/Inf fails, whatever the verifier says. A comparison with NaN is never "different",
    # so a NaN from a calc-precedence bug once passed (2026-11-12: unary minus binds tighter than
    # ^ in EPICS calc, so EXP(-(x)^1.22) came out NaN).
    bad = [x for x, v in vals.items() if not math.isfinite(v)]
    bad += verify(vals)
    print(f"  SEVR={epics.caget(rec + '.SEVR', as_string=True, timeout=3)}")
    if bad:
        print(f"MISMATCH in {bad}")
        return False
    print("INSTALLED AND VERIFIED")
    return True
