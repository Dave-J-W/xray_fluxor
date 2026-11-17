"""Figures: the 1 s logger record of MonC (S4) with sweep steps, setting changes and power-on.

  logger_overview.png        whole record: S4, EPICS A3 readbacks, MonP S3 and ring current (context)
  logger_poweron_sweep2.png  13:25-13:45 zoom: power-on transient, warm-up, A3init, sweep 2
  logger_dark.png            S4 at the baseline setting since sweep 2 ended (dark-drift record, still growing)

Raw counts (S4, counts per 1.000 s count) are plotted as recorded. Counts with S4 <= 1 are
clipped (unipolar V2F at or below 0 V) and drawn with their own marker. MonP (S3) is shown
read-only, as context only: nothing here was done to MonP.
"""
from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

import loaders as L
from common import (header, inlabel, CLIP_TEXT, zero_line, AQUA, BLUE, CLIP_COUNTS, CLIP_INK, GRAY, INK, INK2, ORANGE, T_A3INIT,
                    T_POWER_ON, TZ, VIOLET, footer, hms, input_key, input_marks, local, save, say, time_axis)

LONG_S = 2700      # a window longer than 45 min: step names and unlogged-change notes don't fit in the panel

SWEEP_SHADE = {"sweep1": GRAY, "sweep1b": GRAY, "sweep2": BLUE, "set3": BLUE, "rerun1": BLUE}


def find_events(lg: L.Logger) -> dict:
    """Locate the power-on transient and A3init in the data and check them against the
    constants in common.py (which come from monc_sweep1_results.md). Refuse on disagreement."""
    t, s4 = lg.scaler_t, lg.S4
    m = (t > T_POWER_ON - 300) & (t < T_A3INIT) & (s4 > 1000)
    if not m.any():
        raise SystemExit("REFUSED: no power-on transient (S4 > 1000) found before A3init")
    t_on = t[m][0]
    if abs(t_on - T_POWER_ON) > 2:
        raise SystemExit(f"REFUSED: power-on transient at {hms(t_on)}, constant says {hms(T_POWER_ON)}")
    ch = [r[0] for r in lg.settings.get("A3invert_on", []) if abs(r[0] - T_A3INIT) < 5]
    if not ch:
        raise SystemExit("REFUSED: no A3init re-send (A3invert_on update) near the A3init constant")
    return dict(power_on=t_on, s4_on=s4[m][0], a3init=ch[0])


def all_changes(lg: L.Logger, pvs=L.A3_STATE_PVS):
    out = []
    for pv in pvs:
        out += [(t, pv, v, lab) for t, v, lab in lg.settings.get(pv, []) if t > lg.t_first + 0.5]
    return sorted(out)


def dt(x):
    return [local(v) for v in np.atleast_1d(x)]


def step_series(lg, pv, t0, t1, f=lambda v, lab: v):
    rows = lg.settings.get(pv, [])
    ts, vs = [t0], [None]
    cur = L.setting_at(lg, pv, t0)
    vs[0] = f(*cur) if cur else np.nan
    for t, v, lab in rows:
        if t0 < t <= t1:
            ts.append(t)
            vs.append(f(v, lab))
    ts.append(t1)
    vs.append(vs[-1])
    return np.array(ts), np.array(vs, float)


def sens_val(v, lab):
    return float(lab)


# Who made A3 changes that no step log covers, where that is known. Keyed by the cluster's first
# change (epoch s, matched within 5 s); each with its source.
UNLOGGED_LABELS = {
    1794511573.0: "user, Phoebus tests\n (unit off; results doc)",           # 13:26:13
    1794514485.0: "Experimenter: set\n CAL 1 nA dark hold",                  # 14:14:45 (Experimenter message)
    1794514928.0: "user (confirmed:\n \"Yes, that was me.\")",              # 14:22:08, user 2026-11-12
}


def unlogged_clusters(lg, gap=60.0):
    """Spans of A3 setting changes that fall outside every known step log's [t_start, t_end].

    These are changes this branch has no record of the purpose of (manual Phoebus tests, a
    sweep whose step log is not in this branch). Clustered when closer than `gap` seconds."""
    steps = [s for sw in L.SWEEP_FILES for s in L.load_steps(sw)]
    ts = [c[0] for c in all_changes(lg)
          if not any(s.t_start - 1 <= c[0] <= s.t_end + 1 for s in steps)
          and abs(c[0] - T_A3INIT) > 3]                       # A3init's re-send is marked separately
    out = []
    for t in ts:
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
            out[-1][2] += 1
        else:
            out.append([t, t, 1])
    return out


def visible_clusters(lg, t0, t1):
    return [c for c in unlogged_clusters(lg) if not (c[1] < t0 or c[0] > t1)]


def unlogged_key(lg, t0, t1, width=190):
    """Header lines naming each tagged unlogged cluster (long windows, where the panel has no room)."""
    import textwrap
    items = []
    for i, (a, b, n) in enumerate(visible_clusters(lg, t0, t1)):
        who = next((v for k_, v in UNLOGGED_LABELS.items() if abs(k_ - a) < 5), "").replace("\n ", " ")
        span = hms(a) if b - a < 1 else f"{hms(a)}–{hms(b)}"
        item = f"U{i + 1} {span}, {n} change{'s' if n > 1 else ''}" + (f": {who}" if who else "")
        items.append(item.replace(" ", " "))       # no line break inside one entry
    if not items:
        return ""
    return "\n".join(textwrap.wrap("Hatched, tagged U1… above the top panel: A3 changes no step log covers.  "
                                   + ";  ".join(items) + ".", width, break_on_hyphens=False))


def shade_steps(ax, t0, t1, label_ax=None, lg=None):
    if lg is not None:
        vis = visible_clusters(lg, t0, t1)
        for i, (a, b, n) in enumerate(vis):
            ax.axvspan(local(a - 2), local(b + 2), facecolor="none", edgecolor=INK2, hatch="////",
                       lw=0, alpha=0.5)
            if label_ax is ax and t1 - t0 > LONG_S:      # tag only; unlogged_key() goes in the header
                ax.text(local(0.5 * (a + b)), 1.008 + 0.028 * (i % 3), f"U{i + 1}",
                        transform=ax.get_xaxis_transform(), fontsize=6.5, color=INK2, ha="center",
                        va="bottom")
            elif label_ax is ax:
                who = next((v for k_, v in UNLOGGED_LABELS.items() if abs(k_ - a) < 5), "")
                ax.text(local(a), 0.88 - 0.17 * (i % 3), f" {n} unlogged A3 changes\n {hms(a)}–{hms(b)}"
                        + (f"\n {who}" if who else ""),          # staggered so neighbours don't overprint
                        transform=ax.get_xaxis_transform(), fontsize=6.5, color=INK2, va="top",
                        bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.8))
    # hand-made input changes (chamber disconnected etc.): on every panel; labelled on the top one
    input_marks(ax, t0, t1, label=("tag" if t1 - t0 > LONG_S else "full") if label_ax is ax else "none")
    # step names only when they can be read (a window under 45 min); the overview shades them only
    if label_ax is not None and t1 - t0 > LONG_S:
        label_ax = None
    for sw in L.SWEEP_FILES:
        col = SWEEP_SHADE.get(sw, BLUE)
        for st in L.load_steps(sw):
            if st.t_end < t0 or st.t_start > t1:
                continue
            ax.axvspan(local(st.t_settled), local(st.t_end), color=col, alpha=0.13, lw=0)
            if label_ax is ax and (st.t_end - st.t_start) > 0:
                ax.text(local(0.5 * (st.t_settled + st.t_end)), 1.01, st.step, rotation=90,
                        transform=ax.get_xaxis_transform(), fontsize=5.5, ha="center", va="bottom",
                        color=INK2)


def event_lines(ax, ev, label=False):
    for t, txt, col, y in ((ev["power_on"], "SR570 switched on", ORANGE, 0.985),
                           (ev["a3init"], "A3init", AQUA, 0.935)):
        ax.axvline(local(t), color=col, lw=1.2, ls="--")
        if label:
            ax.text(local(t), y, f" {txt} {hms(t)}", transform=ax.get_xaxis_transform(),
                    fontsize=7.5, color=col, va="top", ha="left", rotation=0)


def plot_s4(ax, lg, m, ev, log=True, label_steps=True, t0=None, t1=None):
    t, s4 = lg.scaler_t[m], lg.S4[m]
    clip = s4 <= CLIP_COUNTS
    ax.plot(dt(t[~clip]), s4[~clip], ".", ms=2.5, color=BLUE, label="S4 (MonC), one dot per 1 s count")
    if clip.any():
        ax.plot(dt(t[clip]), np.full(clip.sum(), CLIP_COUNTS), "v", ms=3.5, mfc="none", mec=CLIP_INK,
                mew=0.8, label=f"clipped: S4 ≤ 1 count ({clip.sum()} counts)")
    if log:
        ax.set_yscale("log")
        ax.set_ylim(0.7, 2e5)
    shade_steps(ax, t0, t1, label_ax=ax if label_steps else None, lg=lg)
    long = t1 - t0 > LONG_S
    event_lines(ax, ev, label=not long)       # long window: the lines sit under the headline; the subtitle names them
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    ax.legend(loc="lower right" if long else "center left", fontsize=7, markerscale=2.5)
    inlabel(ax, "MonC's counter, every second (log scale: each grid line is 10× more)")


def setting_panels(axs, lg, t0, t1, ev):
    """Readback lanes: vernier u, sensitivity, offset level, and the ON / CAL / sign state."""
    a_u, a_s, a_l = axs
    ts, u = step_series(lg, "A3off_u_put", t0, t1)
    a_u.step(dt(ts), u, where="post", color=INK, lw=1.0)
    a_u.set_ylabel("vernier u")
    a_u.set_ylim(-115, 115)
    # ON / CAL / sign as filled lanes on the same axis, outside the u range
    for pv, on_lab, yb, txt in (("A3offset_on", "ON", 125, "offset ON"),
                               ("A3offset_cal", "CAL", 140, "CAL"),
                               ("A3offset_sign", "-", 155, "sign −")):
        tt, vv = step_series(lg, pv, t0, t1, f=lambda v, lab, o=on_lab: 1.0 if lab == o else 0.0)
        for i in range(len(tt) - 1):
            if vv[i] > 0.5:
                a_u.axhspan(yb - 5, yb + 5, xmin=0, xmax=1, alpha=0)  # keep limits
                a_u.fill_between(dt([tt[i], tt[i + 1]]), yb - 5, yb + 5, color={"A3offset_on": AQUA, "A3offset_cal": "#eda100"}.get(pv, ORANGE),
                                 lw=0, step=None)
        a_u.text(1.002, yb, txt, transform=a_u.get_yaxis_transform(), fontsize=6.5, va="center", color=INK2)
    a_u.set_ylim(-115, 162)
    a_u.set_yticks([-100, -50, 0, 50, 100])
    ts, s = step_series(lg, "A3sens_num", t0, t1, f=sens_val)
    _, su = step_series(lg, "A3sens_unit", t0, t1, f=lambda v, lab: {"pA/V": 1e-3, "nA/V": 1, "uA/V": 1e3}.get(lab, np.nan))
    # sens_unit changes are rare; combine on the union of change times
    a_s.step(dt(ts), s, where="post", color=INK, lw=1.0)
    a_s.set_yscale("log")
    a_s.set_ylabel("A3sens_num\n(nA/V when unit = nA/V)", fontsize=7.5)
    tl, lv = step_series(lg, "A3offset_num", t0, t1, f=sens_val)
    a_l.step(dt(tl), lv, where="post", color=INK, lw=1.0)
    a_l.set_yscale("log")
    a_l.set_ylabel("A3offset_num\n(nA when unit = nA)", fontsize=7.5)
    inlabel(a_u, "Offset knob position; coloured bars show which offset switches were on", where="bottom")
    inlabel(a_s, "Amplifier gain setting (the number on the dial)")
    inlabel(a_l, "Offset size setting (the number on the dial)")
    unit_ch = [r for r in all_changes(lg, ("A3sens_unit", "A3offset_unit")) if t0 < r[0] <= t1]
    for t, pv, v, lab in unit_ch:
        ax = a_s if pv == "A3sens_unit" else a_l
        ax.axvline(local(t), color=CLIP_INK, lw=0.6, ls=":")
    if unit_ch:
        a_l.text(0.995, 0.05, f"dotted red: unit field changed ({len(unit_ch)} times, e.g. to "
                 f"{unit_ch[0][3]}); the number is then not in nA/V or nA", transform=a_l.transAxes,
                 fontsize=6.5, ha="right", color=CLIP_INK)
    for ax in axs:
        shade_steps(ax, t0, t1, lg=lg)
        event_lines(ax, ev)


def context_panels(a3, ar, lg, m, ev, t0, t1):
    a3.plot(dt(lg.scaler_t[m]), lg.S3[m], ".", ms=2, color=VIOLET)
    a3.set_yscale("log")
    a3.set_ylabel("S3 (MonP), counts\nper 1 s count", fontsize=7.5)
    inlabel(a3, "The upstream monitor (MonP), shown only for comparison: nothing was done to it")
    mr = (lg.ring_t >= t0) & (lg.ring_t <= t1)
    ar.plot(dt(lg.ring_t[mr]), lg.ring_mA[mr], "-", lw=0.8, color=INK2)
    ar.set_ylabel("ring current, mA", fontsize=7.5)
    inlabel(ar, "Electron current in the storage ring (the X-ray source)")
    for ax in (a3, ar):
        shade_steps(ax, t0, t1, lg=lg)
        event_lines(ax, ev)


def timeseries(lg, ev, t0, t1, name, plain, title, sub):
    m = (lg.scaler_t >= t0) & (lg.scaler_t <= t1)
    fig = plt.figure(figsize=(15, 13))
    gs = GridSpec(6, 1, figure=fig, height_ratios=[4.2, 1.6, 1.0, 1.0, 1.3, 0.9], hspace=0.12,
                  left=0.07, right=0.94, top=0.90, bottom=0.06)
    ax0 = fig.add_subplot(gs[0])
    axs = [fig.add_subplot(gs[i], sharex=ax0) for i in range(1, 6)]
    plot_s4(ax0, lg, m, ev, t0=t0, t1=t1)
    setting_panels(axs[:3], lg, t0, t1, ev)
    context_panels(axs[3], axs[4], lg, m, ev, t0, t1)
    for ax in [ax0] + axs[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)
    axs[-1].set_xlabel(time_axis(axs[-1], t0, t1))
    ax0.set_xlim(local(t0), local(t1))
    key = unlogged_key(lg, t0, t1) if t1 - t0 > LONG_S else ""
    ikey = input_key(t0, t1)
    key = "\n".join(k for k in (key, ikey) if k)
    top = header(fig, 0.07, plain, title, sub + ("\n" + key if key else ""),
                 extra_in=0.25 + (0.2 if ikey and t1 - t0 > LONG_S else 0))
    # 0.25 in: rotated step labels, or the staggered U tags, above the top panel; +0.2 in for a C tag above them
    gs.update(top=top)
    footer(fig, lg)
    return save(fig, name)


# Dark-record windows ("holds"), as data. Each starts at a stated event + a skip, and ends at the
# next A3 setting change or the last count. `expect` is checked against the EPICS readback over the
# whole window (refused on mismatch). `offset_hz` is a known injected offset: dark = S4 - offset_hz.
T_CAL_HOLD = 1794514489.0   # 14:14:49 CST: end of the Experimenter's change to the CAL 1 nA hold
#                             (14:14:45-49; user chose "Move above zero"; Experimenter message 2026-11-12)
BASELINE = {"A3sens_num": "50", "A3sens_unit": "nA/V", "A3offset_cal": "UNCAL", "A3offset_num": "20",
            "A3offset_unit": "nA", "A3offset_on": "ON", "A3offset_sign": "+", "A3off_u_put": "6"}
CAL_HOLD = {"A3sens_num": "50", "A3sens_unit": "nA/V", "A3offset_cal": "CAL", "A3offset_num": "1",
            "A3offset_unit": "nA", "A3offset_on": "ON", "A3offset_sign": "+"}
SKIP_S = 12.0   # near-clip / settling recovery takes ~10 s (Experimenter, sweep-1 re-run block H)


def _r_settled(sw):
    return [s for s in L.load_steps(sw) if s.step == "R"][0].t_settled


HOLDS = [
    dict(key="after_sweep2", start=lambda lg: _r_settled("sweep2"), expect=BASELINE, offset_hz=0.0,
         what="baseline (UNCAL, u = +6) after sweep 2's restore step settled"),
    dict(key="after_rerun1", start=lambda lg: _r_settled("rerun1"), expect=BASELINE, offset_hz=0.0,
         what="baseline (UNCAL, u = +6) after the sweep-1 re-run's restore step settled"),
    dict(key="cal1nA_hold", start=lambda lg: T_CAL_HOLD, expect=CAL_HOLD, offset_hz=2000.0,
         what="CAL 1 nA hold at 50 nA/V",
         offset_note=("Hold set 14:14:45–14:14:49 by the Experimenter (the user chose \"Move above zero\").  "
                      "dark-equivalent = S4 − 2000 Hz (nominal 1e5 Hz/V × 1 nA / 50 nA/V).\n"
                      "CONFOUND: S4 drift = dark drift + CAL-generator drift; this record cannot separate them "
                      "(0.05 % of the CAL offset = 1 Hz).  Set 3 A measured this CAL at 2001.0 Hz above the dark,\n"
                      "so the absolute dark-equivalent is uncertain by ~1 Hz; its drift is not.")),
]
# The CAL hold was interrupted at 14:22:08–14:22:25 by the user (CAL/UNCAL and u toggles; user
# 2026-11-12: "Yes, that was me."). The latest stretch in the hold state after the first hold window
# gets its own window: it starts at the last A3 change whose resulting readback is the hold state,
# and ends at the next change (or the last count).


def _latest_cal_hold_start(lg):
    ch = [c for c in all_changes(lg) if c[0] > T_CAL_HOLD + 1]
    for t, *_ in reversed(ch):
        st = {pv: L.setting_at(lg, pv, t + 0.01) for pv in CAL_HOLD}
        if all(st[pv] and st[pv][1] == want for pv, want in CAL_HOLD.items()):
            return t
    return None


INTERIM = {"A3sens_num": "5", "A3sens_unit": "uA/V", "A3offset_cal": "CAL", "A3offset_num": "2",
           "A3offset_unit": "nA", "A3offset_on": "ON", "A3offset_sign": "+"}


def _first_reach(lg, expect, after_t):
    """Time of the first A3 change after `after_t` that leaves the readback equal to `expect`."""
    for t, *_ in (c for c in all_changes(lg) if c[0] > after_t):
        st = {pv: L.setting_at(lg, pv, t + 0.01) for pv in expect}
        if all(st[pv] and st[pv][1] == want for pv, want in expect.items()):
            return t
    return None


def _interim_start(lg):
    if "set5" not in L.SWEEP_FILES:
        return None
    t5 = [s for s in L.load_steps("set5") if s.step == "R"][0].t_end
    return _first_reach(lg, INTERIM, t5)


HOLDS.append(dict(HOLDS[-1], key="cal1nA_latest", start=_latest_cal_hold_start,
                  what="CAL 1 nA hold at 50 nA/V, after the user's 14:22 changes",
                  offset_note=HOLDS[-1]["offset_note"].replace(
                      "Hold set 14:14:45–14:14:49 by the Experimenter (the user chose \"Move above zero\").",
                      "Hold resumed after the user's A3 changes at 14:22:08–14:22:25 (confirmed by the user).")))
# Interim operating configuration after set 5 (Experimenter, ~15:20:44; the user: "set MonC to 5uA/V
# and set the offset such that counts are less than 120 Hz"). Nominal CAL 2 nA at 5 uA/V = 40 Hz.
HOLDS.append(dict(key="interim_5uA_cal2nA", start=_interim_start, expect=INTERIM, offset_hz=40.0,
                  what="interim configuration 5 µA/V, CAL +2 nA",
                  offset_note=("Set ~15:20:44 by the Experimenter (the user: \"set MonC to 5uA/V and set the offset such that "
                               "counts are less than 120 Hz\").  dark-equivalent = S4 − 40 Hz (nominal 1e5 Hz/V × 2 nA / 5 µA/V).\n"
                               "CONFOUND: S4 drift = dark drift + CAL-generator drift (0.5 % of the 40 Hz offset = 0.2 Hz).  "
                               "Sets 4/5 put the 5 µA/V CAL ratios at 0.995–1.003, so the absolute dark-equivalent\n"
                               "is uncertain by ≲ 0.2 Hz from the offset itself.")))


ELI5_HOLD = {
    "after_sweep2": "after sweep 2, offset knob at its usual +6",
    "after_rerun1": "after the re-run, offset knob at its usual +6",
    "cal1nA_hold": "with a known 1 nA test signal added on top",
    "cal1nA_latest": "with a known 1 nA test signal added, after your 14:22 changes",
    "interim_5uA_cal2nA": "at MonC's everyday gain, with a small known test signal",
}


def make_dark(lg, ev, hold):
    """One dark-record window. PROVISIONAL while it is the open (last) window."""
    t_ev = hold["start"](lg)
    if t_ev is None:
        say(f"[logger] logger_dark_{hold['key']}.png: not made (no such window yet)")
        return None
    t0 = t_ev + SKIP_S
    if t0 >= lg.t_last:
        say(f"[logger] logger_dark_{hold['key']}.png: not made (window starts after the last count)")
        return None
    early = [c for c in all_changes(lg) if t_ev < c[0] <= t0]
    if early:
        raise SystemExit(f"REFUSED {hold['key']}: A3 change inside the {SKIP_S:.0f} s skip: {early[:3]}")
    later = [c for c in all_changes(lg) if c[0] > t0]
    # a hand-made input change (no readback shows it) also ends the window, like a setting change
    later += [(c["t0"], f"input change {c['tag']}: {c['short']}", None, None)
              for c in L.INPUT_CHANGES if c["t1"] > t0]
    later.sort(key=lambda c: c[0])
    t1 = later[0][0] if later else lg.t_last
    state = L.settings_during(lg, t0, t1 - 0.01)
    bad = {pv: (state[pv][1], want) for pv, want in hold["expect"].items()
           if (state[pv][1] if pv != "A3off_u_put" else f"{state[pv][0]:.0f}") != want}
    if bad:
        raise SystemExit(f"REFUSED {hold['key']}: readback does not match the hold's expected state: {bad}")
    off = hold["offset_hz"]
    z0 = L.v2f_zero(lg)
    m = (lg.scaler_t - 1.0 >= t0) & (lg.scaler_t <= t1)
    t, s4 = lg.scaler_t[m], lg.S4[m]
    clip = s4 <= CLIP_COUNTS
    # Excursions: isolated counts far from the record's median (robust scale). Shown, listed and
    # excluded from every average; never silently dropped.
    med = np.median(s4[~clip]) if (~clip).any() else np.nan
    mad = 1.4826 * np.median(np.abs(s4[~clip] - med)) if (~clip).any() else np.nan
    exc_thr = max(10.0, 10 * mad)
    exc = (~clip) & (np.abs(s4 - med) > exc_thr)
    bounds = np.array([b for sw in L.SWEEP_FILES for s in L.load_steps(sw) for b in (s.t_start, s.t_end)])
    good = ~clip & ~exc
    is_open = not later
    fig = plt.figure(figsize=(14, 9))
    gs = GridSpec(3, 1, figure=fig, height_ratios=[3.2, 1.0, 0.8], hspace=0.12,
                  left=0.07, right=0.93, top=0.80 if hold["offset_hz"] else 0.855, bottom=0.08)
    ax = fig.add_subplot(gs[0])
    a3 = fig.add_subplot(gs[1], sharex=ax)
    ar = fig.add_subplot(gs[2], sharex=ax)
    ax.plot(dt(t[good]), s4[good], ".", ms=3, color=BLUE, alpha=0.5, label="S4, one dot per 1 s count")
    if off == 0:
        ylo, ytop = 0, (max(30, np.percentile(s4[good], 99.5) * 1.3) if good.any() else 30)
        ax.axhline(CLIP_COUNTS, color=CLIP_INK, lw=0.8, ls="--")
        ax.text(local(t0), CLIP_COUNTS + 0.3, " " + CLIP_TEXT, fontsize=7, color=CLIP_INK, va="bottom")
        zero_line(ax, z0, x_text=local(t0), fontsize=7)
    else:
        span = max(25.0, 1.3 * (np.percentile(s4[good], 99.5) - np.percentile(s4[good], 0.5))) if good.any() else 25
        ylo, ytop = med - span, med + span
    if clip.any():
        ax.plot(dt(t[clip]), np.full(clip.sum(), max(CLIP_COUNTS, ylo + 1)), "v", ms=4, mfc="none", mec=CLIP_INK,
                label=f"clipped: S4 ≤ 1 count ({clip.sum()} counts) — never averaged as values")
    exc_lines = []
    if exc.any():
        ytag = ytop - 0.03 * (ytop - ylo)
        ax.plot(dt(t[exc]), np.full(exc.sum(), ytag), "^", ms=7, color=ORANGE,
                label=f"excursion: |S4 − median| > {exc_thr:.0f} counts, drawn at the top edge ({exc.sum()} counts) — excluded from averages")
        for te, ve in zip(t[exc], s4[exc]):
            d = np.min(np.abs(bounds - te)) if len(bounds) else np.inf
            ax.annotate(f"{ve:.0f}", (local(te), ytag), xytext=(5, -3), textcoords="offset points",
                        fontsize=7, color=ORANGE, va="top")
            exc_lines.append(f"{hms(te)} S4 = {ve:.0f}" + (f" ({d:.0f} s from a sweep step boundary)" if d < 120 else ""))
    W = 60
    if len(s4) >= W:
        k = np.ones(W) / W
        rm = np.convolve(s4, k, mode="valid")
        ok = np.convolve((~good).astype(float), k, mode="valid") == 0
        tm = t[W - 1:]
        rm = np.where(ok, rm, np.nan)
        ax.plot(dt(tm), rm, "-", color=INK, lw=1.4,
                label=f"{W}-count trailing mean (gaps: window contains a clipped or excursion count)")
    ax.set_ylabel("S4, counts per 1 s count (= Hz)")
    ax.set_ylim(ylo, ytop)
    if off:
        sec_y = ax.secondary_yaxis("right", functions=(lambda y: y - off, lambda d: d + off))
        sec_y.set_ylabel(f"dark-equivalent = S4 − {off:.0f} Hz", fontsize=8.5)
    ax.legend(loc="upper right", fontsize=7.5, markerscale=2)
    dur_min = (t[-1] - t[0]) / 60 if len(t) else 0
    txt = []
    if dur_min >= 30:
        a = (t <= t[0] + 600) & good
        b = (t >= t[-1] - 600) & good
        txt.append(f"first 10 min ({hms(t[0])}–{hms(t[0] + 600)}): mean S4 {s4[a].mean():.2f} Hz, sd {s4[a].std(ddof=1):.2f}, n {a.sum()}")
        txt.append(f"last 10 min ({hms(t[-1] - 600)}–{hms(t[-1])}): mean S4 {s4[b].mean():.2f} Hz, sd {s4[b].std(ddof=1):.2f}, n {b.sum()}")
        txt.append(f"difference over {dur_min:.0f} min: {s4[b].mean() - s4[a].mean():+.2f} Hz "
                   f"(model-free; the unit is still warming up, so no single drift rate is quoted)")
    else:
        txt.append(f"record only {dur_min:.0f} min long: no drift summary (needs ≥ 30 min after the last setting change)")
    if off == 0:
        txt.append(f"headroom: median {med:.0f} counts, {med - z0['mean']:.1f} Hz above the V2F zero-input rate "
                   f"({z0['mean']:.2f} Hz) and ~{med - CLIP_COUNTS:.0f} counts above the 1-count clip; "
                   "a downward drift larger than that would be hidden by clipping")
    else:
        txt.append(f"median S4 {med:.1f} Hz → dark-equivalent {med - off:+.1f} Hz; the clip is {med - CLIP_COUNTS:.0f} counts below")
    if exc_lines:
        txt.append("excursions (no A3 setting change logged): " + "; ".join(exc_lines))
    ax.text(0.995, 0.04, "\n".join(txt), transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5, color=INK)
    context_panels(a3, ar, lg, m, ev, t0, t1)
    for a in (ax, a3):
        plt.setp(a.get_xticklabels(), visible=False)
    ar.set_xlabel(time_axis(ar, t0, t1))
    ax.set_xlim(local(t0), local(t1))
    sec = ax.secondary_xaxis("top", functions=(lambda x: (x - mdates.date2num(local(ev["power_on"]))) * 1440,
                                               lambda m_: m_ / 1440 + mdates.date2num(local(ev["power_on"]))))
    sec.set_xlabel("minutes since the SR570 was switched on (13:29:56)", fontsize=8)
    st = (f"{state['A3sens_num'][1]} {state['A3sens_unit'][1]}, offset {state['A3offset_num'][1]} "
          f"{state['A3offset_unit'][1]} {state['A3offset_on'][1]} {state['A3offset_cal'][1]}, "
          f"sign {state['A3offset_sign'][1]}" + (f", u = {state['A3off_u_put'][0]:+.0f}" if state["A3offset_cal"][1] == "UNCAL" else ""))
    top = header(
        fig, 0.07,
        f"Does MonC's no-signal count creep over time? ({ELI5_HOLD.get(hold['key'], hold['what'])})",
        f"MonC dark record: {hold['what']}" + (" — PROVISIONAL, still accumulating" if is_open else ""),
        f"From {hms(t_ev)} + {SKIP_S:.0f} s ({hms(t0)}) to "
        + ((f"the next A3 setting change ({hms(t1)}, {later[0][1]})" if later[0][2] is not None
            else f"the next hand-made change ({hms(t1)}, {later[0][1]})") if later else f"the last count ({hms(t1)})")
        + f".  EPICS readback, checked constant over the window: {st}.\n"
        + (hold.get("offset_note", "") + "\n" if off else "")
        + "No beam on MonC; MonP (S3) and ring current are context only.  A setting change ends the window.",
        extra_in=0.45)   # the top axis (minutes since power-on) needs room
    gs.update(top=top)
    inlabel(ax, "MonC's counter every second, with no X-rays going in")
    footer(fig, lg)
    p = save(fig, f"logger_dark_{hold['key']}.png")
    say(f"[logger] {p.name}: {hms(t0)}-{hms(t1)}, {len(t)} counts, median {med:.1f}, {exc.sum()} excursions; {txt[0]}")
    return p


def make(lg: L.Logger):
    ev = find_events(lg)
    ch = all_changes(lg)
    sub = (f"MonC SR570 (15IDC:A3) → V2F → scaler1.S4, raw 1 s counts.  Shaded: sweep step count windows "
           "(grey: sweeps 1/1b, SR570 OFF; blue: live sweeps); hatched: A3 changes outside every step log.\n"
           f"Orange dashed: SR570 switched on ({hms(ev['power_on'])}, first count {ev['s4_on']:.0f}); "
           f"aqua dashed: A3init ({hms(ev['a3init'])}, all EPICS settings re-sent).  "
           f"Lower panels: EPICS readbacks of the A3 settings ({len(ch)} changes in this record; logged on change).\n"
           "Before power-on, writes reached EPICS only, not the switched-off unit.  "
           "S4 ≤ 1 count = clipped (unipolar V2F floor, output well below 0 V).")
    p1 = timeseries(lg, ev, lg.t_first, lg.t_last, "logger_overview.png",
                    "Everything MonC's counter recorded, with every knob change and the switch-on marked",
                    f"MonC 1 s logger record, {local(lg.t_first):%Y-%m-%d %H:%M} to {local(lg.t_last):%Y-%m-%d %H:%M}: "
                    "S4 with sweep steps, setting changes and power-on", sub)
    t0, t1 = ev["power_on"] - 300, min(lg.t_last, ev["a3init"] + 600)
    p2 = timeseries(lg, ev, t0, t1, "logger_poweron_sweep2.png",
                    "Close-up: switching MonC's amplifier on, letting it warm up, then sweep 2",
                    "MonC power-on, warm-up and sweep 2 (zoom)", sub)
    p3 = [make_dark(lg, ev, h) for h in HOLDS]
    say(f"[logger] {p1.name}, {p2.name}: power-on {hms(ev['power_on'])} (S4 {ev['s4_on']:.0f}), "
        f"A3init {hms(ev['a3init'])}, {len(ch)} A3 changes")
    return [p1, p2, *[p for p in p3 if p]]
