"""Figures: MonC experiment set 3 and the sweep-1 re-run (Experimenter, branch monc-dark).

  set3_response.png      A CAL linearity at 50 nA/V; B gain per range from CAL; C UNCAL vernier transfer
                         (fit, residuals, zoom near the clip); D UNCAL level groups; E sign A/B with the
                         EPICS readback; H near-clip recovery, per count.
  (The per-range dark figure moved to fig_ranges.py: darks_by_range.png, one axis.)

Same rules as fig_sweeps: strict count windows (loaders.step_window), EPICS readbacks per window,
S4 <= 1 count = clipped (own marker, never fitted), the step-log guard must pass.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

import loaders as L
from common import (PANEL_TITLE_IN, titled, header, zero_line, AQUA, BLUE, CLIP_COUNTS, CLIP_INK, GRAY, INK, INK2, ORANGE, T_POWER_ON,
                    V2F_HZ_PER_V, footer, hms, save, say)

YELLOW = "#eda100"
SPEC = 0.005          # SR570 gain accuracy spec, ±0.5 % (as quoted in normalization_proposal.md)


# ---------------------------------------------------------------- data
def assemble(lg, sweeps=("sweep2", "set3", "rerun1")):
    out, problems = {}, []
    for sw in sweeps:
        steps = L.load_steps(sw)
        stats = [L.step_stats(lg, s) for s in steps]
        problems += L.check_against_log(stats)
        d = {}
        prev_u = None
        for s in stats:
            st = s.step
            state = L.settings_during(lg, st.t_settled, st.t_end - 0.5)
            u = state["A3off_u_put"][0]
            d[st.step] = dict(stat=s, state=state, S=L.sens_nA_per_V(state), level=L.offset_level_nA(state),
                              u=u, sign=state["A3offset_sign"][1], on=state["A3offset_on"][1],
                              cal=state["A3offset_cal"][1], clipped=s.mean <= CLIP_COUNTS + 1e-9,
                              prev_u=prev_u)
            prev_u = u
        out[sw] = d
    return out, problems


def sem(p):
    s = p["stat"]
    return s.sd / np.sqrt(s.n) if s.n > 1 else 0.0


def is_baseline(p):
    return (p["S"] == 50 and p["level"] == 20 and p["cal"] == "UNCAL" and p["on"] == "ON"
            and p["u"] == 6 and p["sign"] == "+")


def counts_since_write(lg, st):
    """All counts from the step's first write to its end: (s since write, S4). Count end times."""
    m = (lg.scaler_t > st.t_start) & (lg.scaler_t <= st.t_end)
    return lg.scaler_t[m] - st.t_start, lg.S4[m]


# ---------------------------------------------------------------- panels
def panel_cal(ax, s3):
    dark_k = [k for k in ("A0", "A9") if s3[k]["on"] == "OFF" and s3[k]["S"] == 50]
    dark = np.mean([s3[k]["stat"].mean for k in dark_k])
    ks = [k for k in s3 if k.startswith("A") and k.endswith("nA")]
    lv = np.array([s3[k]["level"] for k in ks])
    for k in ks:
        assert s3[k]["cal"] == "CAL" and s3[k]["on"] == "ON" and s3[k]["S"] == 50, k
    f = np.array([s3[k]["stat"].mean for k in ks])
    nom = V2F_HZ_PER_V * lv / 50.0
    r = (f - dark) / nom - 1
    e = np.array([sem(s3[k]) for k in ks]) / nom
    ax.axhspan(-100 * SPEC, 100 * SPEC, color=GRAY, alpha=0.12, lw=0, label="SR570 spec ±0.5 %")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.errorbar(lv, 100 * r, yerr=100 * e, fmt="o", color=BLUE, ms=7, label="block A: CAL, 50 nA/V")
    # the same levels at 50 nA/V in block B (B50l = 10 nA, B50h = 50 nA)
    bk = [k for k in ("B50l", "B50h") if k in s3]
    db = s3["B50d"]["stat"].mean
    for k in bk:
        p = s3[k]
        nb = V2F_HZ_PER_V * p["level"] / 50.0
        ax.plot([p["level"] * 1.12], [100 * ((p["stat"].mean - db) / nb - 1)], "D", mfc="white", mec=BLUE,
                mew=1.5, ms=7, label="block B at 50 nA/V (dark B50d), drawn offset right" if k == bk[0] else None)
    for l_, r_, f_ in zip(lv, r, f):
        ax.annotate(f"S4 {f_:.0f}", (l_, 100 * r_), xytext=(6, -12 if r_ < -0.005 else 5),
                    textcoords="offset points", fontsize=7, color=INK2)
    ax.set_xscale("log")
    ax.set_xlabel("CAL offset level, nA (A3offset_num/unit readback)")
    ax.set_ylabel("(S4 − dark) / nominal − 1, %")
    ax.set_ylim(-1.6, 1.0)
    titled(ax, "(a) Bigger test signals give proportionally more counts; 10 nA is 1 % short", f"CAL offset linearity at 50 nA/V; dark = mean of A0, A9 = {dark:.1f} Hz")
    ax.text(0.02, 0.96, "nominal = 1e5 Hz/V × level / 50 nA/V (2 kHz … 100 kHz)", transform=ax.transAxes,
            fontsize=7, color=INK2, va="top")
    ax.legend(loc="lower left", fontsize=7)
    return dict(level=lv, ratio=1 + r, dark=dark)


def panel_gain(ax, s3):
    Ss = sorted({p["S"] for k, p in s3.items() if k.startswith("B") and k.endswith("h")})
    rows = []
    for S in Ss:
        tag = f"{S:g}"
        d, hi = s3[f"B{tag}d"], s3[f"B{tag}h"]
        nom = V2F_HZ_PER_V * hi["level"] / S
        dval = d["stat"].mean
        known = not d["clipped"]
        rows.append((S, (hi["stat"].mean - (dval if known else 0.0)) / nom - 1, known, hi["level"], hi["stat"].mean, dval))
    S = np.array([r[0] for r in rows])
    rr = np.array([r[1] for r in rows])
    known = np.array([r[2] for r in rows])
    ax.axhspan(-100 * SPEC, 100 * SPEC, color=GRAY, alpha=0.12, lw=0, label="SR570 spec ±0.5 %")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.plot(S[known], 100 * rr[known], "o", color=BLUE, ms=7, label="(S4 − offset-OFF dark) / nominal")
    if (~known).any():
        ax.plot(S[~known], 100 * rr[~known], "o", mfc="white", mec=CLIP_INK, mew=1.5, ms=7,
                label="dark clipped (unknown, taken as 0): upper bound on the ratio")
    for r in rows:
        ax.annotate(f"CAL {r[3]:g} nA", (r[0], 100 * r[1]), xytext=(0, 7), textcoords="offset points",
                    fontsize=6.5, ha="center", color=INK2)
    ax.set_xscale("log")
    ax.set_xlabel("SR570 sensitivity S, nA/V")
    ax.set_ylabel("ratio to nominal − 1, %")
    ax.set_ylim(-0.8, 0.8)
    titled(ax, "(b) Every gain setting keeps its ±0.5 % promise", "gain per range: CAL point at ≈1 V (≈100 kHz), block B")
    ax.legend(loc="lower left", fontsize=7)
    return dict(S=S, ratio=1 + rr)


def panel_vernier(ax, axz, axr, s3):
    ks = [k for k in s3 if k.startswith("C") and k[1:].lstrip("-").isdigit()]
    u = np.array([s3[k]["u"] for k in ks])
    y = np.array([s3[k]["stat"].mean for k in ks])
    clip = np.array([s3[k]["clipped"] for k in ks])
    for k in ks:
        assert s3[k]["S"] == 50 and s3[k]["level"] == 20 and s3[k]["cal"] == "UNCAL", k
    # Fit set as in analysis/monc_set3.py: f > 50 Hz and u <= 200 (clear of the knee and of full scale)
    fs = (~clip) & (y > 50) & (u <= 200)
    m, b = np.polyfit(u[fs], y[fs], 1)
    u0 = -b / m
    res = y - (m * u + b)
    ax.plot(u[~clip], y[~clip], "o", color=BLUE, ms=6, label="block C, UNCAL, 20 nA, 50 nA/V")
    ax.plot(u[clip], np.full(clip.sum(), CLIP_COUNTS), "v", mfc="white", mec=CLIP_INK, mew=1.5, ms=7,
            label="clipped: S4 ≤ 1 count")
    uu = np.linspace(u0, 1000, 50)
    ax.plot(uu, m * uu + b, "-", color=ORANGE, lw=1.2,
            label=f"fit {fs.sum()} pts (S4 > 50, u ≤ 200): {m:.2f} Hz/unit × (u − {u0:+.2f})")
    ax.set_xlabel("vernier u (readback)")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(c) The offset knob is a straight line up to 1000", "UNCAL vernier transfer, u = −10 … 1000")
    ax.legend(loc="upper left", fontsize=7)
    # residuals in % of the line, for unclipped points
    ok = ~clip & (m * u + b > 0)
    axr.axhline(0, color=INK2, lw=0.8)
    axr.plot(u[ok & fs], 100 * res[ok & fs] / (m * u + b)[ok & fs], "o", color=ORANGE, ms=5, label="in fit")
    axr.plot(u[ok & ~fs], 100 * res[ok & ~fs] / (m * u + b)[ok & ~fs], "o", mfc="white", mec=ORANGE,
             ms=5, label="not in fit")
    for ui, ri, yi in zip(u[ok], res[ok], (m * u + b)[ok]):
        if abs(100 * ri / yi) > 3:
            axr.annotate(f"u={ui:g}: {100 * ri / yi:+.0f} %", (ui, np.clip(100 * ri / yi, -9, 9)),
                         xytext=(5, 0), textcoords="offset points", fontsize=6.5, color=INK2)
    axr.set_ylim(-10, 10)
    axr.set_xscale("log")
    axr.set_xlim(6, 1300)
    axr.set_xlabel("vernier u (log; only unclipped points, u ≥ 8)")
    axr.set_ylabel("(data − fit) / fit, %")
    titled(axr, "How far each point misses the straight line, in percent", "residuals of the 8-point fit")
    axr.legend(loc="lower right", fontsize=6.5)
    # zoom near the clip
    axz.plot(u[~clip], y[~clip], "o", color=BLUE, ms=6)
    axz.plot(u[clip], np.full(clip.sum(), CLIP_COUNTS), "v", mfc="white", mec=CLIP_INK, mew=1.5, ms=7)
    uu = np.linspace(u0, 32, 20)
    axz.plot(uu, m * uu + b, "-", color=ORANGE, lw=1.2)
    axz.axvline(u0, color=ORANGE, lw=0.8, ls=":")
    axz.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
    bl = [(k, p) for k, p in s3.items() if is_baseline(p) and k[0] in "FR"]
    axz.plot([p["u"] for _, p in bl], [p["stat"].mean for _, p in bl], "D", color=BLUE, mfc="white", ms=6,
             label="baselines F0/F1/F2/R (u = 6 from above)")
    c6 = s3.get("C6")
    if c6:
        axz.annotate(f"C6 (from u = {c6['prev_u']:+.0f}, below): {c6['stat'].mean:.0f}", (6, CLIP_COUNTS),
                     xytext=(8, 30), textcoords="offset points", fontsize=6.5, color=CLIP_INK,
                     arrowprops=dict(arrowstyle="-", color=CLIP_INK, lw=0.6))
    axz.set_xlim(-12, 32)
    axz.set_ylim(-20, 1000)
    axz.set_xlabel("vernier u")
    titled(axz, "Starts above ~5.7", f"zoom: 0 Hz at u = {u0:+.2f}")
    axz.legend(loc="upper left", fontsize=6.5)
    out = dict(slope=m, intercept=b, u0=u0)
    for k in ("C500", "C1000"):
        if k in s3:
            out[f"ratio_{k}"] = s3[k]["stat"].mean / (m * s3[k]["u"] + b)
    return out


def panel_groups(ax, s3):
    ks = [k for k in s3 if k.startswith("D")]
    lv = sorted({s3[k]["level"] for k in ks})
    rows = []
    for l_ in lv:
        a50 = [s3[k] for k in ks if s3[k]["level"] == l_ and s3[k]["u"] == 50]
        a100 = [s3[k] for k in ks if s3[k]["level"] == l_ and s3[k]["u"] == 100]
        y50 = a50[0]["stat"].mean if a50 else np.nan
        y100 = a100[0]["stat"].mean if a100 else np.nan
        rows.append((l_, y50, y100, (y100 - y50) / 50 if a50 and a100 else np.nan))
    L_ = np.array([r[0] for r in rows])
    sl = np.array([r[3] for r in rows])
    ok = np.isfinite(sl)
    ax.plot(L_[ok], sl[ok], "o", color=BLUE, ms=8, label="slope (S4[u=100] − S4[u=50]) / 50")
    nom = V2F_HZ_PER_V * L_ / 1000 / 50
    ax.plot(L_, nom, ":", color=AQUA, marker="_", ms=12, lw=1.4, label="if the full scale were the level: level/1000 per unit")
    for r in rows:
        if np.isfinite(r[3]):
            ax.annotate(f"{r[3]:.1f} Hz/unit\n= {r[3] / V2F_HZ_PER_V * 50 * 1e3:.2f} pA/unit", (r[0], r[3]),
                        xytext=(7, -4), textcoords="offset points", fontsize=6.5, color=INK2, va="top")
        else:
            ax.annotate(f"{r[0]:g} nA: u=50 only, S4 {r[1]:.0f}", (r[0], nom[list(L_).index(r[0])]),
                        xytext=(-6, 12), textcoords="offset points", fontsize=6.5, color=INK2, ha="right")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("offset level, nA")
    ax.set_ylabel("vernier slope, Hz per unit")
    titled(ax, "(d) What one knob step is worth depends on the offset group", "UNCAL scale per level group, 50 nA/V (block D)")
    ax.legend(loc="upper left", fontsize=7)
    return rows


def panel_sign(ax, lg, s3):
    ks = [k for k in ("E0", "E1-", "E2+", "E3-", "E4+") if k in s3]
    x0 = 0
    for i, k in enumerate(ks):
        p = s3[k]
        st = p["stat"].step
        tt, vv = counts_since_write(lg, st)
        xs = x0 + tt
        win = (lg.scaler_t[(lg.scaler_t > st.t_start) & (lg.scaler_t <= st.t_end)] - L.COUNT_S >= st.t_settled)
        ax.plot(xs[~win], vv[~win], "o", mfc="white", mec=GRAY, ms=4)
        ax.plot(xs[win], vv[win], "o", color=BLUE if "-" not in st.writes else ORANGE, ms=4)
        ax.hlines(p["stat"].mean, xs[win][0], xs[win][-1], color=INK, lw=1.2)
        wrote = "sign −, u 100" if "offset_sign=-" in st.writes else (
            "sign +, u 100" if "offset_sign=+" in st.writes else "u 100")
        ax.text(x0 + 4, 3866, f"{k}\nwrote {wrote}\nread {p['sign']}, {p['u']:+.0f}\n"
                f"{p['stat'].mean:.1f} Hz", fontsize=6.5, ha="center", va="top",
                color=CLIP_INK if ("offset_sign=-" in st.writes and p["sign"] == "+") else INK)
        x0 += 8.5
    ax.set_ylim(3700, 3870)
    ax.set_xlabel("s since each step's first write (steps laid end to end)")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(e) Same settings, yet 1.4 % fewer counts after a detour through minus", "sign A/B (block E): EPICS read back sign + in every count window")
    ax.text(0.01, 0.03, "Writing sign − made the IOC set u = −100; the runner's u = 100 write then set the sign back to +.\n"
            "The −1.4 % follows the passage through (−, −100), not the sign read back while counting.  "
            "Open grey: counts before settling (not used).",
            transform=ax.transAxes, fontsize=6.8, color=INK2, va="bottom")


def panel_nearclip(ax, lg, rr):
    ks = [k for k in rr if k.startswith("H")]
    cols = {True: CLIP_INK, False: BLUE}
    over = []
    for k in ks:
        p = rr[k]
        if p["u"] != 6:
            continue
        st = p["stat"].step
        tt, vv = counts_since_write(lg, st)
        below = p["prev_u"] is not None and p["prev_u"] < 6
        c = cols[below]
        clip = vv <= CLIP_COUNTS
        ax.plot(tt[~clip], vv[~clip], "o-", color=c, ms=4, lw=0.8,
                label=f"{k}: u = +6 from u = {p['prev_u']:+.0f} ({'below' if below else 'above'})")
        ax.plot(tt[clip], vv[clip], "v", color=c, mfc="white", ms=5)
        first_ok = tt[~clip][0] if (~clip).any() else np.nan
        if below and np.isfinite(first_ok):
            nb = sum(1 for j in ks if j < k and rr[j]["u"] == 6 and rr[j]["prev_u"] is not None and rr[j]["prev_u"] < 6)
            ax.text(10.5, 13.4 - 2.0 * nb, f"{k}: clipped for {int(clip.sum())} counts; first unclipped count "
                    f"{first_ok:.0f} s after the write", fontsize=6.8, color=c)
        if vv.max() > 30:
            over.append(f"{k} {vv[0]:.0f}")
    ax.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
    z0 = L.v2f_zero(lg)
    zero_line(ax, z0, x_text=19.5, fontsize=6.5, label=f"V2F zero {z0['mean']:.2f} Hz (SR570 off)")
    ax.axvline(2, color=INK2, lw=0.8, ls=":")
    ax.text(2.2, 27, "runner's 2 s settle", fontsize=6.5, color=INK2)
    if over:
        ax.text(2.2, 25.5, "off scale, first count straddles the write from u = 20: " + ", ".join(over),
                fontsize=6.5, color=BLUE)
    ax.set_ylim(-1, 30)
    ax.set_xlabel("s since the write of u = +6 (count end times)")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    titled(ax, "(f) Coming up from below zero, the counter stays on the floor for about 10 s", "near-clip recovery at the baseline, per count (re-run block H)")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 0.06), fontsize=6.5)


def make_response(lg, data):
    s3, rr = data["set3"], data["rerun1"]
    fig = plt.figure(figsize=(14, 18))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[2.4, 3.0, 1.3, 2.6], hspace=0.42, wspace=0.2,
                  left=0.06, right=0.98, top=0.925, bottom=0.04)
    ax_a = fig.add_subplot(gs[0, 0]); ax_b = fig.add_subplot(gs[0, 1])
    gsc = gs[1, 0].subgridspec(1, 2, width_ratios=[2.0, 1], wspace=0.25)
    ax_c = fig.add_subplot(gsc[0, 0]); ax_cz = fig.add_subplot(gsc[0, 1])
    ax_cr = fig.add_subplot(gs[2, 0])
    ax_d = fig.add_subplot(gs[1:3, 1])
    ax_e = fig.add_subplot(gs[3, 0]); ax_f = fig.add_subplot(gs[3, 1])
    res = dict(cal=panel_cal(ax_a, s3), gain=panel_gain(ax_b, s3),
               vern=panel_vernier(ax_c, ax_cz, ax_cr, s3), groups=panel_groups(ax_d, s3))
    panel_sign(ax_e, lg, s3)
    panel_nearclip(ax_f, lg, rr)
    t0 = s3["F0"]["stat"].step.t_start
    t1 = rr["R"]["stat"].step.t_end
    ns = sorted({p["stat"].n for p in s3.values()})
    top = header(
        fig, 0.06,
        "Set 3 and the re-run: how accurate and how straight MonC's amplifier really is",
        "MonC SR570 (15IDC:A3): experiment set 3 and the sweep-1 re-run",
        f"Set 3 {hms(t0)}–{hms(s3['R']['stat'].step.t_end)} and re-run {hms(rr['F0']['stat'].step.t_start)}–{hms(t1)} CST, "
             "2026-11-12, SR570 live (on since 13:29:56).  Runs by the Experimenter (branch monc-dark); "
             f"step logs read from {', '.join(sorted(set(L.SOURCES.values())))}.\n"
             f"Each point: mean of the 1 s counts that started after the step's 2 s settle (n = {ns[0]}–{ns[-1]}); "
             "settings are EPICS readbacks during those counts.  S4 counts per 1.000 s count = Hz.  "
             "Clipped counts (S4 ≤ 1) are never fitted.\n"
             "Not shown: block B's low CAL points and two-point intercepts (intercepts unreliable where a level is 10 nA, see (a)).",
        extra_in=PANEL_TITLE_IN)
    gs.update(top=top)
    footer(fig, lg)
    p = save(fig, "set3_response.png")
    v = res["vern"]
    say(f"[set3] {p.name}: vernier {v['slope']:.2f} Hz/unit, zero u = {v['u0']:+.2f}, "
        f"C500 ratio {v.get('ratio_C500', float('nan')):.4f}, C1000 {v.get('ratio_C1000', float('nan')):.4f}")
    say("[set3] CAL ratios: " + ", ".join(f"{l:g} nA {r:.4f}" for l, r in zip(res["cal"]["level"], res["cal"]["ratio"])))
    say("[set3] gain ratios: " + ", ".join(f"{S:g} {r:.4f}" for S, r in zip(res["gain"]["S"], res["gain"]["ratio"])))
    return res


def make(lg: L.Logger):
    data, problems = assemble(lg)
    if problems:
        raise SystemExit("REFUSED: raw logger does not reproduce the step logs:\n  " + "\n  ".join(problems))
    make_response(lg, data)
