"""MonC chamber leakage current from dark passes with and without the chamber. Read-only.

Usage: python -I analysis/monc_leak.py <steplog with chamber> <steplog without chamber> [n_last=10]
For each offset-off dark series (p<N>_<range>_d; 5 uA/V uses the first 5u_d of each pass), compares the
last n_last passes of the first log (chamber cabled; the end of the overnight run, closest in time) with
every pass of the second (chamber unplugged, BNC cable end open):
  I_leak = (dark_with - dark_without) * S / 1e5 Hz/V,  u = S/1e5 * sqrt(sd_w^2/n_w + sd_wo^2/n_wo)
using the pass-to-pass sd (the scatter is set at each gain selection, so passes are the samples).
Then the inverse-variance mean over gains, with and without 20 uA/V (its dark jumps inside a step, F9).
Controls: the blanked 5 uA/V reading and the interim hold. Blanking grounds the path after the input,
so the leakage can't reach it: blanked should not change. The hold should drop by 1e5 * I / 5 uA/V.
Caveat: "with minus without" also contains any effect of the open cable (pickup, input capacitance).
"""
import csv, re, sys
from collections import defaultdict
import numpy as np

K = 1e5
S = {"200n": 200e-9, "500n": 500e-9, "1u": 1e-6, "2u": 2e-6, "5u": 5e-6, "10u": 10e-6, "20u": 20e-6}


def series(path):
    ser = defaultdict(list)
    for r in csv.DictReader(open(path)):
        m = re.fullmatch(r"p(\d+)_(\w+?)_(d|b|ub|hold)|p(\d+)_(hold)", r["step"])
        if m:
            key = "hold" if m[5] else f"{m[2]}_{m[3]}"
            ser[key].append(float(r["mean_S4"]))
    d5 = ser.pop("5u_d")
    ser["5u_d"] = d5[0::2]
    return ser


w_all, wo = series(sys.argv[1]), series(sys.argv[2])
n_last = int(sys.argv[3]) if len(sys.argv) > 3 else 10
w = {k: v[-n_last:] for k, v in w_all.items()}
print(f"with chamber: last {n_last} passes of {sys.argv[1].split(chr(92))[-1]}; without: {len(wo['5u_d'])} passes")
print(f"{'gain':6} {'with Hz':>9} {'sd':>5} {'without Hz':>11} {'sd':>5} {'diff Hz':>8} {'I_leak nA':>10} {'u nA':>7}")
est = {}
for g, s in S.items():
    a, b = np.array(w[f"{g}_d"]), np.array(wo[f"{g}_d"])
    d = a.mean() - b.mean()
    u = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    est[g] = (d * s / K * 1e9, u * s / K * 1e9)
    print(f"{g:6} {a.mean():9.1f} {a.std(ddof=1):5.1f} {b.mean():11.1f} {b.std(ddof=1):5.1f} {d:8.1f} {est[g][0]:10.3f} {est[g][1]:7.3f}")
# Model: diff(S) = c + 1e5 * I / S. c is a gain-independent output offset added by the chamber connection,
# I a true input current. Use only gains where the 'without' dark is above the 1-count clip (a clipped
# reading is a bound, not a value) and leave out 20 uA/V (F9). Weighted least squares in Hz.
use = [g for g in S if g != "20u" and np.array(wo[f"{g}_d"]).min() > 1.5]
x = np.array([1 / S[g] for g in use])
y = np.array([np.mean(w[f"{g}_d"]) - np.mean(wo[f"{g}_d"]) for g in use])
uy = np.array([np.sqrt(np.var(w[f"{g}_d"], ddof=1) / len(w[f"{g}_d"]) + np.var(wo[f"{g}_d"], ddof=1) / len(wo[f"{g}_d"])) for g in use])
A = np.vstack([np.ones_like(x), x]).T / uy[:, None]
cov = np.linalg.inv(A.T @ A)
c, b = cov @ A.T @ (y / uy)
chi2 = (((y - (c + b * x)) / uy) ** 2).sum() / max(len(y) - 2, 1)
print(f"fit over {use} (unclipped, no 20u): offset c = {c:.1f} +- {np.sqrt(cov[0,0]):.1f} Hz, "
      f"I_leak = {b/K*1e12:.1f} +- {np.sqrt(cov[1,1])/K*1e12:.1f} pA (reduced chi2 {chi2:.2f})")
print("pure-current model (c = 0) for comparison: per-gain I above; it is rejected if they disagree")
clipped = [g for g in S if np.array(wo[f"{g}_d"]).min() <= 1.5]
print(f"clipped without the chamber (diff is a lower bound): {clipped}")
for k, note in (("5u_b", "blanked 5 uA/V (should not change)"), ("hold", "interim hold (should drop by 1e5*I/5e-6)")):
    a, b = np.array(w[k]), np.array(wo[k])
    print(f"{note}: with {a.mean():.1f} +- {a.std(ddof=1):.1f}, without {b.mean():.1f} +- {b.std(ddof=1):.1f} Hz; diff {a.mean()-b.mean():+.1f} Hz")
