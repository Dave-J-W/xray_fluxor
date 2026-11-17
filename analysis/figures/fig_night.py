"""Figures for the overnight MonC program (Experimenter; plan monc_night_plan.csv on monc-dark; step log
growing outside git in xray_fluxor-data/sweeps/).

  night_darks.png   offset-OFF dark per range vs time across all passes and grids, one axis, with the
                    blanked readings (SR570 output blank ON) as their own series.
  night_hold.png    the interim setting (5 µA/V, CAL +2 nA) during its 480 s holds: S4 − 40 Hz per count
                    and per hold, on the same axis as the 5 µA/V offset-OFF darks (blanked and not).

Both carry hutch temperature in a panel below when a raw archiver pull is available (temperature.py).
Rules as elsewhere: strict count windows, readback state per window, clip and V2F-zero lines, guards.
"""
from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

import loaders as L
from common import (CLIP_COUNTS, CLIP_INK, CLIP_TEXT, GRAY, INK, INK2, T_POWER_ON, TZ, footer, header,
                    hms, inlabel, input_key, input_marks, local, save, say, time_axis, zero_line)
from fig_ranges import style

NIGHT = "night"
HOLD_OFFSET_HZ = 40.0      # nominal CAL 2 nA at 5 µA/V: 1e5 Hz/V × 2 nA / 5 µA/V
GAP_S = 25 * 60            # passes run every ~10 min; a longer gap is drawn dotted
SWING_TEST_C = 1.0         # degC; a smaller hutch swing cannot test a temperature coefficient
ENDED_S = 20 * 60          # step log short of its plan AND silent this long before the logger's end = run over


def run_status(lg):
    """('running' | 'ended', n_logged, n_planned). 'ended' when the log stopped short of the plan and has been
    silent for ENDED_S while the logger kept recording (e.g. the 08:15 deadline stop)."""
    steps = L.load_steps(NIGHT)
    n_plan = len(L.sweep_csv(L.SWEEP_FILES[NIGHT][1]))
    if len(steps) >= n_plan:
        return "complete", len(steps), n_plan
    return ("ended" if lg.t_last - steps[-1].t_end > ENDED_S else "running"), len(steps), n_plan


def status_text(lg):
    s, n, m = run_status(lg)
    return {"complete": "", "running": " — PROVISIONAL, still running",
            "ended": f" — run ended after {n} of {m} planned steps"}[s]


def night_rows(lg):
    steps = L.load_steps(NIGHT)
    stats = [L.step_stats(lg, s) for s in steps]
    bad = L.check_against_log(stats)
    if bad:
        raise SystemExit("REFUSED: raw logger does not reproduce the night step log:\n  " + "\n  ".join(bad))
    rows = []
    for s in stats:
        st = s.step
        state = L.settings_during(lg, st.t_settled, st.t_end - 0.5)
        m = L.step_window(lg, st)
        rows.append(dict(stat=s, step=st.step, block=st.block, S=L.sens_nA_per_V(state),
                         level=L.offset_level_nA(state), on=state["A3offset_on"][1],
                         cal=state["A3offset_cal"][1], blank=state["A3blank_on"][1],
                         t=0.5 * (st.t_settled + st.t_end), t_end=st.t_end,
                         clipped=s.mean <= CLIP_COUNTS + 1e-9,
                         part=bool(np.any(lg.S4[m] <= CLIP_COUNTS)) and s.mean > CLIP_COUNTS + 1e-9))
    return rows


def _time_axes(ax, t0, t1):
    ax.set_xlim(local(t0), local(t1))
    time_axis(ax, t0, t1)
    sec = ax.secondary_xaxis("top", functions=(lambda x: (x - mdates.date2num(local(T_POWER_ON))) * 24,
                                               lambda h: h / 24 + mdates.date2num(local(T_POWER_ON))))
    sec.set_xlabel("hours since the SR570 was switched on (13:29:56)", fontsize=8)


def _temperature_panel(ax, t0, t1):
    """Hutch temperature from raw archiver pulls, if present; otherwise say so in the panel."""
    try:
        import temperature
        series = temperature.load(t0, t1)
    except Exception as e:      # missing pulls are reported, never invented
        series, err = [], str(e)
    else:
        err = ""
    if not series:
        ax.text(0.5, 0.5, "hutch temperature: no raw archiver pull covering this window yet"
                + (f" ({err[:80]})" if err else ""), transform=ax.transAxes, ha="center", va="center",
                fontsize=8, color=INK2)
        ax.set_yticks([])
        return
    for name, t, v, col in series:
        ax.plot([local(x) for x in t], v, "-", lw=1.0, color=col,
                label=f"{name}: {v.min():.2f}–{v.max():.2f} °C")
    ax.set_ylabel("°C", fontsize=8)
    lo = min(np.min(v) for _, _, v, _ in series)
    hi = max(np.max(v) for _, _, v, _ in series)
    swing = max(np.ptp(v) for _, _, v, _ in series)
    if swing < SWING_TEST_C:      # refuse a verdict the room never tested
        ax.text(0.005, 0.06, f"Largest swing {swing:.2f} °C peak to peak: too small to judge whether the darks "
                f"follow temperature. A deliberate change of ≥ {SWING_TEST_C:.0f} °C would test it.",
                transform=ax.transAxes, fontsize=7.5, color=CLIP_INK, va="bottom")
    pad = max(0.3, 0.25 * (hi - lo))
    ax.set_ylim(lo - 1.8 * pad, hi + 2.2 * pad)    # room for the swing note below and the panel label above
    shown = {name.split(":")[1].split(" ")[0] for name, *_ in series}
    missing = [f"Sensor{n}" for n in temperature.SENSORS if f"Sensor{n}" not in shown]
    ax.legend(loc="upper right", fontsize=7, ncol=3, title_fontsize=6.5,
              title=(f"not shown: {', '.join(missing)} (no valid reading; 0.0 °C = no sensor)" if missing else None))


def _ikey(t0, t1):
    k = input_key(t0, t1)
    return ("\n" + k) if k else ""


def make_darks(lg, rows):
    dark = [r for r in rows if r["on"] == "OFF"]
    if not dark:
        say("[night] night_darks.png: not made (no offset-OFF steps yet)")
        return None
    t0 = min(r["t"] for r in rows) - 120
    t1 = lg.t_last + 60
    fig = plt.figure(figsize=(16, 11))
    gs = GridSpec(2, 1, figure=fig, height_ratios=[5, 1], hspace=0.08, left=0.06, right=0.9, bottom=0.07)
    ax = fig.add_subplot(gs[0])
    axt = fig.add_subplot(gs[1], sharex=ax)
    keys = sorted({(r["S"], r["blank"]) for r in dark})
    labels, pts = [], []
    for S, blank in keys:
        col, mk, lab = style(S)
        rs = sorted([r for r in dark if r["S"] == S and r["blank"] == blank], key=lambda r: r["t"])
        tm = np.array([r["t"] for r in rs])
        y = np.array([r["stat"].mean for r in rs])
        clip = np.array([r["clipped"] for r in rs])
        part = np.array([r["part"] for r in rs])
        ok = ~clip & ~part
        ya = np.where(clip, CLIP_COUNTS, y)
        b = blank == "ON"
        mkr = "X" if b else mk
        lab2 = lab + (" blanked" if b else "")
        for i in range(len(tm) - 1):
            ax.plot([local(tm[i]), local(tm[i + 1])], ya[i:i + 2],
                    "-" if (ok[i] and ok[i + 1] and tm[i + 1] - tm[i] < GAP_S) else ":",
                    color=col, lw=1.4 if b else 1.0, alpha=0.9)
        ax.plot([local(x) for x in tm[ok]], y[ok], mkr, color=col, ms=7 if b else 6, mec="white", mew=0.5,
                ls="none", label=lab2)
        if (~ok).any():
            ax.plot([local(x) for x in tm[~ok]], ya[~ok], mkr, mfc="white", mec=col, mew=1.3, ms=6, ls="none")
        labels.append([tm[-1], ya[-1], lab2 + f"  {ya[-1]:.0f}", col])
        pts.extend(zip(tm, np.log10(np.maximum(ya, 0.7))))
    # labels just right of each series' last point. A label is moved (nearest free height, up or down,
    # with a short grey leader) if it would sit within 0.035 decade of another label or of any data point
    # in the stretch of time it covers (a series that ends early, e.g. the blanked ones, has others' data
    # to its right).
    placed, span = [], t1 - t0
    pts = np.array(pts)
    w = 0.09 * span                     # time covered by a label's text

    def free(x_, l_):
        near = (pts[:, 0] > x_ + 0.002 * span) & (pts[:, 0] < x_ + w) & (np.abs(pts[:, 1] - l_) < 0.035)
        return not near.any() and not any(abs(l_ - pl) < 0.045 and abs(x_ - px) < w for px, pl in placed)

    for x_, y_, lab, col in sorted(labels, key=lambda r: r[1]):
        l0 = np.log10(max(y_, 0.7))
        l_ = next((l0 + s * d for d in np.arange(0, 1.0, 0.005) for s in (1, -1) if free(x_, l0 + s * d)), l0)
        placed.append((x_, l_))
        ax.annotate(lab, (local(x_), y_), xytext=(local(x_ + 0.008 * span), 10 ** l_), textcoords="data",
                    fontsize=7, va="center", color=INK, annotation_clip=False,
                    arrowprops=(dict(arrowstyle="-", color=GRAY, lw=0.4) if l_ - l0 > 0.01 else None))
    ax.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
    ax.set_yscale("log")
    zero_line(ax, L.v2f_zero(lg), x_text=local(t0 + 0.01 * span), fontsize=7)
    ax.text(local(t0 + 0.01 * span), CLIP_COUNTS * 1.08, CLIP_TEXT, fontsize=7, color=CLIP_INK, va="bottom")
    ymax = max(r["stat"].mean for r in dark)
    ax.set_ylim(0.7, max(1500, 2.0 * ymax))      # never cut off a reading (blanked 20 µA/V is ~3.5 kHz)
    ax.set_ylabel("offset-OFF dark: S4, counts per 1 s count (= Hz), log scale")
    _time_axes(ax, t0, t1)
    input_marks(ax, t0, t1, label="tag", y=0.9)
    plt.setp(ax.get_xticklabels(), visible=False)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 0.06), ncol=4, fontsize=7,
              title="sensitivity (hue = decade, marker = 1/2/5; × = output blanked)",
              title_fontsize=7, frameon=True, framealpha=0.9, edgecolor="none")
    inlabel(ax, "MonC's no-signal counts for each gain setting, every pass through the night")
    _temperature_panel(axt, t0, t1)
    input_marks(axt, t0, t1)
    inlabel(axt, "Hutch temperature (does the drift follow the room?)")
    axt.set_xlabel(time_axis(axt, t0, t1))
    n_pass = len({r["step"].split("_")[0] for r in rows if r["block"] == "pass_dark"})
    n_grid = len({r["step"].split("_")[0] for r in rows if r["block"].startswith("grid")})
    so_far = " so far" if run_status(lg)[0] == "running" else ""
    top = header(
        fig, 0.06,
        "Overnight: do MonC's no-signal counts creep, gain setting by gain setting?",
        "MonC overnight program: offset-OFF dark per range vs time" + status_text(lg),
        f"Step log {L.SWEEP_FILES[NIGHT][0]} ({L.SOURCES.get(L.SWEEP_FILES[NIGHT][0], '?')}), plan {L.SWEEP_FILES[NIGHT][1]} "
        f"({L.SOURCES.get(L.SWEEP_FILES[NIGHT][1], '?')}); {len(rows)} steps{so_far}: {n_pass} dark passes, {n_grid} grid(s).\n"
        "Each marker: one offset-OFF step, mean of the 1 s counts that started after settling.  × markers: the SR570 output "
        "was blanked (blank_on ON).  Open markers: clipped or part-clipped.\n"
        f"Solid lines join neighbouring readings less than {GAP_S // 60} min apart; dotted lines cross longer gaps or a clipped reading."
        + _ikey(t0, t1), extra_in=0.5)
    gs.update(top=top)
    footer(fig, lg)
    p = save(fig, "night_darks.png")
    say(f"[night] {p.name}: {len(dark)} offset-OFF steps, {len(keys)} series, {n_pass} passes, {n_grid} grids")
    return p


def make_hold(lg, rows):
    holds = [r for r in rows if r["block"] == "interim_hold"]
    d5 = [r for r in rows if r["on"] == "OFF" and r["S"] == 5000]
    t0 = min(r["t"] for r in rows) - 120
    t1 = lg.t_last + 60
    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(2, 1, figure=fig, height_ratios=[4, 1], hspace=0.08, left=0.06, right=0.97, bottom=0.08)
    ax = fig.add_subplot(gs[0])
    axt = fig.add_subplot(gs[1], sharex=ax)
    for r in holds:
        assert r["S"] == 5000 and r["cal"] == "CAL" and r["level"] == 2 and r["on"] == "ON" and r["blank"] == "OFF", r["step"]
        st = r["stat"].step
        m = L.step_window(lg, st)
        ax.plot([local(x) for x in lg.scaler_t[m]], lg.S4[m] - HOLD_OFFSET_HZ, ".", ms=2, color=GRAY, alpha=0.5)
    if holds:
        th = [local(r["t"]) for r in holds]
        yh = np.array([r["stat"].mean for r in holds]) - HOLD_OFFSET_HZ
        sd = np.array([r["stat"].sd for r in holds])
        ax.errorbar(th, yh, yerr=sd, fmt="s-", color=INK, ms=6, lw=1.2, capsize=0,
                    label=f"interim hold (CAL +2 nA): S4 − {HOLD_OFFSET_HZ:.0f} Hz, mean ± sd of each 480 s hold")
    col5 = style(5000)[0]
    rs = sorted([r for r in d5 if r["blank"] == "OFF" and not r["clipped"]], key=lambda r: r["t"])
    if rs:
        ax.plot([local(r["t"]) for r in rs], [r["stat"].mean for r in rs], "^-", color=col5, ms=6, lw=1.0,
                mec="white", mew=0.5, label="5 µA/V offset OFF (pass darks, output not blanked)")
    rb = [r for r in d5 if r["blank"] == "ON" and not r["clipped"]]
    if rb:      # ~10x higher: kept off this linear axis (it would flatten the comparison); shown in night_darks
        ax.text(0.995, 0.80, f"5 µA/V with the output blanked: {min(r['stat'].mean for r in rb):.0f}–"
                f"{max(r['stat'].mean for r in rb):.0f} Hz ({len(rb)} readings), off this scale; see night_darks.png",
                transform=ax.transAxes, ha="right", fontsize=7.5, color=INK2)
    if not holds:
        ax.text(0.5, 0.6, "no 480 s hold step has completed yet", transform=ax.transAxes, ha="center", fontsize=10,
                color=CLIP_INK)
    z = L.v2f_zero(lg)
    zero_line(ax, z, x_text=local(t0 + 60), fontsize=7)
    vals = [r["stat"].mean for r in d5 if not r["clipped"] and r["blank"] == "OFF"] + (list(yh) if holds else [])
    if vals:
        ax.set_ylim(min(0, min(vals) - 3), max(vals) * 1.25 + 2)
    ax.set_ylabel("dark at 5 µA/V, Hz (S4, or S4 − 40 Hz during holds)")
    _time_axes(ax, t0, t1)
    input_marks(ax, t0, t1, label="tag", y=0.9)
    plt.setp(ax.get_xticklabels(), visible=False)
    ax.legend(loc="upper right", fontsize=7.5)
    inlabel(ax, "MonC at its everyday setting: is the no-signal level steady through the night?")
    _temperature_panel(axt, t0, t1)
    input_marks(axt, t0, t1)
    inlabel(axt, "Hutch temperature (does the drift follow the room?)")
    axt.set_xlabel(time_axis(axt, t0, t1))
    top = header(
        fig, 0.06,
        "Overnight at MonC's everyday setting: is the leftover count steady, and do the two ways of measuring it agree?",
        "MonC interim configuration (5 µA/V, CAL +2 nA, ON): hold level vs time, against the 5 µA/V offset-OFF darks"
        + status_text(lg),
        f"Holds: {len(holds)}{' so far' if run_status(lg)[0] == 'running' else ''} (block interim_hold, 480 s each).  dark-equivalent = S4 − {HOLD_OFFSET_HZ:.0f} Hz "
        "(nominal 1e5 Hz/V × 2 nA / 5 µA/V); it includes any CAL-generator drift.\n"
        "Triangles: the same range with the offset OFF, measured in every dark pass (output not blanked).  "
        "Grey dots: the individual 1 s counts of the holds." + _ikey(t0, t1),
        extra_in=0.5)
    gs.update(top=top)
    footer(fig, lg)
    p = save(fig, "night_hold.png")
    say(f"[night] {p.name}: {len(holds)} holds, {len(d5)} 5 uA/V offset-OFF steps")
    return p


def make(lg):
    if NIGHT not in L.SWEEP_FILES:
        say("[night] no overnight step log found; skipped")
        return
    rows = night_rows(lg)
    make_darks(lg, rows)
    make_hold(lg, rows)
