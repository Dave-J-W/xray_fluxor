"""Figure: MonC SR570 sweep response by block (sweep 2 live; sweep 1 + 1b with the unit off as control).

Every point is recomputed from the raw 1 s logger record over the step's settled window
(loaders.step_window) and checked against the sweep runner's step log. Settings are the EPICS
readbacks from the logger during that window, not the plan, because the IOC rewrites some
fields (offset_sign follows the vernier sign).
"""
from __future__ import annotations

import numpy as np
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt

import loaders as L
from common import (PANEL_TITLE_IN, titled, header, zero_line, AQUA, BLUE, CLIP_COUNTS, CLIP_INK, GRAY, INK, INK2, ORANGE, V2F_HZ_PER_V,
                    footer, hms, save, say)


# ---------------------------------------------------------------- data assembly
def assemble(lg: L.Logger):
    """sweep -> step -> dict(stat, state, S, level, u, ...). Runs the step-log guard."""
    out, problems = {}, []
    for sw in L.SWEEP_FILES:
        steps = L.load_steps(sw)
        stats = [L.step_stats(lg, s) for s in steps]
        problems += L.check_against_log(stats)
        d = {}
        for s in stats:
            st = s.step
            # t_end (host clock) is taken just before the next step's writes, whose IOC stamps
            # can sort a few tens of ms earlier; 0.5 s margin keeps them out of this window.
            state = L.settings_during(lg, st.t_settled, st.t_end - 0.5)
            d[st.step] = dict(
                stat=s, state=state, S=L.sens_nA_per_V(state), level=L.offset_level_nA(state),
                u=state["A3off_u_put"][0], sign=state["A3offset_sign"][1],
                on=state["A3offset_on"][1], cal=state["A3offset_cal"][1],
                clipped=s.mean <= CLIP_COUNTS + 1e-9)
        out[sw] = d
    return out, problems


def nominal_Hz(p) -> float:
    """Plan's nominal S4 for a step, in Hz (= counts per 1 s count), from the readback state.

    offset ON, UNCAL: I = level x |u| / 1000  (plan: 40 Hz/unit at 20 nA, 50 nA/V)
    offset ON, CAL:   I = level
    offset OFF:       I = 0 (dark only)
    S4 = 1e5 Hz/V x I / S, for the sign that counts; the other sign clips at 0 Hz."""
    if p["on"] == "OFF":
        return 0.0
    I = p["level"] if p["cal"] == "CAL" else p["level"] * abs(p["u"]) / 1000.0
    return V2F_HZ_PER_V * I / p["S"]


def sweep1_control(data, step):
    """Sweep 1 / 1b value for the same step name (SR570 off), or None."""
    for sw in ("sweep1", "sweep1b"):
        if step in data[sw]:
            return data[sw][step]
    return None


def err(p):
    s = p["stat"]
    return s.sd / np.sqrt(s.n) if s.n > 1 else 0.0


def mark_clip(ax, xs, label=True):
    ys = np.full(len(xs), CLIP_COUNTS)
    ax.plot(xs, ys, linestyle="none", marker="v", mfc="white", mec=CLIP_INK, mew=1.5, ms=8,
            label="clipped: S4 ≤ 1 count (unipolar V2F floor, input < 0 V)" if label else None, zorder=5)


# ---------------------------------------------------------------- panels
def panel_vernier(ax, axz, axr, data):
    s2 = data["sweep2"]
    V = [k for k in ("V1", "V2", "V3", "V4", "V5", "V6", "V7")]
    u = np.array([s2[k]["u"] for k in V])
    y = np.array([s2[k]["stat"].mean for k in V])
    e = np.array([err(s2[k]) for k in V])
    clip = np.array([s2[k]["clipped"] for k in V])
    fit_set = (~clip) & (u > 0)
    # control: sweep 1 V block (unit off)
    c = [sweep1_control(data, k) for k in V]
    ax.plot([p["u"] for p in c], [p["stat"].mean for p in c], "s", color=GRAY, ms=5,
            label="sweep 1 (SR570 OFF): V2F zero-input rate ≈ 8.4 Hz")
    ax.errorbar(u[~clip], y[~clip], yerr=e[~clip], fmt="o", color=BLUE, ms=7, zorder=4,
                label=f"sweep 2 (SR570 live), mean of {s2['V2']['stat'].n} × 1 s counts")
    mark_clip(ax, u[clip])
    for k, ui, yi, ci in zip(V, u, y, clip):
        ax.annotate(k, (ui, yi), xytext=(4, 6 if not ci else -14), textcoords="offset points",
                    fontsize=7.5, color=INK2)
    # nominal
    uu = np.linspace(0, 105, 50)
    ax.plot(uu, V2F_HZ_PER_V * 20 * uu / 1000 / 50, ":", color=AQUA, lw=1.6,
            label="nominal (plan): 40 Hz/unit, 0 at u = 0")
    res = {}
    if fit_set.sum() >= 3:
        m, b = np.polyfit(u[fit_set], y[fit_set], 1)
        u0 = -b / m
        uu = np.linspace(u0, 105, 50)
        ax.plot(uu, m * uu + b, "-", color=ORANGE, lw=1.4,
                label=f"fit V2–V4: {m:.2f} Hz/unit × (u − {u0:+.2f})")
        r = y[fit_set] - (m * u[fit_set] + b)
        axr.axhline(0, color=INK2, lw=0.8)
        axr.plot(u[fit_set], r, "o", color=ORANGE, ms=6, label="fit points V2–V4")
        # baselines (u = 6, not in the fit): what the line predicts vs what was read
        bl = [k for k in ("R0", "B0", "R") if k in s2]
        ub = np.array([s2[k]["u"] for k in bl])
        yb = np.array([s2[k]["stat"].mean for k in bl])
        rb = yb - (m * ub + b)
        axr.plot(ub, rb, "D", color=BLUE, ms=5, label="baselines R0 / B0 / R at u = +6 (not in fit)")
        axr.annotate(" / ".join(f"{k} {v:+.1f}" for k, v in zip(bl, rb)) + " Hz", (ub[0], rb.max()),
                     xytext=(8, -4), textcoords="offset points", fontsize=7, color=INK2, va="top")
        axr.set_ylabel("data − fit, Hz")
        titled(axr, "How far each point misses that straight line", "residuals of the V2–V4 fit, Hz")
        axr.set_xlabel("vernier u (A3off_u_put readback), UNCAL, level 20 nA, 50 nA/V")
        axr.legend(loc="lower left", fontsize=7)
        axr.set_ylim(min(-10, r.min() - 3), max(25, rb.max() + 6))
        axr.text(0.99, 0.95, "3 points, 2 parameters → 1 degree of freedom: the fit residuals cannot test\n"
                 "linearity. The baselines (u = +6) test the line where it meets the clip.",
                 transform=axr.transAxes, fontsize=7, va="top", ha="right", color=INK2)
        res = dict(slope=m, intercept=b, u0=u0, resid=r,
                   baseline_resid=dict(zip(bl, rb)), pred_u6=m * 6 + b)
        # zoom near the zero crossing, own axis
        uu = np.linspace(u0, 12, 20)
        axz.plot(uu, m * uu + b, "-", color=ORANGE, lw=1.4, label="fit V2–V4, extrapolated")
        uu = np.linspace(0, 12, 20)
        axz.plot(uu, V2F_HZ_PER_V * 20 * uu / 1000 / 50, ":", color=AQUA, lw=1.4, label="nominal (plan)")
        axz.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
        axz.text(11.8, CLIP_COUNTS + 1.5, "clip: 1 count", fontsize=7, color=CLIP_INK, ha="right", va="bottom")
        zero_line(axz, ZERO, x_text=-0.8, fontsize=6.5, label=f"V2F zero {ZERO['mean']:.1f} Hz (SR570 off)")
        axz.plot(ub + np.array([-0.15, 0, 0.15])[:len(ub)], yb, "D", color=BLUE, ms=6,
                 label="baselines R0 / B0 / R (u = +6)")
        axz.plot([0], [CLIP_COUNTS], "v", mfc="white", mec=CLIP_INK, mew=1.5, ms=8, label="V1 (u = 0): clipped")
        c = [sweep1_control(data, k) for k in ("V1",)] + [data["sweep1"]["B0"]]
        axz.plot([p["u"] for p in c], [p["stat"].mean for p in c], "s", color=GRAY, ms=5,
                 label="sweep 1 V1, B0 (SR570 OFF)")
        axz.axvline(u0, color=ORANGE, lw=0.8, ls=":")
        axz.set_xlim(-1, 12)
        axz.set_ylim(-5, 80)
        axz.set_xlabel("vernier u")
        titled(axz, "Near zero: the floor", "zoom near the clip")
        axz.text(0.97, 0.42, f"line: 0 Hz at u = {u0:+.2f}\nbaselines at u = +6:\n"
                 f"{yb.min():.1f}–{yb.max():.1f} Hz", transform=axz.transAxes, ha="right",
                 fontsize=7.5, color=INK)
        axz.legend(loc="upper left", fontsize=6.5)
    else:
        ax.text(0.5, 0.5, "NO FIT: fewer than 3 unclipped points with u > 0", transform=ax.transAxes,
                ha="center", color=CLIP_INK)
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(a) Offset knob up: counts rise in a straight line", "UNCAL vernier: S4 vs u (one sign clips)")
    ax.legend(loc="upper left", fontsize=7)
    ax.set_xlim(-110, 110)
    axr.set_xlim(-110, 110)
    return res


def panel_gain(ax, axr, data):
    s2 = data["sweep2"]
    G = ["G1", "G2", "G3", "G4", "G5", "G6", "G7"]
    Z = {s2[k]["S"]: s2[k] for k in ("Z1", "Z2", "Z3", "Z4", "Z5", "Z6")}
    S = np.array([s2[k]["S"] for k in G])
    y = np.array([s2[k]["stat"].mean for k in G])
    nom = np.array([nominal_Hz(s2[k]) for k in G])
    o = np.argsort(S)
    c = [sweep1_control(data, k) for k in G]
    ax.plot([p["S"] for p in c], [p["stat"].mean for p in c], "s", color=GRAY, ms=5,
            label="sweep 1 (SR570 OFF)")
    ax.plot(S[o], nom[o], ":", color=AQUA, lw=1.6, marker="_", ms=10,
            label=f"plan's naive nominal: 1e5 Hz/V × {s2['G1']['level'] * abs(s2['G1']['u']) / 1000:g} nA / S")
    ax.plot(S[o], y[o], "o-", color=BLUE, lw=1.0, ms=7, label="sweep 2: offset ON, UNCAL u = +50, 20 nA")
    zs = np.array(sorted(Z))
    ax.plot(zs, [Z[s]["stat"].mean for s in zs], "o--", mfc="white", color=BLUE, lw=0.8, ms=6,
            label="sweep 2: offset OFF (dark, Z block)")
    for k, Si, yi in zip(G, S, y):
        ax.annotate(k, (Si, yi), xytext=(5, 3), textcoords="offset points", fontsize=7.5, color=INK2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(b) Changing the gain with the knob offset on: not a fair test of the gain", "UNCAL offset vs sensitivity S — NOT a gain test (gain: set3_response (b))")
    ax.text(0.99, 0.97, "The UNCAL offset at u = +50 is not 1 nA: set 3 C gives\n"
            "20.19 pA/unit with zero at u = +5.68 (≈ 0.89 nA), plus a\n"
            "range-dependent zero error. Ratios below are therefore not\n"
            "SR570 gain errors; CAL (set 3 B) puts the gain within 0.2 %.",
            transform=ax.transAxes, ha="right", va="top", fontsize=7, color=CLIP_INK)
    ax.legend(loc="lower left", fontsize=7)
    # ratio panel
    axr.axhline(1, color=INK2, lw=0.8)
    axr.plot(S[o], (y / nom)[o], "o", color=BLUE, ms=6, label="S4 / nominal")
    has_d = np.array([s in Z for s in S])
    yd = np.array([y[i] - Z[S[i]]["stat"].mean if has_d[i] else np.nan for i in range(len(S))])
    axr.plot(S[has_d], (yd / nom)[has_d], "o", mfc="white", color=BLUE, ms=6,
             label="(S4 − offset-OFF dark at same S) / nominal")
    for Si in S[~has_d]:
        axr.annotate("no dark at\nthis S", (Si, (y / nom)[S == Si][0]), xytext=(9, 0),
                     textcoords="offset points", fontsize=6.5, ha="left", va="center", color=INK2)
    axr.set_xscale("log")
    axr.set_xlabel("SR570 sensitivity S, nA/V (A3sens readback)")
    axr.set_ylabel("ratio to naive nominal")
    titled(axr, "Measured counts divided by what the plan expected", "ratio to the plan's naive nominal")
    axr.legend(loc="upper left", fontsize=7)
    axr.set_ylim(0.7, 1.6)
    return dict(S=S, y=y, nom=nom, ratio=y / nom, ratio_dark=yd / nom)


def panel_dark(ax, data):
    s2 = data["sweep2"]
    Zk = ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]
    S = np.array([s2[k]["S"] for k in Zk])
    y = np.array([s2[k]["stat"].mean for k in Zk])
    c = [sweep1_control(data, k) for k in Zk]
    ax.plot([p["S"] for p in c], [p["stat"].mean for p in c], "s", color=GRAY, ms=5,
            label="sweep 1 (SR570 OFF): V2F zero-input rate")
    ax.plot(S, y, "o", color=BLUE, ms=7, label="sweep 2: offset OFF")
    for k, Si, yi in zip(Zk, S, y):
        if k == "Z6":
            continue
        ax.annotate("Z1, Z6" if k == "Z1" else k, (Si, yi), xytext=(5, 3), textcoords="offset points", fontsize=7.5, color=INK2)
    a = s2["Z1"]
    ss = np.array([0.8, 650])
    ax.plot(ss, a["stat"].mean * a["S"] / ss, ":", color=AQUA, lw=1.4,
            label=f"if a pure input current: ∝ 1/S through Z1 ({a['stat'].mean * a['S'] / V2F_HZ_PER_V * 1e3:.1f} pA)")
    ax.plot(ss, [a["stat"].mean] * 2, "--", color=AQUA, lw=1.0,
            label="if a pure output voltage: flat through Z1")
    ax.set_xscale("log")
    ax.set_yscale("log")
    zero_line(ax, ZERO, x_text=0.85, fontsize=7, label=f"V2F zero-input rate {ZERO['mean']:.2f} Hz (SR570 off): output < 0 V below")
    ax.set_ylim(3, 5000)
    ax.set_xlabel("SR570 sensitivity S, nA/V")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(c) With the offset off, the leftover counts follow no simple rule across gains", "offset-OFF dark vs sensitivity: neither a current nor a voltage")
    ax.legend(loc="upper right", fontsize=7)
    return dict(S=S, y=y)


def panel_level(ax, data):
    s2 = data["sweep2"]
    keys = ["Z7", "L2", "L1", "L4", "L3"]   # Z7 is the only 1 nA-level step (u = +50, 50 nA/V)
    lv = np.array([s2[k]["level"] for k in keys])
    y = np.array([s2[k]["stat"].mean for k in keys])
    nom = np.array([nominal_Hz(s2[k]) for k in keys])
    for k in keys:
        p = s2[k]
        assert p["u"] == 50 and p["S"] == 50 and p["cal"] == "UNCAL" and p["on"] == "ON", k
    c = [sweep1_control(data, k) for k in keys]
    ax.plot([p["level"] for p in c], [p["stat"].mean for p in c], "s", color=GRAY, ms=5,
            label="sweep 1 (SR570 OFF)")
    ax.plot(lv, nom, ":", color=AQUA, marker="_", ms=12, lw=1.6, label="nominal: level × u/1000, u = +50")
    ax.plot(lv, y, "o", color=BLUE, ms=7, label="sweep 2: UNCAL u = +50, 50 nA/V")
    for k, l_, yi in zip(keys, lv, y):
        ax.annotate(f"{k}  {yi:.0f}", (l_, yi), xytext=(6, -10 if k != "L2" else 6),
                    textcoords="offset points", fontsize=7.5, color=INK2)
    ax.axvspan(0.7, 7, color=GRAY, alpha=0.10, lw=0)
    ax.axvspan(7.5, 70, color=BLUE, alpha=0.06, lw=0)
    ax.text(2.2, 6000, "1, 5 nA: same output", ha="center", fontsize=7.5, color=INK2)
    ax.text(23, 6000, "10, 20, 50 nA: same output", ha="center", fontsize=7.5, color=INK2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(3, 12000)
    ax.set_xlabel("offset level, nA (A3offset_num readback)")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(d) The knob's offset jumps in groups instead of following the level dial", "UNCAL level: the scale follows a range group, not the level")
    ax.legend(loc="lower right", fontsize=7)
    return dict(level=lv, y=y, nom=nom)


def panel_cal(ax, data):
    s2 = data["sweep2"]
    c1, c2 = s2["C1"], s2["C2"]
    dark = np.mean([s2[k]["stat"].mean for k in ("Z1", "Z6") if s2[k]["S"] == c1["S"]])
    nom = nominal_Hz(c1)
    v1 = c1["stat"].values
    rows = [(f"nominal: 1e5 Hz/V × {c1['level']:g} nA / {c1['S']:g} nA/V", nom, AQUA),
            ("nominal + offset-OFF dark at 50 nA/V (mean of Z1, Z6)", nom + dark, AQUA),
            (f"C1 measured (CAL, sign +): {c1['stat'].n} counts, values {sorted(set(v1.astype(int).tolist()))}",
             c1["stat"].mean, BLUE)]
    for i, (lab, v, col) in enumerate(rows):
        yy = len(rows) - i
        if col == AQUA:
            ax.plot([v], [yy], "|", color=col, ms=16, mew=2.5)
        else:
            ax.plot(v1, yy + np.linspace(-0.08, 0.08, len(v1)), "o", color=col, ms=6)
        ax.text(1953, yy + 0.3, lab, va="center", fontsize=7.5, color=INK)
        ax.text(v + 2, yy - 0.05, f"{v:.1f} Hz", va="center", ha="left", fontsize=7.5, color=INK2)
    d = c1["stat"].mean - (nom + dark)
    ax.set_yticks([])
    ax.set_xlim(1950, 2100)
    ax.set_ylim(-0.6, len(rows) + 0.75)
    ax.set_xlabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(e) The calibrated 1 nA offset gives exactly the counts it should", "CAL offset 1 nA at 50 nA/V: matches nominal once the dark is added")
    ctl = sweep1_control(data, "C1")["stat"].mean
    ax.text(0.99, 0.03,
            f"C1 − (nominal + dark) = {d:+.1f} Hz = {100 * d / (nom + dark):+.2f} %\n"
            f"C2 (CAL, sign −): S4 = {c2['stat'].mean:.1f} count → clipped (the sign that does not count)\n"
            f"sweep 1 C1 (SR570 OFF): {ctl:.1f} Hz (off scale)",
            transform=ax.transAxes, fontsize=7.5, color=INK2, va="bottom", ha="right")
    return dict(c1=c1["stat"].mean, nominal=nom, dark=dark, diff=d)


def panel_sign(ax, data, steps2):
    s2 = data["sweep2"]
    ax.axis("off")
    titled(ax, "(f) We asked for a minus sign; the control system flipped it back to plus", "sign block: what was written vs what EPICS read back while counting")
    hdr = ["step", "written (step log)", "readback: sign", "u", "S4, Hz"]
    xs = [0.0, 0.10, 0.52, 0.70, 0.82]
    yy = 0.86
    for x, h in zip(xs, hdr):
        ax.text(x, yy, h, fontsize=8, weight="bold", transform=ax.transAxes)
    wr = {s.step: s.writes for s in steps2}
    for k in ("S1", "S2", "S3"):
        p = s2[k]
        yy -= 0.13
        vals = [k, wr[k], p["sign"], f"{p['u']:+.0f}",
                f"{p['stat'].mean:.1f}" + ("  (clipped)" if p["clipped"] else "")]
        for x, v in zip(xs, vals):
            ax.text(x, yy, v, fontsize=8, transform=ax.transAxes, family="monospace",
                    color=CLIP_INK if (k == "S1" and x == 0.52) else INK)
    ax.text(0.0, yy - 0.2,
            "S1 asked for sign − but the readback during counting is +: the IOC rewrites offset_sign\n"
            "to follow the vernier's sign (seen for every u sign change in the logger). So this block\n"
            "never counted with sign ≠ sign(u); it cannot show whether the SR570 ignores the sign in UNCAL.\n"
            "S1 vs S3 (same readback state) differ by "
            f"{s2['S3']['stat'].mean - s2['S1']['stat'].mean:+.1f} Hz "
            f"({100 * (s2['S3']['stat'].mean - s2['S1']['stat'].mean) / s2['S3']['stat'].mean:+.1f} %): unexplained.",
            transform=ax.transAxes, fontsize=7.5, color=INK2, va="top")


# ---------------------------------------------------------------- figure
ZERO: dict = {}


def make(lg: L.Logger) -> dict:
    ZERO.update(L.v2f_zero(lg))
    data, problems = assemble(lg)
    if problems:
        raise SystemExit("REFUSED: raw logger does not reproduce the step logs:\n  " + "\n  ".join(problems))
    s2 = data["sweep2"]
    fig = plt.figure(figsize=(14, 17))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[3.2, 1.3, 3.0, 2.0], hspace=0.38, wspace=0.18,
                  left=0.06, right=0.98, top=0.915, bottom=0.04)
    gsa = gs[0, 0].subgridspec(1, 2, width_ratios=[2.3, 1], wspace=0.22)
    ax_a = fig.add_subplot(gsa[0, 0]); ax_az = fig.add_subplot(gsa[0, 1])
    ax_ar = fig.add_subplot(gs[1, 0])
    ax_b = fig.add_subplot(gs[0, 1]); ax_br = fig.add_subplot(gs[1, 1], sharex=ax_b)
    ax_c = fig.add_subplot(gs[2, 0]); ax_d = fig.add_subplot(gs[2, 1])
    ax_e = fig.add_subplot(gs[3, 0]); ax_f = fig.add_subplot(gs[3, 1])
    res = dict(vernier=panel_vernier(ax_a, ax_az, ax_ar, data), gain=panel_gain(ax_b, ax_br, data),
               dark=panel_dark(ax_c, data), level=panel_level(ax_d, data), cal=panel_cal(ax_e, data))
    panel_sign(ax_f, data, L.load_steps("sweep2"))
    ns = [p["stat"].n for k, p in s2.items() if k not in ("R0", "B0", "R")]
    nmin, nmax = min(ns), max(ns)
    t0 = s2["R0"]["stat"].step.t_start
    t1 = s2["R"]["stat"].step.t_end
    top = header(
        fig, 0.06,
        "Sweep 2: how MonC's counter answers each amplifier knob, now that the amplifier is switched on",
        "MonC (15IDC:A3 SR570 → V2F 1e5 Hz/V, unipolar → scaler1.S4): response to SR570 settings",
        f"Sweep 2, SR570 live, 2026-11-12 {hms(t0)}–{hms(t1)} CST; baseline 50 nA/V, offset 20 nA, UNCAL, u = +6.  "
             "Grey squares: the same steps in sweep 1 / 1b (13:09–13:23), run with the SR570 switched OFF (control).\n"
             f"Each point: mean of the 1 s counts that started after the step's 2 s settle (n = {nmin if nmin == nmax else f'{nmin}–{nmax}'} per step, "
             "more for baselines); sd/√n is smaller than the markers.  Settings are EPICS readbacks during the counts.\n"
             "S4 is an integer count per 1.000 s (S1 = 1e7 clock), so counts per count = Hz.  "
             "Fits use only unclipped points.",
        extra_in=PANEL_TITLE_IN)
    gs.update(top=top)
    footer(fig, lg)
    p = save(fig, "sweep2_response.png")
    v = res["vernier"]
    say(f"[sweeps] {p.name}: vernier slope {v['slope']:.2f} Hz/unit, zero crossing u = {v['u0']:+.2f}, "
        f"fit predicts {v['pred_u6']:.1f} Hz at u=+6 vs baselines "
        + ", ".join(f"{k} {s2[k]['stat'].mean:.1f}" for k in ("R0", "B0", "R")))
    say(f"[sweeps] CAL: C1 {res['cal']['c1']:.1f} Hz vs nominal+dark {res['cal']['nominal'] + res['cal']['dark']:.1f} Hz "
        f"({100 * res['cal']['diff'] / (res['cal']['nominal'] + res['cal']['dark']):+.2f} %)")
    say("[sweeps] gain ratio to nominal: " + ", ".join(
        f"{S:g} nA/V {r:.3f}" for S, r in sorted(zip(res["gain"]["S"], res["gain"]["ratio"]))))
    return res
