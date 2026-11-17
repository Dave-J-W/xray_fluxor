"""Collection-length term: the guarded chamber as measured (delta = l_eff / l_calc - 1) and the live symmetric term.

Upstream:
  analysis/out/collection_length_cmc.csv  (case, l_eff_mm, delta_pct, what; from analysis/collection_length_cmc.py)
  analysis/out/fringe_field_scan.csv      (old unguarded scan; leff_over_L_minus_1_pct, relative to the old 6.0 cm plate length)
  analysis/cmc_chamber_geometry.py        derived()["collector_l_eff_guard_rule"] (textbook guard rule, mm)
  calc/quality_slots.py                    SYMMETRIC_TERMS["collection length (guarded)"], collection_term(),
                                           COLLECTION_GROUPS, COLLECTION_MODEL_2D
  calc/monp_transform.py                  L_CM (collection length l the calc uses, cm)
Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/fig_leff_scan.py
"""
import csv
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402
from common import ROOT, plt, save  # noqa: E402

import numpy as np  # noqa: E402
import quality_slots as qs  # noqa: E402
import monp_transform as mt  # noqa: E402
import cmc_chamber_geometry as geo  # noqa: E402

NOMINAL = "nominal"
ALT = "guard_flush"   # no recess: contradicts the measured 0.51 mm; comparison case, not a tolerance
TERM_KEY = "collection length (guarded)"
OLD_L_MM = 60.0       # plate length of the old unguarded scan (its CSV header: L = 6 cm)


def read_csv(name):
    with open(ROOT / "analysis" / "out" / name, newline="") as f:
        return list(csv.DictReader(r for r in f if not r.startswith("#")))


def main(outdir=common.OUT):
    rows = read_csv("collection_length_cmc.csv")
    scan = read_csv("fringe_field_scan.csv")
    l_mm = mt.L_CM * 10.0
    live = 100.0 * qs.SYMMETRIC_TERMS[TERM_KEY]
    calc_term = 100.0 * qs.collection_term()
    rule_mm = geo.derived()["collector_l_eff_guard_rule"]
    rule_d = 100.0 * (rule_mm / l_mm - 1.0)
    by = {r["case"]: r for r in rows}
    d_nom = float(by[NOMINAL]["delta_pct"])
    d_nom_chk = 100.0 * (float(by[NOMINAL]["l_eff_mm"]) / l_mm - 1.0)   # cross-check of the CSV column
    scan_d = np.array([float(r["leff_over_L_minus_1_pct"]) for r in scan])
    # per-group contributions: largest |delta - nominal| in each group (same rule as qs.collection_term)
    groups = [(name, max(abs(float(by[c]["delta_pct"]) - d_nom) for c in cases))
              for name, cases in qs.COLLECTION_GROUPS.items()]
    model2d = 100.0 * qs.COLLECTION_MODEL_2D
    quad = math.sqrt(sum(v * v for _, v in groups) + model2d ** 2)

    fig = plt.figure(figsize=(14, 8.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[2.0, 1.0], height_ratios=[3.2, 1.0], wspace=0.55, hspace=0.45,
                          left=0.27, right=0.97, top=0.88, bottom=0.19)
    ax = fig.add_subplot(gs[0, 0])
    axo = fig.add_subplot(gs[1, 0])
    axg = fig.add_subplot(gs[:, 1])

    # --- main panel: cases relative to the calc's l
    ax.axvspan(-live, live, color="tab:blue", alpha=0.10, zorder=0)
    ax.axvline(0, color="0.3", lw=0.8)
    ax.axvline(d_nom, color="tab:blue", lw=1.0, ls="--", zorder=1)
    for s in (-1, 1):
        ax.axvline(s * calc_term, color="tab:purple", lw=1.2, ls="-.", zorder=1)
    order = list(reversed(rows))
    n = len(order)
    for i, r in enumerate(order):
        d = float(r["delta_pct"])
        is_nom, is_alt = r["case"] == NOMINAL, r["case"] == ALT
        if is_alt:
            ax.barh(i, d, height=0.6, facecolor="white", edgecolor="tab:orange", hatch="///", lw=1.2, zorder=3)
        else:
            ax.barh(i, d, height=0.6, color="tab:blue" if is_nom else "0.65", zorder=3)
        ax.text(d + (0.06 if d >= 0 else -0.06), i, f"{d:+.2f} %", va="center", ha="left" if d >= 0 else "right",
                fontsize=8, fontweight="bold" if is_nom else None)
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r['case']}: {r['what']}" if r["case"] != ALT else
                        f"{r['case']}: no recess (comparison only, not a tolerance)" for r in order], fontsize=8)
    for t, r in zip(ax.get_yticklabels(), order):
        if r["case"] == NOMINAL:
            t.set_fontweight("bold")
        if r["case"] == ALT:
            t.set_color("tab:orange")
    ax.set_ylim(-0.7, n + 2.0)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(fc="tab:blue", alpha=0.15, label=f"live term +-{live:.1f} % (SYMMETRIC_TERMS)"),
                       Line2D([], [], color="tab:purple", ls="-.", label=f"collection_term() +-{calc_term:.2f} %"),
                       Line2D([], [], color="tab:green", ls=":", label=f"textbook guard rule {rule_mm:.1f} mm: {rule_d:+.2f} %")],
              fontsize=7.5, loc="upper left", frameon=True)
    ax.axvline(rule_d, color="tab:green", lw=1.2, ls=":", zorder=1)
    ax.set_xlabel("delta = l_eff / l - 1  (%)\n[l = calc collection length; flux = formula / (1 + delta)]", fontsize=9)
    ax.set_title("Guarded chamber as measured: each case relative to the calc's collection length l", fontsize=10)
    ax.grid(axis="y", alpha=0)

    # --- old unguarded scan, dimmed, same axis
    lo, hi = scan_d.min(), scan_d.max()
    axo.axvspan(-live, live, color="tab:blue", alpha=0.06, zorder=0)
    axo.axvline(0, color="0.3", lw=0.8)
    axo.barh(0, hi - lo, left=lo, height=0.5, color="0.85", edgecolor="0.7", zorder=2)
    axo.plot(scan_d, np.zeros_like(scan_d), "|", color="0.6", ms=10, zorder=3)
    axo.text(0.01, 0.97, "Before the chamber was measured (no guards): dimmed context. delta relative to the OLD "
             f"{OLD_L_MM / 10:g} cm plate length,\n{len(scan_d)} scan points, {lo:+.1f} to {hi:+.1f} %. "
             f"NOTE: own x range (old spread is ~{(hi - lo) / (2 * live):.0f}x the live band)",
             transform=axo.transAxes, fontsize=7.5, color="0.45", va="top")
    axo.set_yticks([])
    axo.set_ylim(-0.6, 1.3)
    axo.set_xlabel("delta relative to the old 6.0 cm length (%)\n[same quantity; wider range than the panel above]", fontsize=9)
    axo.grid(axis="y", alpha=0)
    axo.set_xlim(min(lo, -live) - 1.5, max(hi, live) + 1.5)
    lim = max(abs(float(r["delta_pct"])) for r in rows) * 1.5
    ax.set_xlim(-max(lim, calc_term * 1.3), max(lim, calc_term * 1.3))

    # --- per-group contributions
    names = [g for g, _ in groups] + ["2-D model allowance"]
    vals = [v for _, v in groups] + [model2d]
    yy = np.arange(len(vals))[::-1]
    axg.barh(yy, vals, height=0.6, color=["tab:purple"] * len(groups) + ["0.6"], zorder=3)
    for y, v in zip(yy, vals):
        axg.text(v + 0.02, y, f"{v:.2f} %", va="center", fontsize=8)
    axg.axvline(calc_term, color="tab:purple", lw=1.2, ls="-.")
    axg.axvline(live, color="tab:blue", lw=1.2, ls="--")
    axg.set_yticks(yy)
    axg.set_yticklabels(names, fontsize=8)
    axg.set_xlim(0, max(max(vals), live, calc_term) * 1.35)
    axg.set_ylim(-0.6, len(vals) + 1.4)
    axg.text(calc_term, len(vals) - 0.1, f"collection_term() = {calc_term:.2f} %\n(quadrature of these bars)",
             color="tab:purple", fontsize=7.5, ha="right", va="bottom")
    axg.text(live, len(vals) + 0.6, f"live {live:.1f} %", color="tab:blue", fontsize=7.5, ha="left", va="bottom")
    axg.set_xlabel("contribution = largest |delta - nominal| in the group (%)")
    axg.set_title("Per-group contributions (qs.COLLECTION_GROUPS)", fontsize=10)
    axg.grid(axis="y", alpha=0)

    fig.suptitle("Collection-length term: the guarded chamber as measured vs the live symmetric term", fontsize=12, y=0.98)
    fig.text(0.02, 0.045,
             f"Calc collection length l = {l_mm:g} mm (calc/monp_transform.py L_CM, set to the modelled l_eff {float(by[NOMINAL]['l_eff_mm']):.3f} mm); "
             f"nominal delta = {d_nom:+.3f} % (CSV column; recomputed from l_eff and L_CM: {d_nom_chk:+.3f} %).\n"
             f"Live term SYMMETRIC_TERMS['{TERM_KEY}'] = +-{live:.1f} %; collection_term() from the CSV = +-{calc_term:.2f} % "
             f"(recomputed here from the groups: {quad:.2f} %). Cases span {min(float(r['delta_pct']) for r in rows if r['case'] != ALT):+.2f} to "
             f"{max(float(r['delta_pct']) for r in rows if r['case'] != ALT):+.2f} % (guard_flush {float(by[ALT]['delta_pct']):+.2f} % excluded).\n"
             f"Old scan: 2-D Laplace, plate length 6 cm, gap 1 cm, no guards; its delta is relative to 6.0 cm, not to the calc's l.",
             ha="left", va="bottom", fontsize=8)
    return save(fig, "leff_scan", ["analysis/out/collection_length_cmc.csv", "analysis/out/fringe_field_scan.csv",
                                   "analysis/cmc_chamber_geometry.py derived()",
                                   "calc/quality_slots.py SYMMETRIC_TERMS, collection_term(), COLLECTION_GROUPS",
                                   "calc/monp_transform.py L_CM"], outdir)


if __name__ == "__main__":
    print(main())
