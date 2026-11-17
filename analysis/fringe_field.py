"""Effective collection length of a guard-less parallel-plate ion chamber (CMC-custom), from a 2-D
Laplace solution and field-line tracing.

Why field lines decide it. An electron-ion pair born at point r moves along the field line
through r: one carrier goes to the HV plate, the other to whichever grounded conductor the line
ends on. By Shockley-Ramo the charge induced on the collector is e·[φw(end1) − φw(end2)], where
φw is the collector's weighting potential (1 on the collector, 0 on every other conductor). The
pair therefore contributes e if its line ends on the collector, and 0 if it ends on the
grounded chamber body. The HV polarity does not matter.

Geometry (2-D cross-section in the plane of the beam (x) and the gap (y); the plates are at least
as wide as they are long (user), so the third dimension is a weaker effect):
- collector: 0 V, plate of length L = 6 cm and thickness t, inner face at y = −g/2 (g = 1 cm)
- HV plate:  1 V (normalized), the mirror at y = +g/2
- body:      0 V, a rectangle w_side beyond each plate's outer face, w_end beyond each plate end
             (the end walls carry the Kapton windows; treated as grounded metal)
- beam:      along y = 0 (mid-gap), from wall to wall
l_eff = the length of beam line whose field lines end on the collector.

Analytic check (--check): with the body far away, l_eff − L should approach the classic 2-D
fringe extension of an isolated two-plate capacitor, a fraction of the gap per end, here
compared at large w_side and w_end. The reported numbers do not depend on it.

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/fringe_field.py [--scan] [--h 0.02]
"""
import argparse
import csv
import itertools
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.ndimage import map_coordinates

OUT = Path(__file__).resolve().parents[1] / "analysis" / "out"
OUT.mkdir(exist_ok=True)
L, G = 6.0, 1.0          # cm
PLATE_T_CM = 0.2         # assumed plate thickness for single-case runs and figures (PROVISIONAL; the scan uses 0.1 and 0.3)


def solve(t, w_side, w_end, h):
    """Return the grids, the potential V and the conductor label map (0 free, 1 HV, 2 collector, 3 body)."""
    xmax = L / 2 + w_end
    ymax = G / 2 + t + w_side
    x = np.arange(-xmax, xmax + h / 2, h)
    y = np.arange(-ymax, ymax + h / 2, h)
    X, Y = np.meshgrid(x, y, indexing="ij")
    lab = np.zeros(X.shape, np.int8)
    lab[[0, -1], :] = 3
    lab[:, [0, -1]] = 3
    inx = np.abs(X) <= L / 2
    lab[inx & (Y >= G / 2) & (Y <= G / 2 + t)] = 1
    lab[inx & (Y <= -G / 2) & (Y >= -G / 2 - t)] = 2
    fixed = lab > 0
    vfix = np.where(lab == 1, 1.0, 0.0)
    nx, ny = X.shape
    idx = -np.ones(X.shape, np.int64)
    free = ~fixed
    idx[free] = np.arange(free.sum())
    n = free.sum()
    rows, cols, vals = [], [], []
    b = np.zeros(n)
    fi, fj = np.nonzero(free)
    k = idx[fi, fj]
    rows.append(k); cols.append(k); vals.append(np.full(n, -4.0))
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = fi + di, fj + dj
        nb_free = free[ni, nj]
        rows.append(k[nb_free]); cols.append(idx[ni[nb_free], nj[nb_free]]); vals.append(np.ones(nb_free.sum()))
        b[~nb_free] -= vfix[ni[~nb_free], nj[~nb_free]]
        np.add.at(b, k[~nb_free], 0)  # (b already updated per element above)
    A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    # rebuild b exactly (vectorised accumulation)
    b = np.zeros(n)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = fi + di, fj + dj
        m = ~free[ni, nj]
        np.add.at(b, k[m], -vfix[ni[m], nj[m]])
    V = vfix.copy()
    V[free] = spla.spsolve(A, b)
    return x, y, V, lab


def trace_endpoints(x, y, V, lab, x0, y0, h, max_steps=20000):
    """Follow -grad V (toward lower potential) from each start point until it enters a conductor.
    Return the conductor label hit (2 collector, 3 body; 1 is impossible downhill)."""
    gx, gy = np.gradient(V, h, h)
    px = np.array(x0, float)
    py = np.full_like(px, y0)
    done = np.zeros(len(px), bool)
    hit = np.zeros(len(px), np.int8)
    step = 0.25 * h

    def ij(px, py):
        return (px - x[0]) / h, (py - y[0]) / h

    for _ in range(max_steps):
        a = ~done
        if not a.any():
            break
        fi, fj = ij(px[a], py[a])
        ex = -map_coordinates(gx, [fi, fj], order=1, mode="nearest")
        ey = -map_coordinates(gy, [fi, fj], order=1, mode="nearest")
        nrm = np.hypot(ex, ey) + 1e-30
        px[a] += step * ex / nrm
        py[a] += step * ey / nrm
        fi, fj = ij(px[a], py[a])
        li = np.clip(np.rint(fi).astype(int), 0, lab.shape[0] - 1)
        lj = np.clip(np.rint(fj).astype(int), 0, lab.shape[1] - 1)
        l = lab[li, lj]
        stop = l > 0
        ai = np.nonzero(a)[0]
        hit[ai[stop]] = l[stop]
        done[ai[stop]] = True
    return hit


def l_eff(t, w_side, w_end, h=0.02, n_pts=None):
    x, y, V, lab = solve(t, w_side, w_end, h)
    # beam-line sample points, dense near the plate ends, beyond the plate region only
    # (inside |x| < L/2 - g every line ends on the collector to very high accuracy; checked below)
    xs = np.arange(L / 2 - 2 * G, L / 2 + w_end - h, h / 2)
    hit = trace_endpoints(x, y, V, lab, xs, 0.0, h)
    coll = hit == 2
    # extension beyond one plate end, and any shortfall inside it
    beyond = coll & (xs > L / 2)
    inside_lost = (~coll) & (xs <= L / 2)
    dx = h / 2
    ext = beyond.sum() * dx - inside_lost.sum() * dx
    return L + 2 * ext, ext, inside_lost.sum() * dx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--h", type=float, default=0.02, help="grid spacing, cm")
    a = ap.parse_args()
    if a.check:
        print("convergence and far-wall limit (t = 0.1 cm):")
        for h in (0.04, 0.02, 0.01):
            le, ext, lost = l_eff(0.1, 4.0, 4.0, h)
            print(f"  h={h:.3f} cm: extension per end {ext*10:.3f} mm = {ext/G:.3f} gap; l_eff/L-1 = {100*(le/L-1):.2f} %")
        return
    rows = []
    combos = list(itertools.product((0.1, 0.3), (0.5, 1.0, 2.0, 4.0), (0.5, 1.0, 2.0, 4.0))) if a.scan else [(PLATE_T_CM, 1.0, 1.0)]
    for t, ws, we in combos:
        t0 = time.time()
        le, ext, lost = l_eff(t, ws, we, a.h)
        rows.append([t, ws, we, f"{ext*10:.3f}", f"{100*(le/L-1):.2f}", f"{lost*10:.3f}"])
        print(f"t {t*10:.0f} mm  side gap {ws:.1f} cm  end gap {we:.1f} cm -> extension/end {ext*10:5.2f} mm, "
              f"l_eff/L - 1 = {100*(le/L-1):5.2f} %  ({time.time()-t0:.1f} s)")
    if a.scan:
        with (OUT / "fringe_field_scan.csv").open("w", newline="") as f:
            f.write("# effective collection length of a guard-less 2-plate chamber (2-D Laplace + field lines); L=6 cm, gap 1 cm\n")
            csv.writer(f).writerows([["plate_t_cm", "side_gap_cm", "end_gap_cm", "ext_per_end_mm", "leff_over_L_minus_1_pct", "inside_lost_mm"]] + rows)


if __name__ == "__main__":
    main()
