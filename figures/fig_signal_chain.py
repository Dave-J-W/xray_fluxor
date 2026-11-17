"""Signal chain: scaler counts -> photons/s at the MonP chamber exit -> RESULT with bounds.

Every PV name, transform letter, expression and constant on the figure is read from
  calc/lanes.py (build, rec, LANES), calc/monp_transform.py (W_EV, E_CHARGE, K_FLUX, L_CM, SLOT),
  calc/quality_slots.py (FLAG_BITS, severity).
Layout coordinates and colours are the only things typed here.
Run:  <bluesky venv>\\Scripts\\python.exe -I -X utf8 figures/fig_signal_chain.py
"""
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import plt, save  # noqa: E402
from lanes import LANES, build, rec  # noqa: E402
from monp_transform import W_EV, E_CHARGE, K_FLUX, L_CM  # noqa: E402
from quality_slots import FLAG_BITS, clcc as qs_clcc  # noqa: E402

LANE = "MonP"
WRAP = 52
LINE_H = 1.55      # data units per text line (1 unit = 0.1 in)
TITLE_H = 3.4
PAD = 2.2


def _pv(link):
    """'15IDC:util:userTran1.E NPP NMS' -> '15IDC:util:userTran1.E'."""
    return link.split()[0]


def _wrap(items, width=WRAP):
    out = []
    for kind, text in items:
        parts = textwrap.wrap(text, width=width, subsequent_indent="  ") or [""]
        out += [(kind, p) for p in parts]
    return out


def _height(items, width=WRAP):
    return PAD * 2 + TITLE_H + LINE_H * len(_wrap(items, width))


STYLE_OF = {"eq": dict(family="monospace", color="#0b3d91"),
            "pv": dict(family="monospace", color="#1b5e20"),
            "note": dict(family="sans-serif", color="#555555", style="italic"),
            "txt": dict(family="sans-serif", color="black")}


def box(ax, x, y, w, h, title, items, fc, width=WRAP, ec="0.25", ls="-"):
    """x, y = lower-left corner. Text flows from the top."""
    ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec=ec, lw=1.1, ls=ls, zorder=2))
    ax.text(x + 1.2, y + h - PAD, title, fontsize=8.6, fontweight="bold", va="top", ha="left", zorder=3)
    yy = y + h - PAD - TITLE_H
    for kind, text in _wrap(items, width):
        ax.text(x + 1.2, yy, text, fontsize=6.9, va="top", ha="left", zorder=3, **STYLE_OF[kind])
        yy -= LINE_H


def arrow(ax, p0, p1, rad=0.0, ls="-", color="0.15", label=None, lpos=(0, 0)):
    ax.annotate("", xy=p1, xytext=p0, zorder=4,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.4, ls=ls, shrinkA=0, shrinkB=0,
                                connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p0[0] + p1[0]) / 2 + lpos[0], (p0[1] + p1[1]) / 2 + lpos[1], label, fontsize=6.8,
                ha="center", va="center", color=color, zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.8))


def main(outdir=common.OUT):
    rows = {r: (d, f) for r, d, f, _, _ in build(LANE)}
    fl, bk, bd = rec(LANE, "flux"), rec(LANE, "bkg"), rec(LANE, "bounds")
    st, dk, fg = rec(LANE, "status"), rec(LANE, "dark"), rec(LANE, "flags")
    F, B, G = rows[fl][1], rows[bd][1], rows[fg][1]
    K = rows[bk][1]
    MC_B = {r: f for r, _, f, _, _ in build("MonC")}[rec("MonC", "bounds")]
    assert MC_B["CLCC"] == qs_clcc("MonC") and B["CLCC"] == qs_clcc(LANE)   # lanes.py and quality_slots agree
    short = lambda r: r.split(":")[-1]          # noqa: E731  userTran1
    v2f = W_EV / (E_CHARGE * 1e3) / K_FLUX      # Hz/V, backed out of K_FLUX = W/(e*1e3)/V2F
    sc, sr = LANES[LANE]["scaler"], LANES[LANE]["sr570"]

    # ---- the ten chain boxes: (title, items, colour) -----------------------------------------
    chain = [
        ("1  Scaler counts, count time",
         [("eq", "A = counts, B = count time (s)"),
          ("pv", f"A <- {_pv(F['INPA'])}"), ("pv", f"B <- {_pv(F['INPB'])}"),
          ("note", f"copied into {fl}.A and .B ({LANE} = scaler channel {sc})")], "#eef3fb"),
        ("2  Net rate (counts - background)",
         [("eq", f"J = {F['CLCJ']}"), ("note", "Hz; H = background, clamped at 0"),
          ("pv", f"J held in {fl}.J"), ("pv", f"H <- {_pv(F['INPH'])}")], "#eef3fb"),
        ("3  V2F voltage",
         [("eq", f"V = J / {v2f:.6g} Hz/V"),
          ("note", "no PV of its own: the V2F factor is folded into K_FLUX "
                   f"= W/(e*1e3)/V2F = {K_FLUX:.5e}"), ("pv", f"inside {fl}.P (CLC{'P'})")], "#eef3fb"),
        ("4  SR570 current",
         [("eq", f"I_A = V * S;  S = {F['CLCI']}"), ("note", "A/V, S from sensitivity index C and unit D"),
          ("pv", f"S held in {fl}.I"), ("pv", f"C <- {_pv(F['INPC'])}"), ("pv", f"D <- {_pv(F['INPD'])}")],
         "#eef3fb"),
        ("5  Ion pairs / s",
         [("eq", f"N_ip = I_A / e;  e = {E_CHARGE:.9e} C"),
          ("note", f"no PV of its own: e is inside K_FLUX"), ("pv", f"inside {fl}.P")], "#eef3fb"),
        ("6  Absorbed energy / s",
         [("eq", f"P_abs = N_ip * W;  W = {W_EV} eV / ion pair"),
          ("note", "no PV of its own: W is inside K_FLUX"), ("pv", f"inside {fl}.P")], "#eef3fb"),
        ("7  Photons / s entering the plates",
         [("eq", "Phi_in = P_abs / (E * O)"), ("eq", f"O = {F['CLCO']}"),
          ("note", f"fraction absorbed over the collection length l = l_eff = {L_CM:g} cm; M = mu_en/rho, K = density"),
          ("pv", f"O held in {fl}.O;  M in {fl}.M"), ("pv", f"E <- {_pv(F['INPE'])}")], "#eef3fb"),
        ("8  Photons / s at the exit",
         [("eq", f"P = {F['CLCP']}"), ("note", f"exit transmission exp(-l*N*K), l = l_eff = {L_CM:g} cm, N = mu/rho"),
          ("pv", f"P held in {fl}.P  (formula, NOT result)")], "#eef3fb"),
        ("9  Wall-loss correction",
         [("eq", f"{LANE} C = {B['CLCC']}"), ("eq", f"MonC C = {MC_B['CLCC']}"), ("eq", f"L = {B['CLCL']}"),
          ("note", "C = photoelectron signal lost to the plates (Monte Carlo fit); each lane has its own fit"),
          ("pv", f"C held in {bd}.C"), ("pv", f"B = E_eff held in {bd}.B")], "#fdf3e1"),
        ("10  RESULT with low / high bounds",
         [("eq", f"low  D = {B['CLCD']}"), ("eq", f"high E = {B['CLCE']}"), ("eq", "best L = A/(1-C)"),
          ("pv", f"RESULT {bd}.L ({B['EGU']})"), ("pv", f"low {bd}.D, high {bd}.E")], "#fbe3d4"),
    ]

    # ---- side inputs -------------------------------------------------------------------------
    side_bkg = ("Background estimator (no beam)",
                [("txt", f"{short(bk)}  ->  {short(dk)}  ->  {short(fl)}.H"),
                 ("eq", f"L = {K['CLCL']}"), ("pv", f"estimate {bk}.L (Hz)"),
                 ("note", f"{short(dk)} carries the status severity (MS link) onto the flux record")], "#e6f4ea")
    side_E = ("Mono energy",
              [("eq", f"E <- {_pv(F['INPE'])}"), ("note", "keV; also read by the bounds slot (INPB)"),
               ("pv", f"E held in {fl}.E")], "#e6f4ea")
    side_rho = ("Gas density from pressure and temperature",
                [("eq", f"K = {F['CLCK']}"), ("note", "g/cm3 N2; F = hutch temperature C, G = pressure kPa"),
                 ("pv", f"F <- {_pv(F['INPF'])}"),
                 ("pv", f"G = live pressure, set by the updater; {fl}.G"),
                 ("pv", f"K held in {fl}.K")], "#e6f4ea")
    sev_txt = ", ".join(f"{v}{'*' if 'MAJOR' in c else ''}" for v, _, _, c in FLAG_BITS)
    side_flags = ("Status flags",
                  [("pv", f"flags {fg}.L = sum of bits ({sev_txt}; * = MAJOR)"),
                   ("pv", f"status {st}.VAL (0 ok / 1 MINOR / 2 MAJOR)"),
                   ("note", "no flag blocks or changes the number: it only sets alarm severity")], "#e6f4ea")

    # ---- geometry ----------------------------------------------------------------------------
    BW, GAP = 34.0, 6.0
    xs = [3 + i * (BW + GAP) for i in range(5)]
    h1 = max(_height(c[1]) for c in chain[:5])
    h2 = max(_height(c[1]) for c in chain[5:])
    hs_top = _height(side_bkg[1])
    wide = 2 * BW + GAP
    hs_bot = max(_height(side_E[1]), _height(side_rho[1], 74), _height(side_flags[1], 74))
    ROWGAP, SIDEGAP = 16.0, 13.0
    y_flags = 20.0                                   # bottom band baseline (room for notes below)
    y2 = y_flags + hs_bot + SIDEGAP
    y1 = y2 + h2 + ROWGAP
    y_top = y1 + h1 + SIDEGAP
    top = y_top + hs_top + 9
    W_TOT = 3 + 5 * BW + 4 * GAP + 3

    fig = plt.figure(figsize=(W_TOT / 10, top / 10 + 0.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W_TOT)
    ax.set_ylim(0, top + 4)
    ax.axis("off")

    ax.text(2, top + 1.5,
            f"Signal chain, {LANE}: scaler counts -> photons/s at the chamber exit -> RESULT with bounds",
            fontsize=13, fontweight="bold", va="center")
    ax.text(2, top - 2.2,
            "Blue: formula in the live transform record. Green: side inputs. Orange: wall-loss correction and RESULT. "
            "Monospace = text read from calc/lanes.py; italic = note. "
            "This is the formula chain only, with no live values.",
            fontsize=8, va="center", color="0.3")

    # chain boxes
    pos = {}
    for i, (title, items, fc) in enumerate(chain):
        row, col = divmod(i, 5)
        y, h = (y1, h1) if row == 0 else (y2, h2)
        box(ax, xs[col], y, BW, h, title, items, fc)
        pos[i + 1] = (xs[col], y, BW, h)
    for i in range(1, 10):
        x, y, w, h = pos[i]
        x2, y2_, w2, h2_ = pos[i + 1]
        if i == 5:       # row 1 -> row 2: elbow down the gap
            ym = y1 - ROWGAP / 2
            ax.plot([x + w / 2, x + w / 2, x2 + w2 / 2], [y, ym, ym], color="0.15", lw=1.4, zorder=4)
            arrow(ax, (x2 + w2 / 2, ym), (x2 + w2 / 2, y2_ + h2_))
        else:
            arrow(ax, (x + w, y + h - 6), (x2, y2_ + h2_ - 6 if i > 5 else y2_ + h2_ - 6))
    # unit labels on the connectors
    units = {1: "counts, s", 2: "Hz", 3: "V", 4: "A", 6: "eV/s", 7: "ph/s", 8: "ph/s", 9: "ph/s"}
    for i, u in units.items():
        x, y, w, h = pos[i]
        ax.text(x + w + GAP / 2, y + h - 3.6, u, fontsize=6.8, ha="center", va="bottom", color="0.15")
    ax.text(pos[5][0] + BW / 2 + 1, y1 - ROWGAP / 2 + 1.0, "ion pairs/s", fontsize=6.8, color="0.15",
            ha="left", va="bottom")

    # top side input: background -> box 2
    bx, by = xs[1], y_top
    box(ax, bx, by, wide, hs_top, side_bkg[0], side_bkg[1], side_bkg[2], width=74)
    arrow(ax, (bx + BW / 2, by), (bx + BW / 2, y1 + h1), label="H, Hz", lpos=(5, 0))

    # bottom side inputs
    ex, dx, fx = xs[0], xs[1], xs[3]
    box(ax, ex, y_flags, BW, hs_bot, side_E[0], side_E[1], side_E[2])
    box(ax, dx, y_flags, wide, hs_bot, side_rho[0], side_rho[1], side_rho[2], width=74)
    box(ax, fx, y_flags, wide, hs_bot, side_flags[0], side_flags[1], side_flags[2], width=74)
    b6, b7, b8, b9, b10 = (pos[i] for i in (6, 7, 8, 9, 10))
    # E -> box 7 (diagonal across box 6's bottom); density -> boxes 7 and 8
    arrow(ax, (ex + BW * 0.85, y_flags + hs_bot), (b7[0] + 6, b7[1]), rad=-0.05, label="E, keV", lpos=(0, 0))
    arrow(ax, (dx + wide * 0.30, y_flags + hs_bot), (b7[0] + 24, b7[1]), label="K, g/cm3", lpos=(5, 0))
    arrow(ax, (dx + wide * 0.78, y_flags + hs_bot), (b8[0] + 17, b8[1]), label="K, g/cm3", lpos=(5, 0))
    arrow(ax, (fx + wide * 0.85, y_flags + hs_bot), (b10[0] + 17, b10[1]), ls="--", color="#b00020",
          label="alarm severity (MS links)", lpos=(0, 0))

    ax.text(2, 13.0,
            f"Constants (calc/monp_transform.py): W = {W_EV} eV/pair, e = {E_CHARGE:.9e} C, "
            f"K_FLUX = {K_FLUX:.5e}, collection length l = l_eff = {L_CM:g} cm (L_CM). "
            f"V2F = W/(e*1e3)/K_FLUX = {v2f:.6g} Hz/V is derived from these, not typed.",
            fontsize=7.5, va="center", color="0.25")
    mc = {r: f for r, _, f, _, _ in build("MonC")}
    ax.text(2, 9.5,
            f"MonC runs the same expressions on scaler channel {LANES['MonC']['scaler']} / SR570 {LANES['MonC']['sr570']} "
            f"(records {rec('MonC', 'flux')} ... {rec('MonC', 'bounds')}) and reads its pressure G "
            f"through INPG = {_pv(mc[rec('MonC', 'flux')]['INPG'])}.",
            fontsize=7.5, va="center", color="0.25")

    return save(fig, "signal_chain",
                ["calc/lanes.py", "calc/monp_transform.py", "calc/quality_slots.py"], outdir)


if __name__ == "__main__":
    print(main())
