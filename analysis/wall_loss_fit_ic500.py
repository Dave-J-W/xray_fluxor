r"""Fit the IC-500-50's signal wall loss (f_pe x MC) and check that the live band formula covers its MC variants.

Reuses analysis/wall_loss_fit.py (fit, coverage, f_pe) with an extra lane key "IC500". The family comes from
analysis/wall_loss_ic500.py (geometry ASSUMED, see fluxor/ASSUMPTIONS.md). The band is the SAME formula as MonP and MonC
(calc/quality_slots.BAND); whether it covers this chamber is exactly what this script tests.
Run: <bluesky venv>\Scripts\python.exe -I -X utf8 analysis/wall_loss_fit_ic500.py
Output: analysis/out/wall_loss_fit_IC500.txt. Exit 1 if the fluxor constant differs from the rounded fit or a gated point
is outside the band.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import wall_loss_fit as wlf  # noqa: E402

wlf.FAMILIES = ("IC500",)


def main():
    from fluxor.chambers import ic500_50
    wlf.qs.WALL_FITS["IC500"] = ic500_50.WALL_FIT
    ok, rounded = wlf.run_family("IC500")
    same = tuple(round(v, 2) for v in rounded) == tuple(round(v, 2) for v in ic500_50.WALL_FIT)
    print(f"fluxor.chambers.ic500_50.WALL_FIT {ic500_50.WALL_FIT} vs rounded fit {rounded}: {'EQUAL' if same else 'DIFFER'}")
    print("PASS" if ok and same else "FAIL")
    return 0 if ok and same else 1


if __name__ == "__main__":
    sys.exit(main())
