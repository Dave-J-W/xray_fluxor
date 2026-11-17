"""Collection length of the GUARDED CMC-custom chamber: 2-D Laplace solution + field lines (plane of beam x and gap z).

Everything chamber-related comes from analysis/collection_length_cmc.py (Geom.nominal, solve, l_eff, trace_endpoints,
labels HV=1, COLL=2, GND=3), analysis/cmc_chamber_geometry.py (PARAMS tags, derived()) and calc/monp_transform.py (L_CM).
Field lines are re-traced here only to get drawable paths (same stepping rule as trace_endpoints); the colour of the
beam line and the l_eff numbers come from l_eff() itself.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402

import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from scipy.ndimage import map_coordinates  # noqa: E402

import collection_length_cmc as cl  # noqa: E402
import cmc_chamber_geometry as cg  # noqa: E402
from monp_transform import L_CM  # noqa: E402

# --- choices of this figure (cosmetic or grid) ---
H_MAIN = 0.05           # mm, main solve (the grid the calc's l_eff comes from)
H_COARSE = 0.1          # mm, for the convergence line
LINE_STEP = 0.5         # mm, spacing of traced field lines along the beam
OVERVIEW_EVERY = 4      # overview draws every Nth traced line (sparse)
ZOOM_BACK = 4.0         # mm, zoom starts this far inside the collector end
C_COLL, C_GUARD, C_SHELL = "#1a9850", "#d95f02", "#7b3294"
C_HV, C_CO, C_GR = "#e6b0aa", "#aed6f1", "#c8c8c8"


def trace_paths(x, y, V, lab, x0, y0, h, stride=6, max_steps=20000):
    """Same stepping rule as trace_endpoints, but keep the path. Returns list of (n,2) arrays."""
    gx, gy = np.gradient(V, h, h)
    p = np.array([x0, np.full_like(x0, y0)], float)
    done = np.zeros(p.shape[1], bool)
    paths = [[(p[0, i], p[1, i])] for i in range(p.shape[1])]
    step = 0.25 * h
    for it in range(max_steps):
        a = np.nonzero(~done)[0]
        if len(a) == 0:
            break
        fi, fj = (p[0, a] - x[0]) / h, (p[1, a] - y[0]) / h
        ex = -map_coordinates(gx, [fi, fj], order=1, mode="nearest")
        ey = -map_coordinates(gy, [fi, fj], order=1, mode="nearest")
        nrm = np.hypot(ex, ey) + 1e-30
        p[0, a] += step * ex / nrm
        p[1, a] += step * ey / nrm
        fi, fj = (p[0, a] - x[0]) / h, (p[1, a] - y[0]) / h
        li = np.clip(np.rint(fi).astype(int), 0, lab.shape[0] - 1)
        lj = np.clip(np.rint(fj).astype(int), 0, lab.shape[1] - 1)
        stop = lab[li, lj] > 0
        for i, s in zip(a, stop):
            if s or it % stride == 0:
                paths[i].append((p[0, i], p[1, i]))
        done[a[stop]] = True
    return [np.array(q) for q in paths]


def draw_layers(ax, g, x, z, V, lab, paths, hits, xs, hit, h, every, label_contours):
    w = cg.v("shell_wall_thickness")
    d = cg.derived()
    xi = g.inner_length / 2
    # shell (grey body) around the solved domain, then the vacuum/gas region
    ax.add_patch(Rectangle((-xi - w, g.z_bot - w), 2 * (xi + w), g.z_top - g.z_bot + 2 * w, fc="0.55", ec="none", zorder=0))
    ax.add_patch(Rectangle((-xi, g.z_bot), 2 * xi, g.z_top - g.z_bot, fc="white", ec="none", zorder=0.2))
    # guards
    g0, g1 = g.coll_len / 2 + g.guard_gap, g.inner_length / 2 - g.guard_wall_gap
    for s in (-1, 1):
        xa, xb = (g0, g1) if s > 0 else (-g1, -g0)
        ax.add_patch(Rectangle((xa, g.guard_z0), xb - xa, g.z_top - g.guard_z0, fc=C_GR, ec="k", lw=0.7, zorder=3))
    # plates
    ax.add_patch(Rectangle((-g.hv_len / 2, g.hv_z1 - g.plate_t), g.hv_len, g.plate_t, fc=C_HV, ec="k", lw=0.8, zorder=3))
    ax.add_patch(Rectangle((-g.coll_len / 2, g.coll_z0), g.coll_len, g.plate_t, fc=C_CO, ec="k", lw=0.8, zorder=3))
    # equipotentials (conductor cells excluded)
    X, Z = np.meshgrid(x, z, indexing="ij")
    Vp = np.where(lab > 0, np.nan, V)
    cs = ax.contour(X, Z, Vp, levels=np.arange(0.1, 1.0, 0.1), colors="0.45", linewidths=0.5, zorder=1)
    if label_contours:
        ax.clabel(cs, fmt="%.1f", fontsize=5.5, inline=True)
    # field lines
    for q, c in list(zip(paths, hits))[::every]:
        ax.plot(q[:, 0], q[:, 1], color=c, lw=0.7, alpha=0.9, zorder=2)
    # beam line coloured by where its field line ends (l_eff sampling)
    ax.plot(np.where(hit == cl.COLL, xs, np.nan), np.full_like(xs, g.beam_z), color=C_COLL, lw=4, solid_capstyle="butt", zorder=5)
    ax.plot(np.where(hit == cl.GND, xs, np.nan), np.full_like(xs, g.beam_z), color=C_GUARD, lw=4, solid_capstyle="butt", zorder=5)
    ax.set_aspect("equal")
    ax.set_xlabel("x along the beam (mm)")
    ax.set_ylabel("z across the gap (mm)")


def main(outdir=common.OUT):
    g = cl.Geom.nominal()
    d = cg.derived()
    L_mm = L_CM * 10
    h = H_MAIN
    x, z, V, lab = cl.solve(g, h)
    le, (e_up, e_dn), xs, hit = cl.l_eff(g, h)
    le_c = cl.l_eff(g, H_COARSE)[0]
    delta = le / L_mm - 1
    g0, g1 = g.coll_len / 2 + g.guard_gap, g.inner_length / 2 - g.guard_wall_gap

    # field lines from the beam line
    x_start = np.arange(-g.inner_length / 2 + 1.0, g.inner_length / 2 - 1.0, LINE_STEP)
    hits_code = cl.trace_endpoints(x, z, V, lab, x_start, g.beam_z, h)
    paths = trace_paths(x, z, V, lab, x_start, g.beam_z, h)
    colors = []
    for q, code in zip(paths, hits_code):
        if code == cl.COLL:
            colors.append(C_COLL)
        else:
            xe, ze = abs(q[-1, 0]), q[-1, 1]
            in_guard = (g0 - h <= xe <= g1 + h) and (g.guard_z0 - h <= ze < g.z_top - h)
            colors.append(C_GUARD if in_guard else C_SHELL)

    fig = plt.figure(figsize=(14, 12.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.25], width_ratios=[1.0, 1.0], left=0.06, right=0.98, top=0.90,
                          bottom=0.09, hspace=0.28, wspace=0.12)
    fig.text(0.06, 0.975, "Collection length of the guarded CMC-custom chamber (2-D Laplace + field lines; "
             "user's MonC measurements 2026-11-13)", fontsize=12.5, fontweight="bold", va="top")
    fig.text(0.06, 0.948, "Pair charge counts only if the field line through its birth point ends on the collector (Shockley-Ramo). "
             "Collector, HV plate and guard dimensions are MEASURED by the user's meter/rule; HV polarity does not matter.",
             fontsize=8.5, va="top", color="0.25")

    # 1. full cross-section
    ax1 = fig.add_subplot(gs[0, :])
    draw_layers(ax1, g, x, z, V, lab, paths, colors, xs, hit, h, OVERVIEW_EVERY, True)
    ax1.set_xlim(-g.inner_length / 2 - 3, g.inner_length / 2 + 3)
    ax1.set_ylim(g.z_bot - 3, g.z_top + 3)
    ax1.set_title("Full chamber cross-section, nominal geometry, true aspect (every %dth traced line drawn)" % OVERVIEW_EVERY,
                  fontsize=10, loc="left")
    ax1.text(-g.coll_len / 2 + 1.5, g.coll_z0 + g.plate_t + 0.6, "collector (upper plate, %.1f mm), MEASURED" % g.coll_len,
             fontsize=7.5, va="bottom", zorder=6)
    ax1.text(-g.hv_len / 2 + 1.5, g.hv_z1 - g.plate_t - 0.6, "HV plate (lower, %.1f mm), MEASURED" % g.hv_len,
             fontsize=7.5, va="top", zorder=6)
    ax1.text(-(g0 + g1) / 2, g.z_top - 5.0, "guard (grounded Al)\nMEASURED", fontsize=7, ha="center", va="center", zorder=6)
    ax1.text((g0 + g1) / 2 + 2, g.z_top - 2.0, "guard", fontsize=7, ha="center", va="center", zorder=6)
    ax1.text(0, g.z_bot + 1.2, "grounded steel shell", fontsize=7.5, ha="center", va="bottom", color="0.3", zorder=6)
    # zoom box
    zx0, zx1 = g.coll_len / 2 - ZOOM_BACK, g.inner_length / 2
    zz0, zz1 = g.hv_z1 - g.plate_t - 2.0, g.coll_z0 + g.plate_t + 6.0
    ax1.add_patch(Rectangle((zx0, zz0), zx1 - zx0, zz1 - zz0, fc="none", ec="k", lw=1.0, ls="--", zorder=7))
    leg = [Line2D([], [], color=C_COLL, lw=4, label="beam line / field line ends on collector (counted)"),
           Line2D([], [], color=C_GUARD, lw=4, label="beam line (code 3); field line ends on a guard (not counted)"),
           Line2D([], [], color=C_SHELL, lw=1.2, label="field line ends on the shell (not counted)"),
           Line2D([], [], color="0.45", lw=0.8, label="equipotentials, 0.1 steps of V_HV")]
    ax1.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=7.5, frameon=False)

    # 2. zoom on downstream collector end
    ax2 = fig.add_subplot(gs[1, 0])
    draw_layers(ax2, g, x, z, V, lab, paths, colors, xs, hit, h, 1, False)
    ax2.set_xlim(zx0, zx1 + 1.0)
    ax2.set_ylim(zz0, zz1)
    ax2.set_title("Zoom: downstream collector end (dashed box above); every traced line drawn", fontsize=10, loc="left")
    ce = g.coll_len / 2
    yb = g.beam_z
    ax2.plot([ce, ce], [g.hv_z1 - g.plate_t - 1.5, g.coll_z0 + g.plate_t + 3.5], color="k", lw=0.8, ls=":", zorder=6)
    ax2.annotate("", xy=(ce, yb + 0.9), xytext=(e_dn, yb + 0.9), arrowprops=dict(arrowstyle="<->", lw=1.0, color="k"), zorder=8)
    ax2.plot([e_dn, e_dn], [yb - 0.4, yb + 1.4], color="k", lw=1.2, zorder=8)
    ax2.text((e_dn + ce) / 2, yb + 1.15, "collection edge %+.2f mm\nbeyond collector end" % (e_dn - ce),
             fontsize=7.5, ha="center", va="bottom", zorder=8,
             bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
    ax2.text(ce - 0.2, g.coll_z0 + g.plate_t + 2.8, "collector end\nx = %.2f mm" % ce, fontsize=7, ha="right", va="center", zorder=8)
    ax2.annotate("collector-guard gap\n%.1f mm" % g.guard_gap, xy=(ce + g.guard_gap / 2, g.coll_z0 + g.plate_t / 2),
                 xytext=(ce + 4.5, g.coll_z0 + g.plate_t + 3.6), fontsize=7, ha="left", va="center",
                 arrowprops=dict(arrowstyle="->", lw=0.7), zorder=8)
    ax2.text(ce + 4.5, g.hv_z1 - g.plate_t / 2, "HV plate end\n(%.1f mm beyond the collector end)" % (g.hv_len / 2 - ce),
             fontsize=7, ha="left", va="center", zorder=8, bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))
    ax2.text(g1 - 0.2, g.guard_z0 + 1.0, "guard", fontsize=7, ha="right", va="bottom", zorder=8)

    # 3. text panel
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.axis("off")
    rule = d["collector_l_eff_guard_rule"]
    p = cg.PARAMS
    lines = [
        ("Result, nominal case (h = %.2f mm)" % h, True),
        ("l_eff (beam length whose field lines end on collector) = %.3f mm" % le, False),
        ("collection edges: %+.3f mm (upstream), %+.3f mm (downstream)" % (e_up, e_dn), False),
        ("collector length = %.1f mm;  l_eff - collector = %+.3f mm" % (g.coll_len, le - g.coll_len), False),
        ("calc collection length l = 10*L_CM = %.1f mm" % L_mm, False),
        ("  (set to the modelled l_eff)", False),
        ("delta = l_eff/l - 1 = %+.2f %%" % (100 * delta), False),
        ("flux factor 1/(1+delta) = %.4f  (%+.2f %%)" % (1 / (1 + delta), 100 * (1 / (1 + delta) - 1)), False),
        ("", False),
        ("Textbook guard rule (collector + block_gap): %.2f mm" % rule, True),
        ("  l_eff - rule = %+.3f mm;  delta_rule = %+.2f %%" % (le - rule, 100 * (rule / L_mm - 1)), False),
        ("", False),
        ("Grid convergence (recomputed here)", True),
        ("  h = %.2f mm: l_eff = %.3f mm" % (H_COARSE, le_c), False),
        ("  h = %.2f mm: l_eff = %.3f mm" % (h, le), False),
        ("  difference = %+.3f mm  (module --check also runs h = 0.2 mm)" % (le - le_c), False),
        ("", False),
        ("ASSUMED / INTERPRETED items", True),
        ("  window aperture BC = %s  [%s]: Kapton windows modelled grounded" % (p["window_bc"].value, p["window_bc"].tag), False),
        ("  2-D model: plates treated as wide vs the gap (width %.0f mm vs gap %.0f mm);" % (cg.v("plate_width"), cg.v("plate_gap")), False),
        ("    no end-on-y fringe; beam offset in y not modelled", False),
        ("  guard face set back %.2f mm from the collector face [%s];" % (cg.v("block_recess"), p["block_recess"].tag), False),
        ("    measured from the collector's gap-facing face [INTERPRETED]; guards sit on the top shell", False),
        ("  guard gaps %.1f mm [%s], block width %.0f mm [%s]" % (cg.v("block_gap"), p["block_gap"].tag,
                                                                 cg.derived()["block_width"], p["block_extra_inboard"].tag), False),
        ("  shell wall %.1f mm [%s]; plate thickness %.2f mm [%s]" % (cg.v("shell_wall_thickness"), p["shell_wall_thickness"].tag,
                                                                   g.plate_t, p["plate_thickness"].tag), False),
        ("  beam z = %.2f mm (beam %.1f mm below aperture top) [%s]" % (g.beam_z, cg.v("beam_below_aperture_top"),
                                                                    p["beam_below_aperture_top"].tag), False),
    ]
    yy = 0.98
    for s, bold in lines:
        ax3.text(0.0, yy, s, transform=ax3.transAxes, fontsize=8.2, va="top", family="monospace" if not bold else None,
                 fontweight="bold" if bold else "normal")
        yy -= 0.040
    ax3.set_title("Numbers (all from the model and its geometry module)", fontsize=10, loc="left")
    ax3.grid(False)

    fig.text(0.06, 0.035, "Field lines drawn start on the beam line (z = beam_z) every %.1f mm and run toward lower potential. "
             "Guard vs shell for field-line ends: the end point lies inside a guard box (x between collector end + gap and the wall - gap, "
             "z at or above the guard face) or not; the model's hit code is 3 for both." % LINE_STEP,
             fontsize=7.2, va="bottom", color="0.25", wrap=True)
    return common.save(fig, "fringe_field",
                       ["analysis/collection_length_cmc.py (Geom, solve, l_eff, trace_endpoints)",
                        "analysis/cmc_chamber_geometry.py (PARAMS, derived)", "calc/monp_transform.py (L_CM)"], outdir)


if __name__ == "__main__":
    main(common.OUT)
