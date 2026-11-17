"""Photoelectron wall loss vs photon energy, per chamber: band, live fit and every MC variant of that chamber.

Two columns (MonP, MonC); each has the signal-loss panel (top) and the correction-factor panel (bottom).
Everything plotted is the SIGNAL loss, the MC loss per photoabsorption times the photoelectric share f_pe of mu_en
(what the live slot's C holds). Density variants are drawn at E_eff (where the live band evaluates them).

Upstream (nothing retyped):
  analysis/wall_loss_families.py: families() (chamber settings, for the column titles)
  analysis/wall_loss_fit.py: family_files(lane), signal_points(), variant_label(), gated(), coverage(path, lane),
      N_SE, FIT_EMIN (the same functions as the fit gate, so the figure and the gate cannot disagree)
  calc/quality_slots.py: wall_loss_band(E_eff, lane), clcc(lane), WALL_FITS, e_eff(), RHO0
Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/fig_wall_loss.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402  (sets sys.path for calc/, analysis/ and the style)
from common import plt, save  # noqa: E402

import numpy as np  # noqa: E402
import quality_slots as qs  # noqa: E402
import wall_loss_fit as wf  # noqa: E402
import wall_loss_families as wfam  # noqa: E402

E_MIN, E_MAX = 8.0, 30.0   # plot range, keV
LANES = ("MonP", "MonC")
COLORS = {"range": "tab:orange", "sigma": "tab:green", "offset": "tab:purple", "rho": "tab:brown",
          "combined": "tab:red", "stress": "0.35", "other": "0.5"}
MARKS = {"range": "v", "sigma": "s", "offset": "D", "rho": "^", "combined": "P", "stress": "x", "other": "x"}


def lane_columns(lane, ax, ax2, fam):
    central, others = wf.family_files(lane)
    c0 = wf.signal_points(central)
    sel0 = (c0["E"] >= E_MIN) & (c0["E"] <= E_MAX)
    variants = [(p,) + wf.variant_label(p) + (wf.signal_points(p),) for p in others]
    eg = np.linspace(E_MIN, E_MAX, 441)
    lo, ce, hi = np.array([qs.wall_loss_band(qs.e_eff(e, qs.RHO0), lane) for e in eg]).T

    for p, lab, kind, d in variants:
        x = d["E_eff"] if kind == "rho" else d["E"]
        m = (x >= E_MIN) & (x <= E_MAX)
        mk = MARKS[kind] if kind != "range" else ("^" if "+" in lab else "v")
        ax.plot(x[m], d["target"][m], mk, ms=4.5, color=COLORS[kind], alpha=0.55, ls="none",
                label=(lab + " (not gated)") if kind == "stress" else lab + (" (at E_eff)" if kind == "rho" else ""))
    ax.fill_between(eg, lo, hi, color="tab:blue", alpha=0.18, label="band (bounds slot): low to high")
    ax.plot(eg, lo, color="tab:blue", lw=0.8, ls=":")
    ax.plot(eg, hi, color="tab:blue", lw=0.8, ls=":")
    ax.plot(eg, ce, color="tab:blue", lw=1.8, label="live fit (central)")
    ax.errorbar(c0["E"][sel0], c0["target"][sel0], yerr=c0["se"][sel0], fmt="o", color="k", ms=4, capsize=2, lw=1,
                label="central MC signal loss = f_pe x MC (1 sigma stat.)", zorder=5)
    ax.set_ylabel("signal fraction lost to plates, Lw (dimensionless)", fontsize=9)
    ax.set_title(f"{lane}: {fam['note']}\nhalf gap {fam['half_gap_mm']:g} mm, beam FWHM {fam['fwhm_mm']:g} mm, "
                 f"offset {fam['offset_mm']:g} mm; rho0 = {qs.RHO0:.4e} g/cm3", fontsize=8.5)
    ax.legend(fontsize=6.5, loc="upper left")

    # coverage of the lane's live band, gated points only
    pts = [("central", r) for r in wf.coverage(central, lane)]
    pts += [(lab, r) for p, lab, kind, d in variants if wf.gated(p) for r in wf.coverage(p, lane)]
    n_tot = len(pts)
    outside = [(lab, r) for lab, r in pts if not r[4]]
    sel_fit = c0["E"] >= wf.FIT_EMIN
    fit_c = np.array([qs.wall_loss_band(x, lane)[1] for x in c0["E_eff"][sel_fit]])
    max_dev = float(np.max(np.abs(fit_c - c0["target"][sel_fit])))
    txt = (f"fit: {qs.clcc(lane)}\n"
           f"Band vs MC (E >= {wf.FIT_EMIN:g} keV, gated points only): {n_tot - len(outside)}/{n_tot} inside,\n"
           f"within {wf.N_SE:g} MC standard errors. Stress cases not gated.\n"
           f"Max |fit - central| over E >= {wf.FIT_EMIN:g} keV = {max_dev:.3f}")
    if outside:
        txt += "\nOUTSIDE band: " + "; ".join(f"{l} @ {r[0]:g} keV ({r[1]:.3f})" for l, r in outside[:4])
    ax.text(0.02, 0.50, txt, transform=ax.transAxes, ha="left", va="top", fontsize=6.5,
            bbox=dict(fc="w", ec="0.7", alpha=0.9))

    corr = lambda x: 1.0 / (1.0 - x)   # noqa: E731
    y0, s0 = c0["target"][sel0], c0["se"][sel0]
    ax2.fill_between(eg, corr(lo), corr(hi), color="tab:blue", alpha=0.18, label="band: 1/(1 - Lw) at low and high Lw")
    ax2.plot(eg, corr(ce), color="tab:blue", lw=1.8, label="live fit: 1/(1 - Lw)")
    ax2.errorbar(c0["E"][sel0], corr(y0), yerr=[corr(y0) - corr(y0 - s0), corr(y0 + s0) - corr(y0)],
                 fmt="o", color="k", ms=4, capsize=2, lw=1, label="central MC (1 sigma stat.)")
    ax2.axhline(1, color="0.5", lw=0.8)
    c30 = qs.wall_loss_band(qs.e_eff(E_MAX, qs.RHO0), lane)
    i30 = int(np.argmin(np.abs(c0["E"] - E_MAX)))
    mc30 = corr(c0["target"][i30])
    ax2.annotate(f"{E_MAX:g} keV: fit x{corr(c30[1]):.3f} (band x{corr(c30[0]):.3f} to x{corr(c30[2]):.3f})\n"
                 f"central MC x{mc30:.3f}",
                 xy=(E_MAX, corr(c30[1])), xytext=(-40, 30), textcoords="offset points", ha="right", fontsize=7.5,
                 arrowprops=dict(arrowstyle="-", color="0.4"))
    ax2.set_ylabel("correction factor 1/(1 - Lw) (dimensionless)", fontsize=9)
    ax2.set_xlabel("photon energy E (keV)")
    ax2.legend(fontsize=7, loc="upper left")
    ax2.text(0.99, 0.04, "Wall-loss term only; the collection-length and other\nterms of the bounds slot are NOT in this panel.",
             transform=ax2.transAxes, ha="right", va="bottom", fontsize=6.5)
    ax2.set_xlim(E_MIN, E_MAX)


def main(outdir=common.OUT):
    fams = wfam.families()
    fig, axs = plt.subplots(2, 2, figsize=(14, 10), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})
    for j, lane in enumerate(LANES):
        lane_columns(lane, axs[0, j], axs[1, j], fams[lane])
    axs[0, 0].set_xlim(E_MIN, E_MAX)
    fig.suptitle("Photoelectron wall loss (signal) per chamber: live band and fit vs the chamber's own MC variants. "
                 f"f_pe = photoelectric share of mu_en (xraydb); band evaluated at rho0 = {qs.RHO0:.4e} g/cm3", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return save(fig, "wall_loss", ["analysis/wall_loss_fit.py (family_files, signal_points, coverage, variant_label)",
                                   "analysis/wall_loss_families.py (families)",
                                   "analysis/out/wall_loss/<lane>/*.csv",
                                   "data/queries/out/xraydb_N.csv (f_pe)",
                                   "calc/quality_slots.py wall_loss_band(), clcc(), e_eff(), RHO0"], outdir)


if __name__ == "__main__":
    print(main())
