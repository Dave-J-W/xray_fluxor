"""CMC-custom ion chamber (MonC): shell, plates, guard blocks, end walls, beam and crusts as the user described
them, drawn so the user can confirm we understood the hand measurements.

Every chamber number comes from analysis/cmc_chamber_geometry.py (PARAMS, v(), derived(), blocks_x()), and the
modelled collection length from analysis/out/collection_length_cmc.csv (row "nominal", column l_eff_mm). None is
typed here. The only literals are cosmetic (colours, font sizes, margins, arrow sizes, the z exaggeration).

Tag styles (the PARAMS tag, except that a MEASURED value whose note says "(INTERPRETED)" is drawn as INTERPRETED):
  MEASURED     solid black outline, no bracket in the label
  INTERPRETED  dashed orange, "[INTERPRETED]"
  ASSUMED      dotted purple (hatched where it is a whole object), "[ASSUMED]"
  UNKNOWN      dashed grey, "[UNKNOWN]"
  DERIVED      thin solid blue, "[DERIVED]"
Plus/minus tolerances are read from the "+-x mm" text in the PARAMS note.
"""
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402  (puts analysis/ on sys.path, sets matplotlib style)

import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Patch, Polygon  # noqa: E402

import cmc_chamber_geometry as cg  # noqa: E402
import monp_transform as mt  # noqa: E402  (L_CM, the collection length the calc uses)

LEFF_CSV = common.ROOT / "analysis" / "out" / "collection_length_cmc.csv"

# --- cosmetic choices of this figure (not chamber numbers) ---
ZX = 2.0                  # z exaggeration in the side and end views (top views are 1:1)
XPAD = 14.0               # mm, axis padding beyond the shell
FS = 8.0                  # label font size
FS_S = 7.0
COL = {"MEASURED": "k", "INTERPRETED": "#d35400", "ASSUMED": "#7d3c98", "UNKNOWN": "#7f8c8d", "DERIVED": "#1f618d"}
LS = {"MEASURED": "-", "INTERPRETED": "--", "ASSUMED": ":", "UNKNOWN": "--", "DERIVED": "-"}
HATCH = {"MEASURED": None, "INTERPRETED": None, "ASSUMED": "////", "UNKNOWN": "....", "DERIVED": None}
C_UP, C_LO, C_STEEL, C_BEAM, C_GUARD = "#e6b0aa", "#aed6f1", "#b3b6b7", "#e67e22", "#d5d8dc"


def tag_of(name):
    """PARAMS tag, with MEASURED + '(INTERPRETED)' in the note shown as INTERPRETED."""
    p = cg.PARAMS[name]
    return "INTERPRETED" if (p.tag == "MEASURED" and "(INTERPRETED)" in p.note) else p.tag


def num(x):
    s = f"{x:.1f}"
    return s if abs(float(s) - x) < 0.005 else f"{x:.2f}"


def mm(x):
    return f"{num(x)} mm"


def mmx(x):
    """Up to three decimals, trailing zeros stripped (for values like 10.85, 0.375, 61.925)."""
    t = f"{x:.3f}".rstrip("0")
    return (t + "0" if t.endswith(".") else t) + " mm"


def tols(name):
    """All '+-x' tolerances in the PARAMS note of `name`."""
    return re.findall(r"\+-\s*([\d.]+)", cg.PARAMS[name].note)


def br(tag):
    return "" if tag == "MEASURED" else f" [{tag}]"


def pm(name):
    """'95.0 +- 0.2 mm' with the tolerance read from the PARAMS note ('+-0.2 mm')."""
    m = re.search(r"\+-\s*([\d.]+)", cg.PARAMS[name].note)
    if not m:
        raise ValueError(f"no +- tolerance in the note of {name}")
    return f"{num(cg.v(name))} ± {m.group(1)} mm"


def leff_nominal():
    with open(LEFF_CSV, encoding="utf8") as f:
        for row in csv.DictReader(line for line in f if not line.startswith("#")):
            if row["case"] == "nominal":
                return float(row["l_eff_mm"])
    raise ValueError(f"no 'nominal' row in {LEFF_CSV}")


def leff_text(g):
    return (f"collector {mm(g['collector_length'])}; guarded:\nmodelled l_eff {mmx(leff_nominal())}\n"
            f"(analysis/\ncollection_length_cmc.py)\ncalc l = {mmx(mt.L_CM * 10)} (L_CM)")


def rect(ax, x0, x1, y0, y1, tag, fc, lw=1.4, z=3, hatch="tag", **kw):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=fc, ec=COL[tag], ls=LS[tag],
                           hatch=HATCH[tag] if hatch == "tag" else hatch, lw=lw, zorder=z, **kw))


def hdim(ax, x0, x1, y, label, tag, dy=0.6, va="bottom", fs=FS):
    ax.annotate("", xy=(x0, y), xytext=(x1, y), zorder=8,
                arrowprops=dict(arrowstyle="<->", color=COL[tag], lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=7))
    if label:
        ax.text((x0 + x1) / 2, y + (dy if va == "bottom" else -dy), label, ha="center", va=va, fontsize=fs,
                color=COL[tag], zorder=9, bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.5))


def vdim(ax, x, y0, y1, label, tag, dx=0.8, ha="left", rot=0, ty=None, fs=FS):
    ax.annotate("", xy=(x, y0), xytext=(x, y1), zorder=8,
                arrowprops=dict(arrowstyle="<->", color=COL[tag], lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=7))
    if label:
        ax.text(x + (dx if ha == "left" else -dx), (y0 + y1) / 2 if ty is None else ty, label, ha=ha, va="center",
                fontsize=fs, color=COL[tag], rotation=rot, zorder=9)


def note(ax, text, xy, xytext, tag, ha="center", va="center", fs=FS):
    ax.annotate(text, xy=xy, xytext=xytext, ha=ha, va=va, fontsize=fs, color=COL[tag], zorder=10,
                arrowprops=dict(arrowstyle="-", color=COL[tag], lw=0.8, shrinkA=0, shrinkB=0),
                bbox=dict(fc="white", ec=COL[tag], lw=0.6, alpha=0.92, pad=1.5))


def steel(ax, x0, x1, y0, y1, z=2.2):
    rect(ax, x0, x1, y0, y1, "MEASURED", C_STEEL, z=z, hatch=None)
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="none", ec="0.45", hatch="////", lw=0, zorder=z))


def sgn(a):
    return 1.0 if a > 0 else -1.0


def top_view(ax, which, g, bx):
    """Plan section (x-y) at the plate level. which = 'upper' or 'lower'."""
    up = which == "upper"
    names = ("upper_plate_length", "upper_plate_end_clearance", "upper_plate_crust_width", "upper_end_clearance_implied") if up \
        else ("lower_plate_length", "lower_plate_end_clearance", "lower_plate_crust_width", "lower_end_clearance_implied")
    plen, clr, crust, impl = cg.v(names[0]), cg.v(names[1]), cg.v(names[2]), g[names[3]]
    t_clr = tag_of(names[1])
    px0, px1 = g["upper_plate_x"] if up else g["lower_plate_x"]
    by = g["beam_y"]
    half = g["inner_length"] / 2
    xe = cg.v("exterior_length") / 2
    ylo, yhi = g["shell_outboard_exterior_y"], g["shell_inboard_exterior_y"]
    tw = cg.v("shell_wall_thickness")
    ilo, ihi = ylo + tw, yhi - tw
    yw = cg.v("plate_width") / 2
    ewall = cg.v("end_wall_thickness")

    # shell: side walls (thickness assumed), end walls (steel, measured), exterior outline (measured)
    rect(ax, -xe, xe, ihi, yhi, "ASSUMED", "#e5e7e9", z=2, hatch=None)
    rect(ax, -xe, xe, ylo, ilo, "ASSUMED", "#e5e7e9", z=2, hatch=None)
    for s in (-1, 1):
        steel(ax, half if s > 0 else -xe, xe if s > 0 else -half, ylo, yhi)
    ax.add_patch(Rectangle((-xe, ylo), 2 * xe, yhi - ylo, fc="none", ec="k", lw=2.2, zorder=3.5))
    ax.text(-xe, yhi + 1.0, f"end wall {mm(ewall)} steel", fontsize=FS_S, ha="left", va="bottom")
    ax.text(xe, yhi + 1.0, f"side wall {mm(tw)}{br(cg.PARAMS['shell_wall_thickness'].tag)}", fontsize=FS_S, ha="right",
            va="bottom", color=COL["ASSUMED"])

    # plate, crust, centre line, beam
    rect(ax, px0, px1, -yw, yw, "MEASURED", C_UP if up else C_LO, lw=1.6)
    rect(ax, px0, px1, by - crust / 2, by + crust / 2, "ASSUMED", "white", lw=1.0, z=4)
    ax.plot([px0, px1], [0, 0], color="0.4", lw=0.7, ls=(0, (6, 3)), zorder=5)
    xb = xe + 3.0
    ax.annotate("", xy=(xb + 2.5, by), xytext=(-xb, by), zorder=7,
                arrowprops=dict(arrowstyle="-|>", color=C_BEAM, lw=1.8, shrinkA=0, shrinkB=0, mutation_scale=14))
    ax.text(xb + 3.0, by + 1.0, "beam", color="#a04000", fontsize=FS, va="bottom", ha="left", zorder=7)

    # guard blocks (upper plate only): asymmetric width, y range from derived()["block_y"]
    if up:
        by0, by1 = g["block_y"]
        for (a, b) in bx:
            rect(ax, a, b, by0, by1, "ASSUMED", C_GUARD, lw=1.3)
        ra, rb = bx[1]
        hdim(ax, ra, rb, by0 - 3.5, f"block length\n{mm(g['block_length'])}{br('DERIVED')}", "DERIVED", dy=0.5, va="top",
             fs=FS_S)
        gt = tag_of("block_gap")
        gg = cg.v("block_gap")
        note(ax, f"gap {mm(gg)} plate-to-block{br(gt)} (mirrored upstream)", (px1 + gg / 2, by1),
             (px1 - 3, yhi + 13), gt, ha="right", fs=FS_S)
        note(ax, f"gap {mm(gg)} block-to-wall{br(gt)} (mirrored upstream)", (half - gg / 2, by1),
             (half + 14, yhi + 21), gt, ha="right", fs=FS_S)
        gy = -22.0
        ax.text(0, gy, f"GUARD: Al blocks, {cg.v('block_connection')}ed to the shell\n"
                f"width {mm(g['block_width'])}{br('DERIVED')} = plate\n"
                f"+ {mm(cg.v('block_extra_inboard'))} inboard{br(cg.PARAMS['block_extra_inboard'].tag)}\n"
                f"+ {mm(cg.v('block_extra_outboard'))} outboard",
                ha="center", va="center", fontsize=FS_S, zorder=9,
                bbox=dict(fc="white", ec=COL["ASSUMED"], ls=":", lw=1.0, alpha=0.93, pad=2))
        for (a, b) in bx:
            ax.annotate("", xy=((a + b) / 2, gy), xytext=(sgn(a) * 20.0, gy), zorder=9,
                        arrowprops=dict(arrowstyle="-|>", color="k", lw=0.8, mutation_scale=7))
        ax.text(0, yw * 0.83, f"UPPER plate = COLLECTOR (BNC centre pin to upper plate)", ha="center", va="center",
                fontsize=FS, zorder=9, bbox=dict(fc="white", ec="k", lw=0.8, alpha=0.92, pad=2))
        ax.text(-12.0, yw * 0.52, leff_text(g), ha="center", va="center", fontsize=FS_S, color=COL["DERIVED"], zorder=9,
                bbox=dict(fc="white", ec=COL["DERIVED"], lw=0.6, alpha=0.92, pad=1.5))
    else:
        ax.text(0, yw * 0.83, "LOWER plate = HV (HV centre pin to lower plate)", ha="center", va="center", fontsize=FS,
                zorder=9, bbox=dict(fc="white", ec="k", lw=0.8, alpha=0.92, pad=2))

    # crust and beam-offset labels
    ax.text(px0 + 2.0, by - crust / 2 - 6.5, f"white crust {mm(crust)} wide (MEASURED)\ncentred on beam [ASSUMED]\n"
            f"x-extent not given: drawn full plate length [ASSUMED]", fontsize=FS_S, color=COL["ASSUMED"],
            va="top", ha="left", zorder=9, bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
    vdim(ax, px1 - 6, 0, by, "", "MEASURED")
    note(ax, f"beam offset {mm(by)}\n(inboard of y = 0, the plate width\ncentre, grey dashed)", (px1 - 6, by / 2),
         (px1 - 14, by + 8), "MEASURED", ha="center", fs=FS_S)
    # side clearances (DERIVED from the slot position; plates centred on the slot is ASSUMED)
    vdim(ax, -12, yw, ihi, "", "DERIVED")
    note(ax, f"inboard side clearance {mm(g['side_clearance_inboard'])}{br('DERIVED')}", (-12, (yw + ihi) / 2),
         (-28, yhi + 6), "DERIVED", ha="center", fs=FS_S)
    vdim(ax, 0, -yw, ilo, "", "DERIVED")
    ax.text(1.0, (-yw + ilo) / 2 - 3.0, f"outboard side clearance\n{mm(g['side_clearance_outboard'])}{br('DERIVED')}\n"
            "OUTBOARD = electronics-mount side:\nroom for the connections", fontsize=FS_S, color=COL["DERIVED"],
            ha="left", va="center", zorder=9)
    # end clearances: drawn length is the value implied by the exterior length
    yc = -44.0
    hdim(ax, -half, px0, yc, mm(impl), "DERIVED", fs=FS_S)
    hdim(ax, px1, half, yc, mm(impl), "DERIVED", fs=FS_S)

    # dimensions below the shell
    yd = ylo - 3.5
    ax.text(0, yd, f"end clearance drawn = {mm(impl)} each end{br('DERIVED')} (exterior length - 2 x end wall, minus plate).\n"
            f"Plate reading: {mm(clr)}, taken as the same at both ends{br(t_clr)}.\n"
            f"Shell width centre at y = {g['shell_centre_y']:+.2f} mm{br('DERIVED')} (outboard of the plate width centre):"
            f" plates centred on the slot{br(cg.PARAMS['plates_centred_on_slot'].tag)}.", ha="center", va="top",
            fontsize=FS_S, color=COL["DERIVED"])
    hdim(ax, px0, px1, yd - 12, f"{which} plate length {mm(plen)}", "MEASURED")
    hdim(ax, -half, half, yd - 18, f"wall to wall (inner length) {mm(g['inner_length'])}{br('DERIVED')}", "DERIVED",
         fs=FS_S)
    hdim(ax, -xe, xe, yd - 24, f"exterior length {pm('exterior_length')}", "MEASURED")
    vdim(ax, -xe - 4, -yw, yw, f"plate width {mm(cg.v('plate_width'))}", "MEASURED", dx=1.3, ha="right", rot=90)
    vdim(ax, xe + 4, ylo, yhi, f"exterior width {pm('exterior_width')}", "MEASURED", dx=1.3, ha="left", rot=90, ty=-30)
    ax.set_xlim(-xe - XPAD - 3, xe + XPAD + 3)
    ax.set_ylim(yd - 28, yhi + (27 if up else 10))
    ax.set_aspect("equal")
    ax.set_xlabel("x along the beam, downstream positive (mm)")
    ax.set_ylabel("y across the plate width, +y inboard (mm)")
    ax.set_title(f"{which.upper()} plate, plan section (x-y) through the shell, 1:1 scale", fontsize=10.5,
                 fontweight="bold", loc="left")


def side_view(ax, g, bx):
    zap = cg.v("window_aperture_h") / 2
    t = cg.v("plate_thickness")
    zmid = cg.v("plate_mid_gap_above_aperture_centre")
    bz = g["beam_z"]
    half = g["inner_length"] / 2
    xe = cg.v("exterior_length") / 2
    ztop_o, ztop_i = g["shell_top_outer_z"], g["shell_top_inner_z"]
    zbot_o, zbot_i = g["shell_bottom_outer_z"], g["shell_bottom_inner_z"]
    ux0, ux1 = g["upper_plate_x"]
    lx0, lx1 = g["lower_plate_x"]
    tw_tag = cg.PARAMS["shell_wall_thickness"].tag
    # shell: top and bottom walls (assumed thickness), end walls with window apertures (steel, measured)
    rect(ax, -xe, xe, ztop_i, ztop_o, "ASSUMED", "#e5e7e9", z=2, hatch=None)
    rect(ax, -xe, xe, zbot_o, zbot_i, "ASSUMED", "#e5e7e9", z=2, hatch=None)
    for s in (-1, 1):
        x0, x1 = (half, xe) if s > 0 else (-xe, -half)
        steel(ax, x0, x1, zap, ztop_o)
        steel(ax, x0, x1, zbot_o, -zap)
    ax.add_patch(Rectangle((-xe, zbot_o), 2 * xe, ztop_o - zbot_o, fc="none", ec="k", lw=2.2, zorder=3.5))
    ax.text(-20, ztop_o + 0.7, f"top wall {mm(cg.v('shell_wall_thickness'))}{br(tw_tag)}", fontsize=FS_S, ha="center",
            va="bottom", color=COL["ASSUMED"])
    ax.text(-20, zbot_o - 0.7, f"bottom wall {mm(cg.v('shell_wall_thickness'))}{br(tw_tag)}", fontsize=FS_S,
            ha="center", va="top", color=COL["ASSUMED"])
    ax.text(xe + 1.0, -12.0, f"end wall {mm(cg.v('end_wall_thickness'))} steel,\nwith the machined slot\n(Kapton window)",
            fontsize=FS_S - 0.5, ha="left", va="center")
    # plates
    rect(ax, ux0, ux1, g["upper_inner_z"], g["upper_outer_z"], "MEASURED", C_UP, lw=1.4)
    rect(ax, lx0, lx1, g["lower_outer_z"], g["lower_inner_z"], "MEASURED", C_LO, lw=1.4)
    # guard blocks: z-span interpreted
    bt = tag_of("block_recess")
    gz0 = g["guard_z0"]
    for (a, b) in bx:
        rect(ax, a, b, gz0, ztop_i, bt, C_GUARD, lw=1.4)
    ra, rb = bx[1]
    zx0, zx1 = ux1 - 4.0, rb - 3.0          # zoom window (cosmetic margins) on the collector end / guard step
    zz0, zz1 = g["upper_inner_z"] - 1.5, gz0 + 2.5
    ax.add_patch(Rectangle((zx0, zz0), zx1 - zx0, zz1 - zz0, fc="none", ec="k", ls="--", lw=0.8, zorder=9))
    ins = ax.inset_axes([0.075, 0.05, 0.17, 0.27])
    ins.grid(False)
    ins.set_facecolor("white")
    rect(ins, ux0, ux1, g["upper_inner_z"], g["upper_outer_z"], "MEASURED", C_UP, lw=1.2)
    for (a, b) in bx:
        rect(ins, a, b, gz0, ztop_i, bt, C_GUARD, lw=1.2)
    ins.plot([zx0, zx1], [g["upper_inner_z"]] * 2, color="k", lw=0.6, ls=":")
    ins.plot([zx0, zx1], [zap, zap], color="0.4", lw=0.6, ls="--")
    ins.text(zx0 + 0.3, zap + 0.1, f"aperture top ledge z = +{mm(zap)}", fontsize=FS_S - 1.5, color="0.3", va="bottom",
             ha="left")
    vdim(ins, ux1 + 0.5 * (bx[1][0] - ux1), g["upper_inner_z"], gz0, "", bt)
    ins.text(zx0 + 0.3, zz1 - 0.2, f"ZOOM (dashed box in the main view): guard face\nrecessed {mm(cg.v('block_recess'))}{br(bt)}\n"
             "from the collector gap-facing face", fontsize=FS_S - 1.0, color=COL[bt], va="top", ha="left")
    ins.text(zx1 - 0.2, g["upper_inner_z"] - 0.2, f"collector face z = +{mm(g['upper_inner_z'])}", fontsize=FS_S - 1.5,
             ha="right", va="top")
    ins.text(zx1 - 0.2, gz0 + 0.15, f"guard face z = +{mm(gz0)}", fontsize=FS_S - 1.5, ha="right", va="bottom",
             color=COL[bt])
    ins.set_xlim(zx0, zx1)
    ins.set_ylim(zz0, zz1)
    ins.tick_params(labelsize=FS_S - 1.5, length=2)
    ins.set_title("zoom, true mm (axes not to the main scale)", fontsize=FS_S - 1.0, loc="left", pad=2)
    for sp in ins.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.8)
    # reference lines
    xl0, xl1 = -xe - 3, xe + 4
    ax.plot([xl0, xl1], [0, 0], color="0.35", lw=0.8, ls="-.", zorder=4)
    ax.plot([xl0, xl1], [zmid, zmid], color="#16a085", lw=0.9, ls="--", zorder=5)
    ax.annotate("", xy=(xl1 + 1, bz), xytext=(xl0, bz), zorder=6,
                arrowprops=dict(arrowstyle="-|>", color=C_BEAM, lw=1.6, shrinkA=0, shrinkB=0, mutation_scale=12))
    # right-hand labels
    xr = xe + 8
    kw = dict(fontsize=FS_S, ha="left", va="center", zorder=10)
    ax.annotate(f"beam z = +{mm(bz)} above aperture\ncentre{br('DERIVED')} (aperture half-height\n"
                f"{mm(zap)} minus {mm(cg.v('beam_below_aperture_top'))})",
                xy=(xl1, bz), xytext=(xr, 7.8), color="#a04000", arrowprops=dict(arrowstyle="-", color="#a04000", lw=0.7), **kw)
    ax.annotate(f"plate mid-gap z = +{mmx(zmid)}{br(tag_of('plate_mid_gap_above_aperture_centre'))} above\n"
                f"aperture centre (from the upper inset and\nthe gap). Beam is {mmx(g['beam_above_mid_gap'])} above "
                f"mid-gap{br('DERIVED')}",
                xy=(xl1 - 2, zmid), xytext=(xr, 3.0), color="#16a085",
                arrowprops=dict(arrowstyle="-", color="#16a085", lw=0.7), **kw)
    ax.annotate("window aperture centre, z = 0 (dash-dot)", xy=(xl1 - 4, 0), xytext=(xr, -1.8), color="0.3",
                arrowprops=dict(arrowstyle="-", color="0.4", lw=0.7), **kw)
    ax.annotate(f"GUARD: Al blocks (both ends), {cg.v('block_connection')}ed to\nthe shell, sitting directly on the top shell.\n"
                f"Thickness {mm(cg.v('block_thickness'))}. Gap-facing face recessed\n{mm(cg.v('block_recess'))}{br(bt)} from the collector "
                f"face\n(larger clear aperture; see zoom).\n"
                f"{mm(cg.v('block_gap'))} gaps to plate and to end wall{br(tag_of('block_gap'))}.", xy=(rb, ztop_i - 3), xytext=(xr, 16.0), color=COL[bt],
                arrowprops=dict(arrowstyle="-", color=COL[bt], lw=0.8), **kw)
    # plate insets from the aperture ledges (upper: measured; lower: implied by the gap, reading differs)
    vdim(ax, -40, g["upper_inner_z"], zap, "", "MEASURED")
    note(ax, f"upper plate inset from the\naperture top {mm(cg.v('upper_plate_inset_from_aperture_top'))}", (-40, (g["upper_inner_z"] + zap) / 2),
         (-64, 11.0), "MEASURED", fs=FS_S)
    li = cg.v("lower_inset_implied")
    vdim(ax, 41, -zap, g["lower_inner_z"], "", "DERIVED")
    note(ax, f"lower plate inset {mmx(li)}{br('DERIVED')} implied by the gap;\nreading "
         f"{mm(cg.v('lower_plate_inset_from_aperture_bottom'))}: plates not parallel", (41, (-zap + g["lower_inner_z"]) / 2),
         (xe + 8, -7.5), "DERIVED", ha="left", fs=FS_S)
    # left: aperture, beam below top, exterior height
    xa = -xe - 5
    vdim(ax, xa, -zap, zap, f"window aperture\nheight {mm(cg.v('window_aperture_h'))}\n(input and exit)", "MEASURED",
         ha="right", ty=-3.2, fs=FS_S)
    vdim(ax, xa - 15, zap, bz, f"beam {mm(cg.v('beam_below_aperture_top'))}\nbelow aperture top", "MEASURED", ha="right",
         ty=3.6, fs=FS_S)
    ax.plot([xa - 15 - 1, -xe], [zap, zap], color="0.5", lw=0.5, ls=":")
    vdim(ax, xa - 40, zbot_o, ztop_o, f"exterior height {pm('exterior_height')}", "MEASURED", dx=1.5, ha="right", rot=90)
    # beam to faces
    d_up, d_lo = g["beam_to_upper_inner_face"], g["beam_to_lower_inner_face"]
    vdim(ax, -26, bz, g["upper_inner_z"], f"beam to upper plate inner face {mm(d_up)}{br('DERIVED')}", "DERIVED", ty=3.3,
         fs=FS_S)
    vdim(ax, 26, bz, g["lower_inner_z"], f"beam to lower plate inner face {mm(d_lo)}{br('DERIVED')}", "DERIVED", ha="right",
         ty=-3.0, fs=FS_S)
    gt = tag_of("plate_gap")
    vdim(ax, 34, g["lower_inner_z"], g["upper_inner_z"], "", gt)
    tl = tols("plate_gap")
    ax.text(35, -3.4, f"gap {mmx(cg.v('plate_gap'))}{br(gt)}, inner face to inner face,\n"
            f"\u00b1 {tl[0]} mm at the beam track, \u00b1 {tl[1]} mm across\nthe width (plates not parallel)", fontsize=FS_S,
            color=COL[gt], va="center", ha="left", zorder=10)
    # plate faces to shell
    vdim(ax, -28, g["upper_outer_z"], ztop_i, "", "DERIVED")
    ax.text(-27, 10.5, f"upper plate outer face\nto shell {mm(g['upper_outer_face_to_shell'])}{br('DERIVED')}", fontsize=FS_S,
            color=COL["DERIVED"], va="center", ha="left", zorder=10)
    vdim(ax, -33, g["lower_outer_z"], zbot_i, "", "DERIVED")
    ax.text(-32, -9.5, f"lower plate outer face\nto shell {mm(g['lower_outer_face_to_shell'])}{br('DERIVED')}", fontsize=FS_S,
            color=COL["DERIVED"], va="center", ha="left", zorder=10)
    # plate labels
    ax.text(0, 15.5, f"UPPER plate = COLLECTOR (BNC centre pin)\nlength {mm(cg.v('upper_plate_length'))}, thickness {mm(t)}\n"
            + leff_text(g), ha="center", va="center", fontsize=FS_S)
    ax.text(0, -16.0, f"LOWER plate = HV (HV centre pin)\nlength {mm(cg.v('lower_plate_length'))}, thickness {mm(t)}",
            ha="center", va="center", fontsize=FS_S)
    ax.set_xlim(-xe - 52, xe + 62)
    ax.set_ylim(zbot_o - 4, ztop_o + 4)
    ax.set_aspect(ZX)
    ax.set_xlabel("x along the beam, downstream positive (mm)")
    ax.set_ylabel("z across the gap, up on MonC (mm)")
    ax.set_title(f"SIDE elevation (x-z) through the shell, MonC as mounted, z up. x is true scale; z is stretched x{ZX:g} "
                 f"(all numbers are true mm)", fontsize=10.5, fontweight="bold", loc="left")


def end_view(ax, g):
    zap = cg.v("window_aperture_h") / 2
    zmid = cg.v("plate_mid_gap_above_aperture_centre")
    yw = cg.v("plate_width") / 2
    ylo, yhi = g["shell_outboard_exterior_y"], g["shell_inboard_exterior_y"]
    tw = cg.v("shell_wall_thickness")
    ilo, ihi = ylo + tw, yhi - tw
    ztop_o, ztop_i = g["shell_top_outer_z"], g["shell_top_inner_z"]
    zbot_o, zbot_i = g["shell_bottom_outer_z"], g["shell_bottom_inner_z"]
    bz, by = g["beam_z"], g["beam_y"]
    sf = cg.slot_fit()
    s0, s1 = g["slot_y"]
    f0, f1 = g["slot_flat_y"]
    tw_tag = cg.PARAMS["shell_wall_thickness"].tag
    # shell cross-section and the far end wall (steel) with the machined slot (flat part + semicircular ends)
    rect(ax, ylo, yhi, zbot_o, ztop_o, "MEASURED", "#d7dbdd", lw=2.2, z=0.5, hatch=None)
    rect(ax, ilo, ihi, zbot_i, ztop_i, "ASSUMED", "#f2f3f4", lw=1.2, z=1, hatch=None)
    th = np.linspace(np.pi / 2, -np.pi / 2, 41)
    pts = [(f0, zap), (f1, zap)] + [(f1 + zap * np.cos(t), zap * np.sin(t)) for t in th] + [(f1, -zap), (f0, -zap)] \
        + [(f0 + zap * np.cos(t), zap * np.sin(t)) for t in np.linspace(-np.pi / 2, -3 * np.pi / 2, 41)]
    assert abs((s1 - s0) - sf["W"]) < 1e-6 and abs((f1 - f0) - sf["F"]) < 1e-6   # drawn slot = fitted slot
    ax.add_patch(Polygon(pts, closed=True, fc="white", ec="none", zorder=1.2))
    ax.plot([q[0] for q in pts] + [pts[0][0]], [q[1] for q in pts] + [pts[0][1]], color=COL["DERIVED"], lw=1.8, ls=":",
            zorder=1.3)
    ax.plot([s0, s1], [0, 0], color="0.35", lw=0.8, ls="-.", zorder=4)
    ax.text((ylo + yhi) / 2, ztop_o + 0.6, f"shell wall {mm(cg.v('shell_wall_thickness'))}{br(tw_tag)}", fontsize=FS_S,
            color=COL["ASSUMED"], ha="center", va="bottom")
    # plates, guard, lines
    rect(ax, -yw, yw, g["upper_inner_z"], g["upper_outer_z"], "MEASURED", C_UP, lw=1.6, z=3)
    rect(ax, -yw, yw, g["lower_outer_z"], g["lower_inner_z"], "MEASURED", C_LO, lw=1.6, z=3)
    bt = tag_of("block_recess")
    b0, b1 = g["block_y"]
    rect(ax, b0, b1, g["guard_z0"], ztop_i, bt, C_GUARD, lw=1.4, z=3.5, alpha=0.6)
    ax.plot([-yw, yw], [zmid, zmid], color="#16a085", lw=0.9, ls="--", zorder=5)
    ax.plot([0, 0], [-zap, zap], color="0.55", lw=0.6, ls=(0, (6, 3)), zorder=4)
    ax.plot([by], [bz], "o", color=C_BEAM, ms=7, mec="#a04000", zorder=9)
    ax.text(0, g["upper_outer_z"] + 0.4, f"UPPER plate = COLLECTOR, width {mm(cg.v('plate_width'))}", ha="center",
            va="bottom", fontsize=FS_S, zorder=9)
    ax.text((b0 + b1) / 2, (g["guard_z0"] + ztop_i) / 2 + 1.5,
            f"GUARD block seen end-on,\n{cg.v('block_connection')}ed to the shell\n"
            f"thickness {mm(cg.v('block_thickness'))}, on the top shell\nface recessed {mm(cg.v('block_recess'))}{br(bt)}\n"
            f"width {mm(g['block_width'])}{br('DERIVED')}\n(plate + {mm(cg.v('block_extra_inboard'))} inboard"
            f"{br(cg.PARAMS['block_extra_inboard'].tag)}\n+ {mm(cg.v('block_extra_outboard'))} outboard)",
            ha="center", va="center", fontsize=FS_S, zorder=9)
    ax.text(0, g["lower_outer_z"] - 0.8, f"LOWER plate = HV, width {mm(cg.v('plate_width'))}", ha="center", va="top",
            fontsize=FS_S, zorder=9)
    note(ax, f"beam: y = +{mm(by)}, z = +{mm(bz)}{br('DERIVED')}\n(into the page, downstream)", (by, bz), (by, -2.1),
         "MEASURED", fs=FS_S)
    gt = tag_of("plate_gap")
    vdim(ax, -yw - 3, g["lower_inner_z"], g["upper_inner_z"], "", gt)
    ax.text(-yw - 4.0, -2.6, f"gap {mmx(cg.v('plate_gap'))}{br(gt)}\n\u00b1 {tols('plate_gap')[0]} mm at beam track", fontsize=FS_S, color=COL[gt], va="center", ha="right",
            zorder=10)
    # slot apex distances to the exterior faces (fitted values; the raw readings are in the table)
    ha_ = g["shell_outboard_exterior_y"]
    hdim(ax, ylo, s0, 0.0, f"slot apex to outboard exterior\n{mm(sf['a_outboard'])}{br('DERIVED')}", "DERIVED", fs=FS_S)
    hdim(ax, s1, yhi, 0.0, "", "DERIVED")
    note(ax, f"slot apex to inboard\nexterior {mm(sf['b_inboard'])}{br('DERIVED')}", ((s1 + yhi) / 2, 0.0), (yhi + 12, -4.0),
         "DERIVED", fs=FS_S)
    # side clearances
    hdim(ax, ilo, -yw, 12.5, f"outboard side clearance\n{mm(g['side_clearance_outboard'])}{br('DERIVED')}\n"
         "(OUTBOARD = electronics-mount side)", "DERIVED", fs=FS_S)
    hdim(ax, yw, ihi, 12.5, "", "DERIVED")
    note(ax, f"inboard side\nclearance {mm(g['side_clearance_inboard'])}\n{br('DERIVED').strip()}", ((yw + ihi) / 2, 12.5),
         (yhi + 13, 15.0), "DERIVED", fs=FS_S)
    ax.text(0, -zap - 1.8, f"machined slot (dotted; input and exit): height {mm(cg.v('window_aperture_h'))}, semicircular ends\n"
            f"(r = {mm(zap)}); length {mm(sf['W'])}, flat {mm(sf['F'])}{br('DERIVED')} (reconciled, table at right);\n"
            f"plates centred on the slot{br(cg.PARAMS['plates_centred_on_slot'].tag)}", fontsize=FS_S, color=COL["DERIVED"],
            va="top", ha="center", zorder=9)
    hdim(ax, -yw, yw, zbot_i + 3.0, f"plate width {mm(cg.v('plate_width'))}", "MEASURED", dy=0.6, fs=FS_S)
    hdim(ax, ylo, yhi, zbot_o - 3.5, f"exterior width {pm('exterior_width')}", "MEASURED", va="top", dy=0.5)
    vdim(ax, ylo - 4, zbot_o, ztop_o, f"exterior height {pm('exterior_height')}", "MEASURED", dx=1.3, ha="right", rot=90)
    ax.set_xlim(ylo - 13, yhi + 24)
    ax.set_ylim(zbot_o - 8, ztop_o + 4)
    ax.set_aspect(1.0)
    ax.set_xlabel("y across the plate width, y = 0 at the plate width centre, +y inboard (mm); left/right sense not given")
    ax.set_ylabel("z across the gap, up on MonC (mm)")
    ax.set_title(f"END view (y-z) through the shell, looking downstream, TRUE SCALE 1:1 in y and z", fontsize=10.5,
                 fontweight="bold", loc="left")


def legend_panel(ax, g):
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    items = [("MEASURED", "what the user told us (unmarked in labels)"),
             ("INTERPRETED", "our reading of the user's words"),
             ("ASSUMED", "not given; placeholder needed to draw it"),
             ("UNKNOWN", "not known"),
             ("DERIVED", "computed from the values above")]
    handles = [Patch(fc="#f4f6f7", ec=COL[k], ls=LS[k], hatch=HATCH[k], lw=1.6, label=f"{k}: {d}") for k, d in items]
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=FS + 1, frameon=True,
                    title="Outline / label style = tag of the value", title_fontsize=FS + 1.5, handlelength=3.2,
                    handleheight=1.6)
    ax.add_artist(leg)
    ax.text(0.0, 0.50,
            "Wiring (MEASURED): upper plate = collector (BNC centre pin); lower plate = HV (HV centre pin);\n"
            f"HV ground and BNC ground both to the {cg.v('grounds')}; the Al guard blocks are {cg.v('block_connection')}ed to the shell.\n"
            f"Window (Kapton) modelled as {cg.v('window_bc')}ed{br(cg.PARAMS['window_bc'].tag)}.\n"
            "Orange arrow = beam; grey hatched = steel end wall; dash-dot grey = aperture centre (z = 0);\n"
            "dashed green = plate mid-gap; dotted blue = machined slot; light grey with dotted purple edge = shell\n"
            "top, bottom, side walls.\n"
            f"Consistency: plates read {mm(cg.v('upper_plate_end_clearance'))} (upper), {mm(cg.v('lower_plate_end_clearance'))} (lower) "
            f"end clearance; the exterior length implies\n{mm(g['upper_end_clearance_implied'])} and "
            f"{mm(g['lower_end_clearance_implied'])}. Wall to wall: plates give {mm(g['inner_length_from_lower_plate'])} (lower), "
            f"{mm(g['inner_length_from_upper_plate'])} (upper);\nthe exterior length gives {mm(g['inner_length'])}, drawn here.\n"
            f"Plates are centred on the slot ({cg.v('plates_centred_on_slot')}, ASSUMED), which puts the shell width centre\n"
            f"{mm(abs(g['shell_centre_y']))} outboard of the plate width centre [DERIVED].\n"
            f"Plate positions: upper inset {mm(cg.v('upper_plate_inset_from_aperture_top'))} from the aperture top (MEASURED); the lower plate\n"
            f"follows from the measured gap ({mmx(cg.v('plate_gap'))}); its reading ({mm(cg.v('lower_plate_inset_from_aperture_bottom'))}) differs from "
            f"the implied {mmx(cg.v('lower_inset_implied'))}\n(plates not parallel).\n"
            f"Superseded by-eye readings (not drawn): plate gap {mm(cg.v('plate_gap_reading'))}, plate bias "
            f"{mm(cg.v('plate_bias_reading'))}.",
            fontsize=FS_S + 0.5, va="top", ha="left", color="0.15", linespacing=1.35)


def table_panel(ax, g):
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    sf = cg.slot_fit()
    rows = [("outboard apex to exterior", cg.v("slot_apex_to_outboard_exterior"), sf["a_outboard"], sf["res_a"]),
            ("inboard apex to exterior", cg.v("slot_apex_to_inboard_exterior"), sf["b_inboard"], sf["res_b"]),
            ("slot length (with ends)", cg.v("slot_width_measured"), sf["W"], sf["res_W"]),
            ("flat part of the slot", cg.v("slot_flat_measured"), sf["F"], sf["res_F"])]
    tab = (f"Slot readings reconciled (slot_fit(); exterior width {mm(cg.v('exterior_width'))} held fixed; equal-weight\n"
           "least squares; fitted values are DERIVED; residual = fit - reading)\n"
           f"{'reading':27s}{'raw (mm)':>10s}{'fitted [DERIVED]':>18s}{'residual (mm)':>15s}\n"
           + "\n".join(f"{n:27s}{r:10.2f}{f:18.2f}{d:+15.2f}" for n, r, f, d in rows)
           + f"\nraw slot length from the apexes: {sf['W_from_apexes_raw']:.2f} mm; from flat + height: "
             f"{sf['W_from_flat_raw']:.2f} mm\n"
           f"drawn slot: {mm(sf['W'])} x {mm(cg.v('window_aperture_h'))}, end radius {mm(cg.v('window_aperture_h') / 2)}")
    ax.text(0.0, 1.0, tab, fontsize=FS_S, family="monospace", va="top", ha="left", color="0.1", linespacing=1.4,
            bbox=dict(fc="#f4f6f7", ec=COL["DERIVED"], lw=0.8, pad=4))
    ax.text(0.0, 0.0, "NOTE: MonP is the same design with vertical plates. Beam position, plate bias and\n"
            "crust were seen on MonC only. Wiring is assumed the same on MonP.",
            fontsize=FS + 0.5, va="bottom", ha="left", fontweight="bold", color="#922b21", linespacing=1.4)


def main(outdir=common.OUT):
    g = cg.derived()
    bx = cg.blocks_x()

    fig = plt.figure(figsize=(16, 31))
    gs = fig.add_gridspec(4, 2, height_ratios=[8.8, 7.4, 6.4, 4.0], hspace=0.2, wspace=0.14,
                          left=0.06, right=0.985, top=0.94, bottom=0.03)
    fig.text(0.06, 0.99, "CMC-custom ion chamber plates as described by the user (MonC, measured 2026-11-13)",
             fontsize=14, fontweight="bold", va="top")
    fig.text(0.06, 0.972, "Drawn to confirm we understood the hand measurements. Outline style and the bracket in each label "
             "say whether a value was MEASURED, INTERPRETED, ASSUMED, UNKNOWN or DERIVED. All dimensions in mm.",
             fontsize=9, va="top", color="0.25")

    top_view(fig.add_subplot(gs[0, 0]), "upper", g, bx)
    top_view(fig.add_subplot(gs[0, 1]), "lower", g, bx)
    side_view(fig.add_subplot(gs[1, :]), g, bx)
    end_view(fig.add_subplot(gs[2, :]), g)
    legend_panel(fig.add_subplot(gs[3, 0]), g)
    table_panel(fig.add_subplot(gs[3, 1]), g)

    return common.save(fig, "cmc_plates",
                       ["analysis/cmc_chamber_geometry.py (PARAMS, v(), derived(), blocks_x())",
                        "analysis/out/collection_length_cmc.csv (nominal, l_eff_mm)"], outdir)


if __name__ == "__main__":
    main(common.OUT)
