r"""Wall-loss Monte Carlo family for the AVS IC-500-50 at the E-station (10 mm gap, flowing N2).

Same MC (analysis/wall_loss_mc.py) and the same variants as analysis/wall_loss_families.py, with the IC-500-50's geometry:
  half gap 5.0 mm (gap 10 mm, user 2026-11-13), N2 at the MC reference density rho0.
  ASSUMED (not given; fluxor/ASSUMPTIONS.md A-ids): plates horizontal and E-vector along the plates (the MonC mounting),
  beam centred in the gap, beam FWHM across the gap 0.1 mm. Only the 14-30 keV loss depends on them, and weakly (the
  electron range is millimetres, the beam tenths of a millimetre).
Output: analysis/out/wall_loss/IC500/<variant>.csv. Run (about as long as one lane of wall_loss_families.py):
  <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/wall_loss_ic500.py [--jobs 4]
"""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wall_loss_families as wf  # noqa: E402

OUT = HERE / "out" / "wall_loss" / "IC500"
GEOMETRY = {"half_gap_mm": 5.0, "offset_mm": 0.0, "fwhm_mm": 0.1, "e_parallel": True}


def command(var):
    v = wf.VARIANTS[var]
    f = GEOMETRY
    cmd = [sys.executable, "-I", "-X", "utf8", str(wf.MC),
           "--half-gap-mm", f"{f['half_gap_mm']}", "--beam-fwhm-mm", f"{f['fwhm_mm']}",
           "--offset-mm", f"{f['offset_mm'] + v.get('offset_add', 0.0)}",
           "--range-scale", f"{v.get('range', 1.0)}", "--sigma-scale", f"{v.get('sigma', 1.0)}",
           "--density-scale", f"{v.get('density', 1.0)}", "--out", str(OUT / f"{var}.csv")]
    if f["e_parallel"]:
        cmd.append("--plates-parallel-to-e")
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    def run(var):
        r = subprocess.run(command(var), capture_output=True, text=True, encoding="utf-8")
        return var, r.returncode, (r.stdout.strip().splitlines() or ["(no output)"])[-1]

    failed = []
    with ThreadPoolExecutor(a.jobs) as ex:
        for var, rc, last in ex.map(run, list(wf.VARIANTS)):
            print(f"IC500 {var:38s} rc={rc}  {last.strip()}", flush=True)
            if rc != 0:
                failed.append(var)
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
