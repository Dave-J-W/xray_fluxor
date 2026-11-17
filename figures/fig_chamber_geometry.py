"""CMC-custom ion chamber, MonP vs MonC: the same chamber mounted two ways, with sample photoelectron tracks at
30 keV and the wall loss versus energy for both orientations.

  MonP: plates VERTICAL, E-vector (horizontal) toward the plates, beam ~1 mm FWHM across the gap.
  MonC: plates HORIZONTAL, E-vector (horizontal) ALONG the plates, beam ~0.03 mm FWHM across the gap.

Numbers come from upstream (nothing chamber- or physics-valued is typed here):
  analysis/cmc_chamber_geometry.py  PARAMS / derived(): gap, plate thickness and width, MonC beam distances to the
                                    plates, beam position across the plate width
  analysis/wall_loss_mc.py          HALF_GAP, RHO, T_CUT, B_K and the primitives sauter_dirs, elastic, range_gcm2,
                                    energy_from_range, rotate; the E_PARALLEL option
  analysis/wall_loss_families.py    families()[lane]: half_gap_mm, offset_mm, fwhm_mm, e_parallel (track settings)
  analysis/out/wall_loss/<lane>/central.csv   each lane's own central MC
  analysis/wall_loss_fit.py         f_pe(E), load_mc, family_files
  calc/quality_slots.py             wall_loss_band(E_eff, lane)[1] (each lane's live fit), e_eff, RHO0
The track loop reuses the MC primitives and only records the path (wall_loss_mc.transport() keeps no positions).
Tracks are projected on the plane perpendicular to the beam: displacement along the plate normal vs along the
in-plane transverse direction. The displacement along the beam is dropped.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402  (sets sys.path for analysis/, calc/, matplotlib style)

import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, FancyArrowPatch  # noqa: E402

import wall_loss_mc as mc  # noqa: E402
import wall_loss_fit as wf  # noqa: E402
import quality_slots as qs  # noqa: E402
import cmc_chamber_geometry as geo  # noqa: E402
import wall_loss_families as wfam  # noqa: E402

# --- choices of this figure (not physics inputs) ---
E_TRACK_KEV = 30.0            # photon energy of the sample tracks (requested)
N_TRACKS = 240                # tracks per panel (user, 2026-11-13: doubled from 120, alpha unchanged)
TRACK_ALPHA = 0.3             # track line opacity (user, 2026-11-13)
SEED = 20261113               # fixed RNG seed; each panel starts from a fresh generator with this seed
WINDOW_MM = 13.0              # half-size of the (square, equal-scale) track windows, mm (cosmetic)
E_PLOT = (8.0, 30.0)          # energy range of the loss plot, keV (requested)
C_HIT, C_MISS = "#c0392b", "#2471a3"
C_MONP, C_MONC, C_LIVE = "#1b7837", "#762a83", "0.15"
MM = 10.0                     # cm -> mm
LANES = ("MonP", "MonC")
FAM = wfam.families()         # per-lane MC settings: half_gap_mm, offset_mm, fwhm_mm, e_parallel


def record_track(E_keV, rng):
    """One photoelectron, same transport rule as wall_loss_mc.transport(). Returns (x_mm[], y_mm[], hit) with
    x along the plate normal and y along the in-plane transverse direction. Start direction and start x follow
    wall_loss.wall_loss(): u is along the E-vector, swapped with v when mc.E_PARALLEL (then the plate normal
    stays x, perpendicular to E and to the beam). Uses the module globals set by the caller."""
    T = E_keV * 1e-3 - mc.B_K                                   # MeV
    u, v, w = (a[0] for a in mc.sauter_dirs(T, 1, rng))
    if mc.E_PARALLEL:
        u, v = v, u
    x = rng.normal(mc.OFFSET_X, mc.BEAM_SIGMA_X)
    y = 0.0
    Rcut = mc.range_gcm2(np.array([mc.T_CUT]))[0] / mc.RHO
    xs, ys = [x], [y]
    while True:
        lam, _ = mc.elastic(T)
        s = -lam * np.log(rng.random())
        R0 = mc.range_gcm2(np.array([T]))[0] / mc.RHO
        smax = R0 - Rcut
        last = s >= smax
        s = min(s, smax)
        xn = x + u * s
        if abs(xn) >= mc.HALF_GAP:
            sb = (np.sign(u) * mc.HALF_GAP - x) / u
            xs.append(np.sign(u) * mc.HALF_GAP)
            ys.append(y + v * sb)
            return np.array(xs) * MM, np.array(ys) * MM, True
        x, y = xn, y + v * s
        xs.append(x)
        ys.append(y)
        if last:
            return np.array(xs) * MM, np.array(ys) * MM, False
        T = mc.energy_from_range(np.array([max(R0 - s, 1e-12)]) * mc.RHO)[0]
        _, eta = mc.elastic(T)
        xi = rng.random()
        cost = 1 - 2 * eta * xi / (1 - xi + eta)
        u, v, w = (a[0] for a in mc.rotate(np.array([u]), np.array([v]), np.array([w]),
                                           np.array([cost]), np.array([2 * np.pi * rng.random()])))


def sample_tracks(lane):
    """N_TRACKS tracks with the MC globals set from wall_loss_families.families()[lane]; always restored."""
    f = FAM[lane]
    e_parallel, fwhm_mm, offset_mm = f["e_parallel"], f["fwhm_mm"], f["offset_mm"]
    saved = (mc.E_PARALLEL, mc.BEAM_SIGMA_X, mc.OFFSET_X, mc.HALF_GAP, mc.BASE_HALF_GAP)
    try:
        mc.HALF_GAP = mc.BASE_HALF_GAP = f["half_gap_mm"] / MM
        mc.E_PARALLEL = e_parallel
        mc.BEAM_SIGMA_X = fwhm_mm / MM / 2.3548
        mc.OFFSET_X = offset_mm / MM
        rng = np.random.default_rng(SEED)
        return [record_track(E_TRACK_KEV, rng) for _ in range(N_TRACKS)]
    finally:
        mc.E_PARALLEL, mc.BEAM_SIGMA_X, mc.OFFSET_X, mc.HALF_GAP, mc.BASE_HALF_GAP = saved


def track_panel(ax, tracks, monc, fwhm_mm, offset_mm, t_mm, lo_mm, hi_mm, title):
    """Draw in the plate-normal / in-plane frame. MonP: normal is the horizontal axis. MonC: normal is vertical.
    Normal coordinate is the MC's x, measured from mid-gap (+ = toward the upper/collector plate for MonC)."""
    W = WINDOW_MM

    def pt(n, t):                                   # (normal, transverse) -> (horizontal, vertical) on the page
        return (t, n) if monc else (n, t)

    n_hit = 0
    for xs, ys, hit in tracks:
        n_hit += hit
        h, vv = pt(xs, ys)
        ax.plot(h, vv, color=C_HIT if hit else C_MISS, lw=0.9, alpha=TRACK_ALPHA, zorder=4)
    for (n0, sign) in ((hi_mm, +1), (lo_mm, -1)):   # plate inner faces at lo (negative) and hi (positive)
        if monc:
            ax.add_patch(Rectangle((-W, n0 if sign > 0 else n0 - t_mm), 2 * W, t_mm, fc="#d5d8dc", ec="k", lw=0.8, zorder=3))
        else:
            ax.add_patch(Rectangle((n0 if sign > 0 else n0 - t_mm, -W), t_mm, 2 * W, fc="#d5d8dc", ec="k", lw=0.8, zorder=3))
    # beam spot: FWHM along the plate normal (the MC's only beam dimension); the other dimension is not modelled
    nb0, nb1 = offset_mm - fwhm_mm / 2, offset_mm + fwhm_mm / 2
    (h0, v0), (h1, v1) = pt(nb0, 0.0), pt(nb1, 0.0)
    ax.plot([h0, h1], [v0, v1], color="#f39c12", lw=5, solid_capstyle="butt", zorder=6)
    hb, vb = pt(offset_mm, 0.0)
    ax.plot(hb, vb, "o", color="#7e5109", ms=3, zorder=7)
    ax.set_xlim(-W, W)
    ax.set_ylim(-W, W)
    ax.set_aspect("equal")
    # E-vector arrow (horizontal in both mountings)
    ax.add_patch(FancyArrowPatch((-W + 1.5, W - 1.8), (-W + 7.5, W - 1.8), arrowstyle="-|>", mutation_scale=14,
                                 color="#1a5276", lw=2.2, zorder=8))
    ax.text(-W + 1.5, W - 3.3, "E-vector (horizontal)", fontsize=8, color="#1a5276", va="top", zorder=8)
    ax.set_title(f"{title}\n{n_hit} of {N_TRACKS} sample tracks reach a plate", fontsize=9.5)
    return n_hit


def main(outdir=common.OUT):
    # ---- geometry, from the modules ----
    d = geo.derived()
    gap_mm = geo.v("plate_gap")
    t_mm = geo.v("plate_thickness")
    for lane in LANES:
        if abs(gap_mm / 2 - FAM[lane]["half_gap_mm"]) > 1e-9:
            raise ValueError(f"upstream inconsistent: cmc_chamber_geometry plate_gap/2 = {gap_mm / 2} mm, "
                             f"{lane} family half_gap_mm = {FAM[lane]['half_gap_mm']} mm")
    half_mm = gap_mm / 2          # plates drawn at +- half gap (== each family's half_gap_mm, checked above)
    # MonC beam distances to the plates. Upper (collector) is +x in the MC frame; offset = (d_lower - d_upper)/2.
    d_up, d_lo = d["beam_to_upper_inner_face"], d["beam_to_lower_inner_face"]
    off_geo_mm = (d_lo - d_up) / 2
    fwhm_p, off_p = FAM["MonP"]["fwhm_mm"], FAM["MonP"]["offset_mm"]
    fwhm_c, off_c = FAM["MonC"]["fwhm_mm"], FAM["MonC"]["offset_mm"]
    if abs(off_c - off_geo_mm) > 0.01:
        raise ValueError(f"MonC family offset {off_c} mm differs from the geometry module's {off_geo_mm:.3f} mm")
    if abs(d_up + d_lo - gap_mm) > 1e-6:
        raise ValueError("beam-to-plate distances do not add up to the plate gap")

    tracks_p = sample_tracks("MonP")
    tracks_c = sample_tracks("MonC")

    # ---- wall-loss curves: each lane's central MC x f_pe, and its live fit ----
    Egrid = np.linspace(E_PLOT[0], E_PLOT[1], 300)
    corr = lambda L: 1.0 / (1.0 - L)
    S = {}
    for lane in LANES:
        central, _ = wf.family_files(lane)
        E, L, se, _ = wf.load_mc(central)
        f = np.array([wf.f_pe(e) for e in E])
        i30 = int(np.argmin(np.abs(E - E_TRACK_KEV)))
        if abs(E[i30] - E_TRACK_KEV) > 1e-9:
            raise ValueError(f"no {E_TRACK_KEV:g} keV row in {central}")
        live_30 = qs.wall_loss_band(qs.e_eff(E_TRACK_KEV, qs.RHO0), lane)[1]
        S[lane] = dict(E=E, sig=L * f, err=se * f, i=i30, c_mc=corr(L[i30] * f[i30]),
                       c_err=se[i30] * f[i30] * corr(L[i30] * f[i30]) ** 2, loss30=L[i30] * f[i30],
                       live=np.array([qs.wall_loss_band(qs.e_eff(e, qs.RHO0), lane)[1] for e in Egrid]),
                       live30=live_30, c_live=corr(live_30))

    # ---- range of the 30 keV photoelectron and plate edge distance ----
    T_pe = E_TRACK_KEV * 1e-3 - mc.B_K
    range_mm = mc.range_gcm2(np.array([T_pe]))[0] / mc.RHO * MM
    edge_mm = geo.v("plate_width") / 2 - d["beam_y"]

    # ---------- figure ----------
    fig = plt.figure(figsize=(11, 12.4))
    gs = fig.add_gridspec(4, 2, height_ratios=[1.0, 0.2, 0.9, 0.34], hspace=0.38, wspace=0.12,
                          left=0.08, right=0.97, top=0.865, bottom=0.03)
    fig.text(0.08, 0.985, "CMC-custom ion chamber: MonP (plates vertical) vs MonC (plates horizontal)",
             fontsize=12, fontweight="bold", va="top")
    fig.text(0.08, 0.958, "Same chamber, two mountings; the beam E-vector is horizontal in both. Gap measured; MonP beam "
             "position assumed (see wall_loss_families.py, cmc_chamber_geometry.py).", fontsize=8.5, va="top", color="0.25")

    axp = fig.add_subplot(gs[0, 0])
    axc = fig.add_subplot(gs[0, 1])
    track_panel(axp, tracks_p, False, fwhm_p, off_p, t_mm, -half_mm, half_mm,
                f"MonP: plates vertical, E-vector toward the plates\n(gap {gap_mm:g} mm measured,\nbeam centred ASSUMED, FWHM {fwhm_p:g} mm)")
    track_panel(axc, tracks_c, True, fwhm_c, off_c, t_mm, -half_mm, half_mm,
                f"MonC: plates horizontal, E-vector along the plates\n(beam {d_up:.2f} mm from collector, "
                f"{d_lo:.2f} mm from HV,\nFWHM {fwhm_c:g} mm, from Kapton scar)")
    axp.set_xlabel("displacement along the plate normal (mm)")
    axp.set_ylabel("in-plane transverse, vertical (mm)")
    axc.set_xlabel("in-plane transverse, along E (mm)")
    axc.set_ylabel("displacement along the plate normal, up = toward collector (mm)")
    axc.yaxis.set_label_position("right")
    axc.yaxis.tick_right()
    axc.text(WINDOW_MM - 0.5, half_mm + t_mm / 2, "collector (upper plate)", ha="right", va="center", fontsize=7.5, zorder=9)
    axc.text(WINDOW_MM - 0.5, -half_mm - t_mm / 2, "HV (lower plate)", ha="right", va="center", fontsize=7.5, zorder=9)
    axp.plot([], [], color=C_HIT, label="track reaches a plate (energy lost to the plate)")
    axp.plot([], [], color=C_MISS, label="track stops in the gas (signal kept)")
    axp.plot([], [], color="#f39c12", lw=5, label="beam spot: FWHM across the gap (other dimension not modelled)")
    axt = fig.add_subplot(gs[1, :])
    axt.axis("off")
    axt.legend(*axp.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=8,
               frameon=False)
    axt.text(0, 0.62,
             f"Tracks at {E_TRACK_KEV:g} keV (photoelectron {T_pe * 1e3:.2f} keV), {N_TRACKS} per panel, same seed {SEED} and "
             "same transport rule as the MC (Sauter start direction, screened-Rutherford scattering, CSDA energy loss).\n"
             "Projection drawn: displacement along the plate normal vs along the in-plane transverse direction, i.e. the plane "
             "perpendicular to the beam (beam direction dropped, so drawn paths are lower bounds). Both panels at the same scale.\n"
             "In-plane transverse = vertical for MonP, the E direction for MonC. All tracks start at transverse 0; start spread across the gap = beam FWHM.",
             fontsize=7.8, va="top", color="0.2", transform=axt.transAxes)

    # ---------- loss vs energy ----------
    ax = fig.add_subplot(gs[2, :])
    sp, sc = S["MonP"], S["MonC"]
    ax.errorbar(sp["E"], 100 * sp["sig"], 100 * sp["err"], color=C_MONP, marker="o", ms=4, lw=1.3, capsize=2,
                label=f"MonP MC (E toward plates, FWHM {fwhm_p:g} mm, centred ASSUMED)")
    ax.errorbar(sc["E"], 100 * sc["sig"], 100 * sc["err"], color=C_MONC, marker="s", ms=4, lw=1.3, capsize=2,
                label=f"MonC MC (E along plates, FWHM {fwhm_c:g} mm, offset {off_c:g} mm)")
    ax.plot(Egrid, 100 * sp["live"], color=C_MONP, ls="--", lw=1.8, label="MonP live fit (its own)")
    ax.plot(Egrid, 100 * sc["live"], color=C_MONC, ls="--", lw=1.8, label="MonC live fit (its own)")
    ax.set_xlim(*E_PLOT)
    ax.set_ylim(bottom=-1.5)
    ax.set_xlabel("photon energy (keV)")
    ax.set_ylabel("signal loss to the plates (%)\n= MC loss per photoabsorption x f_pe(E)")
    ax.set_title("Signal loss vs photon energy (points: central MC x f_pe, error bars: MC statistical error x f_pe; "
                 "dashed: each lane's live fit at E_eff = E, rho0)", fontsize=9)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.text(0.015, 0.40,
            f"Correction factor 1/(1 - loss) at {E_TRACK_KEV:g} keV:\n"
            f"  MonP MC        loss {100 * sp['loss30']:5.2f} %  ->  x{sp['c_mc']:.3f} +- {sp['c_err']:.3f}\n"
            f"  MonP live fit  loss {100 * sp['live30']:5.2f} %  ->  x{sp['c_live']:.3f}\n"
            f"  MonC MC        loss {100 * sc['loss30']:5.2f} %  ->  x{sc['c_mc']:.3f} +- {sc['c_err']:.3f}\n"
            f"  MonC live fit  loss {100 * sc['live30']:5.2f} %  ->  x{sc['c_live']:.3f}",
            transform=ax.transAxes, ha="left", va="top", fontsize=8.5, family="monospace",
            bbox=dict(fc="white", ec="0.6", boxstyle="round,pad=0.4"))

    axf = fig.add_subplot(gs[3, :])
    axf.axis("off")
    axf.text(0, 0.95,
             "Beam position:\n"
             "  - MonP: the beam position in its gap is NOT measured; it is taken as centred (ASSUMED).\n"
             "  - MonC: the beam position comes from the Kapton scar "
             f"({d_up:.2f} mm from the collector, {d_lo:.2f} mm from the HV plate; MC offset {off_c:g} mm toward the collector).\n"
             "Plate extent in the MC:\n"
             "  - The MonC MC has the plates infinite in-plane. This is reasonable: the plates are "
             f"{geo.v('plate_width'):.0f} mm wide and the beam is {edge_mm:.0f} mm from the nearer edge,\n"
             f"    against a {E_TRACK_KEV:g} keV photoelectron CSDA range of {range_mm:.1f} mm in N2 at {mc.RHO * 1e3:.3f} mg/cm3 "
             "(mc.range_gcm2 / mc.RHO).\n"
             "Wall-loss curves are the signal loss (MC loss per photoabsorption x photoelectric share f_pe(E)); Compton electrons are deposited locally.",
             fontsize=8, va="top", color="0.2", transform=axf.transAxes, linespacing=1.35)

    return common.save(fig, "chamber_geometry",
                       ["analysis/cmc_chamber_geometry.py (plate_gap, plate_thickness, plate_width, derived beam distances)",
                        "analysis/wall_loss_mc.py (HALF_GAP, RHO, T_CUT, B_K, E_PARALLEL, primitives)",
                        "analysis/wall_loss_families.py (families())",
                        "analysis/out/wall_loss/<lane>/central.csv",
                        "analysis/wall_loss_fit.py (f_pe, load_mc, family_files)",
                        "calc/quality_slots.py (wall_loss_band, e_eff, RHO0)"], outdir)


if __name__ == "__main__":
    main(common.OUT)
