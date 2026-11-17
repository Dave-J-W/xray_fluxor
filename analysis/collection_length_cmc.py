"""Effective collection length of the CMC-custom chamber as built: a GUARDED collector, from a 2-D Laplace
solution and field-line tracing in the plane of the beam (x) and the gap (z).

Geometry: analysis/cmc_chamber_geometry.py (the user's MonC measurements and meter checks, 2026-11-13):
  - collector: upper plate, 60.5 mm long, at signal ground (SR570 virtual ground)
  - HV: lower plate, 75.5 mm long
  - guards: Al blocks beside the collector, grounded to the shell, ~1 mm from the collector and the end wall,
    set back 0.51 mm from the collector's plane (larger clear aperture) and sitting on the top shell
  - shell: grounded steel, inner length 89.0 mm; the Kapton window apertures are modelled as grounded (ASSUMED)
Why field lines decide it (as in analysis/fringe_field.py): a pair born at r drifts along the field line through r.
By Shockley-Ramo it induces e on the collector if that line ends on the collector, and 0 if it ends on a guard or
the shell. l_eff = the length of beam line whose field lines end on the collector. HV polarity does not matter.

The calc uses l = calc/monp_transform.py L_CM (set to this model's nominal l_eff), so delta = l_eff / l - 1 is ~0 for the nominal case,
and the flux factor is 1/(1 + delta) (METHOD_REVIEW.md M3).

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/collection_length_cmc.py [--h 0.1] [--check]
Output: analysis/out/collection_length_cmc.csv (nominal case and one-at-a-time sensitivity cases).
"""
import argparse
import csv
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "calc"))
import cmc_chamber_geometry as cg  # noqa: E402
from fringe_field import trace_endpoints  # noqa: E402
from monp_transform import L_CM  # noqa: E402

OUT = HERE / "out"
HV, COLL, GND = 1, 2, 3


@dataclass(frozen=True)
class Geom:
    """All lengths in mm. Defaults come from cmc_chamber_geometry; sensitivity cases override single fields."""
    inner_length: float
    z_bot: float               # shell inner faces
    z_top: float
    coll_len: float
    coll_z0: float             # collector gap-facing face
    plate_t: float
    hv_len: float
    hv_z1: float               # HV plate gap-facing face
    guard_gap: float           # collector end to guard
    guard_wall_gap: float      # guard to end wall
    guard_z0: float            # guard gap-facing face
    beam_z: float

    @classmethod
    def nominal(cls):
        d = cg.derived()
        return cls(inner_length=d["inner_length"], z_bot=d["shell_bottom_inner_z"], z_top=d["shell_top_inner_z"],
                   coll_len=cg.v("upper_plate_length"), coll_z0=d["upper_inner_z"], plate_t=cg.v("plate_thickness"),
                   hv_len=cg.v("lower_plate_length"), hv_z1=d["lower_inner_z"],
                   guard_gap=cg.v("block_gap"), guard_wall_gap=cg.v("block_gap"), guard_z0=d["guard_z0"],
                   beam_z=d["beam_z"])


def label_map(g, h):
    x = np.arange(-g.inner_length / 2, g.inner_length / 2 + h / 2, h)
    z = np.arange(g.z_bot, g.z_top + h / 2, h)
    X, Z = np.meshgrid(x, z, indexing="ij")
    lab = np.zeros(X.shape, np.int8)
    lab[[0, -1], :] = GND
    lab[:, [0, -1]] = GND
    ax = np.abs(X)
    lab[(ax <= g.hv_len / 2) & (Z <= g.hv_z1) & (Z >= g.hv_z1 - g.plate_t)] = HV
    lab[(ax <= g.coll_len / 2) & (Z >= g.coll_z0) & (Z <= g.coll_z0 + g.plate_t)] = COLL
    g0, g1 = g.coll_len / 2 + g.guard_gap, g.inner_length / 2 - g.guard_wall_gap
    lab[(ax >= g0) & (ax <= g1) & (Z >= g.guard_z0)] = GND
    return x, z, lab


def laplace(lab, v_fixed):
    """Solve Laplace on the grid with Dirichlet values on every labelled cell (5-point stencil)."""
    free = lab == 0
    idx = -np.ones(lab.shape, np.int64)
    idx[free] = np.arange(free.sum())
    fi, fj = np.nonzero(free)
    k = idx[fi, fj]
    n = len(k)
    rows, cols, vals = [k], [k], [np.full(n, -4.0)]
    b = np.zeros(n)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = fi + di, fj + dj
        m = free[ni, nj]
        rows.append(k[m]); cols.append(idx[ni[m], nj[m]]); vals.append(np.ones(m.sum()))
        np.add.at(b, k[~m], -v_fixed[ni[~m], nj[~m]])
    A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    V = v_fixed.astype(float).copy()
    V[free] = spla.spsolve(A.tocsc(), b)
    return V


def solve(g, h):
    x, z, lab = label_map(g, h)
    V = laplace(lab, np.where(lab == HV, 1.0, 0.0))
    return x, z, V, lab


def l_eff(g, h=0.1):
    """Return (l_eff mm, x of the collection edges (upstream, downstream) mm, sampled x, hit codes)."""
    x, z, V, lab = solve(g, h)
    xs = np.arange(-g.inner_length / 2 + h, g.inner_length / 2 - h, h / 2)
    hit = trace_endpoints(x, z, V, lab, xs, g.beam_z, h)
    coll = hit == COLL
    edges = (float(xs[coll].min()), float(xs[coll].max())) if coll.any() else (np.nan, np.nan)
    return float(coll.sum() * h / 2), edges, xs, hit


def cases():
    n = Geom.nominal()
    d = cg.derived()
    return [
        ("nominal", n, "as measured (cmc_chamber_geometry)"),
        ("guard_gap_0.5", replace(n, guard_gap=0.5), "collector-to-guard gap 0.5 mm"),
        ("guard_gap_1.5", replace(n, guard_gap=1.5), "collector-to-guard gap 1.5 mm"),
        ("guard_touches_wall", replace(n, guard_wall_gap=0.0), "no gap between guard and end wall"),
        ("guard_recess_0.25", replace(n, guard_z0=n.coll_z0 + 0.25), "guard set back 0.25 mm (measured 0.51)"),
        ("guard_recess_0.75", replace(n, guard_z0=n.coll_z0 + 0.75), "guard set back 0.75 mm (measured 0.51)"),
        ("guard_flush", replace(n, guard_z0=n.coll_z0), "guard level with the collector face (no recess)"),
        ("coll_len_-0.5", replace(n, coll_len=n.coll_len - 0.5), "collector 0.5 mm shorter"),
        ("coll_len_+0.5", replace(n, coll_len=n.coll_len + 0.5), "collector 0.5 mm longer"),
        ("beam_z_+1", replace(n, beam_z=n.beam_z + 1.0), "beam 1 mm toward the collector"),
        ("beam_z_-1", replace(n, beam_z=n.beam_z - 1.0), "beam 1 mm toward the HV plate"),
        ("hv_len_-2", replace(n, hv_len=n.hv_len - 2.0), "HV plate 2 mm shorter"),
        ("gap_+0.2", replace(n, hv_z1=n.hv_z1 - 0.2), "plate gap 0.2 mm wider (HV plate moved)"),
        ("gap_-0.2", replace(n, hv_z1=n.hv_z1 + 0.2), "plate gap 0.2 mm narrower (HV plate moved)"),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h", type=float, default=0.1, help="grid spacing, mm")
    ap.add_argument("--check", action="store_true", help="grid convergence of the nominal case")
    a = ap.parse_args()
    L = L_CM * 10
    if a.check:
        for h in (0.2, 0.1, 0.05):
            t0 = time.time()
            le, ed, _, _ = l_eff(Geom.nominal(), h)
            print(f"h {h:.2f} mm: l_eff {le:.3f} mm, edges {ed[0]:+.3f} / {ed[1]:+.3f} mm, "
                  f"delta vs {L:.0f} mm {100 * (le / L - 1):+.2f} %  ({time.time() - t0:.0f} s)")
        return
    rows = []
    for name, g, what in cases():
        t0 = time.time()
        le, ed, _, _ = l_eff(g, a.h)
        dl = le / L - 1
        rows.append([name, f"{le:.3f}", f"{ed[0]:.3f}", f"{ed[1]:.3f}", f"{100 * dl:.3f}", f"{100 * (1 - 1 / (1 + dl)):.3f}", what])
        print(f"{name:26s} l_eff {le:7.3f} mm  edges {ed[0]:+8.3f} / {ed[1]:+8.3f}  delta {100 * dl:+6.2f} %  "
              f"flux deficit {100 * (1 - 1 / (1 + dl)):+5.2f} %   {what}  ({time.time() - t0:.0f} s)")
    with (OUT / "collection_length_cmc.csv").open("w", newline="", encoding="utf-8") as f:
        f.write(f"# guarded CMC-custom chamber, 2-D Laplace + field lines, grid {a.h} mm; delta = l_eff / {L:.2f} mm - 1 "
                f"(calc L_CM); flux factor 1/(1+delta)\n")
        f.write("# geometry: analysis/cmc_chamber_geometry.py (user's MonC measurements, 2026-11-13)\n")
        csv.writer(f).writerows([["case", "l_eff_mm", "edge_up_mm", "edge_down_mm", "delta_pct", "flux_deficit_pct", "what"]] + rows)


if __name__ == "__main__":
    main()
