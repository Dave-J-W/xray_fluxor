"""Photons/s per net scaler Hz vs energy: formula P, RESULT L and its low/high bounds, at the site mean, for BOTH lanes.

Upstream (nothing retyped):
  calc/monp_transform.py: full_physics() (independent NIST formula), M_OVER_R, L_CM
  calc/quality_slots.py:  bounds(P, E, rho, lane)   (L = RESULT, D = low, E = high, F/G = +%/-% of L),
                          SYMMETRIC_TERMS, OTHER_TERMS, HIGH_FACTOR, LOW_FACTOR, WALL_FITS
  data/queries/crosscheck_calculators.py: SITE_P_KPA, SITE_T_C
Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/fig_flux_bounds.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402
from common import plt, save  # noqa: E402

import numpy as np  # noqa: E402
import monp_transform as mt  # noqa: E402
import quality_slots as qs  # noqa: E402
from crosscheck_calculators import SITE_P_KPA, SITE_T_C  # noqa: E402

E_MIN, E_MAX = 5.0, 30.0
SENS_A_PER_V = 5e-7          # SR570 500 nA/V: the EXAMPLE setting, not a measured one
MARK_KEV = (10.0, 30.0)      # cosmetic marks requested
LANES = ("MonP", "MonC")
COLOR = {"MonP": "tab:blue", "MonC": "tab:red"}


def compute(lane):
    rho = SITE_P_KPA * mt.M_OVER_R / (SITE_T_C + 273.15)       # g/cm3, ideal-gas N2 (same as the live calc)
    es = np.linspace(E_MIN, E_MAX, 251)
    P = np.array([mt.full_physics(1.0, SENS_A_PER_V, e, SITE_T_C, SITE_P_KPA) for e in es])
    B = [qs.bounds(p, e, rho, lane=lane) for p, e in zip(P, es)]
    g = lambda k: np.array([b[k] for b in B])   # noqa: E731
    return rho, es, P, g("L"), g("D"), g("E"), g("F"), g("G"), g("C")


def main(outdir=common.OUT):
    fig, axs = plt.subplots(2, 2, figsize=(15, 8.8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    for j, lane in enumerate(LANES):
        rho, es, P, L, D, Eh, F, G, C = compute(lane)
        ax, ax2 = axs[0, j], axs[1, j]
        c = COLOR[lane]
        ax.fill_between(es, D, Eh, color=c, alpha=0.18, label="stated low to high bound")
        ax.plot(es, Eh, color=c, lw=0.9, ls=":", label="high bound")
        ax.plot(es, D, color=c, lw=0.9, ls="--", label="low bound")
        ax.plot(es, L, color=c, lw=2, label="RESULT L = P/(1 - Lw)  (wall-loss corrected)")
        ax.plot(es, P, color="k", lw=1.5, label="formula P (NIST mu_en, mu; no wall-loss correction)")
        ax.set_yscale("log")
        ax.set_title(f"{lane}  (wall-loss fit {qs.WALL_FITS[lane]})", fontsize=10, fontweight="bold", color=c)
        ax2.fill_between(es, -G, F, color=c, alpha=0.18)
        ax2.plot(es, F, color=c, ls=":", lw=1.5, label="high bound, + % of RESULT")
        ax2.plot(es, -G, color=c, ls="--", lw=1.5, label="low bound, - % of RESULT")
        ax2.axhline(0, color="0.4", lw=0.8)
        ax2.set_xlabel("photon energy E (keV)")
        ax2.set_xlim(E_MIN, E_MAX)
        lines = []
        for em in MARK_KEV:
            i = int(np.argmin(np.abs(es - em)))
            for a in (ax, ax2):
                a.axvline(em, color="0.5", lw=0.8, ls="-.")
            lines.append(f"{em:g} keV: P = {P[i]:.4g}, RESULT = {L[i]:.4g} (x{L[i] / P[i]:.3f}), low = {D[i]:.4g}, "
                         f"high = {Eh[i]:.4g};  +{F[i]:.1f} % / -{G[i]:.1f} %")
            ax2.text(em, ax2.get_ylim()[0], f" {em:g} keV", fontsize=8, va="bottom", ha="left")
        ax.text(0.99, 0.02, "ph/s per Hz:\n" + "\n".join(lines), transform=ax.transAxes, fontsize=7, va="bottom", ha="right",
                bbox=dict(fc="w", ec="0.7", alpha=0.9))
        ax.legend(fontsize=7.5, loc="upper left")
        ax2.legend(fontsize=8, loc="upper left")
    axs[0, 1].sharey(axs[0, 0])
    axs[1, 1].sharey(axs[1, 0])
    axs[0, 0].set_ylabel("photons/s per net scaler Hz  (ph s$^{-1}$ Hz$^{-1}$)")
    axs[1, 0].set_ylabel("bound relative to RESULT L  (%)")
    sym = ", ".join(f"{k} {100 * v:.1f}" for k, v in qs.SYMMETRIC_TERMS.items())
    fig.suptitle("MonP and MonC flux per net scaler Hz and its stated bounds, at the site mean\n"
                 f"SR570 {SENS_A_PER_V * 1e9:g} nA/V (example setting), V2F 1e5 Hz/V; N2 {SITE_P_KPA:g} kPa, "
                 f"{SITE_T_C:g} C (rho = {rho:.4e} g/cm3); collection length l = L_CM = {mt.L_CM:g} cm (the modelled l_eff)",
                 fontsize=10.5)
    fig.tight_layout(rect=(0, 0.09, 1, 0.94))
    fig.text(0.5, 0.075,
             f"Bounds = symmetric terms in quadrature, sigma_s = {100 * qs.OTHER_TERMS:.2f} % (HIGH_FACTOR {qs.HIGH_FACTOR}, "
             f"LOW_FACTOR {qs.LOW_FACTOR}), plus the wall-loss band. Each lane has its own wall-loss fit (WALL_FITS); the formula P is the same for both.\n"
             f"The collection length is one of the SYMMETRIC_TERMS (collection length (guarded) = "
             f"{100 * qs.SYMMETRIC_TERMS['collection length (guarded)']:.1f} %); no one-sided allowance remains.\n"
             f"SYMMETRIC_TERMS (%): {sym}.",
             ha="center", va="top", fontsize=7.5)
    return save(fig, "flux_bounds", ["calc/monp_transform.py full_physics(), L_CM",
                                     "calc/quality_slots.py bounds(lane=), SYMMETRIC_TERMS, WALL_FITS",
                                     "data/queries/crosscheck_calculators.py SITE_P_KPA, SITE_T_C"], outdir)


if __name__ == "__main__":
    print(main())
