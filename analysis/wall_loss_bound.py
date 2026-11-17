"""Bound the photoelectron energy lost to the collection plates in MonP.

Geometry [PROVISIONAL, user 2026-11-12]:
- vertical plates 1 cm apart, so the field is horizontal and the half-gap is 5 mm
- beam centred, horizontal FWHM ~1 mm, vertical FWHM 20-40 um
- synchrotron polarisation horizontal, i.e. the E-vector is perpendicular to the plates

Model:
- A K-shell photoelectron gets T0 = E - B_K (B_K(N) = 0.41 keV). The binding energy returns
  locally as an Auger electron (~0.38 keV, range << 1 mm) and is always deposited.
- Angular distribution: dipole, dN/du = 3/2 u^2 with u = cos(angle to the E-vector). That is
  beta = 2 for an s-shell; Sauter forward tilt is ignored at 5-30 keV.
- The electron travels a straight line of total length R_eff = k * R_CSDA(T0). k = 1 is an
  upper bound on reach. Real tracks in a low-Z gas wander, and k = 0.5 is illustrative only.
- Its energy along the track follows the CSDA: after path s the remaining energy T satisfies
  R(T) = R(T0) - s/k. If it reaches a plate (s = d/|u| < R_eff), the remaining energy T is lost.
- Average over u and over a Gaussian beam position across the gap.

Output: the fraction of deposited energy lost, i.e. the fraction by which the computed flux
would be UNDER-estimated if the loss were ignored. Inputs: NIST ESTAR CSDA ranges for N
(data/queries/nist_estar/estar_N_table.html).

Run: <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/wall_loss_bound.py
"""
import csv
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ESTAR = ROOT / "data" / "queries" / "nist_estar" / "estar_N_table.html"
OUT = ROOT / "analysis" / "out"
OUT.mkdir(exist_ok=True)

HALF_GAP_CM = 0.5
BEAM_FWHM_X_CM = 0.1
RHO = 99.0e3 * 28.0134 / (8.314462618 * 295.15) / 1e6   # g/cm3, 99 kPa, 22 C
B_K_KEV = 0.41


def load_estar():
    """Return (T_MeV, R_CSDA g/cm2) from the saved ESTAR table (7 columns per row)."""
    txt = re.sub(r"<[^>]+>", " ", ESTAR.read_text(encoding="latin-1"))
    nums = re.findall(r"\d\.\d{3}E[+-]\d\d", txt)
    vals = [float(x) for x in nums]
    rows = [vals[i:i + 7] for i in range(0, len(vals) - 6, 7)]
    T = np.array([r[0] for r in rows])
    R = np.array([r[4] for r in rows])
    ok = np.concatenate([[True], np.diff(T) > 0])   # keep a clean monotone grid
    T, R = T[ok], R[ok]
    assert np.all(np.diff(R) > 0), "ESTAR parse: range not monotone"
    return T, R


T_TAB, R_TAB = load_estar()


def r_csda_cm(t_kev):
    # ESTAR starts at 10 keV; below it, scale R ~ T^1.7 from the first point (adequate here:
    # such ranges are < 2.5 mm, half the gap, so they never reach a plate in this geometry)
    if t_kev < T_TAB[0] * 1e3:
        return R_TAB[0] * (t_kev / (T_TAB[0] * 1e3)) ** 1.7 / RHO
    return float(np.exp(np.interp(np.log(t_kev / 1e3), np.log(T_TAB), np.log(R_TAB)))) / RHO


def t_of_r_kev(r_cm):
    if r_cm <= 0:
        return 0.0
    g = r_cm * RHO
    return float(np.exp(np.interp(np.log(g), np.log(R_TAB), np.log(T_TAB)))) * 1e3


def lost_fraction(e_kev, k, n_u=2001, n_x=41):
    t0 = e_kev - B_K_KEV
    r0 = r_csda_cm(t0)              # CSDA path length
    reach = k * r0                  # straight-line reach
    sigma = BEAM_FWHM_X_CM / 2.3548
    xs = np.linspace(-3 * sigma, 3 * sigma, n_x)
    wx = np.exp(-0.5 * (xs / sigma) ** 2)
    wx /= wx.sum()
    us = np.linspace(-1, 1, n_u)
    wu = 1.5 * us ** 2
    wu /= wu.sum()
    loss = 0.0
    for x0, w0 in zip(xs, wx):
        for u, w in zip(us, wu):
            if u == 0:
                continue
            d = (HALF_GAP_CM - x0) if u > 0 else (HALF_GAP_CM + x0)
            s = d / abs(u)
            if s < reach:
                t_left = t_of_r_kev(r0 - s / k)
                loss += w0 * w * t_left
    return loss / e_kev, r0


def main():
    rows = []
    print(f"rho_N2 = {RHO:.5g} g/cm3, half-gap {HALF_GAP_CM*10:.1f} mm, beam FWHM_x {BEAM_FWHM_X_CM*10:.1f} mm")
    print("E_keV  R_CSDA_mm  loss_k1(upper)  loss_k0.5")
    for e in [8, 10, 12, 14, 15, 16, 17, 18, 20, 22, 25, 30]:
        f1, r0 = lost_fraction(e, 1.0)
        f5, _ = lost_fraction(e, 0.5)
        rows.append([e, f"{r0*10:.2f}", f"{f1:.4f}", f"{f5:.4f}"])
        print(f"{e:5d}  {r0*10:8.2f}  {f1:12.4f}  {f5:10.4f}")
    with (OUT / "wall_loss_bound.csv").open("w", newline="") as fh:
        fh.write("# fraction of deposited energy lost to the plates (flux under-estimate if ignored)\n")
        fh.write("# vertical plates, horizontal polarisation, 1 cm gap, 1 mm FWHM_x beam, 99 kPa 22 C, ESTAR CSDA\n")
        csv.writer(fh).writerows([["E_keV", "R_CSDA_mm", "loss_k1_upper", "loss_k0p5"]] + rows)


if __name__ == "__main__":
    main()
