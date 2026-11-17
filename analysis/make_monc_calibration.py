"""Build the MonC SR570 per-gain calibration table from the overnight step log. Read-only on EPICS (none).

Usage: python -I analysis/make_monc_calibration.py [steplog] [out.csv]
  defaults: data/sweeps/monc_sweep_steps_20261112_154045.csv  data/calibration/monc_sr570_ranges.csv

One row per SR570 sensitivity index 0..27 (SENS0 = 1 pA/V ... SENS27 = 1 mA/V; it is the value of
15IDC:A3sens_put, checked live 2026-11-13: 20 = 5 uA/V). Columns:
- factor: measured range scale (gain x mean CAL level x V2F), mean of grids g2-g4, all-range joint fit
  (analysis/monc_grid.py). Live calc: I = f_net * S / (1e5 Hz/V * factor). Unmeasured indices: 1.
- u_factor_rel: spread (max - min) of the factor over g2-g4 and over the fit with 20 uA/V left out;
  for 20 uA/V a floor of 0.0003 (finding F9: in-step dark jumps; 0.030 % on strict windows).
  Unmeasured indices: FALLBACK_U (the write-up's +-0.7 % SR570 x V2F term) and measured = 0.
- dark_Hz, dark_sd_reselect_Hz: offset-off dark, mean and pass-to-pass sd over the 92 overnight passes
  (each pass reselects the gain). dark_sd_same_Hz: dark error within one selection, where measured
  (5 uA/V: 92 pairs 5u_d2 -> 5u_ub, sd(diff)/sqrt2, finding F10); blank = not measured, use reselect.
Common to every row, not in the arrays: the absolute scale of the SR570 CAL current, which the factors
are relative to. Not measured; carry the write-up's type-B term for absolute flux (it cancels in ratios).
The header records the SHA-256 of the source file and of this script and monc_grid.py. The output is
deterministic, so the check is: regenerate, then `git diff --exit-code data/calibration/monc_sr570_ranges.csv`.
"""
import csv, hashlib, re, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import monc_grid  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/sweeps/monc_sweep_steps_20261112_154045.csv"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data/calibration/monc_sr570_ranges.csv"
GRIDS = ("g2", "g3", "g4")  # g1 left out: 2.5 h after power-on, warm-up
FALLBACK_U = 0.007
F9_FLOOR = {"20u": 0.0003}
UNITS = ["pA/V", "nA/V", "uA/V", "mA/V"]
LABELS = [f"{n} {UNITS[i // 9]}" for i, n in enumerate([1, 2, 5, 10, 20, 50, 100, 200, 500] * 3)] + ["1 mA/V"]
KEY = {lab: f"{lab.split()[0]}{lab.split()[1][0]}" for lab in LABELS}  # "5 uA/V" -> "5u"

steps = monc_grid.load(src)
fac = defaultdict(list)
for g in GRIDS:
    for variant in ((), ("20u",)):
        for r, v in monc_grid.fit(steps, g, variant)["scale"].items():
            fac[r].append((variant == (), v))
# darks from the passes, in time order; 5u_d appears twice per pass
rows = list(csv.DictReader(open(src)))
dk = defaultdict(list)
for r in rows:
    m = re.fullmatch(r"p\d+_(\w+?)_(d|ub)", r["step"])
    if m:
        dk[f"{m[1]}_{m[2]}"].append(float(r["mean_S4"]))
d5 = dk.pop("5u_d")
dk["5u_d1"], dk["5u_d2"] = d5[0::2], d5[1::2]
same = {"5u": float(np.std(np.array(dk["5u_d2"]) - np.array(dk["5u_ub"]), ddof=1) / np.sqrt(2))}


def dark(k):
    a = np.array(dk["5u_d1"] if k == "5u" else dk.get(f"{k}_d", []))
    return (float(a.mean()), float(a.std(ddof=1)), len(a)) if len(a) > 2 else (None, None, 0)


def sha(p):  # line endings normalised, so a CRLF checkout hashes the same as LF
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


here = Path(__file__).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="\n") as f:
    f.write(f"# MonC (15IDC:A3) SR570 per-gain calibration, written by analysis/make_monc_calibration.py "
            f"(sha256 {sha(here)[:16]}, with monc_grid.py {sha(here.parent / 'monc_grid.py')[:16]}). Deterministic: regenerate and diff.\n")
    f.write(f"# source {src.name} sha256 {sha(src)}; grids {','.join(GRIDS)}; 92 dark passes 2026-11-12 15:40 - 2026-11-13 08:10\n")
    f.write("# valid for MonC's SR570 unit as installed 2026-11-12; re-measure after a swap or repair. MonP (A2): not measured, use the fallback.\n")
    f.write(f"# factors are relative to the mean SR570 CAL level (absolute scale not measured: type B, write-up term {FALLBACK_U:.3f})\n")
    f.write("# darks taken with the MonC chamber cabled (no beam): they include +21.5 +- 1.3 Hz at every gain from the chamber connection;"
            " leakage current -2.6 +- 12.8 pA (analysis/monc_leak.py, 2026-11-13)\n")
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["index", "sensitivity", "measured", "factor", "u_factor_rel", "dark_Hz", "dark_sd_reselect_Hz", "dark_sd_same_Hz", "n_passes"])
    for i, lab in enumerate(LABELS):
        k = KEY[lab]
        dm, ds, n = dark(k)
        if k in fac:
            vals = [v for _, v in fac[k]]
            allr = [v for a, v in fac[k] if a]
            u = max(max(vals) - min(vals), F9_FLOOR.get(k, 0))
            w.writerow([i, lab, 1, f"{np.mean(allr):.5f}", f"{u:.5f}", f"{dm:.1f}", f"{ds:.1f}",
                        f"{same[k]:.2f}" if k in same else "", n])
        else:
            w.writerow([i, lab, 0, "1.00000", f"{FALLBACK_U:.5f}", f"{dm:.1f}" if dm else "", f"{ds:.1f}" if ds else "", "", n])
print(f"wrote {out} from {src.name} (sha256 {sha(src)[:12]}...)")
