"""Figures across all live MonC runs, one axis each, sensitivity range as the series.

  darks_by_range.png   offset-OFF dark (S4, Hz) vs time since power-on, every range on ONE axis (log y).
                       Plus the dark-equivalent from the two CAL holds (S4 minus the nominal CAL offset).
  cal_ladders.png      (S4 - dark) / nominal - 1 (%) vs SR570 output voltage, every CAL point on ONE axis.

Encoding (the same in both figures): hue = decade group of the sensitivity, marker = its mantissa
(1 circle, 2 square, 5 triangle). Every series is also labelled directly, so identity never rests on
colour alone (the five-hue set is the reference palette's first five slots, which pass on adjacent
pairs; yellow and magenta are low-contrast on white and need the labels).

Rules as elsewhere: strict count windows, EPICS readbacks per window, S4 <= 1 = clipped (own marker,
never used as a value), step-log guard. Dark for a CAL point = mean of the nearest offset-OFF steps
before and after it at the same sensitivity in the same run (reproduces analysis/monc_ladders.py).
"""
from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

import loaders as L
from common import (header, CLIP_TEXT, CLIP_COUNTS, CLIP_INK, zero_line, GRAY, INK, INK2, T_POWER_ON, TZ, V2F_HZ_PER_V, footer, hms,
                    local, save, say)

HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # palette slots 1-5, fixed order
GROUPS = [(1, 5), (10, 50), (100, 500), (1000, 5000), (10000, 50000)]  # nA/V
MARK = {1: "o", 2: "s", 5: "^"}
SPEC = 0.005
GAP_MIN = 15.0   # min: clean points further apart than this are joined only by the dotted path


def style(S):
    """(colour, marker, label) for a sensitivity in nA/V."""
    gi = next(i for i, (a, b) in enumerate(GROUPS) if a <= S <= b)
    mant = int(round(S / 10 ** np.floor(np.log10(S) + 1e-9)))
    lab = f"{S:g} nA/V" if S < 1000 else f"{S / 1000:g} µA/V"
    return HUES[gi], MARK[mant], lab


def _first_input_state():
    return L.INPUT_CHANGES[0]["before"] if L.INPUT_CHANGES else "unknown"


def live_sweeps():
    """Live runs with MonC's input in its original state (chamber cabled). Runs after a hand-made input
    change (loaders.INPUT_CHANGES) are kept out of these pooled, one-axis figures and named in not_shown()."""
    return [sw for sw in L.SWEEP_FILES if L.SR570_STATE.get(sw) == "SR570 live"
            and L.input_state_at(L.load_steps(sw)[0].t_start) == _first_input_state()]


def not_shown() -> str:
    other = [sw for sw in L.SWEEP_FILES if L.SR570_STATE.get(sw) == "SR570 live" and sw not in live_sweeps()]
    if not other:
        return ""
    tag = lambda sw: next((c["tag"] for c in reversed(L.INPUT_CHANGES) if c["t1"] < L.load_steps(sw)[0].t_start), "?")
    return ("\nNOT SHOWN: " + "; ".join(f"{sw} ({hms(L.load_steps(sw)[0].t_start)}, after input change {tag(sw)})"
                                        for sw in other)
            + ": MonC's input was not as in the runs shown (all with the chamber cabled), so pooling it here would hide the change.")


def assemble(lg):
    out, problems = {}, []
    for sw in live_sweeps():
        steps = L.load_steps(sw)
        stats = [L.step_stats(lg, s) for s in steps]
        problems += L.check_against_log(stats)
        rows = []
        for s in stats:
            st = s.step
            state = L.settings_during(lg, st.t_settled, st.t_end - 0.5)
            m = L.step_window(lg, st)
            rows.append(dict(sw=sw, stat=s, S=L.sens_nA_per_V(state), level=L.offset_level_nA(state),
                             on=state["A3offset_on"][1], cal=state["A3offset_cal"][1],
                             sign=state["A3offset_sign"][1], u=state["A3off_u_put"][0],
                             clipped=s.mean <= CLIP_COUNTS + 1e-9,
                             part=bool(np.any(lg.S4[m] <= CLIP_COUNTS)) and s.mean > CLIP_COUNTS + 1e-9))
        out[sw] = rows
    return out, problems


def tmid(p):
    st = p["stat"].step
    return 0.5 * (st.t_settled + st.t_end)


# Known single-step anomalies, keyed by (run, step), each with its source. Drawn, labelled, and kept
# out of the connecting line so it doesn't pull the eye.
ANOMALIES: dict = {
    # ("set4", "P0") was listed here as "630 Hz at 50 nA/V". The readback during P0 is 20 uA/V
    # (set 15:04:49-51, before set 4 started; the step log's own state_end agrees), so it is an
    # ordinary 20 uA/V dark, plotted with that range. Review finding F8, 2026-11-12.
}


# ---------------------------------------------------------------- darks
def holds_dark_equiv(lg):
    """Dark-equivalent series from the CAL holds: (label, S nA/V, t[], value[], offset Hz)."""
    import fig_logger as FL
    out = []
    for h in FL.HOLDS:
        if not h["offset_hz"]:
            continue
        t_ev = h["start"](lg)
        if t_ev is None:
            continue
        t0 = t_ev + FL.SKIP_S
        later = [c for c in FL.all_changes(lg) if c[0] > t0]
        t1 = later[0][0] if later else lg.t_last
        try:
            state = L.settings_during(lg, t0, t1 - 0.01)
        except ValueError:
            continue
        if any(state[pv][1] != want for pv, want in h["expect"].items() if pv != "A3off_u_put"):
            continue
        m = (lg.scaler_t - 1 >= t0) & (lg.scaler_t <= t1)
        t, v = lg.scaler_t[m], lg.S4[m]
        if len(v) < 60:
            continue
        n = len(v) // 60
        tb = t[: n * 60].reshape(n, 60).mean(1)
        vb = v[: n * 60].reshape(n, 60).mean(1) - h["offset_hz"]
        out.append((h["key"], L.sens_nA_per_V(state), tb, vb, h["offset_hz"], h["what"]))
    return out


def make_darks(lg, data):
    pts = {}
    for sw, rows in data.items():
        for p in rows:
            if p["on"] == "OFF":
                pts.setdefault(p["S"], []).append(p)
    fig, ax = plt.subplots(figsize=(15, 9.5))
    fig.subplots_adjust(left=0.06, right=0.97, top=0.84, bottom=0.08)
    end_labels = []
    for S in sorted(pts):
        col, mk, lab = style(S)
        rows = sorted(pts[S], key=tmid)
        tm = np.array([(tmid(p) - T_POWER_ON) / 60 for p in rows])
        y = np.array([p["stat"].mean for p in rows])
        sd = np.array([p["stat"].sd if p["stat"].n > 1 else 0 for p in rows])
        clip = np.array([p["clipped"] for p in rows])
        part = np.array([p["part"] for p in rows])
        anom = np.array([(p["sw"], p["stat"].step.step) in ANOMALIES for p in rows])
        ok = ~clip & ~part & ~anom
        # dotted path through every point (clipped drawn on the clip line, anomalies skipped);
        # solid only between consecutive clean points less than GAP_MIN apart
        ya = np.where(clip, CLIP_COUNTS, y)
        ax.plot(tm[~anom], ya[~anom], ":", color=col, lw=0.9, alpha=0.9)
        for i in range(len(tm) - 1):          # neighbours in time, both clean, close enough
            if ok[i] and ok[i + 1] and tm[i + 1] - tm[i] < GAP_MIN:
                ax.plot(tm[i:i + 2], y[i:i + 2], "-", color=col, lw=1.2, alpha=0.9)
        ax.errorbar(tm[ok], y[ok], yerr=sd[ok], fmt=mk, color=col, ms=7, mec="white", mew=0.6,
                    elinewidth=0.8, capsize=0, label=lab)
        if part.any():
            ax.plot(tm[part], y[part], mk, mfc="white", mec=col, mew=1.5, ms=7)
        if clip.any():
            ax.plot(tm[clip], np.full(clip.sum(), CLIP_COUNTS), mk, mfc="white", mec=col, mew=1.5, ms=7)
        for p, t_, y_ in zip(np.array(rows)[anom], tm[anom], y[anom]):
            ax.plot([t_], [y_], mk, mfc="white", mec=col, mew=1.5, ms=9)
            ax.annotate(ANOMALIES[(p["sw"], p["stat"].step.step)], (t_, y_), xytext=(8, 6),
                        textcoords="offset points", fontsize=7, color=INK2)
        last = np.where(~anom)[0][-1]
        end_labels.append([tm[last], ya[last], lab + (" (all clipped)" if clip.all() else ""), col])
    # dark-equivalent from the CAL holds (one label per hold configuration, at its last window)
    last_hold = {}
    for key, S, tb, vb, off, what in holds_dark_equiv(lg):
        col, mk, lab = style(S)
        tmb = (tb - T_POWER_ON) / 60
        ax.plot(tmb, vb, "--", color=col, lw=1.6)
        last_hold[(S, off)] = [tmb[-1], vb[-1], f"{lab}, S4 − {off:.0f} Hz (CAL hold)", col]
    end_labels += list(last_hold.values())
    # direct labels just right of each series' last point; labels that would collide (within
    # 25 min in x and 0.05 decade in y) are pushed up, with a short grey leader to the point
    placed = []
    for x_, y_, lab, col in sorted(end_labels, key=lambda r: r[1]):
        l0 = l_ = np.log10(max(y_, 0.7))
        while any(abs(x_ - px) < 25 and abs(l_ - pl) < 0.05 for px, pl in placed):
            l_ += 0.05
        placed.append((x_, l_))
        ax.annotate(lab, (x_, y_), xytext=(x_ + 1.5, 10 ** l_), textcoords="data", fontsize=7.5,
                    color=INK, va="center", annotation_clip=False,
                    arrowprops=(dict(arrowstyle="-", color=GRAY, lw=0.5) if l_ - l0 > 0.02 else None))
    xmax = max(r[0] for r in end_labels) if end_labels else 60
    ax.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
    ax.text(6, CLIP_COUNTS * 1.08, CLIP_TEXT + "; open markers on this line = clipped",
            fontsize=7.5, color=CLIP_INK, va="bottom")
    ax.set_yscale("log")
    zero_line(ax, L.v2f_zero(lg), x_text=6)
    ax.set_ylim(0.7, 1500)
    ax.set_xlim(5, xmax + 14)
    ax.set_xlabel("minutes since the SR570 was switched on (13:29:56 CST)")
    ax.set_ylabel("offset-OFF dark: S4, counts per 1 s count (= Hz), log scale")
    sec = ax.secondary_xaxis("top", functions=(lambda m_: m_, lambda m_: m_))
    sec.set_xticks(np.arange(10, xmax + 2, 10))
    sec.set_xticklabels([local(T_POWER_ON + 60 * v).strftime("%H:%M") for v in np.arange(10, xmax + 2, 10)])
    sec.set_xlabel("time, CST", fontsize=8.5)
    leg = ax.legend(loc="upper left", ncol=5, fontsize=7.5, title="sensitivity (hue = decade, marker = 1 / 2 / 5)",
                    title_fontsize=7.5, frameon=True, framealpha=0.9, edgecolor="none")
    runs = ", ".join(f"{sw} {hms(data[sw][0]['stat'].step.t_start)}" for sw in data)
    src = ", ".join(sorted(set(L.SOURCES.values())))
    top = header(fig, 0.06, "How many counts MonC shows with nothing going in, for each gain setting, as time goes by",
                 "MonC offset-OFF dark by sensitivity range, all live runs, one axis",
             f"Runs (start CST): {runs}.  Step logs: {src}.\n"
             "Filled markers: step means of the 1 s counts that started after settling (bars: sd of those counts); "
             f"solid lines join a range's clean means less than {GAP_MIN:.0f} min apart; dotted lines join all its points in time order "
             "(not an interpolation).\nOpen markers: window contains clipped counts "
             "(mean biased low), a clipped step (drawn on the clip line), or a labelled anomaly (not joined).\n"
             "Dashed: dark-equivalent from the CAL holds (60-count means of S4 minus the nominal CAL offset); it includes any "
             "CAL-generator drift." + not_shown(),
                 extra_in=0.55)
    fig.subplots_adjust(top=top)
    footer(fig, lg)
    p = save(fig, "darks_by_range.png")
    say(f"[ranges] {p.name}: {sum(len(v) for v in pts.values())} offset-OFF steps over {len(pts)} ranges")
    return p


# ---------------------------------------------------------------- ladders
def ladder_points(data):
    pts = []
    for sw, rows in data.items():
        for i, p in enumerate(rows):
            if not (p["on"] == "ON" and p["cal"] == "CAL" and p["sign"] == "+") or p["clipped"]:
                continue
            before = next((q for q in reversed(rows[:i]) if q["on"] == "OFF" and q["S"] == p["S"]), None)
            after = next((q for q in rows[i + 1:] if q["on"] == "OFF" and q["S"] == p["S"]), None)
            ds = [q for q in (before, after) if q is not None]
            if not ds:
                continue
            dclip = any(q["clipped"] or q["part"] for q in ds)
            dark = np.mean([q["stat"].mean for q in ds if not q["clipped"]] or [0.0])
            nom = V2F_HZ_PER_V * p["level"] / p["S"]
            pts.append(dict(sw=sw, step=p["stat"].step.step, S=p["S"], level=p["level"], f=p["stat"].mean,
                            dark=dark, nom=nom, V=nom / V2F_HZ_PER_V, r=(p["stat"].mean - dark) / nom,
                            dclip=dclip, nd=len(ds), sem=(p["stat"].sd / np.sqrt(p["stat"].n)) / nom if p["stat"].n > 1 else 0))
    return pts


def make_ladders(lg, data):
    pts = [q for q in ladder_points(data) if q["V"] >= 0.015]   # below ~1.5 kHz the dark dominates
    fig, ax = plt.subplots(figsize=(14, 8.5))
    fig.subplots_adjust(left=0.07, right=0.95, top=0.85, bottom=0.09)
    ax.axhspan(-100 * SPEC, 100 * SPEC, color=GRAY, alpha=0.12, lw=0)
    ax.text(0.0165, 100 * SPEC + 0.03, "SR570 gain spec ±0.5 %", fontsize=7.5, color=INK2, va="bottom")
    ax.axhline(0, color=INK2, lw=0.8)
    end = []
    for S in sorted({q["S"] for q in pts}):
        col, mk, lab = style(S)
        qs = sorted([q for q in pts if q["S"] == S], key=lambda q: q["V"])
        V = np.array([q["V"] for q in qs])
        r = 100 * (np.array([q["r"] for q in qs]) - 1)
        dclip = np.array([q["dclip"] for q in qs])
        ax.plot(V, r, "-", color=col, lw=0.9, alpha=0.8)
        ax.plot(V[~dclip], r[~dclip], mk, color=col, ms=7, mec="white", mew=0.6, label=lab)
        if dclip.any():
            ax.plot(V[dclip], r[dclip], mk, mfc="white", mec=col, mew=1.5, ms=7)
        for q, v_, r_ in zip(qs, V, r):
            if abs(r_) > 0.55 or q["level"] in (10.0,):
                ax.annotate(f"{q['level']:g} nA" if q["level"] < 1000 else f"{q['level'] / 1000:g} µA", (v_, r_),
                            xytext=(5, -10 if r_ < 0 else 4), textcoords="offset points", fontsize=6.5, color=INK2)
        end.append([V[-1], r[-1], lab, col])
    # labels just right of each series' last point; collisions (within 0.25 decade in V and
    # 0.07 % in y) pushed up, with a short grey leader
    placed = []
    for v_, r_, lab, col in sorted(end, key=lambda e: e[1]):
        l_ = r_
        while any(abs(np.log10(v_) - np.log10(pv)) < 0.25 and abs(l_ - pl) < 0.07 for pv, pl in placed):
            l_ += 0.07
        placed.append((v_, l_))
        ax.annotate(lab, (v_, r_), xytext=(v_ * 1.12, l_), textcoords="data", fontsize=7.5, color=INK,
                    va="center", annotation_clip=False,
                    arrowprops=(dict(arrowstyle="-", color=GRAY, lw=0.5) if l_ - r_ > 0.02 else None))
    ax.set_xscale("log")
    ax.set_xlim(0.015, 9)
    ax.set_ylim(-1.6, 1.2)
    ax.set_xlabel("SR570 output, V = nominal / 1e5 Hz/V  (0.02 V = 2 kHz … 4 V = 400 kHz)")
    ax.set_ylabel("(S4 − dark) / nominal − 1, %")
    ax.legend(loc="lower left", ncol=4, fontsize=7.5, title="sensitivity (hue = decade, marker = 1 / 2 / 5)",
              title_fontsize=7.5, frameon=True, framealpha=0.9, edgecolor="none")
    lowest = [q for q in pts if q["level"] == 10.0 and q["S"] == 50]
    runs = ", ".join(sorted({q["sw"] for q in pts}))
    top = header(fig, 0.07, "How close each gain setting gets to the right answer, from small signals to big ones",
                 "MonC CAL ladders: gain × CAL level × V2F, every range on one axis",
             f"Runs: {runs}.  Each point: one CAL step, sign +, ON.  nominal = 1e5 Hz/V × CAL level / S.  "
             "dark = mean of the nearest offset-OFF steps before and after, same range, same run.\n"
             "Open markers: a bracketing dark was clipped or part-clipped (dark taken from the other, or 0): ratio is an upper bound.  "
             "Points below 0.015 V (≈1.5 kHz) are not shown: there the dark dominates.\n"
             "Each point mixes range gain and CAL-level error; they are not separated here "
             "(the 10 nA level reads ≈ −1.2 % on every range it was used on)." + not_shown(),
                 extra_in=0.05)
    fig.subplots_adjust(top=top)
    footer(fig, lg)
    p = save(fig, "cal_ladders.png")
    say(f"[ranges] {p.name}: {len(pts)} CAL points over {len({q['S'] for q in pts})} ranges; "
        f"range of ratios {min(q['r'] for q in pts):.4f}-{max(q['r'] for q in pts):.4f}")
    return p, pts


LADDER = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]   # nA/V
RUN_STYLE = [  # (run key, plan block or None, label, colour, marker) in time order; fixed palette order
    ("sweep2", None, "sweep 2 (13:40), mixed order", HUES[0], "o"),
    ("set3", None, "set 3 (13:52), downward in S", HUES[1], "s"),
    ("rerun1", "dark_up", "re-run, upward in S (14:02)", HUES[2], "^"),
    ("rerun1", "dark_down", "re-run, downward in S (14:04)", HUES[2], "v"),
    ("set4", None, "set 4 (15:05)", HUES[3], "D"),
    ("set5", None, "set 5 (15:14)", HUES[4], "P"),
]


def make_vs_range(lg, data):
    """Offset-OFF dark vs sensitivity, one series per run (and per direction in the re-run)."""
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.85, bottom=0.14)
    used = []
    for sw, block, lab, col, mk in RUN_STYLE:
        if sw not in data:
            continue
        rows = [p for p in data[sw] if p["on"] == "OFF" and (block is None or p["stat"].step.block == block)
                and (p["sw"], p["stat"].step.step) not in ANOMALIES]
        if not rows:
            continue
        used.append(sw)
        S = np.array([p["S"] for p in rows])
        y = np.array([p["stat"].mean for p in rows])
        clip = np.array([p["clipped"] for p in rows])
        part = np.array([p["part"] for p in rows])
        ok = ~clip & ~part
        # per-S median of the clean steps (several repeats at 5 µA/V in sets 4/5), joined in S order
        Su = np.array(sorted(set(S[ok])))
        med = np.array([np.median(y[ok][S[ok] == s]) for s in Su])
        # solid between neighbouring ranges on the SR570's 1-2-5 ladder; dotted across a skipped,
        # unmeasured or clipped range (not an interpolation)
        for i in range(len(Su) - 1):
            adj = LADDER.index(Su[i + 1]) - LADDER.index(Su[i]) == 1
            ax.plot(Su[i:i + 2], med[i:i + 2], "-" if adj else ":", color=col, lw=1.1 if adj else 0.9, alpha=0.85)
        ax.plot(S[ok], y[ok], mk, color=col, ms=7, mec="white", mew=0.6, label=lab, ls="none")
        if (part | clip).any():
            ax.plot(S[part], y[part], mk, mfc="white", mec=col, mew=1.5, ms=7, ls="none")
            ax.plot(S[clip], np.full(clip.sum(), CLIP_COUNTS), mk, mfc="white", mec=col, mew=1.5, ms=7, ls="none")
    for (sw, step), txt in ANOMALIES.items():
        if sw in data:
            p = next(q for q in data[sw] if q["stat"].step.step == step)
            ax.plot([p["S"]], [p["stat"].mean], "x", color=INK2, ms=8)
            ax.annotate(f"{sw} {step}: {p['stat'].mean:.0f} Hz at {p['S']:g} nA/V\n(anomaly, not joined)",
                        (p["S"], p["stat"].mean), xytext=(-8, 8), textcoords="offset points", fontsize=7,
                        color=INK2, ha="right")
    ax.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
    ax.text(0.85, CLIP_COUNTS * 1.08, CLIP_TEXT + "; open markers on this line = clipped",
            fontsize=7.5, color=CLIP_INK, va="bottom")
    ref = [p for p in data.get("set3", []) if p["on"] == "OFF" and p["S"] == 1 and not p["clipped"]]
    if ref:
        a = ref[0]
        ss = np.array([0.8, 25000])
        ax.plot(ss, a["stat"].mean * a["S"] / ss, ":", color=GRAY, lw=1.2,
                label=f"if a pure input current: ∝ 1/S through set 3's 1 nA/V ({a['stat'].mean * a['S'] / V2F_HZ_PER_V * 1e3:.1f} pA)")
    ax.axvspan(4500, 5500, color=GRAY, alpha=0.15, lw=0)
    ax.text(5000, 1300, "MonC's standard\ngain 5 µA/V", ha="center", fontsize=7.5, color=INK2, va="top")
    ax.set_xscale("log")
    ax.set_yscale("log")
    zero_line(ax, L.v2f_zero(lg), x_text=0.85)
    ax.set_ylim(0.7, 1500)
    ax.set_xlim(0.8, 25000)
    ticks = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g} nA/V" if t < 1000 else f"{t / 1000:g} µA/V" for t in ticks], rotation=45, ha="right", fontsize=8)
    ax.minorticks_off()
    ax.set_xlabel("SR570 sensitivity S (readback)")
    ax.set_ylabel("offset-OFF dark: S4, counts per 1 s count (= Hz), log scale")
    ax.legend(loc="lower left", bbox_to_anchor=(0.30, 0.07), fontsize=7.5, title="run (and direction)",
              title_fontsize=7.5, frameon=True, framealpha=0.9, edgecolor="none")
    top = header(fig, 0.07, "The no-signal counts for every gain setting, run by run: which ones repeat and which wander",
                 "MonC offset-OFF dark vs sensitivity range, by run and sweep direction",
             f"Runs: {', '.join(dict.fromkeys(used))} (SR570 on since 13:29:56).  Each marker: one offset-OFF step, mean of the "
             "1 s counts that started after settling; lines join a run's per-range medians in S order.\n"
             "Open markers: window part-clipped (mean biased low) or fully clipped (on the clip line).  "
             "The re-run measured every range twice, upward then downward in S, to test order dependence.\n"
             "Ranges are not all in every run; a missing marker means not measured." + not_shown(),
                 extra_in=0.05)
    fig.subplots_adjust(top=top)
    footer(fig, lg)
    p = save(fig, "darks_vs_range.png")
    say(f"[ranges] {p.name}: runs {', '.join(dict.fromkeys(used))}")
    return p


def make(lg):
    data, problems = assemble(lg)
    if problems:
        raise SystemExit("REFUSED: raw logger does not reproduce the step logs:\n  " + "\n  ".join(problems))
    make_darks(lg, data)
    make_vs_range(lg, data)
    make_ladders(lg, data)
