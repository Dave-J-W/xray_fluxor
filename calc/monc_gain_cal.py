"""MonC SR570 per-gain calibration lookup for utilioc: slot design, offline mirror, self-test. DRAFT.

Single source of truth for the slot, like calc/monp_transform.py. It writes nothing to EPICS:
  python -I calc/monc_gain_cal.py          self-test (expression lengths, lookup vs table, rates)
  python -I calc/monc_gain_cal.py --print  print the caput lines an install would run (slot N unset)

Data: data/calibration/monc_sr570_ranges.csv (from analysis/make_monc_calibration.py; its header holds
the source SHA-256). Arrays are indexed by the SR570 sensitivity index, the value of 15IDC:A3sens_put
(0 = 1 pA/V ... 27 = 1 mA/V; 20 = 5 uA/V, read live 2026-11-13).

One userArrayCalc (aCalcout) slot:
  inputs   A  sensitivity index   <- 15IDC:A3sens_put
           B  S4 counts           <- 15IDC:scaler1.S4
           C  count time s        <- 15IDC:scaler1.T
  arrays   AA factor, BB u_factor_rel, CC dark sd Hz (same-selection where measured, else reselect, else 0)
  VAL  = factor for the gain now set. Use: I = f_net * S / (1e5 Hz/V * VAL).
  OVAL = live relative uncertainty of the electronics, sqrt(u_factor^2 + (dark_sd / rate)^2).
         u_factor = 0.007 marks a gain that was never measured (the write-up fallback): flag it, don't hide it.
  NOT included, by design: the common absolute scale of the SR570 CAL current (type B, the write-up's
  +-0.7 %). Add it for absolute flux; leave it out for MonC ratios, where it cancels.
Trap: A is the gain EPICS last SENT. The SR570 link is listen-only, so a front-panel change or a unit that
restarted on its own settings is invisible here (ELECTRONICS_CONCLUSIONS.md section 4).

VERIFY on a bench aCalcout before install (calc R3-7-5), none of it tested yet:
  - `AA@A` returns element A of AA, 0-based;
  - OVAL is computed from OCAL with DOPT = "Use OCAL" and OOPT = "Every Time" and an empty OUT;
  - utilioc's autosave saves the AA/BB/CC array fields (if not, that is a utilioc change: ask the user).
"""
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "calibration" / "monc_sr570_ranges.csv"
N_SENS = 28

SLOT = {
    "DESC": "MonC SR570 gain cal (xray_fluxor)",
    "SCAN": "1 second",
    "PREC": "5",
    "links": {
        "INPA": "15IDC:A3sens_put NPP NMS",
        "INPB": "15IDC:scaler1.S4 NPP NMS",
        "INPC": "15IDC:scaler1.T NPP NMS",
    },
    "expr": {
        "CALC": "AA@A",
        "OCAL": "SQRT((BB@A)^2+(CC@A*C/MAX(B,1))^2)",
    },
    "fields": {"DOPT": "Use OCAL", "OOPT": "Every Time", "OUT": ""},
}


def load_table(path=TABLE):
    rows = [r for r in csv.DictReader(line for line in open(path) if not line.startswith("#"))]
    assert [int(r["index"]) for r in rows] == list(range(N_SENS)), "table must have indices 0..27 in order"
    aa = [float(r["factor"]) for r in rows]
    bb = [float(r["u_factor_rel"]) for r in rows]
    cc = [float(r["dark_sd_same_Hz"] or r["dark_sd_reselect_Hz"] or 0) for r in rows]
    return rows, aa, bb, cc


def evaluate(A, B, C, aa, bb, cc):
    """Mirror of SLOT['expr'] (aCalcout: @ = 0-based element; parenthesised so precedence can't matter)."""
    i = int(A)
    val = aa[i]
    oval = math.sqrt(bb[i] ** 2 + (cc[i] * C / max(B, 1)) ** 2)
    return val, oval


def main():
    rows, aa, bb, cc = load_table()
    ok = True
    for k, s in list(SLOT["expr"].items()) + list(SLOT["links"].items()):
        n = len(s)
        flag = "OK" if n <= 39 else "TOO LONG"
        ok &= n <= 39
        print(f"  {k}: {n:2d} chars {flag}  {s}")
    print(f"  DESC: {len(SLOT['DESC'])} (limit 40)")
    ok &= len(SLOT["DESC"]) <= 40
    # lookup must return the table, and the uncertainty must reduce to its two terms
    for r in rows:
        i = int(r["index"])
        v, o = evaluate(i, 2e5, 1.0, aa, bb, cc)
        ok &= v == float(r["factor"])
        ok &= abs(o - math.hypot(bb[i], cc[i] / 2e5)) < 1e-12
    print("  rate check, 5 uA/V (index 20), 1 s counts:")
    for f in (1e3, 1e4, 1e5, 1e6):
        v, o = evaluate(20, f, 1.0, aa, bb, cc)
        print(f"    {f:9.0f} Hz: factor {v:.5f}, u {o*100:.4f} %")
    v, o = evaluate(17, 2e5, 1.0, aa, bb, cc)
    print(f"  500 nA/V (17): factor {v:.5f}, u {o*100:.4f} %;  unmeasured 50 nA/V (14): u {evaluate(14, 2e5, 1, aa, bb, cc)[1]*100:.2f} % (flag)")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def print_install():
    _, aa, bb, cc = load_table()
    p = "15IDC:util:userArrayCalcN"  # slot N: to be given by the user
    print(f"# DRAFT, not run. Slot {p}: ask the user first (f99 handoff, 'Ask the user first').")
    print(f"caput {p}Enable 0   # field/record names to confirm against utilioc OPERATOR")
    for k, v in [("DESC", SLOT["DESC"]), ("SCAN", SLOT["SCAN"]), ("PREC", SLOT["PREC"])] + \
            list(SLOT["links"].items()) + list(SLOT["expr"].items()) + list(SLOT["fields"].items()):
        print(f'caput {p}.{k} "{v}"')
    for name, arr in (("AA", aa), ("BB", bb), ("CC", cc)):
        print(f"caput -a {p}.{name} {N_SENS} " + " ".join(f"{x:.6g}" for x in arr))
    print(f"caput {p}Enable 1   # after every field has been read back and compared")


if __name__ == "__main__":
    if "--print" in sys.argv:
        print_install()
    else:
        sys.exit(main())
