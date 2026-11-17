"""Analyse one overnight grid: darks, blanked readings, and a joint fit of the CAL ladder.

Usage: python -I analysis/monc_grid.py <steplog.csv> <grid tag, e.g. g1> [ranges to leave out of the fit, e.g. 20u]
(20 uA/V's dark jumps by ~20-30 Hz inside a step (finding F9), so its points can dominate the fit.)
Uses the runner's step means, which can include a count from before settling (finding F3).
For each ladder point: ratio = (f - dark) / (1e5 Hz/V * I / S), where dark is the mean of the range's
_d, _ub and _off steps. Fit  ln(ratio) = a_range + b_level + c * V_out  by least squares, with the
constraint mean(b_level) = 0. So a_range carries the overall scale (gain x mean level x V2F), b is each
CAL level relative to the mean level, and c is a V2F (or output-stage) term linear in output voltage. Read-only.
fit() is imported by analysis/make_monc_calibration.py.
"""
import csv, re, sys
import numpy as np

K = 1e5
U = {"n": 1e-9, "u": 1e-6, "nA": 1e-9, "uA": 1e-6}


def load(path):
    return {r["step"]: float(r["mean_S4"]) for r in csv.DictReader(open(path))}


def fit(steps, g, exclude=()):
    """Return dict: darks {range: (d, b, ub, off, dark)}, scale {range: factor}, level {level: factor},
    c (per volt), rms, pts [(range, level, V, ratio)], res (residuals)."""
    ranges = sorted({m[1] + m[2] for s in steps if (m := re.fullmatch(rf"{g}_(\d+)([nu])_d", s))},
                    key=lambda x: float(x[:-1]) * U[x[-1]])
    darks, pts = {}, []
    for r in ranges:
        d, b, ub, off = (steps.get(f"{g}_{r}_{k}") for k in ("d", "b", "ub", "off"))
        dark = np.mean([x for x in (d, ub, off) if x is not None])
        darks[r] = (d, b, ub, off, dark)
        if r in exclude:
            continue
        S = float(r[:-1]) * U[r[-1]]
        for s, f in steps.items():
            m = re.fullmatch(rf"{g}_{r}_(\d+)(nA|uA)", s)
            if m:
                I = float(m[1]) * U[m[2]]
                pts.append((r, m[1] + m[2], I / S, (f - dark) / (K * I / S)))
    R = sorted({p[0] for p in pts}, key=lambda x: float(x[:-1]) * U[x[-1]])
    L = sorted({p[1] for p in pts}, key=lambda x: float(x[:-2]) * U[x[-2:]])
    A = np.zeros((len(pts) + 1, len(R) + len(L) + 1)); y = np.zeros(len(pts) + 1)
    for i, (r, l, V, rat) in enumerate(pts):
        A[i, R.index(r)] = 1; A[i, len(R) + L.index(l)] = 1; A[i, -1] = V; y[i] = np.log(rat)
    A[-1, len(R):len(R) + len(L)] = 1  # constraint: sum of level terms = 0
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = y[:-1] - A[:-1] @ sol
    return dict(darks=darks, scale={r: float(np.exp(sol[i])) for i, r in enumerate(R)},
                level={l: float(np.exp(sol[len(R) + j])) for j, l in enumerate(L)},
                c=float(sol[-1]), rms=float(np.std(res)), pts=pts, res=res)


if __name__ == "__main__":
    g = sys.argv[2]
    F = fit(load(sys.argv[1]), g, sys.argv[3:])
    print(f"== {g}: per range (Hz): dark(_d) / blanked / unblanked / after ladder;  SR570 share = dark - 8.4 Hz V2F zero")
    for r, (d, b, ub, off, dark) in F["darks"].items():
        print(f"   {r:>5}/V: {d:8.1f} / {b:8.1f} / {ub:8.1f} / {off:8.1f}   dark {dark:8.1f}  (SR570 {dark-8.4:+8.1f})")
    print(f"\n== joint fit, {len(F['pts'])} points, {len(F['scale']) + len(F['level']) + 1} parameters; rms residual {F['rms']*100:.3f} %")
    print("   range scale (gain x mean level x V2F at 0 V):", "  ".join(f"{r}/V {v:.5f}" for r, v in F["scale"].items()))
    print("   level relative to mean level:            ", "  ".join(f"{l} {v:.5f}" for l, v in F["level"].items()))
    print(f"   output-voltage term: {F['c']*100:+.3f} % per volt")
    print("   residuals (%):", "  ".join(f"{r}/{l}@{V:.2f}V {e*100:+.2f}" for (r, l, V, _), e in zip(F["pts"], F["res"])))
