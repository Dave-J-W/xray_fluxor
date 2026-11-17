"""Dark-drift record from the overnight MonC passes (2026-11-12/13).

Usage: python -I analysis/monc_passes.py <steplog.csv>
Each pass p<N> has offset-off darks on 200 nA/V-20 uA/V (p<N>_<range>_d; the 5 uA/V dark is taken twice,
the second with blank/unblank after it), and a 480 s hold at the interim setting (p<N>_hold). For each
series: n, mean, sd across passes, min/max, the least-squares slope in Hz/h, and the mean of the first and last
10 passes. The first 5u_d of each pass is reported as '5u_d1' and the repeat as '5u_d2'. Read-only.
"""
import csv, re, sys
from collections import defaultdict
import numpy as np

rows = list(csv.DictReader(open(sys.argv[1])))
t0 = float(rows[0]["t_start"])
ser = defaultdict(list)  # name -> [(t_h, mean, sd, n)]
for r in rows:
    m = re.fullmatch(r"p(\d+)_(\w+?)_(d|b|ub)|p(\d+)_(hold)", r["step"])
    if not m:
        continue
    t = (float(r["t_settled"]) - t0) / 3600
    if m[5]:
        key = "hold"
    else:
        key = f"{m[2]}_{m[3]}"
    ser[key].append((t, float(r["mean_S4"]), float(r["sd_S4"]), int(r["n"])))
# split the two 5u_d per pass: rows are in time order, so they alternate
if "5u_d" in ser:
    s = ser.pop("5u_d")
    ser["5u_d1"], ser["5u_d2"] = s[0::2], s[1::2]
order = ["200n_d", "500n_d", "1u_d", "2u_d", "5u_d1", "5u_d2", "10u_d", "20u_d", "5u_b", "5u_ub", "hold"]
print(f"t from {rows[0]['step']} start; hours since then. Values are per-step means of S4 (Hz).")
print(f"{'series':8} {'n':>3} {'mean':>8} {'sd':>6} {'min':>8} {'max':>8} {'slope Hz/h':>11} {'first10':>8} {'last10':>8} {'within-step sd':>14}")
for k in order:
    if k not in ser:
        continue
    a = np.array(ser[k])
    t, y = a[:, 0], a[:, 1]
    slope = np.polyfit(t, y, 1)[0]
    print(f"{k:8} {len(y):3d} {y.mean():8.1f} {y.std(ddof=1):6.1f} {y.min():8.1f} {y.max():8.1f} {slope:+11.2f} "
          f"{y[:10].mean():8.1f} {y[-10:].mean():8.1f} {np.median(a[:, 2]):14.1f}")
if len(sys.argv) > 2:  # optional: write the per-pass table for figures
    with open(sys.argv[2], "w", newline="") as f:
        w = csv.writer(f); w.writerow(["series", "t_h", "mean_S4", "sd_S4", "n"])
        for k in order:
            for t, y, sd, n in ser.get(k, []):
                w.writerow([k, f"{t:.4f}", f"{y:.3f}", f"{sd:.3f}", n])
