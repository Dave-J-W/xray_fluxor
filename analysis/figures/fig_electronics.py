"""Figures for the MonC electronics uncertainty assessment (Experimenter's ELECTRONICS_CONCLUSIONS.md on monc-dark).

  elec1_linearity.png     joint-fit residuals vs SR570 output voltage, every range, grids g1-g4
  elec2_range_scale.png   range scale factors per range, g1-g4 (repeatability)
  elec3_cal_levels.png    CAL level factors per level, g1-g4
  elec4_dark_scatter.png  overnight offset-OFF dark per range vs time; within-step vs pass-to-pass scatter
  elec5_dark_error.png    dark error as a fraction of signal vs count rate, three subtraction cases

All from the raw logger with strict count windows and EPICS readbacks (fig_night.night_rows), not from the runner's
logged means. The joint fit is monc-dark's analysis/monc_grid.py, re-implemented here and cross-checked:
    ratio = (f - dark) / (1e5 Hz/V * I / S),   dark = mean of that range's _d, _ub and _off in the SAME grid,
    ln(ratio) = a_range + b_level + c * V,     V = I / S (nominal SR570 output, volts),   mean(b_level) = 0.
Everything here is MonC's channel (SR570 15IDC:A3, V2F, scaler1.S4). MonP's electronics were never measured.
"""
from __future__ import annotations

import re

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

import loaders as L
from common import (CLIP_INK, GRAY, INK, INK2, footer, header, hms, inlabel, local, save, say, time_axis, titled)
from fig_night import night_rows
from fig_ranges import style

K_HZ_PER_V = 1e5
CAVEAT = ("MonC only: SR570 15IDC:A3 → V2F → scaler1.S4.  MonP's electronics (15IDC:A2 → S3) were never measured; "
          "nothing here applies to them.")
GRID_MARK = {1: "o", 2: "s", 3: "^", 4: "D"}
WARM = 1                     # grid 1 ran ~2.5 h after power-on: drawn grey, kept out of the g2-g4 summaries
THRESH_LIGHT_HZ = 400.0      # Experimenter's operating rule: below 400 cps the record counts as dark
GAIN_CHANGE_HZ = 4e5         # Experimenter's operating rule: change gain above 400 kHz
INTERIM_HZ = None            # computed: mean S4 of the interim holds


def _rng(S):
    return f"{S:g} nA/V" if S < 1000 else f"{S / 1000:g} µA/V"


def _lev(nA):
    return f"{nA:g} nA" if nA < 1000 else f"{nA / 1000:g} µA"


# ---------------------------------------------------------------- grid data and joint fit
def grid_points(rows):
    """{grid: dict(pts=[...], dark={S: Hz})}. A ladder point is a CAL, ON, blank-OFF step named g<N>_<r>_<level>;
    its sensitivity and level come from the readback and must agree with the step name."""
    out = {}
    for g in sorted({int(m[1]) for r in rows if (m := re.match(r"g(\d+)_", r["step"]))}):
        gr = [r for r in rows if r["step"].startswith(f"g{g}_")]
        dark = {}
        for S in sorted({r["S"] for r in gr}):
            ds = [r for r in gr if r["S"] == S and re.search(r"_(d|ub|off)$", r["step"])]
            assert all(r["on"] == "OFF" for r in ds), [r["step"] for r in ds if r["on"] != "OFF"]
            dark[S] = (np.mean([r["stat"].mean for r in ds]), np.std([r["stat"].mean for r in ds], ddof=1), len(ds))
        pts = []
        for r in gr:
            m = re.fullmatch(rf"g{g}_(\d+)([nu])_(\d+)(nA|uA)", r["step"])
            if not m:
                continue
            S_name = float(m[1]) * (1 if m[2] == "n" else 1000)
            I_name = float(m[3]) * (1 if m[4] == "nA" else 1000)
            assert r["cal"] == "CAL" and r["on"] == "ON" and r["blank"] == "OFF", r["step"]
            assert abs(r["S"] - S_name) < 1e-6 and abs(r["level"] - I_name) < 1e-6, (r["step"], r["S"], r["level"])
            assert not r["clipped"] and not r["part"], r["step"]
            st = r["stat"]
            V = r["level"] / r["S"]
            f_sig = st.mean - dark[r["S"]][0]
            pts.append(dict(S=r["S"], I=r["level"], V=V, f=st.mean, sem=st.sem, n=st.n,
                            ratio=f_sig / (K_HZ_PER_V * V), t=r["t"]))
        out[g] = dict(pts=pts, dark=dark)
    return out


NOISY_DARK_S = 20000.0      # 20 µA/V: its offset-OFF dark jumps by up to ~40 Hz inside one step (elec4), so its
                            # ladder points carry a dark error of ~0.1-0.4 %; the second candidate fit leaves it out


def align(F, F0):
    """Put F0 (a fit on fewer ranges, so fewer CAL levels) on F's reference: the constraint mean(b) = 0 runs over
    different level sets, which shifts every b by a constant and every a by the opposite constant (a and b are
    degenerate). Shift F0 so that its levels shared with F have the same mean as in F. Changes no prediction."""
    shared = [I for I in F0["L"] if I in F["L"]]
    d = np.mean([F["b"][F["L"].index(I)] for I in shared]) - np.mean([F0["b"][F0["L"].index(I)] for I in shared])
    F0 = dict(F0, b=F0["b"] + d, a=F0["a"] - d)
    return F0


def joint_fit(pts, exclude=()):
    pts = [p for p in pts if p["S"] not in exclude]
    R = sorted({p["S"] for p in pts})
    Lv = sorted({p["I"] for p in pts})
    n, k = len(pts), len(R) + len(Lv) + 1
    A = np.zeros((n + 1, k))
    y = np.zeros(n + 1)
    w = np.ones(n + 1)
    for i, p in enumerate(pts):
        A[i, R.index(p["S"])] = 1
        A[i, len(R) + Lv.index(p["I"])] = 1
        A[i, -1] = p["V"]
        y[i] = np.log(p["ratio"])
    A[-1, len(R):len(R) + len(Lv)] = 1           # constraint: sum of level terms = 0
    w[-1] = 1e3                                   # held (almost) exactly
    sol, *_ = np.linalg.lstsq(A * w[:, None], y * w, rcond=None)
    res = y[:-1] - A[:-1] @ sol
    dof = n - (k - 1)
    s2 = float(res @ res) / dof
    cov = s2 * np.linalg.pinv((A * w[:, None]).T @ (A * w[:, None]))
    se = np.sqrt(np.diag(cov))
    partial = y[:-1] - A[:-1, :-1] @ sol[:-1]     # range and level removed, V term kept
    return dict(pts=pts, R=R, L=Lv, a=sol[:len(R)], b=sol[len(R):-1], c=sol[-1], se_a=se[:len(R)],
                se_b=se[len(R):-1], se_c=se[-1], res=res, partial=partial, rms=float(np.std(res)), dof=dof)


# ---------------------------------------------------------------- figure 1: linearity
def _scatter(ax, fit, yv, g, legend):
    pts = fit["pts"]
    V = np.array([p["V"] for p in pts])
    err = np.array([p["sem"] / (p["ratio"] * K_HZ_PER_V * p["V"]) for p in pts])
    for S in fit["R"]:
        m = np.array([p["S"] == S for p in pts])
        col, mk, lab = style(S)
        c = GRAY if g == WARM else col
        ax.errorbar(V[m], 100 * yv[m], yerr=100 * err[m], fmt=mk, color=c, ms=5 if g != WARM else 4,
                    mfc=c if g != WARM else "white", mec=c, elinewidth=0.6, capsize=0, ls="none",
                    alpha=0.9 if g != WARM else 0.7, label=(lab if legend and g == 2 else None),
                    zorder=3 if g != WARM else 2)


def make_linearity(lg, F, F0):
    """F: every range (monc_grid.py's model); F0: the same fit without 20 µA/V (NOISY_DARK_S)."""
    fig = plt.figure(figsize=(15, 14))
    gs = GridSpec(3, 1, figure=fig, height_ratios=[1.15, 0.9, 0.9], hspace=0.5, left=0.07, right=0.78, bottom=0.06)
    axp = fig.add_subplot(gs[0])
    axr0 = fig.add_subplot(gs[1], sharex=axp)
    axr = fig.add_subplot(gs[2], sharex=axp)
    vv = np.linspace(0, 4.6, 50)
    for g in sorted(F):
        _scatter(axp, F0[g], F0[g]["partial"], g, legend=False)
        _scatter(axr0, F0[g], F0[g]["res"], g, legend=False)
        _scatter(axr, F[g], F[g]["res"], g, legend=True)
        axp.plot(vv, 100 * F0[g]["c"] * vv, "-" if g != WARM else ":", color=INK if g != WARM else GRAY, lw=1.0,
                 label=f"g{g}: c = {100 * F0[g]['c']:+.4f} ± {100 * F0[g]['se_c']:.4f} %/V "
                       f"(all ranges: {100 * F[g]['c']:+.4f} ± {100 * F[g]['se_c']:.4f})"
                       + ("  warm-up" if g == WARM else ""))
        axp.text(4.62, 100 * F0[g]["c"] * 4.6, f"g{g}", fontsize=7.5, va="center",
                 color=INK if g != WARM else GRAY)
    for ax in (axp, axr0, axr):
        ax.axhline(0, color=INK2, lw=0.6)
        ax.set_xlim(0, 4.85)
    lim = 1.15 * max(np.max(np.abs(F[g]["res"])) for g in F) * 100
    axr0.set_ylim(-lim, lim)
    axr.set_ylim(-lim, lim)
    axp.set_ylabel("ln(ratio) − range − level, %\n(output-voltage term left in)")
    axr0.set_ylabel("residual, %")
    axr.set_ylabel("residual, %")
    axr.set_xlabel("SR570 output voltage V = I / S (nominal), volts      (signal above dark: 100 kHz per volt, so 4 V = 400 kHz)")
    axp.legend(loc="upper left", fontsize=7.5, frameon=False, title="slope c of each grid (fit without 20 µA/V)",
               title_fontsize=7.5)
    hp, lp = axr.get_legend_handles_labels()
    fig.legend(hp, lp, loc="upper left", bbox_to_anchor=(0.79, 0.70), fontsize=8,
               title="range: hue = decade, marker = 1/2/5\ngrids g2–g4 filled; g1 grey open (warm-up)",
               title_fontsize=7.5, frameon=False)
    titled(axp, "Does MonC's reading stay proportional to the current up to 4.5 V?",
           "(a) fit without 20 µA/V, output-voltage term kept: slope = c; lines c·V per grid")
    titled(axr0, "Without the 20 µA/V points, almost nothing is left over",
           "(b) residuals of (a): ln(ratio) = range + level + c·V on 500 nA/V–10 µA/V")
    titled(axr, "With them, the misfit is mostly 20 µA/V, whose dark wanders inside a step",
           "(c) residuals of the same model on every range (monc_grid.py); error bars: counting sd of each step mean")
    for ax, FF, what in ((axr0, F0, "without 20 µA/V"), (axr, F, "every range")):
        ax.text(0.995, 0.05, f"rms residual, {what}: " + "  ".join(f"g{g} {100 * FF[g]['rms']:.4f} %" for g in sorted(FF))
                + f"   ({len(FF[2]['pts'])} points per grid)", transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7.5, color=INK, bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1))
    g24 = [g for g in F if g != WARM]
    c0 = [100 * F0[g]["c"] for g in g24]
    c1 = [100 * F[g]["c"] for g in g24]
    top = header(fig, 0.07,
                 f"MonC's electronics are linear: over 0–4.5 V the response bends by at most {max(c0) * 4.5:.2f} %",
                 "MonC CAL-ladder linearity, overnight grids g1–g4 (2026-11-12/13): two candidate fits",
                 "ratio = (S4 − dark) / (1e5 Hz/V × I / S); dark = mean of the same grid's _d, _ub, _off steps at that range "
                 "(the dark changes each time a range is selected).  Strict count windows, EPICS readbacks.\n"
                 "Fit ln(ratio) = a_range + b_level + c·V with mean(b) = 0 (monc_grid.py on monc-dark).  Gain and mean CAL "
                 "level are degenerate: only their product (the range scale) is fixed.\n"
                 f"Output-voltage term c, g2–g4: {min(c0):+.4f} to {max(c0):+.4f} %/V without 20 µA/V; {min(c1):+.4f} to "
                 f"{max(c1):+.4f} %/V with it (its dark error, not the V2F, sets that spread; see elec4).\n" + CAVEAT,
                 extra_in=0.35)
    gs.update(top=top)
    footer(fig, lg)
    return save(fig, "elec1_linearity.png")


# ---------------------------------------------------------------- figures 2 and 3: factors per range / level
def _factor_fig(lg, F, F0, which, name, plain, tech, plain_a, note):
    """Small multiples, one panel per range (which='a') or CAL level ('b'): exp(term) − 1 per grid from the
    all-range fit (markers ± 1 standard error) and from the fit without 20 µA/V (red bars). Every panel has the
    SAME y span around its own g2–g4 mean, so grid-to-grid spreads compare directly; the centre is in its title."""
    keys = F[2]["R"] if which == "a" else F[2]["L"]

    def vals(FF, g):
        ks = FF[g]["R"] if which == "a" else FF[g]["L"]
        return {k: (100 * (np.exp(v) - 1), 100 * s) for k, v, s in zip(ks, FF[g][which], FF[g]["se_" + which])}

    g24 = [g for g in sorted(F) if g != WARM]
    centre, spread, spread0 = {}, [], []
    need = 0.0
    for k in keys:
        v = [vals(F, g)[k][0] for g in g24]
        centre[k] = float(np.mean(v))
        spread.append(max(v) - min(v))
        v0 = [vals(F0, g)[k][0] for g in g24 if k in vals(F0, g)]
        if v0:
            spread0.append(max(v0) - min(v0))
        for FF in (F, F0):
            for g in F:
                if k in vals(FF, g):
                    y, s = vals(FF, g)[k]
                    need = max(need, abs(y - centre[k]) + s)
    half = 1.2 * need
    n = len(keys)
    fig = plt.figure(figsize=(max(13, 2.1 * n + 2), 8.2))
    gs = GridSpec(1, n, figure=fig, left=0.07, right=0.86, bottom=0.12, wspace=0.12)
    axs = []
    for i, k in enumerate(keys):
        ax = fig.add_subplot(gs[i], sharey=axs[0] if axs else None)
        axs.append(ax)
        for g in sorted(F):
            c = GRAY if g == WARM else INK
            if k in vals(F, g):
                y, s = vals(F, g)[k]
                ax.errorbar([g], [y - centre[k]], yerr=[s], fmt=GRID_MARK[g], color=c, ms=7,
                            mfc="white" if g == WARM else c, mec=c, capsize=0, elinewidth=0.9, ls="none",
                            label=f"g{g}" + (" (warm-up)" if g == WARM else ""), zorder=3)
            if k in vals(F0, g):
                ax.plot([g], [vals(F0, g)[k][0] - centre[k]], "_", color=CLIP_INK, ms=16, mew=1.8, ls="none",
                        label="fit without 20 µA/V", zorder=4)
        ax.axhline(0, color=INK2, lw=0.5)
        if which == "a":
            ax.set_facecolor((*plt.matplotlib.colors.to_rgb(style(k)[0]), 0.07))
        ax.set_xlim(0.4, 4.6)
        ax.set_xticks([1, 2, 3, 4])
        ax.set_xticklabels(["g1", "g2", "g3", "g4"], fontsize=7.5)
        nm = _rng(k) if which == "a" else _lev(k)
        v0 = [vals(F0, g)[k][0] for g in g24 if k in vals(F0, g)]
        ax.set_title(f"{nm}\ncentre {centre[k]:+.3f} %\ng2–g4 span {spread[len(axs) - 1]:.3f} %"
                     + (f"\n(w/o 20 µA/V: {max(v0) - min(v0):.3f})" if v0 else "\n(not in that fit)"),
                     fontsize=8, color=INK, loc="center")
        if i:
            plt.setp(ax.get_yticklabels(), visible=False)
    axs[0].set_ylim(-half, half)
    axs[0].set_ylabel("factor − 1, minus the panel's centre, %\n(error bars: ±1 standard error from the fit)")
    h, l_ = axs[0].get_legend_handles_labels()
    seen = {}
    for hh, ll in zip(h, l_):
        seen.setdefault(ll, hh)
    fig.legend(list(seen.values()), list(seen), loc="upper left", bbox_to_anchor=(0.87, 0.75), fontsize=8,
               frameon=False, title="grid", title_fontsize=8)
    fig.text(0.465, 0.04, "overnight grid (g1 ran ~2.5 h after power-on)", ha="center", fontsize=9)
    top = header(fig, 0.07, plain, tech + ", overnight grids g1–g4",
                 note + f"\nLargest g2–g4 span: {max(spread):.3f} % with every range; {max(spread0):.3f} % in the fit "
                 "without 20 µA/V (whose dark wanders inside a step; see elec4), re-referenced to the CAL levels both fits share.  "
                 "Same y span in every panel.\n"
                 + CAVEAT, extra_in=1.0)
    gs.update(top=top)
    fig.text(0.07, top + 0.72 / fig.get_size_inches()[1], plain_a, fontsize=10, weight="bold",
             color=INK, va="bottom")
    footer(fig, lg)
    return save(fig, name), max(spread), max(spread0)


# ---------------------------------------------------------------- figure 4: overnight dark scatter
def pass_series(rows):
    """{label: [(t, mean, sd, n)]} for pass darks (unblanked), keyed by readback range; 5 µA/V split into its
    first and second reading of each pass (step names repeat, so by time order inside each pass)."""
    ser = {}
    for r in rows:
        m = re.fullmatch(r"p(\d+)_(\d+[nu])_d", r["step"])
        if not m or r["on"] != "OFF" or r["blank"] != "OFF":
            continue
        ser.setdefault((r["S"], int(m[1])), []).append(r)
    out = {}
    for (S, p), rs in sorted(ser.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        rs = sorted(rs, key=lambda r: r["t"])
        for j, r in enumerate(rs):
            key = (S, j + 1 if len(rs) > 1 else 0)
            out.setdefault(key, []).append((r["t"], r["stat"].mean, r["stat"].sd, r["stat"].n, r["clipped"] or r["part"],
                                            float(np.ptp(r["stat"].values))))
    return out


def series_stats(a):
    t, y, sd, n = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    th = (t - t[0]) / 3600
    p, cov = np.polyfit(th, y, 1, cov=True)
    d = y - np.polyval(p, th)
    lag1 = float(np.corrcoef(d[:-1], d[1:])[0, 1])
    return dict(mean=y.mean(), sd=y.std(ddof=1), slope=p[0], se_slope=np.sqrt(cov[0, 0]), lag1=lag1,
                within=float(np.median(sd)), sem=float(np.median(sd / np.sqrt(n))), n=len(y),
                sd_diff=float(np.std(np.diff(y), ddof=1) / np.sqrt(2)), p2p95=float(np.percentile(a[:, 5], 95)))


def make_dark_scatter(lg, rows, PS):
    keys = list(PS)
    fig = plt.figure(figsize=(16, 13))
    gs = GridSpec(len(keys), 2, figure=fig, width_ratios=[2.3, 1], hspace=0.12, wspace=0.28,
                  left=0.07, right=0.97, bottom=0.06)
    t0 = min(r["t"] for r in rows) - 120
    t1 = max(r["t"] for r in rows) + 120
    stats = {}
    axs = []
    for i, k in enumerate(keys):
        S, j = k
        a = np.array(PS[k], float)
        assert not a[:, 4].any(), f"clipped pass dark in {k}"
        st = stats[k] = series_stats(a)
        ax = fig.add_subplot(gs[i, 0], sharex=axs[0] if axs else None)
        axs.append(ax)
        col, mk, lab = style(S)
        lab = lab + ({1: " (1st of pass)", 2: " (2nd of pass)"}.get(j, ""))
        dev = a[:, 1] - st["mean"]
        ax.axhspan(-st["sd"], st["sd"], color=col, alpha=0.12, lw=0)
        ax.axhspan(-st["sem"], st["sem"], color=INK, alpha=0.25, lw=0)
        ax.plot([local(x) for x in a[:, 0]], dev, mk + "-", color=col, ms=3.5, lw=0.7, mec="white", mew=0.3)
        ax.axhline(0, color=INK2, lw=0.5)
        lim = max(4 * st["sd"], np.max(np.abs(dev)) * 1.15)
        ax.set_ylim(-lim, lim)
        ax.text(0.003, 0.93, f"{lab}: mean {st['mean']:.1f} Hz", transform=ax.transAxes, fontsize=7.5, weight="bold",
                va="top", color=INK, bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))
        ax.text(0.997, 0.93, f"slope {st['slope']:+.2f} ± {st['se_slope']:.2f} Hz/h   lag-1 r {st['lag1']:+.2f}",
                transform=ax.transAxes, fontsize=7, ha="right", va="top", color=INK,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))
        ax.tick_params(labelsize=7)
        if i < len(keys) - 1:
            plt.setp(ax.get_xticklabels(), visible=False)
    axs[len(keys) // 2].set_ylabel("dark − its overnight mean, Hz  (each row its own scale)")
    axs[-1].set_xlim(local(t0), local(t1))
    axs[-1].set_xlabel(time_axis(axs[-1], t0, t1))
    titled(axs[0], "Each gain's no-signal count, every pass: the scatter dwarfs any slow creep",
           "(a) pass darks minus their mean; light band ±1 sd across passes, dark band ±1 sd of one step mean")
    # summary
    axs2 = fig.add_subplot(gs[:, 1])
    y = np.arange(len(keys))[::-1]
    for yy, k in zip(y, keys):
        st, col = stats[k], style(k[0])[0]
        axs2.plot([st["sem"], st["sd"]], [yy, yy], "-", color=GRAY, lw=1)
        axs2.plot(st["within"], yy, "|", color=INK2, ms=12, mew=1.5)
        axs2.plot(st["p2p95"], yy, "x", color=CLIP_INK, ms=7, mew=1.4)
        axs2.plot(st["sem"], yy, "o", color=INK, ms=6)
        axs2.plot(st["sd"], yy, "s", color=col, ms=8, mec=INK, mew=0.5)
        axs2.text(st["sem"] / 1.35, yy, f"{st['sd'] / st['sem']:.0f}×", va="center", ha="right", fontsize=8,
                  color=INK)
    axs2.set_xscale("log")
    axs2.set_yticks(y)
    axs2.set_yticklabels([style(k[0])[2] + ({1: " (1st)", 2: " (2nd)"}.get(k[1], "")) for k in keys], fontsize=8)
    axs2.set_xlabel("Hz (log)")
    axs2.set_xlim(0.03, 100)
    axs2.set_ylim(-0.6, len(keys) + 1.4)
    axs2.plot([], [], "o", color=INK, label="sd of one step mean (counting, within step ÷ √n)")
    axs2.plot([], [], "|", color=INK2, ms=10, mew=1.5, label="sd of the 1 s counts within a step (median)")
    axs2.plot([], [], "s", color=GRAY, mec=INK, label="sd across the 92 passes (range re-selected each time)")
    axs2.plot([], [], "x", color=CLIP_INK, ms=7, mew=1.4,
              label="wander inside one step: 95th percentile of max − min of its 1 s counts")
    axs2.legend(loc="upper left", fontsize=7, frameon=False)
    titled(axs2, "The spread comes from re-selecting the gain",
           "(b) spreads per range; label = pass-to-pass sd ÷ step-mean sd")
    lag = [stats[k]["lag1"] for k in keys]
    kmax = max(keys, key=lambda k: abs(stats[k]["slope"]))
    sl = abs(stats[kmax]["slope"])
    sl_rel = sl / stats[kmax]["mean"]
    n_pass = max(stats[k]["n"] for k in keys)
    t_a = min(PS[k][0][0] for k in keys)
    t_b = max(PS[k][-1][0] for k in keys)
    top = header(fig, 0.07,
                 f"MonC's no-signal count is set each time a gain is selected; overnight it creeps by "
                 f"{sl:.1f} Hz/h at most",
                 f"MonC offset-OFF darks, {n_pass} dark passes {local(t_a):%Y-%m-%d %H:%M} to {local(t_b):%m-%d %H:%M} "
                 "(pass darks, output not blanked)",
                 f"Lag-1 correlation of successive passes (linear trend removed): {min(lag):+.2f} to {max(lag):+.2f}, so "
                 "neighbouring passes are no more alike than distant ones: the spread is not slow drift.\n"
                 f"Slopes ± 1 standard error are per row; the largest, {sl:.2f} Hz/h, is {100 * sl_rel:.2f} % of that dark per hour.  So a dark must be measured after the last gain change; a dark from an "
                 "earlier selection\nof the same range carries the pass-to-pass spread.  " + CAVEAT, extra_in=0.35)
    gs.update(top=top)
    footer(fig, lg)
    return save(fig, "elec4_dark_scatter.png"), stats


# ---------------------------------------------------------------- figure 5: dark error vs count rate
def same_selection_5u(rows):
    """Pairs (2nd 5 µA/V dark of a pass, the unblanked dark ~30 s later): same gain selection, only a blank/unblank
    between them. Returns (sd of one reading from the pair differences, n pairs, r between the two)."""
    by = {}
    for r in rows:
        m = re.fullmatch(r"p(\d+)_5u_(d|ub)", r["step"])
        if m and r["S"] == 5000 and r["on"] == "OFF" and r["blank"] == "OFF":
            by.setdefault(int(m[1]), []).append(r)
    a, b = [], []
    for p_, rs in by.items():
        rs = sorted(rs, key=lambda r: r["t"])
        ub = [r for r in rs if r["step"].endswith("_ub")]
        if ub and len(rs) >= 2 and rs[-2]["step"].endswith("_d"):
            a.append(rs[-2]["stat"].mean)
            b.append(ub[-1]["stat"].mean)
    a, b = np.array(a), np.array(b)
    return float(np.std(a - b, ddof=1) / np.sqrt(2)), len(a), float(np.corrcoef(a, b)[0, 1]), float(np.mean(b - a))


SETTLE_S = 120.0            # skip after the last setting change, or after the end of handling
BLOCK_S = 300               # 5-min means: the uncertainty of a window mean comes from their scatter
INTERIM_STATE = {"A3sens_num": "5", "A3sens_unit": "uA/V", "A3offset_num": "2", "A3offset_unit": "nA",
                 "A3offset_on": "ON", "A3offset_cal": "CAL", "A3offset_sign": "+", "A3blank_on": "OFF"}


def _window(lg, a, b):
    m = (lg.scaler_t - 1.0 >= a) & (lg.scaler_t <= b)
    v = lg.S4[m]
    nb = len(v) // BLOCK_S
    blocks = v[: nb * BLOCK_S].reshape(nb, BLOCK_S).mean(1)
    sem = float(np.std(blocks, ddof=1) / np.sqrt(nb)) if nb >= 3 else float("nan")
    return dict(t0=a, t1=b, n=len(v), mean=float(v.mean()), sd=float(v.std(ddof=1)), sem=sem, nb=nb)


def interim_before_after(lg, tag="C1"):
    """The interim setting just before and just after input change `tag` (chamber disconnected). Each window is
    checked against the EPICS readback and against INTERIM_STATE. Returns None (and says why) if the record
    can't support it. The drop is what the chamber connection added to the interim reading; whether that is a
    current is decided by leak_fit(), not here."""
    c = next((c for c in L.INPUT_CHANGES if c["tag"] == tag), None)
    if c is None:
        return None
    ch = sorted(t for pv in L.A3_STATE_PVS for t, *_ in lg.settings.get(pv, []) if t > lg.t_first + 0.5)
    a0 = max([t for t in ch if t < c["t0"]] + [max(s.t_end for s in L.load_steps("night"))]) + SETTLE_S
    a1 = c["t0"] - 1.0
    b0 = c["t1"] + SETTLE_S
    nxt = [t for t in ch if t > c["t1"]]
    b1 = nxt[0] - 1.0 if nxt else lg.t_last
    if a1 - a0 < 1800 or b1 - b0 < 1800:
        say(f"[electronics] interim before/after {tag}: not computed (a window under 30 min: before {(a1 - a0) / 60:.0f} min, "
            f"after {(b1 - b0) / 60:.0f} min)")
        return None
    for a, b in ((a0, a1), (b0, b1)):
        st = L.settings_during(lg, a, b)
        bad = {pv: (st[pv][1], want) for pv, want in INTERIM_STATE.items() if st[pv][1] != want}
        if bad:
            raise SystemExit(f"REFUSED interim before/after: window {hms(a)}-{hms(b)} is not at the interim setting: {bad}")
    A, B = _window(lg, a0, a1), _window(lg, b0, b1)
    return dict(change=c, before=A, after=B, d_hz=A["mean"] - B["mean"], se_hz=float(np.hypot(A["sem"], B["sem"])),
                open=not nxt)


LEAK = "leak"          # the Experimenter's run with the chamber unplugged (plan monc_leak_plan.csv on monc-dark)
REF_PASSES = 10        # reference: the last 10 overnight passes (chamber cabled)


def leak_fit(lg, rows):
    """Is the drop on unplugging the chamber a current? A current I at the SR570 input changes S4 by 1e5·I/S, so it
    scales as 1/S; an offset after the input doesn't. For each offset-OFF, unblanked dark in the leak run:
    drop = (mean of the same range over the last REF_PASSES overnight passes) − (leak reading). Fit
    drop = c + 1e5·I/S over the ranges where neither side clips and the dark is quiet (not 20 µA/V, F9).
    Also the blanked 5 µA/V reading and the interim hold. Returns None if the leak run isn't there."""
    if LEAK not in L.SWEEP_FILES:
        say("[electronics] leak run not found: elec5 can't say whether the connection offset is a current")
        return None
    steps = L.load_steps(LEAK)
    stats = [L.step_stats(lg, s) for s in steps]
    bad = L.check_against_log(stats)
    if bad:
        raise SystemExit("REFUSED: raw logger does not reproduce the leak step log:\n  " + "\n  ".join(bad))
    passes = sorted({int(r["step"].split("_")[0][1:]) for r in rows if r["block"] == "pass_dark"})[-REF_PASSES:]
    inref = lambda r: re.fullmatch(r"p(\d+)_.*", r["step"]) and int(r["step"].split("_")[0][1:]) in passes
    ref = {}
    for r in rows:
        if inref(r) and not r["clipped"] and not r["part"]:
            k = (r["S"], r["on"], r["blank"]) if r["on"] == "OFF" else (r["S"], "hold", r["blank"])
            ref.setdefault(k, []).append(r["stat"].mean)
    x, y, blank, hold, clipped = [], [], [], [], set()
    for s in stats:
        st = L.settings_during(lg, s.step.t_settled, s.step.t_end - 0.5)
        S, on, bl = L.sens_nA_per_V(st), st["A3offset_on"][1], st["A3blank_on"][1]
        k = (S, on, bl) if on == "OFF" else (S, "hold", bl)
        if k not in ref:
            continue
        if s.clipped_frac > 0:
            clipped.add(S)
            continue
        d = float(np.mean(ref[k])) - s.mean
        if on == "ON":
            hold.append(d)
        elif bl == "ON":
            blank.append((S, d))
        elif S != NOISY_DARK_S:
            x.append(K_HZ_PER_V / S)
            y.append(d)
    x, y = np.array(x), np.array(y)
    A_ = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(A_, y, rcond=None)
    res = y - A_ @ coef
    cov = np.linalg.inv(A_.T @ A_) * (res @ res) / (len(y) - 2)
    Ss = sorted({K_HZ_PER_V / v for v in x})
    return dict(c=float(coef[0]), se_c=float(np.sqrt(cov[0, 0])), I_pA=float(coef[1]) * 1e3,
                se_I_pA=float(np.sqrt(cov[1, 1])) * 1e3, n=len(y), S_lo=min(Ss), S_hi=max(Ss),
                blank=blank, hold=hold, clipped=sorted(clipped), passes=passes,
                t0=steps[0].t_start, t1=steps[-1].t_end)


def make_dark_error(lg, rows, stats):
    holds = [r["stat"].mean for r in rows if r["block"] == "interim_hold"]
    hold = float(np.mean(holds))
    hold_sd = float(np.std(holds, ddof=1))
    s_same, n_same, r_same, d_same = same_selection_5u(rows)
    ba = interim_before_after(lg)
    lf = leak_fit(lg, rows)
    a_line = (f"(a) {len(holds)} interim holds of 480 s overnight, chamber cabled, no beam: {hold:.1f} ± {hold_sd:.1f} Hz "
              "(sd across holds); none of it is beam.")
    if ba:
        A, B, c = ba["before"], ba["after"], ba["change"]
        say(f"[electronics] interim before/after {c['tag']}: before {hms(A['t0'])}-{hms(A['t1'])} {A['mean']:.2f} Hz "
            f"(sd {A['sd']:.2f}, 5-min sem {A['sem']:.2f}, n {A['n']}); after {hms(B['t0'])}-{hms(B['t1'])} {B['mean']:.2f} Hz "
            f"(sd {B['sd']:.2f}, sem {B['sem']:.2f}, n {B['n']}); drop {ba['d_hz']:.2f} +- {ba['se_hz']:.2f} Hz")
        hm = lambda t: local(t).strftime("%H:%M")
        a_line += (f"\n     About {ba['d_hz']:.1f} ± {ba['se_hz']:.1f} Hz of it came with the chamber connection: at the same "
                   f"setting S4 fell from {A['mean']:.2f} to {B['mean']:.2f} Hz ({hm(A['t0'])}–{hm(A['t1'])} vs "
                   f"{hm(B['t0'])}–{hm(B['t1'])}{', still accumulating' if ba['open'] else ''}; ± from 5-min means)\n"
                   f"     when the user unplugged the chamber ({c['tag']}, {hms(c['t0'])}–{hms(c['t1'])}; no SR570 setting changed).")
    if ba and lf:
        bd = np.array([d for _, d in lf["blank"]])
        bl = (f"5 µA/V blanked: {bd.mean():+.1f} Hz, {bd.min():+.1f} to {bd.max():+.1f} over {len(bd)} readings"
              if len(bd) else "no blanked reading")
        say(f"[electronics] leak fit: drop = c + 1e5*I/S over {_rng(lf['S_lo'])}-{_rng(lf['S_hi'])} (n {lf['n']}): "
            f"c {lf['c']:.2f} +- {lf['se_c']:.2f} Hz, I {lf['I_pA']:+.1f} +- {lf['se_I_pA']:.1f} pA; blanked {bl}; "
            f"hold {np.mean(lf['hold']):+.1f} Hz (n {len(lf['hold'])}); clipped without the chamber: "
            + ", ".join(_rng(S) for S in lf["clipped"]))
        a_line += (f"\n     It is NOT a current.  In the leak run with the chamber unplugged ({hms(lf['t0'])}–{hms(lf['t1'])}, "
                   f"vs the last {REF_PASSES} overnight passes) every range dropped by the same amount:\n"
                   f"     drop = c + 1e5·I/S over {_rng(lf['S_lo'])}–{_rng(lf['S_hi'])} gives "
                   f"c = {lf['c']:.1f} ± {lf['se_c']:.1f} Hz and I = {lf['I_pA']:+.0f} ± {lf['se_I_pA']:.0f} pA "
                   f"(a current giving {ba['d_hz']:.0f} Hz at 5 µA/V would drop {_rng(lf['S_lo'])} by "
                   f"{ba['d_hz'] * 5000 / lf['S_lo']:.0f} Hz).\n"
                   f"     The blanked reading dropped too ({bl}), so the offset does not enter at the SR570 input.\n"
                   f"     The remaining {B['mean']:.1f} Hz (cable end open) is the V2F zero (8.4 Hz), the SR570 output "
                   "offset and the CAL +2 nA (nominal 40 Hz), not separated here.\n")
    elif ba:
        a_line += ("\n     Whether that is a current or an offset after the input is NOT given: the leak run "
                   "(chamber unplugged, every range) is not in the record.\n")
    else:
        a_line += "  Its parts are NOT given: the record after the chamber was unplugged is too short.\n"
    fig = plt.figure(figsize=(15, 10))
    gs = GridSpec(1, 1, figure=fig, left=0.07, right=0.68, bottom=0.08)
    ax = fig.add_subplot(gs[0])
    f = np.logspace(2, 6, 200)
    ax.plot(f, 100 * hold / f, "-", color=INK, lw=2.4,
            label=f"(a) no subtraction, interim setting\n     (5 µA/V, CAL +2 nA, chamber cabled): {hold:.1f} Hz")
    ax.plot(f, 100 * s_same / f, "--", color=INK, lw=2.0,
            label=f"(b) dark measured at the same gain selection,\n     5 µA/V: ±{s_same:.2f} Hz")
    for k, st in stats.items():
        if k[1] == 2:
            continue
        col, mk, lab = style(k[0])
        ax.plot(f, 100 * st["sd"] / f, "-", color=col, lw=1.1)
        ax.plot(f[::25], 100 * st["sd"] / f[::25], mk, color=col, ms=5, ls="none",
                label=f"(c) earlier selection, {lab}: ±{st['sd']:.1f} Hz")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1e2, 1e6)
    ax.set_ylim(1e-5, 100)
    ax.axvspan(1e2, THRESH_LIGHT_HZ, color=GRAY, alpha=0.10, lw=0)
    ax.axvline(THRESH_LIGHT_HZ, color=INK2, lw=1, ls=":")
    ax.text(THRESH_LIGHT_HZ * 1.08, 40, f"400 cps: dark/light threshold\n(rule; below it the record\ncounts as dark)",
            fontsize=7.5, color=INK2, va="top")
    ax.axvspan(GAIN_CHANGE_HZ, 1e6, color=CLIP_INK, alpha=0.06, lw=0)
    ax.axvline(GAIN_CHANGE_HZ, color=CLIP_INK, lw=1, ls="--")
    ax.text(GAIN_CHANGE_HZ * 1.08, 40, "400 kHz: change gain\n(rule; no range is\nused above it)", fontsize=7.5,
            color=CLIP_INK, va="top")
    for pct in (1, 0.1, 0.01):
        ax.axhline(pct, color=GRAY, lw=0.5)
    ax.set_xlabel("MonC count rate from the beam (signal above dark), Hz")
    ax.set_ylabel("dark error as a fraction of the signal, % (log)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8, frameon=False, labelspacing=0.8)
    titled(ax, "How much does an uncorrected or stale dark bias the flux?",
           "(a)–(c): error / signal = dark error (Hz) / count rate (Hz); straight lines, not fits")
    top = header(fig, 0.07,
                 f"Leaving MonC's dark in costs {100 * hold / 1e3:.0f} % at 1 kHz but {100 * hold / GAIN_CHANGE_HZ:.3f} % "
                 "at 400 kHz; a fresh dark makes it negligible",
                 "MonC dark error vs count rate, from the overnight passes and interim holds",
                 a_line +
                 f"(b) {n_same} pairs, one per pass: the 2nd 5 µA/V dark and the unblanked dark ~30 s later (same selection, only a "
                 f"blank/unblank between): sd of one reading {s_same:.2f} Hz, r = {r_same:.2f}, mean change {d_same:+.2f} Hz.\n"
                 "(c) each range's sd across the 92 passes, where the range was re-selected each time (elec4).  "
                 "(b) and (c) were measured with the chamber cabled.  "
                 "The interim offset alone is "
                 f"{100 * hold / THRESH_LIGHT_HZ:.0f} % at the 400 cps threshold.\n" + CAVEAT,
                 extra_in=0.35)
    gs.update(top=top)
    footer(fig, lg)
    return save(fig, "elec5_dark_error.png"), hold, hold_sd


# ---------------------------------------------------------------- driver
def make(lg):
    if "night" not in L.SWEEP_FILES:
        say("[electronics] no overnight step log found; skipped")
        return
    rows = night_rows(lg)
    G = grid_points(rows)
    F = {g: joint_fit(G[g]["pts"]) for g in G}
    F0 = {g: align(F[g], joint_fit(G[g]["pts"], exclude=(NOISY_DARK_S,))) for g in G}
    lv = {I: np.mean([100 * (np.exp(F[g]["b"][F[g]["L"].index(I)]) - 1) for g in F if g != WARM]) for I in F[2]["L"]}
    for g, fit in F.items():
        say(f"[electronics] g{g}: {len(G[g]['pts'])} points, rms {100 * fit['rms']:.4f} %, "
            f"c {100 * fit['c']:+.4f} +- {100 * fit['se_c']:.4f} %/V; ranges "
            + " ".join(f"{_rng(S)} {np.exp(a):.5f}" for S, a in zip(fit["R"], fit["a"]))
            + "; levels " + " ".join(f"{_lev(I)} {np.exp(b):.5f}" for I, b in zip(fit["L"], fit["b"])))
    for g, fit in F0.items():
        say(f"[electronics] g{g} without 20 uA/V: {len(fit['pts'])} points, rms {100 * fit['rms']:.4f} %, "
            f"c {100 * fit['c']:+.4f} +- {100 * fit['se_c']:.4f} %/V")
    p1 = make_linearity(lg, F, F0)
    p2, s2, s20 = _factor_fig(lg, F, F0, "a", "elec2_range_scale.png",
                         "Each gain setting's scale factor repeats from grid to grid to a few hundredths of a percent",
                         "MonC range scale factors (gain × mean CAL level × V2F)",
                         "How far is each gain from its nominal value, and does it repeat?",
                         "exp(a_range) − 1: the range's scale relative to nominal 1e5 Hz/V × I / S, with the mean CAL level "
                         "folded in (gain and mean level are degenerate).")
    p3, s3, s30 = _factor_fig(lg, F, F0, "b", "elec3_cal_levels.png",
                         f"The SR570's built-in calibration currents differ from each other by up to "
                         f"{max(lv.values()) - min(lv.values()):.2f} %",
                         "MonC CAL offset level factors (each level relative to the mean level)",
                         "How far is each calibration current from its label, relative to the others?",
                         "exp(b_level) − 1, with mean(b) = 0: only relative levels are fixed by the ladder, "
                         "not the absolute current.")
    PS = pass_series(rows)
    p4, stats = make_dark_scatter(lg, rows, PS)
    p5, hold, hold_sd = make_dark_error(lg, rows, stats)
    for k, st in stats.items():
        say(f"[electronics] dark {_rng(k[0])}{'/' + str(k[1]) if k[1] else ''}: n {st['n']}, mean {st['mean']:.1f}, "
            f"sd {st['sd']:.2f} (from successive diffs {st['sd_diff']:.2f}), step-mean sd {st['sem']:.2f}, "
            f"slope {st['slope']:+.3f} +- {st['se_slope']:.3f} Hz/h, lag-1 r {st['lag1']:+.2f}, "
            f"in-step p2p 95th pct {st['p2p95']:.0f} Hz")
    say(f"[electronics] {p1.name}, {p2.name} (g2-g4 span max {s2:.3f} %, w/o 20u {s20:.3f}), {p3.name} (max {s3:.3f} %, w/o 20u {s30:.3f}), {p4.name}, "
        f"{p5.name}: interim hold {hold:.1f} +- {hold_sd:.1f} Hz")
