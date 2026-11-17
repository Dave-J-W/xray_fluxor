"""Run the wall-loss Monte Carlo for each chamber as built: the central case and every variant the band must cover.

One family per lane (calc/lanes.py LANES), with its geometry from analysis/cmc_chamber_geometry.py:
  MonP: plates vertical, E-vector toward the plates; beam position in the gap NOT measured (taken centred, ASSUMED);
        beam FWHM across the gap = the horizontal beam size, ~1 mm (user)
  MonC: plates horizontal, E-vector along the plates; beam offset toward the collector = derived()["beam_above_mid_gap"]
        (from the Kapton scar); beam FWHM across the gap = the vertical size, 0.02-0.04 mm (user), 0.03 taken
  both: half gap = plate_gap / 2 (from the aperture-ledge insets), N2 at the MC reference density rho0
Variants (one-at-a-time, two-change corners, and one stress corner that is reported but not gated):
  range +-10 %, elastic sigma +-20 %, beam offset +1 mm, density +-3 %, (range +10 % & sigma -20 %),
  (range -10 % & sigma +20 %), stress: (range +10 % & sigma -20 % & offset +1 mm)
Output: analysis/out/wall_loss/<family>/<variant>.csv (same seed for all runs).
Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/wall_loss_families.py [--family MonP] [--jobs 4]
"""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cmc_chamber_geometry as cg  # noqa: E402

OUT = HERE / "out" / "wall_loss"
MC = HERE / "wall_loss_mc.py"
def families():
    """Every input comes from cmc_chamber_geometry (METHOD_REVIEW C8); nothing here is a chamber or beam constant."""
    d = cg.derived()
    half = cg.v("plate_gap") / 2
    return {
        "MonP": {"half_gap_mm": half, "offset_mm": cg.v("monp_beam_offset"), "fwhm_mm": cg.v("beam_fwhm_horizontal"),
                 "e_parallel": False, "note": "plates vertical; beam centred in the gap (ASSUMED, not measured on MonP)"},
        "MonC": {"half_gap_mm": half, "offset_mm": round(d["beam_above_mid_gap"], 3),
                 "fwhm_mm": cg.v("beam_fwhm_vertical"), "e_parallel": True,
                 "note": "plates horizontal; beam offset from the Kapton scar"},
    }


VARIANTS = {
    "central": {},
    "range_+10": {"range": 1.1},
    "range_-10": {"range": 0.9},
    "sigma_0.8": {"sigma": 0.8},
    "sigma_1.2": {"sigma": 1.2},
    "offset_+1mm": {"offset_add": 1.0},
    "density_0.97": {"density": 0.97},
    "density_1.03": {"density": 1.03},
    "combo_range+10_sigma0.8": {"range": 1.1, "sigma": 0.8},
    "combo_range-10_sigma1.2": {"range": 0.9, "sigma": 1.2},
    "stress_range+10_sigma0.8_offset+1mm": {"range": 1.1, "sigma": 0.8, "offset_add": 1.0},
}


def command(fam, var):
    f, v = families()[fam], VARIANTS[var]
    cmd = [sys.executable, "-I", "-X", "utf8", str(MC),
           "--half-gap-mm", f"{f['half_gap_mm']}", "--beam-fwhm-mm", f"{f['fwhm_mm']}",
           "--offset-mm", f"{f['offset_mm'] + v.get('offset_add', 0.0)}",
           "--range-scale", f"{v.get('range', 1.0)}", "--sigma-scale", f"{v.get('sigma', 1.0)}",
           "--density-scale", f"{v.get('density', 1.0)}", "--out", str(OUT / fam / f"{var}.csv")]
    if f["e_parallel"]:
        cmd.append("--plates-parallel-to-e")
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(families()), action="append")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    jobs = [(fam, var) for fam in (a.family or sorted(families())) for var in VARIANTS]

    def run(j):
        r = subprocess.run(command(*j), capture_output=True, text=True, encoding="utf-8")
        last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
        return j, r.returncode, last

    failed = []
    with ThreadPoolExecutor(a.jobs) as ex:
        for (fam, var), rc, last in ex.map(run, jobs):
            print(f"{fam:5s} {var:38s} rc={rc}  {last.strip()}", flush=True)
            if rc != 0:
                failed.append(f"{fam}/{var}")
    if failed:                       # a crashed run leaves the previous CSV in place: never pass silently
        print("FAILED:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
