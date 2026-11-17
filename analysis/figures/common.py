"""Shared style, constants and provenance for the MonC figures."""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from loaders import ROOT, UTC_OFFSET_H  # noqa: E402

OUT = ROOT / "analysis" / "figures" / "out"
TZ = timezone(timedelta(hours=UTC_OFFSET_H), "CST")

# Signal chain constants, with provenance (see physics_note.md and monc_sweep1_results.md).
V2F_HZ_PER_V = 1e5          # N101VTF V2F, unipolar 0-10 V -> 0-1 MHz
CLIP_COUNTS = 1.0           # S4 <= 1 count per 1 s: V2F input at or below 0 V (clipped)
T_POWER_ON = 1794511796.0   # 13:29:56 CST, first S4 transient (5945) when the user switched MonC's SR570 on
T_A3INIT = 1794512235.0     # 13:37:15 CST, A3init processed: all EPICS settings re-sent

# Palette: validated reference categorical order (dataviz skill, references/palette.md, light).
BLUE = "#2a78d6"     # sweep 2, SR570 live
ORANGE = "#eb6834"   # fits
AQUA = "#1baf7a"     # nominal / expected
VIOLET = "#6250d6"   # MonP context
GRAY = "#8c8b86"     # sweep 1 control (SR570 off)
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
CLIP_INK = "#b3261e" # clipped counts: always with a distinct marker shape and a label

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 150,
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 8,
    "lines.linewidth": 1.6, "lines.markersize": 6,
})


ZERO_INK = "#6b6a65"
ZERO_LS = (0, (7, 2, 1.5, 2))   # dash-dot: distinct from the clip's dashed red line

INPUT_INK = "#8a2b78"  # hand-made change of what MonC's input is connected to (loaders.INPUT_CHANGES)


def input_marks(ax, t0, t1, label="none", y=None):
    """Mark each hand-made input change (loaders.INPUT_CHANGES) inside [t0, t1]: the handling interval
    filled and a solid line at its end. label: "none"; "tag" (C1 at height y, default just above the
    axes, for long windows whose header carries input_key); "full" (text in the panel at height y)."""
    from loaders import input_changes_during
    for c in input_changes_during(t0, t1):
        ax.axvspan(local(c["t0"]), local(c["t1"]), color=INPUT_INK, alpha=0.28, lw=0, zorder=0.5)
        ax.axvline(local(c["t1"]), color=INPUT_INK, lw=1.3, zorder=0.6)
        if label == "tag":
            ax.text(local(c["t1"]), 1.092 if y is None else y, f" {c['tag']}", transform=ax.get_xaxis_transform(),
                    fontsize=7.5, color=INPUT_INK, weight="bold", ha="left", va="bottom")
        elif label == "full":
            ax.text(local(c["t1"]), 0.5 if y is None else y, f" {c['tag']} {hms(c['t0'])}–{hms(c['t1'])}: {c['short']}\n"
                    f" before: {c['before']}\n after: {c['after']}", transform=ax.get_xaxis_transform(),
                    fontsize=7, color=INPUT_INK, va="center", ha="left", zorder=10,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.8))


def input_key(t0, t1, width=175) -> str:
    """Header lines naming each hand-made input change inside [t0, t1] (empty if none), wrapped to `width`."""
    import textwrap
    from loaders import input_changes_during
    return "\n".join(line for c in input_changes_during(t0, t1) for line in textwrap.wrap(
        f"Purple line {c['tag']} ({local(c['t0']):%d %b} {hms(c['t0'])}–{hms(c['t1'])}, handling shaded): "
        f"{c['short']}; no EPICS setting records it.  Before: {c['before']}.  After: {c['after']}.",
        width, break_on_hyphens=False))


def zero_line(ax, z: dict, x_text=None, text=True, fontsize=7.5, label=None):
    """V2F zero-input rate (SR570 off) as a reference line, distinct from the 1-count clip."""
    ax.axhline(z["mean"], color=ZERO_INK, lw=1.1, ls=ZERO_LS, zorder=1)
    if text:
        ax.text(0.995 if x_text is None else x_text, z["mean"] * 1.06 if ax.get_yscale() == "log" else z["mean"] + 0.4,
                label or f"V2F zero-input rate {z['mean']:.2f} Hz (SR570 off, n = {z['n']}): "
                         "below this line the SR570 output is < 0 V",
                transform=ax.get_yaxis_transform() if x_text is None else ax.transData,
                ha="right" if x_text is None else "left", va="bottom", fontsize=fontsize, color=ZERO_INK)


CLIP_TEXT = "clip: S4 ≤ 1 count (unipolar V2F floor, output well below 0 V)"


def header(fig, x: float, plain: str, tech: str, sub: str = "", gap_in: float = 0.15,
           extra_in: float = 0.0) -> float:
    """Figure header laid out from the top in inches: a plain-language (ELI5) headline, the technical
    title, then the explanatory lines. Returns the figure-fraction y available for the top of the
    axes block (below the header, `gap_in`, and `extra_in` for panel titles or a top axis)."""
    H = fig.get_figheight()
    y = 0.14
    fig.text(x, 1 - y / H, plain, fontsize=13.5, weight="bold", ha="left", va="top", color=INK)
    y += 0.30
    fig.text(x, 1 - y / H, tech, fontsize=10, ha="left", va="top", color=INK)
    y += 0.22
    if sub:
        fig.text(x, 1 - y / H, sub, fontsize=8.5, ha="left", va="top", color=INK2)
        y += (sub.count("\n") + 1) * 8.5 * 1.3 / 72
    return 1 - (y + gap_in + extra_in) / H


PANEL_TITLE_IN = 0.42   # height that titled() needs above an axes


def titled(ax, plain: str, tech: str, **_):
    """Panel title in two lines: plain-language (ELI5) in bold, the technical title below it."""
    ax.set_title(tech, loc="left", fontsize=8, color=INK2, pad=3)
    a = ax.annotate(plain, (0, 1), xycoords="axes fraction", xytext=(0, 3 + 8 * 1.35 + 2),
                    textcoords="offset points", fontsize=9.5, weight="bold", ha="left", va="bottom",
                    color=INK, annotation_clip=False)
    _TITLES.append((ax, a))


_TITLES: list = []


def check_titles(fig):
    """Warn (console) when a panel headline is wider than its panel, i.e. may run into a neighbour."""
    r = fig.canvas.get_renderer()
    for ax, a in [t for t in _TITLES if t[0].figure is fig]:
        w_txt = a.get_window_extent(r).width
        w_ax = ax.get_window_extent(r).width
        if w_txt > 1.04 * w_ax:
            say(f"WARNING headline wider than its panel ({w_txt / w_ax:.2f}x): {a.get_text()[:70]}")


def inlabel(ax, plain: str, where: str = "top"):
    """Plain-language label inside a stacked panel (no room for a title between stacked panels)."""
    y, va = (0.96, "top") if where == "top" else (0.05, "bottom")
    ax.text(0.004, y, plain, transform=ax.transAxes, fontsize=8, weight="bold", color=INK, va=va,
            ha="left", zorder=10, bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1.5))


def local(t: float) -> datetime:
    return datetime.fromtimestamp(t, TZ)


def hms(t: float) -> str:
    return local(t).strftime("%H:%M:%S")


def time_axis(ax, t0: float, t1: float) -> str:
    """HH:MM ticks on `ax`; a tick at midnight is written as the new date (e.g. '13 Nov'), so a record that
    crosses midnight says so on the axis. Returns the x-axis label with the dates the window covers."""
    import matplotlib.dates as mdates
    loc = mdates.AutoDateLocator(tz=TZ)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(
        loc, tz=TZ, formats=["%Y", "%b", "%d %b", "%H:%M", "%H:%M", "%S.%f"],
        zero_formats=["", "%Y", "%b", "%d %b", "%H:%M", "%H:%M"], show_offset=False))
    a, b = local(t0), local(t1)
    span = a.strftime("%Y-%m-%d") if a.date() == b.date() else \
        f"{a.strftime('%Y-%m-%d %H:%M')} to {b.strftime('%Y-%m-%d %H:%M')}"
    return f"time, CST (UTC−6), {span}"


def git_rev() -> str:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "analysis/figures"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return r.stdout.strip() + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def footer(fig, lg, extra: str = ""):
    """Provenance line: raw file, last count used, code revision, regeneration command."""
    txt = (f"raw: {lg.path.name} ({len(lg.scaler_t)} counts, last {local(lg.t_last):%Y-%m-%d %H:%M:%S} CST)"
           f"  |  code {git_rev()}  |  regenerate: python -I analysis/figures/make_figures.py"
           + (f"  |  {extra}" if extra else ""))
    fig.text(0.01, 0.004, txt, fontsize=6.5, color=INK2, ha="left", va="bottom")


def save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    check_titles(fig)
    fig.savefig(p)
    plt.close(fig)
    return p


ASCII = str.maketrans({"−": "-", "→": "->", "≈": "~", "±": "+/-", "×": "x", "≤": "<=",
                       "≥": ">=", "µ": "u", "σ": "sigma", "Δ": "d", "·": "*", "–": "-", "—": "-"})


def say(s: str):
    """Console output is ASCII only (cp1252 consoles); figure text keeps its glyphs."""
    print(s.translate(ASCII).encode("ascii", "replace").decode("ascii"))
