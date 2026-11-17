"""Monte Carlo of photoelectron energy lost to the collection plates in a CMC-custom ion chamber.

Geometry. The defaults below are the first, provisional chamber (user 2026-11-12): vertical plates at
x = ±5 mm (1 cm gap), beam 1 mm FWHM in x, E-vector toward the plates, N2 at 99.26 kPa and 24.9 °C. The lane
runs do NOT use these defaults: `wall_loss_families.py` passes each lane's measured gap, beam offset, beam
width and plate orientation from `cmc_chamber_geometry.py` (--half-gap-mm, --offset-mm, --beam-fwhm-mm,
--plates-parallel-to-e). Plates are taken as at least 6 cm wide and long, so only x matters.
- The --range-scale variants rescale the half gap only (HALF_GAP = BASE_HALF_GAP / range_scale), not the beam
  offset or width. That is equivalent to scaling the offset and width by range_scale as well; for MonC's
  0.525 mm offset the effect is negligible and slightly conservative, and for a centred beam it is none
  (METHOD_REVIEW Q5).

Physics (single-scattering condensed MC, standard for keV electrons in low-Z gas):
- Photoelectron: N K-shell, T0 = E − 0.41 keV. The 0.41 keV goes to an Auger electron that
  deposits locally. The direction follows the Sauter (nonrelativistic, with retardation)
  distribution:
      dσ/dΩ ∝ sin²θ cos²φ / (1 − β cosθ)^4   (θ from the beam, φ from the E-vector)
- Elastic scattering: screened Rutherford (Wentzel) with the Molière screening parameter
      η = 1.7e-5 Z^(2/3) / (τ(τ+2)) · (1.13 + 3.76 (αZ/β)²)
      σ = π Z(Z+1) (e²)² / (pv)² / (η(1+η))         per N atom
  Exponential free paths. Polar angle sampled as cosθ = 1 − 2ηξ/(1 − ξ + η).
- Energy loss: continuous slowing down along the path, from the NIST ESTAR CSDA range of
  nitrogen (data/queries/nist_estar/). Below 10 keV, where ESTAR's table starts, R ∝ T^1.764,
  which matches the 10–20 keV slope.
- An electron reaching |x| = 5 mm loses its remaining kinetic energy to the plate. Backscatter
  from the plate is ignored, so the loss is slightly overestimated (conservative).
- Below the 0.5 keV cutoff (range ~10 µm) the electron deposits locally.

Validation (--validate): normal-incidence pencil beams in N2, compared with Grün's (1957)
measured universal depth–dose curve for electrons in air (5–54 keV):
    λ(ξ) = 0.74 + 4.7ξ − 8.9ξ² + 3.5ξ³,   ξ = depth / R_G,   R_G = 4.57e-6 · E[keV]^1.75 g/cm²

Run:
  <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/wall_loss_mc.py --validate
  <bluesky venv>\\Scripts\\python.exe -I -X utf8 analysis/wall_loss_mc.py
"""
import argparse
import csv
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ESTAR = ROOT / "data" / "queries" / "nist_estar" / "estar_N_table.html"
OUT = ROOT / "analysis" / "out"
OUT.mkdir(exist_ok=True)

MC2 = 0.51099895          # MeV
E2 = 1.43996e-13          # e² in MeV·cm
ALPHA = 1 / 137.035999
Z = 7
RHO = 99.26e3 * 28.0134 / (8.314462618 * (24.9 + 273.15)) / 1e6        # g/cm3
N_ATOMS = 2 * RHO * 6.02214076e23 / 28.0134                              # N atoms / cm3
HALF_GAP = 0.5            # cm (the half gap used in a run: BASE_HALF_GAP / range scale)
BASE_HALF_GAP = 0.5       # cm, the chamber's half gap before any range-scale variant (--half-gap-mm)
OUT_PATH = None           # explicit output CSV (--out); default: analysis/out/wall_loss_mc<tag>.csv
BEAM_SIGMA_X = 0.1 / 2.3548
T_CUT = 0.5e-3            # MeV
B_K = 0.41e-3             # MeV


def load_estar():
    txt = re.sub(r"<[^>]+>", " ", ESTAR.read_text(encoding="latin-1"))
    vals = [float(x) for x in re.findall(r"\d\.\d{3}E[+-]\d\d", txt)]
    rows = [vals[i:i + 7] for i in range(0, len(vals) - 6, 7)]
    T = np.array([r[0] for r in rows])
    R = np.array([r[4] for r in rows])
    keep = np.concatenate([[True], np.diff(T) > 0])
    return T[keep], R[keep]


T_TAB, R_TAB = load_estar()
EXP_LOW = math.log(R_TAB[1] / R_TAB[0]) / math.log(T_TAB[1] / T_TAB[0]) if False else 1.764


def range_gcm2(T):
    T = np.asarray(T, float)
    lo = T < T_TAB[0]
    out = np.empty_like(T)
    out[~lo] = np.exp(np.interp(np.log(T[~lo]), np.log(T_TAB), np.log(R_TAB)))
    out[lo] = R_TAB[0] * (T[lo] / T_TAB[0]) ** EXP_LOW
    return out


def energy_from_range(R):
    R = np.asarray(R, float)
    out = np.empty_like(R)
    lo = R < R_TAB[0]
    out[~lo] = np.exp(np.interp(np.log(R[~lo]), np.log(R_TAB), np.log(T_TAB)))
    out[lo] = T_TAB[0] * (np.clip(R[lo], 1e-30, None) / R_TAB[0]) ** (1 / EXP_LOW)
    return out


SIGMA_SCALE = 1.0          # sensitivity knobs (set from the command line)
OFFSET_X = 0.0             # cm, beam offset from mid-gap
E_PARALLEL = False         # True: plates parallel to the E-vector (MonC, horizontal plates); x stays the plate normal


def elastic(T):
    """Mean free path (cm) and screening η for kinetic energy T (MeV)."""
    tau = T / MC2
    beta2 = tau * (tau + 2) / (tau + 1) ** 2
    pv = T * (T + 2 * MC2) / (T + MC2)
    eta = 1.7e-5 * Z ** (2 / 3) / (tau * (tau + 2)) * (1.13 + 3.76 * (ALPHA * Z) ** 2 / beta2)
    sigma = math.pi * Z * (Z + 1) * E2 ** 2 / pv ** 2 / (eta * (1 + eta))
    return 1.0 / (N_ATOMS * sigma * SIGMA_SCALE), eta


def rotate(u, v, w, cost, phi):
    sint = np.sqrt(np.clip(1 - cost ** 2, 0, None))
    cp, sp = np.cos(phi), np.sin(phi)
    small = np.abs(w) > 0.99999
    den = np.sqrt(np.clip(1 - w ** 2, 1e-30, None))
    un = np.where(small, sint * cp, u * cost + sint * (u * w * cp - v * sp) / den)
    vn = np.where(small, sint * sp, v * cost + sint * (v * w * cp + u * sp) / den)
    wn = np.where(small, np.sign(w) * cost, w * cost - sint * cp * den)
    nrm = np.sqrt(un ** 2 + vn ** 2 + wn ** 2)
    return un / nrm, vn / nrm, wn / nrm


def transport(T0, x0, u, v, w, rng, plates=True, depth_bins=None):
    """Transport electrons. Return the fraction of T0 lost to the plates, and an optional depth-dose histogram along x."""
    n = len(T0)
    T = T0.copy()
    x = x0.copy()
    alive = np.ones(n, bool)
    lost = np.zeros(n)
    hist = np.zeros(len(depth_bins) - 1) if depth_bins is not None else None
    while alive.any():
        idx = np.nonzero(alive)[0]
        Ti = T[idx]
        lam, eta = elastic(Ti)
        s = -lam * np.log(rng.random(len(idx)))
        R0 = range_gcm2(Ti) / RHO                       # cm
        Rcut = range_gcm2(np.full(len(idx), T_CUT)) / RHO
        smax = R0 - Rcut
        last = s >= smax
        s = np.minimum(s, smax)
        xn = x[idx] + u[idx] * s
        if plates:
            hit = np.abs(xn) >= HALF_GAP
            if hit.any():
                sb = (np.sign(u[idx][hit]) * HALF_GAP - x[idx][hit]) / u[idx][hit]
                Tb = energy_from_range((R0[hit] - sb) * RHO)
                lost[idx[hit]] = Tb
                alive[idx[hit]] = False
        else:
            hit = np.zeros(len(idx), bool)
        Tn = np.where(last, 0.0, energy_from_range(np.clip(R0 - s, 1e-12, None) * RHO))
        if hist is not None:     # deposit the energy lost on this step at the step midpoint
            dep = np.where(last, Ti, Ti - Tn)[~hit]
            mid = (x[idx] + 0.5 * u[idx] * s)[~hit]
            hist += np.histogram(mid, bins=depth_bins, weights=dep)[0]
        go = ~hit & ~last
        gi = idx[go]
        x[gi] = xn[go]
        T[gi] = Tn[go]
        done = idx[~hit & last]
        alive[done] = False
        if len(gi):
            _, eta_n = elastic(T[gi])
            xi = rng.random(len(gi))
            cost = 1 - 2 * eta_n * xi / (1 - xi + eta_n)
            phi = 2 * np.pi * rng.random(len(gi))
            u[gi], v[gi], w[gi] = rotate(u[gi], v[gi], w[gi], cost, phi)
    return lost / T0, hist


def sauter_dirs(T, n, rng):
    """Directions from dσ/dΩ ∝ sin²θ cos²φ/(1-β cosθ)^4, by rejection (θ from z, φ from x)."""
    tau = T / MC2
    beta = math.sqrt(tau * (tau + 2)) / (tau + 1)
    ct = np.linspace(-1, 1, 20001)
    fmax = np.max((1 - ct ** 2) / (1 - beta * ct) ** 4)
    out = []
    while sum(len(o[0]) for o in out) < n:
        m = 4 * n
        ct = 2 * rng.random(m) - 1
        ph = 2 * np.pi * rng.random(m)
        f = (1 - ct ** 2) * np.cos(ph) ** 2 / (1 - beta * ct) ** 4
        acc = rng.random(m) * fmax < f
        st = np.sqrt(1 - ct[acc] ** 2)
        out.append((st * np.cos(ph[acc]), st * np.sin(ph[acc]), ct[acc]))
    u = np.concatenate([o[0] for o in out])[:n]
    v = np.concatenate([o[1] for o in out])[:n]
    w = np.concatenate([o[2] for o in out])[:n]
    return u, v, w


def validate(rng, n=4000):
    print("Validation against Grün (1957), electrons in air, normal incidence, depth-dose λ(z/R_G):")
    rows = []
    for E in (10, 20, 30):
        T0 = np.full(n, E * 1e-3)
        RG = 4.57e-6 * E ** 1.75 / RHO                       # cm
        bins = np.linspace(-0.5 * RG, 1.5 * RG, 81)
        _, h = transport(T0, np.zeros(n), np.ones(n), np.zeros(n), np.zeros(n), rng, plates=False, depth_bins=bins)
        xi = 0.5 * (bins[1:] + bins[:-1]) / RG
        lam_mc = h / (n * E * 1e-3) / np.diff(bins / RG)
        lam_g = np.clip(0.74 + 4.7 * xi - 8.9 * xi ** 2 + 3.5 * xi ** 3, 0, None)
        lam_g[(xi < 0) | (xi > 1.1)] = 0
        pk_mc, pk_g = xi[np.argmax(lam_mc)], xi[np.argmax(lam_g)]
        frac_back = h[xi < 0].sum() / (n * E * 1e-3)
        # depth containing 90 % of deposited energy
        c = np.cumsum(h) / h.sum()
        x90 = xi[np.searchsorted(c, 0.9)]
        cg = np.cumsum(lam_g) / lam_g.sum()
        x90g = xi[np.searchsorted(cg, 0.9)]
        print(f"  {E:2d} keV: R_G {RG*10:.2f} mm (CSDA {range_gcm2([E*1e-3])[0]/RHO*10:.2f} mm); "
              f"peak at z/R_G {pk_mc:.2f} (Grün {pk_g:.2f}); 90 % depth {x90:.2f} (Grün {x90g:.2f}); "
              f"energy deposited behind the entrance plane {100*frac_back:.1f} %")
        rows.append([E, f"{RG*10:.3f}", f"{pk_mc:.3f}", f"{pk_g:.3f}", f"{x90:.3f}", f"{x90g:.3f}", f"{frac_back:.4f}"])
    with (OUT / "wall_loss_mc_validation.csv").open("w", newline="") as f:
        f.write("# MC depth-dose vs Grun 1957 universal curve (air); normal-incidence pencil beam in N2 at rho0 = 1.1221e-3 g/cm3 (99.26 kPa, 24.9 C)\n")
        csv.writer(f).writerows([["E_keV", "R_G_mm", "peak_mc", "peak_grun", "x90_mc", "x90_grun", "frac_behind_entrance"]] + rows)


def wall_loss(rng, n=20000):
    print(f"Wall loss, {'horizontal plates, E-vector along them' if E_PARALLEL else 'vertical plates, E-vector toward them'}, "
          f"half gap {HALF_GAP*10:.3f} mm, beam {BEAM_SIGMA_X*10*2.3548:.3g} mm FWHM across the gap, offset {OFFSET_X*10:.2f} mm:")
    rows = []
    # 18.5-21 keV added 2026-11-13 (METHOD_REVIEW Q1): the onset of the 10.85 mm fits lies between 18 and 20 keV
    for E in (8, 10, 12, 13, 14, 15, 16, 17, 18, 18.5, 19, 19.5, 20, 21, 22, 25, 28, 30):
        T = (E - 0.41) * 1e-3
        u, v, w = sauter_dirs(T, n, rng)              # u is along the E-vector
        if E_PARALLEL:
            u, v = v, u                               # plate normal perpendicular to E and to the beam
        x0 = rng.normal(OFFSET_X, BEAM_SIGMA_X, n)
        frac, _ = transport(np.full(n, T), x0, u, v, w, rng)
        loss = frac.mean() * T / (E * 1e-3)              # fraction of the photon energy deposited
        se = frac.std() / math.sqrt(n) * T / (E * 1e-3)
        hitf = (frac > 0).mean()
        print(f"  {E:4g} keV: signal lost {100*loss:6.2f} % ± {100*se:.2f} (stat), electrons reaching a plate {100*hitf:5.1f} %")
        rows.append([E, f"{loss:.5f}", f"{se:.5f}", f"{hitf:.4f}"])
    dens = RHO / (99.26e3 * 28.0134 / (8.314462618 * (24.9 + 273.15)) / 1e6)
    fwhm_mm = BEAM_SIGMA_X * 2.3548 * 10
    default = (HALF_GAP == 0.5 and SIGMA_SCALE == 1.0 and OFFSET_X == 0.0 and abs(dens - 1) < 1e-9
               and not E_PARALLEL and abs(fwhm_mm - 1.0) < 1e-9)
    tag = "" if default else f"_gap{HALF_GAP*20:.2f}mm_sig{SIGMA_SCALE:.2f}_off{OFFSET_X*10:.{1 if abs(OFFSET_X*100 - round(OFFSET_X*100)) < 1e-9 else 2}f}mm_rho{dens:.3f}"
    if E_PARALLEL or abs(fwhm_mm - 1.0) > 1e-9:
        tag += f"_{'Epar' if E_PARALLEL else 'Enorm'}_fwhm{fwhm_mm:.3f}mm"
    path = Path(OUT_PATH) if OUT_PATH else OUT / f"wall_loss_mc{tag}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        f.write("# Monte Carlo signal fraction lost to the plates (photoelectron energy carried into the plates / photon energy)\n")
        f.write(f"# CMC-custom geometry (PROVISIONAL): {'horizontal plates (MonC)' if E_PARALLEL else 'vertical plates (MonP)'}, half gap {HALF_GAP*10:.3f} mm "
                f"(electron reach x{BASE_HALF_GAP/HALF_GAP:.2f} relative to the {BASE_HALF_GAP*10:g} mm half gap), horizontal polarization, "
                f"{fwhm_mm:g} mm FWHM beam (across the gap) offset {OFFSET_X*10:.2f} mm, elastic sigma x{SIGMA_SCALE:.2f}, "
                f"E-vector {'PARALLEL to the plates (MonC)' if E_PARALLEL else 'toward the plates (MonP)'}; "
                f"N2 density {RHO:.5e} g/cm3 = x{dens:.3f} of 99.26 kPa, 24.9 C (the MC reference rho0)\n")
        csv.writer(f).writerows([["E_keV", "loss_frac", "stat_err", "frac_electrons_hitting"]] + rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--range-scale", type=float, default=1.0,
                    help="electron reach x this factor (implemented as half-gap / factor)")
    ap.add_argument("--sigma-scale", type=float, default=1.0, help="elastic cross section x this factor")
    ap.add_argument("--offset-mm", type=float, default=0.0, help="beam offset from mid-gap toward a plate")
    ap.add_argument("--density-scale", type=float, default=1.0, help="N2 density x this factor (weather test)")
    ap.add_argument("--plates-parallel-to-e", action="store_true",
                    help="MonC orientation: horizontal plates, horizontal E-vector (default: MonP, E toward the plates)")
    ap.add_argument("--half-gap-mm", type=float, default=5.0, help="the chamber's half gap (inner face to mid-gap)")
    ap.add_argument("--out", default=None, help="output CSV path (default: analysis/out/wall_loss_mc<tag>.csv)")
    ap.add_argument("--beam-fwhm-mm", type=float, default=1.0,
                    help="beam FWHM across the gap (MonP: horizontal ~1 mm; MonC: vertical 0.02-0.04 mm)")
    a = ap.parse_args()
    BASE_HALF_GAP = a.half_gap_mm / 10
    HALF_GAP = BASE_HALF_GAP / a.range_scale
    OUT_PATH = a.out
    SIGMA_SCALE = a.sigma_scale
    OFFSET_X = a.offset_mm / 10
    E_PARALLEL = a.plates_parallel_to_e
    BEAM_SIGMA_X = a.beam_fwhm_mm / 10 / 2.3548
    RHO = RHO * a.density_scale
    N_ATOMS = N_ATOMS * a.density_scale
    rng = np.random.default_rng(a.seed)
    if a.validate:
        validate(rng)
    else:
        wall_loss(rng)
