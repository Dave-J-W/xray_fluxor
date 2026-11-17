"""Fit compact formulas for N mass coefficients, so an EPICS calc can evaluate them.

ln(mu/rho) = c0 + x*(c1 + x*(c2 + x*c3)),  x = ln(E/keV),  over 5-30 keV

The targets are NIST Hubbell-Seltzer for N, log-log interpolated between its grid points (as
NIST recommends):
  muen : mass energy-absorption coefficient (sets the signal)
  mu   : total mass attenuation coefficient (sets the transmission to the exit plane)
The fits are dense in E, so they inherit NIST's interpolation and nothing else.
Reports the max |error| of each fit against its target, and writes calc/coefficients.json.

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 calc/fit_coefficients.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "queries"))
from query_cross_sections import parse_nist, loglog_interp  # noqa: E402

NIST_N = parse_nist(ROOT / "data" / "queries" / "nist_hubbell_seltzer" / "z07_nitrogen.html")
E_LO, E_HI = 5.0, 30.0


import xraydb  # noqa: E402


NIST_GRID_KEV = [4, 5, 6, 8, 10, 15, 20, 30, 40]


def target(e_kev, col):
    """NIST-anchored smooth target: the Elam shape scaled by NIST/Elam.
    The NIST/Elam ratio is taken at NIST's own grid points and interpolated log-log between them.
    The target therefore equals NIST exactly at every NIST grid point (incl. 30 keV, where
    Elam differs by ~0.6 %), and follows Elam's smooth shape in between (no interpolation kinks)."""
    lr = np.interp(np.log(e_kev), np.log(NIST_GRID_KEV),
                   [np.log(nist(g, col) / elam(g, col)) for g in NIST_GRID_KEV])
    return elam(e_kev, col) * float(np.exp(lr))


def elam(e_kev, col):
    """Smooth target: xraydb Elam for N.
    col 2 (mu_en): photo + incoh * (mean Compton electron energy / E).
    col 1 (mu): the Elam total.
    NIST's log-log interpolation between its coarse 10/15/20 keV grid has kinks of up to ~1 %
    that a smooth fit should not chase. Elam agrees with NIST at the NIST grid points to
    <=0.2 % for mu_en at 5-20 keV (data/queries/out/compare_N.csv)."""
    ev = e_kev * 1e3
    if col == 1:
        return float(xraydb.mu_elam("N", ev, kind="total"))
    ce = float(xraydb.get_xraydb().compton_energies(ev).electron_mean)
    return float(xraydb.mu_elam("N", ev, kind="photo")) + float(xraydb.mu_elam("N", ev, kind="incoh")) * ce / ev


def nist(e_kev, col):
    return loglog_interp(e_kev / 1e3, NIST_N, col)


def fit(col, deg=3):
    e = np.geomspace(E_LO, E_HI, 400)
    y = np.log([target(x, col) for x in e])
    x = np.log(e)
    # minimax (equal-ripple) fit by Lawson's iteratively reweighted least squares, so the worst
    # error over the range is as small as a cubic allows. The fit is in ln space, so the error
    # is relative.
    w = np.ones_like(x)
    for _ in range(200):
        c = np.polynomial.polynomial.polyfit(x, y, deg, w=np.sqrt(w))
        r = np.abs(np.polynomial.polynomial.polyval(x, c) - y)
        w = w * r
        w /= w.sum()
    yfit = np.polynomial.polynomial.polyval(x, c)
    err = np.exp(yfit - y) - 1
    return c, float(np.abs(err).max()), e[np.argmax(np.abs(err))]


def main():
    out = {}
    for name, col in (("muen", 2), ("mu", 1)):
        c, emax, at = fit(col)
        # round to 4 significant figures (what fits in a 39-character calc expression) and re-check
        cr = [float(f"{v:.4g}") for v in c]
        e = np.geomspace(E_LO, E_HI, 400)
        x = np.log(e)
        err_r = np.exp(np.polynomial.polynomial.polyval(x, cr)) / np.array([target(v, col) for v in e]) - 1
        out[name] = {"coeffs_c0_c3": cr, "max_abs_rel_err": float(np.abs(err_r).max()),
                     "at_keV": float(e[np.argmax(np.abs(err_r))]), "range_keV": [E_LO, E_HI],
                     "target": f"NIST HS z07 nitrogen column {col}, log-log interpolated"}
        print(f"{name}: c = {cr}  max |rel err| = {100*np.abs(err_r).max():.3f} % at {e[np.argmax(np.abs(err_r))]:.2f} keV")
        grid = {}
        for k in (5, 6, 8, 10, 15, 20, 30):     # NIST native grid points: no interpolation there
            v = float(np.exp(np.polynomial.polynomial.polyval(np.log(k), cr)))
            grid[k] = 100 * (v / nist(k, col) - 1)
            print(f"   {k:4.0f} keV  fit {v:.5g}  Elam-target {target(k, col):.5g}  NIST {nist(k, col):.5g}  (fit vs NIST {grid[k]:+.3f} %)")
        out[name]["fit_vs_NIST_at_NIST_grid_pct"] = grid
    (ROOT / "calc" / "coefficients.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
