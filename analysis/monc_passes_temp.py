"""Correlate the overnight MonC dark passes with hutch temperature. Read-only.

Usage: python -I analysis/monc_passes_temp.py <steplog.csv> <passes.csv> <temperature RAW csv> [...more sensors]
- steplog: the runner's step log (its first row's t_start is t=0 of the passes table).
- passes:  table from analysis/monc_passes.py (series, t_h, mean_S4, ...).
- temperature: raw archiver CSV, no header: epoch_s, value, severity, status, nanos (no binning operator).
  Readings with severity != 0 or outside 5-45 degC are dropped (0.0 = no sensor).
For each series and sensor: the temperature span, Pearson r with T at the step time (lag 0) and with T 30 min
earlier, the slope in Hz/degC with its standard error, and r after removing a straight line in time from both
(so a shared monotonic trend alone can't make a correlation). |r| > 0.21 is p < 0.05 for 90 points.
"""
import csv, sys
from collections import defaultdict
import numpy as np

t0 = float(next(csv.DictReader(open(sys.argv[1])))["t_start"])
ser = defaultdict(list)
for r in csv.DictReader(open(sys.argv[2])):
    ser[r["series"]].append((t0 + 3600 * float(r["t_h"]), float(r["mean_S4"])))


def detr(t, y):
    return y - np.polyval(np.polyfit(t, y, 1), t)


for path in sys.argv[3:]:
    a = np.loadtxt(path, delimiter=",", usecols=(0, 1, 2), ndmin=2)
    a = a[(a[:, 2] == 0) & (a[:, 1] > 5) & (a[:, 1] < 45)]
    a = a[np.argsort(a[:, 0])]
    name = path.replace("\\", "/").split("/")[-1].split("_RAW")[0]
    if len(a) < 10:
        print(f"== {name}: {len(a)} valid readings; refused"); continue
    tt, TT = a[:, 0], a[:, 1]
    print(f"== {name}: {len(a)} readings, step between readings median {np.median(np.diff(tt)):.0f} s")
    print(f"{'series':8} {'n':>3} {'T span degC':>14} {'r lag0':>7} {'r lag30m':>8} {'Hz/degC':>9} {'+-':>6} {'r detrended':>11}")
    for k, v in ser.items():
        t, y = np.array(v).T
        m = (t >= tt[0]) & (t <= tt[-1])
        t, y = t[m], y[m]
        T0 = np.interp(t, tt, TT)
        T30 = np.interp(t - 1800, tt, TT)
        r0 = np.corrcoef(y, T0)[0, 1]
        r30 = np.corrcoef(y, T30)[0, 1]
        p, cov = np.polyfit(T0, y, 1, cov=True)
        rd = np.corrcoef(detr(t, y), detr(t, T0))[0, 1]
        print(f"{k:8} {len(y):3d} {T0.min():6.2f}-{T0.max():6.2f} {r0:+7.2f} {r30:+8.2f} {p[0]:+9.2f} {np.sqrt(cov[0, 0]):6.2f} {rd:+11.2f}")
