"""Read-only soak: compare the live utilioc slot with the independent full-physics conversion.

Reads 15IDC:util:userTranN A-P every few seconds. Recomputes the flux from the slot's own inputs
with calc/monp_transform.full_physics() (NIST tables, exact constants; no fitted formulas) and
prints the ratio. Expected: 1.000 within about 0.6 % at 5-20 keV and 1.5 % at 30 keV, which is
the fit error. Writes nothing.

Usage: <bluesky venv>\\Scripts\\python.exe -X utf8 calc/soak_check.py [--slot 1] [--n 6] [--dt 5]
"""
import argparse
import sys
import time
from pathlib import Path

import epics

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monp_transform import full_physics  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, default=1)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--dt", type=float, default=5.0)
    a = ap.parse_args()
    r = f"15IDC:util:userTran{a.slot}"
    worst = 0.0
    for _ in range(a.n):
        v = {x: float(epics.caget(f"{r}.{x}", timeout=3)) for x in "EFGIJP"}
        full = full_physics(v["J"], v["I"], v["E"], v["F"], v["G"])
        sevr = epics.caget(f"{r}.SEVR", as_string=True, timeout=3)
        ratio = v["P"] / full if full else float("nan")
        worst = max(worst, abs(ratio - 1))
        print(f"{time.strftime('%H:%M:%S')}  rate {v['J']:9.0f} Hz  sens {v['I']:.3g} A/V  E {v['E']:.3f} keV  "
              f"T {v['F']:.2f} C  P {v['G']:.2f} kPa  slot {v['P']:.4e} ph/s  full {full:.4e}  "
              f"ratio {ratio:.4f}  SEVR {sevr}")
        time.sleep(a.dt)
    print(f"worst |ratio-1| = {100*worst:.3f} %")


if __name__ == "__main__":
    main()
