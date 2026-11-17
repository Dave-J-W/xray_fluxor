"""MonC's uncertainty at one fixed energy (10 keV): what it is, what it is made of, and whether it is honest.

  unc10_summary.png   every source on one log axis: the absolute flux budget (σ_s terms), then the error of a
                      reading used for normalisation at one energy, case by case (same gain, hours, days, a gain
                      change, a stale dark, a beam move), at the typical 200 kHz and at 10 kHz
  unc10_vs_rate.png   the normalisation error at one energy against count rate: measured noise, the dark cases,
                      linearity, and the combined error for readings minutes, hours and days apart
  unc10_check.png     is the stated relative error honest? Grid-to-grid repeats of the same CAL step (4-9 h apart)
                      against noise + fresh dark; the absolute budget has no reference to check against
  unc10_legacy.png    point-to-point error of the method before this repo (raw counts, no dark, no P/T correction,
                      nominal gain ratio) against this repo, by time between the points, and for a flux or gain change

Numbers come from their sources, not retyped: the live budget terms (calc/quality_slots.py SYMMETRIC_TERMS), the
per-gain table (data/calibration/monc_sr570_ranges.csv), the weather statistics (analysis/out/pressure_climatology.txt,
hutch_temperature.txt), the collection-length model (analysis/out/collection_length_cmc.csv), the flux formula
(calc/monp_transform.full_physics) and the raw logger (noise, fresh dark, grid repeats, interim level, linearity fit).
Two numbers are quoted, not recomputed: linearity below 10 kHz (ELECTRONICS_CONCLUSIONS §1: up to 0.7 %, not settled)
and the typical MonC rate (2e5 cps, ELECTRONICS_CONCLUSIONS §3). Read-only toward EPICS and hardware.
"""
from __future__ import annotations

import csv
import itertools
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

import loaders as L
import fig_electronics as FE
from common import (AQUA, BLUE, GRAY, INK, INK2, ORANGE, footer, header, hms, local, save, say, titled)
from fig_night import night_rows

sys.path[:0] = [str(L.ROOT / "calc"), str(L.ROOT / "data" / "queries")]
import monp_transform as MT   # noqa: E402
import quality_slots as QS    # noqa: E402

E_KEV = 10.0
T_C, P_KPA = 24.9, 98.99        # site mean (physics_note.md §1)
S_OP = 5000.0                   # nA/V: MonC's interim gain; the photons/s axis is drawn for it
F_TYP = 2e5                     # Hz, typical MonC rate (ELECTRONICS_CONCLUSIONS §3: "At the typical 2×10⁵ cps")
F_LOW = 1e4                     # Hz, the low end of the measured linearity (10-450 kHz)
F_MAX = 4e5                     # Hz, operating rule: lower the gain above 400 kHz
E_ERR_ASSUMED = 1e-3            # F9.7: ASSUMED 0.1 % energy error
LIN_LOW_PCT = 0.7               # ELECTRONICS_CONCLUSIONS §1: below 10 kHz up to +0.7 %, not settled (quoted)
TARGET = 0.6827                 # coverage of ±1 sigma for a Gaussian

MEAS, BOUND, ASSUMED = "measured", "bound / type B", "assumed"
MARK = {MEAS: "o", BOUND: "s", ASSUMED: "^"}
GROUP_COL = {"abs": BLUE, "rel": AQUA, "spoil": ORANGE}
ABS_NAMES = {"mu_en/rho tables": ("absorption tables μ_en/ρ (NIST vs Chantler/Elam)", BOUND, "F9.1"),
             "collection length (guarded)": ("collection length l_eff (2-D field model)", BOUND, "F4.4"),
             "cross-section fit": ("cross-section fit inside the calc slot (worst at 25 keV)", BOUND, "F9.4"),
             "electronics": ("SR570 gain × V2F scale, absolute (type B)", BOUND, "F5.3"),
             "W": ("W(N₂), energy per ion pair", BOUND, "F9.2"),
             "energy readback": ("mono energy readback (0.1 % in E)", ASSUMED, "F9.7"),
             "density (live P, T)": ("gas density from live P and T", BOUND, "F9.3")}


# ---------------------------------------------------------------- sources
def cal_table():
    p = L.ROOT / "data" / "calibration" / "monc_sr570_ranges.csv"
    with open(p, encoding="utf-8") as fh:
        lines = [x for x in fh if not x.startswith("#")]
    out = {}
    for r in csv.DictReader(lines):
        if r["measured"] == "1" or r["dark_Hz"]:
            num, unit = r["sensitivity"].split()
            S = float(num) * {"nA/V": 1.0, "uA/V": 1e3}[unit]
            out[S] = dict(factor=float(r["factor"]), u=float(r["u_factor_rel"]), measured=r["measured"] == "1",
                          dark=float(r["dark_Hz"]) if r["dark_Hz"] else None,
                          dark_sd=float(r["dark_sd_reselect_Hz"]) if r["dark_sd_reselect_Hz"] else None)
    return out


def weather():
    """{hours: (median %, 95th %)} for pressure; {hours: 95th % in density} for hutch temperature."""
    pr, tp = {}, {}
    for line in open(L.ROOT / "analysis" / "out" / "pressure_climatology.txt", encoding="utf-8"):
        m = re.match(r"change over\s+(\d+) h: \|median\| = ([\d.]+) %\s+95th pct = ([\d.]+) %", line)
        if m:
            pr[int(m[1])] = (float(m[2]), float(m[3]))
    for line in open(L.ROOT / "analysis" / "out" / "hutch_temperature.txt", encoding="utf-8"):
        m = re.match(r"\|change\| over\s+(\d+) h: .*\(95th = ([\d.]+) % in density\)", line)
        if m:
            tp[int(m[1])] = float(m[2])
    if not pr or not tp:
        raise SystemExit("REFUSED: weather statistics not found in analysis/out/")
    return pr, tp


def beam_move_pct():
    """l_eff change for a 1 mm vertical beam move (both directions), %, from the 2-D model."""
    d = {}
    for line in open(L.ROOT / "analysis" / "out" / "collection_length_cmc.csv", encoding="utf-8"):
        if line.startswith("beam_z_"):
            f = line.split(",")
            d[f[0]] = float(f[5])
    return abs(d["beam_z_+1"]), abs(d["beam_z_-1"])


def phot(rate_hz, S_nA=S_OP):
    """photons/s at 10 keV, site-mean gas, from the standard formula (no wall loss below 13 keV)."""
    return MT.full_physics(rate_hz, S_nA * 1e-9, E_KEV, T_C, P_KPA)


def dlnphi_dlnE():
    h = 0.01
    return (np.log(MT.full_physics(1e5, 5e-6, E_KEV + h, T_C, P_KPA))
            - np.log(MT.full_physics(1e5, 5e-6, E_KEV - h, T_C, P_KPA))) / (np.log(E_KEV + h) - np.log(E_KEV - h))


def noise_points(rows, G):
    """Per CAL step of grids 2-4: (S, net rate Hz, sd of successive differences / √2 in Hz, plain sd in Hz).
    The successive-difference sd leaves out the slow settling inside a step; both are kept."""
    out = []
    for g in (2, 3, 4):
        for r in rows:
            if r["step"].startswith(f"g{g}_") and r["on"] == "ON" and r["cal"] == "CAL":
                v = r["stat"].values
                out.append((r["S"], r["stat"].mean - G[g]["dark"][r["S"]][0],
                            float(np.std(np.diff(v), ddof=1) / np.sqrt(2)), float(v.std(ddof=1))))
    return np.array(out)


def grid_repeats(G, exclude=(FE.NOISY_DARK_S,)):
    """Every ladder point measured in two of grids 2-4: actual relative change of the dark-subtracted rate, and the
    stated short-term error (count noise of each step mean, and its own grid's dark-mean error, in quadrature)."""
    pts = {g: {(p["S"], p["I"]): p for p in G[g]["pts"]} for g in (2, 3, 4)}
    out = []
    for a, b in itertools.combinations((2, 3, 4), 2):
        for k in sorted(set(pts[a]) & set(pts[b])):
            if k[0] in exclude:
                continue
            pa, pb = pts[a][k], pts[b][k]
            da, db = G[a]["dark"][k[0]], G[b]["dark"][k[0]]
            fa, fb = pa["f"] - da[0], pb["f"] - db[0]
            st = np.hypot(np.hypot(pa["sem"], da[1] / np.sqrt(da[2])), np.hypot(pb["sem"], db[1] / np.sqrt(db[2]))) / fa
            out.append(dict(pair=(a, b), S=k[0], I=k[1], f=fa, e=(fb - fa) / fa, stated=st, dt_h=(pb["t"] - pa["t"]) / 3600))
    return out


def coverage(rep, k):
    z = np.abs(np.array([r["e"] / r["stated"] for r in rep]))
    return float(np.mean(z < k))


def k_cal(rep):
    return float(np.quantile(np.abs([r["e"] / r["stated"] for r in rep]), TARGET))


def bootstrap(rep, n=2000, seed=1):
    """Block bootstrap: a block is one (grid pair, range), whose points share a dark and a drift."""
    blocks = {}
    for r in rep:
        blocks.setdefault((r["pair"], r["S"]), []).append(r)
    keys = list(blocks)
    rng = np.random.default_rng(seed)
    cov1, kc = [], []
    for _ in range(n):
        smp = [x for i in rng.integers(0, len(keys), len(keys)) for x in blocks[keys[i]]]
        cov1.append(coverage(smp, 1.0))
        kc.append(k_cal(smp))
    return float(np.std(cov1)), float(np.std(kc)), len(keys)


def state_now(lg):
    """MonC's last hour in the logger: mean S4, the A3 readback, and the last hand-made input change."""
    t1 = lg.t_last
    t0 = t1 - 3600
    ch = [t for pv in L.A3_STATE_PVS for t, *_ in lg.settings.get(pv, []) if t0 < t <= t1]
    m = (lg.scaler_t > t0) & (lg.scaler_t <= t1)
    st = L.settings_during(lg, t0, t1) if not ch else None
    return dict(t0=t0, t1=t1, S4=float(lg.S4[m].mean()), n=int(m.sum()), changed=bool(ch),
                setting=(f"{st['A3sens_num'][1]} {st['A3sens_unit'][1]}, offset {st['A3offset_num'][1]} "
                         f"{st['A3offset_unit'][1]} {st['A3offset_on'][1]} {st['A3offset_cal'][1]}") if st else "changed",
                input=L.input_state_at(t1))


def gather(lg):
    rows = night_rows(lg)
    G = FE.grid_points(rows)
    F0 = {g: FE.joint_fit(G[g]["pts"], exclude=(FE.NOISY_DARK_S,)) for g in (2, 3, 4)}
    c_per_V = float(np.mean([F0[g]["c"] for g in F0]))
    cal = cal_table()
    NP = noise_points(rows, G)
    noise_hz = float(np.median(NP[:, 2]))
    s_same, n_same, *_ = FE.same_selection_5u(rows)
    holds = [r["stat"].mean for r in rows if r["block"] == "interim_hold"]
    ba = FE.interim_before_after(lg)
    rep = grid_repeats(G)
    rms_rep = {dt: float(np.sqrt(np.mean([r["e"] ** 2 for r in rep if abs(r["dt_h"] - dt) < 1.5]))) for dt in (4.3, 8.6)}
    stated_med = float(np.median([r["stated"] for r in rep]))
    # per reading: a change between two grids carries two readings' wander
    wander = float(np.sqrt(max(np.mean([r["e"] ** 2 - r["stated"] ** 2 for r in rep]), 0) / 2))
    cov_se, kc_se, nblk = bootstrap(rep)
    pr, tp = weather()
    bm = beam_move_pct()
    g5 = cal[S_OP]
    steps = {S: 100 * (v["factor"] / g5["factor"] - 1) for S, v in cal.items() if v["measured"] and S != S_OP}
    steps_u = {S: 100 * np.hypot(v["u"], g5["u"]) for S, v in cal.items() if v["measured"] and S != S_OP}
    return dict(rows=rows, G=G, c_per_V=c_per_V, cal=cal, NP=NP, noise_hz=noise_hz, s_same=s_same, n_same=n_same,
                hold=float(np.mean(holds)), n_hold=len(holds), ba=ba, rep=rep, rms_rep=rms_rep, stated_med=stated_med,
                wander=wander, cov1=coverage(rep, 1.0), kc=k_cal(rep), cov_se=cov_se, kc_se=kc_se, nblk=nblk,
                pr=pr, tp=tp, bm=bm, steps=steps, steps_u=steps_u, dlnE=dlnphi_dlnE(), now=state_now(lg),
                sigma_s=QS.OTHER_TERMS, terms=dict(QS.SYMMETRIC_TERMS), OL=offset_lags(lg), wm=weather_median(),
                transfer=transfer_sigma_pct())


# ---------------------------------------------------------------- the error models (fractions of the net rate)
def rel_short(B, f, dark_hz):
    """One 1 s reading at one gain: count noise and the dark's error, in quadrature, as a fraction."""
    return np.hypot(B["noise_hz"], dark_hz) / f


def rel_hours(B, f):
    return np.hypot(rel_short(B, f, B["s_same"]), B["wander"])


def rel_days_live(B, f):
    return np.hypot(rel_hours(B, f), B["terms"]["density (live P, T)"])


def lin(B, f, f_ref=F_TYP, S=S_OP):
    """Linearity between a reading at f and one at f_ref, same gain: c × the change in SR570 output (V)."""
    return abs(B["c_per_V"]) * abs(f - f_ref) / FE.K_HZ_PER_V


# ---------------------------------------------------------------- figure 1: the summary
def _rows(B):
    """(group, label, value at 200 kHz %, value at 10 kHz % or None, evidence, note)"""
    out = []
    for k, (lab, ev, fid) in ABS_NAMES.items():
        v = 100 * B["terms"][k]
        note = f"{fid}"
        if k == "energy readback":
            note += f"; at 10 keV itself {100 * E_ERR_ASSUMED * B['dlnE']:.2f} % (d ln Φ/d ln E = {B['dlnE']:.2f})"
        out.append(("abs", lab, v, None, ev, note))
    out.append(("abs", "TOTAL, absolute photons/s (σ_s, quadrature)", 100 * B["sigma_s"], None, BOUND,
                f"F9.5; bounds ×{QS.LOW_FACTOR:.3f} / ×{QS.HIGH_FACTOR:.3f}; no wall loss at 10 keV; never tested"))
    n = B["noise_hz"]
    out.append(("rel", "same gain, seconds to minutes apart, fresh dark (noise + dark)",
                100 * rel_short(B, F_TYP, B["s_same"]), 100 * rel_short(B, F_LOW, B["s_same"]), MEAS,
                f"noise {n:.2f} Hz per 1 s count, dark from the same selection ±{B['s_same']:.2f} Hz"))
    out.append(("rel", "same gain, 4–9 h apart (grid repeats, CAL source, no beam)",
                100 * rel_hours(B, F_TYP), 100 * rel_hours(B, F_LOW), MEAS,
                f"adds a slow wander of {100 * B['wander']:.4f} % (unc10_check); rms {100 * B['rms_rep'][4.3]:.4f} % at 4.3 h, "
                f"{100 * B['rms_rep'][8.6]:.4f} % at 8.6 h"))
    out.append(("rel", "days apart, normalised to the live photons/s (density corrected)",
                100 * rel_days_live(B, F_TYP), 100 * rel_days_live(B, F_LOW), BOUND,
                f"adds the density term {100 * B['terms']['density (live P, T)']:.1f} % (F9.3), a bound, not yet tested"))
    pr, tp = B["pr"], B["tp"]
    for h, lab in ((1, "1 h"), (24, "1 day"), (72, "3 days")):
        out.append(("spoil", f"raw counts (no density correction), {lab} apart: pressure",
                    pr[h][1], pr[h][0], MEAS, f"2025 airport record; hutch temperature adds up to {tp[h]:.2f} % (95th)"))
    smax = max(B["steps"].items(), key=lambda kv: abs(kv[1]))
    out.append(("spoil", "a gain change, nominal ratio (worst: 5 → " + FE._rng(smax[0]) + ")", abs(smax[1]), None, MEAS,
                "F5.6, against 5 µA/V: " + ", ".join(f"{FE._rng(S)} {v:+.2f} %" for S, v in sorted(B["steps"].items()))))
    out.append(("spoil", "a gain change, with the measured factors", max(B["steps_u"].values()), None, MEAS,
                f"F5.4/F5.5 (draft slot calc/monc_gain_cal.py, not installed); worst pair {FE._rng(max(B['steps_u'], key=B['steps_u'].get))}"))
    out.append(("spoil", "dark from an earlier selection of 5 µA/V (stale)",
                100 * rel_short(B, F_TYP, B["cal"][S_OP]["dark_sd"]), 100 * rel_short(B, F_LOW, B["cal"][S_OP]["dark_sd"]),
                MEAS, f"F5.2: ±{B['cal'][S_OP]['dark_sd']:.1f} Hz at 5 µA/V; 20 µA/V ±{B['cal'][20000.0]['dark_sd']:.0f} Hz"))
    out.append(("spoil", "dark not subtracted (interim no-beam level)", 100 * B["hold"] / F_TYP, 100 * B["hold"] / F_LOW,
                MEAS, f"{B['hold']:.1f} Hz chamber cabled ({B['n_hold']} holds); "
                + (f"{B['ba']['after']['mean']:.1f} Hz detached" if B["ba"] else "")))
    out.append(("spoil", "comparing a 10 kHz reading with a 200 kHz one (linearity)", 100 * lin(B, F_LOW), None, MEAS,
                f"c = {100 * B['c_per_V']:+.4f} %/V (grids, without 20 µA/V); below 10 kHz up to {LIN_LOW_PCT} %, not settled"))
    out.append(("spoil", "the beam moves 1 mm vertically (collection length)", max(B["bm"]), None, BOUND,
                f"2-D model: +{B['bm'][0]:.2f} / −{B['bm'][1]:.2f} % per mm; no wall loss below 13 keV"))
    return out


def _wrap(s, width):
    import textwrap
    return "\n".join(line for para in s.split("\n") for line in textwrap.wrap(para, width, break_on_hyphens=False))


def _fmt(v):
    return f"{v:.2g} %" if v < 0.01 else f"{v:.3g} %"


def make_summary(lg, B):
    R = _rows(B)
    fig = plt.figure(figsize=(16, 13))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.0, 1.35], wspace=0.0, left=0.28, right=0.99, bottom=0.07)
    ax = fig.add_subplot(gs[0])
    axn = fig.add_subplot(gs[1], sharey=ax)
    y, ys, heads = 0, [], []
    for grp, title in (("abs", "ABSOLUTE photons/s (cancels in any ratio at one energy)"),
                       ("rel", "ONE ENERGY, ONE GAIN: one normalisation reading"),
                       ("spoil", "ONE ENERGY: what spoils it, each on its own")):
        heads.append((y, title))
        y += 1
        for r in [r for r in R if r[0] == grp]:
            ys.append((y, r))
            y += 1
        y += 0.6
    vt = axn.get_yaxis_transform()
    for yy, (grp, lab, v, v_low, ev, note) in ys:
        col = GROUP_COL[grp]
        bold = lab.startswith("TOTAL")
        ax.plot([v], [yy], MARK[ev], color=col, ms=9.5 if bold else 7.5, mec="white", mew=0.6, zorder=3)
        txt = _fmt(v)
        if v_low is not None and abs(v_low / v - 1) > 0.02:
            ax.plot([v_low], [yy], MARK[ev], mfc="white", mec=col, mew=1.4, ms=7.5, zorder=3)
            ax.plot([min(v, v_low), max(v, v_low)], [yy, yy], "-", color=col, lw=1.2, zorder=2)
            txt = (f"{_fmt(v_low)} median\n{txt} 95th" if lab.startswith("raw counts") else f"{txt} at 200 kHz\n{_fmt(v_low)} at 10 kHz")
        axn.text(0.015, yy, txt, transform=vt, fontsize=8.5, va="center", color=INK, weight="bold" if bold else "normal",
                 linespacing=1.1)
        ax.text(-0.01, yy, lab, transform=ax.get_yaxis_transform(), fontsize=8.5, va="center", ha="right", color=INK,
                weight="bold" if bold else "normal")
        axn.text(0.245, yy, _wrap(note, 85), fontsize=7.5, va="center", color=INK2, transform=vt, linespacing=1.1)
    for yy, title in heads:
        ax.text(-0.01, yy, title, transform=ax.get_yaxis_transform(), fontsize=9.5, weight="bold", va="center",
                ha="right", color=INK)
    ax.axvline(100 * B["sigma_s"], color=BLUE, lw=0.8, ls=":", zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(1e-4, 10)
    ax.set_ylim(y, -0.8)
    ax.set_yticks([])
    ax.set_xlabel("uncertainty, % of the flux (log scale; one sd, or a bound used as one sd)")
    ax.grid(axis="y", visible=False)
    axn.axis("off")
    hdl = [Line2D([], [], marker=MARK[k], color=INK2, ls="none", ms=7, label=k) for k in (MEAS, BOUND, ASSUMED)]
    hdl += [Line2D([], [], marker="o", mfc="white", mec=INK2, ls="none", ms=7,
                   label="open: at 10 kHz\n(weather rows: the median)")]
    hdl += [Line2D([], [], color=GROUP_COL[g], lw=5, label=t) for g, t in
            (("abs", "absolute budget"), ("rel", "normalisation, one gain"), ("spoil", "what spoils normalisation"))]
    ax.legend(handles=hdl, loc="upper left", bbox_to_anchor=(0.0, 0.995), fontsize=7.5, frameon=True, framealpha=0.95,
              edgecolor="none")
    titled(ax, "How big is each source of error, on its own?", "filled marker: at the typical 200 kHz")
    nw = B["now"]
    rep_h = 100 * rel_hours(B, F_TYP)
    sub = _wrap(
        "At one energy every constant of the chamber (absorption tables, W, collection length, the electronics' absolute "
        "scale) is the same in every reading, so it cancels in a ratio. What is left for normalisation is anything that "
        "differs between readings. 'Bound' rows are type-B judgements used as one standard deviation.\n"
        f"Photons/s at 10 keV for MonC at 5 µA/V (formula, site-mean gas): 200 kHz = {phot(F_TYP):.2g} ph/s, "
        f"10 kHz = {phot(F_LOW):.2g} ph/s.  Not in any row: state errors (a gain changed at the front panel, the "
        "SR570 off, the chamber unplugged) and harmonics.\n"
        f"MONC'S CHAMBER: {nw['input']} (CHAMBER_FACTS F7.2).  Last hour in the logger ({hms(nw['t0'])}–{hms(nw['t1'])} "
        f"{local(nw['t1']):%d %b}): S4 {nw['S4']:.1f} Hz at {nw['setting']}.  Until it is reconnected MonC measures no "
        "beam, and its dark must be re-measured (the cabled chamber adds ~21.5 Hz, F6.2).\n"
        "MonP: the same absolute budget; its electronics were never measured, so a gain change is uncertain by up to "
        "0.7 % (F5.3), and its dark is 182–227 Hz (F13.1).\n"
        "The method before this repo (raw counts, no dark subtracted, no pressure or temperature correction, nominal gain "
        "ratio) is the 'raw counts', 'gain change, nominal ratio' and 'dark not subtracted' rows; point to point it is "
        "compared with this repo in unc10_legacy.", 200)
    top = header(
        fig, 0.02,
        f"MonC at 10 keV: photons/s ±{100 * B['sigma_s']:.1f} %; at one energy a reading repeats to ~{rep_h:.3f} % "
        f"(a ratio of two: ~{np.sqrt(2) * rep_h:.3f} %), unless weather, gain or dark spoil it",
        "MonC uncertainty at a fixed energy of 10 keV: absolute budget and normalisation error, source by source",
        sub, extra_in=0.45)
    gs.update(top=top)
    footer(fig, lg, "sources: calc/quality_slots.py, data/calibration/monc_sr570_ranges.csv, analysis/out/*.txt, raw logger")
    return save(fig, "unc10_summary.png")


# ---------------------------------------------------------------- figure 2: against count rate
def make_vs_rate(lg, B):
    fig = plt.figure(figsize=(15, 10.5))
    gs = GridSpec(1, 1, figure=fig, left=0.07, right=0.70, bottom=0.08)
    ax = fig.add_subplot(gs[0])
    f = np.logspace(np.log10(1e3), np.log10(F_MAX), 300)
    NP = B["NP"]
    ax.plot(NP[:, 1], 100 * NP[:, 2] / NP[:, 1], ".", color=GRAY, ms=5, alpha=0.7, zorder=2,
            label=f"measured noise, one 1 s count ({len(NP)} CAL steps, grids 2–4, every gain)")
    ax.plot(f, 100 * B["noise_hz"] / f, "-", color=GRAY, lw=1.0, label=f"  its median: {B['noise_hz']:.2f} Hz / rate")
    ax.plot(f, 100 * B["s_same"] / f, "--", color=AQUA, lw=1.2, label=f"fresh dark, same selection: ±{B['s_same']:.2f} Hz")
    sd5 = B["cal"][S_OP]["dark_sd"]
    ax.plot(f, 100 * sd5 / f, "--", color=ORANGE, lw=1.2, label=f"stale dark, earlier selection: ±{sd5:.1f} Hz (5 µA/V)")
    ax.plot(f, 100 * B["hold"] / f, ":", color=ORANGE, lw=1.6, label=f"dark not subtracted: {B['hold']:.1f} Hz (interim, cabled)")
    ax.plot(f, 100 * lin(B, f), "-.", color=INK2, lw=1.0, label="linearity: a reading at this rate compared\nwith one at 200 kHz, same gain (systematic)")
    ax.axvspan(1e3, F_LOW, color=GRAY, alpha=0.10, lw=0)
    ax.text(1.05e3, 0.45, f"below 10 kHz linearity is\nnot settled (up to {LIN_LOW_PCT} %)", fontsize=7.5, color=INK2, va="top")
    # combined scenarios
    ax.plot(f, 100 * rel_short(B, f, B["s_same"]), "-", color=INK, lw=2.6, label="A  minutes apart, same gain, fresh dark")
    ax.plot(f, 100 * rel_hours(B, f), "-", color=BLUE, lw=2.6, label=f"B  hours apart: A + wander {100 * B['wander']:.4f} % (measured)")
    ax.plot(f, 100 * rel_days_live(B, f), "-", color=AQUA, lw=2.6,
            label=f"C  days apart, live photons/s: B + density {100 * B['terms']['density (live P, T)']:.1f} % (bound)")
    pr = B["pr"]
    ax.axhspan(pr[24][0], pr[24][1], color=ORANGE, alpha=0.10, lw=0)
    ax.text(3.5e5, pr[24][1] * 0.93, f"raw counts a day apart:\n{pr[24][0]:.2f} % median – {pr[24][1]:.2f} % (95th)",
            fontsize=7.5, color=INK, ha="right", va="top")
    for v, t in ((F_TYP, "typical 200 kHz"), (F_MAX, "400 kHz: lower the gain")):
        ax.axvline(v, color=INK2, lw=0.8, ls=":")
        ax.text(v * 0.97, 2.0e-5, t, rotation=90, fontsize=7.5, color=INK2, ha="right", va="bottom")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1e3, F_MAX * 1.05)
    ax.set_ylim(1e-5, 10)
    ax.set_xlabel("MonC net count rate (signal above dark), Hz")
    ax.set_ylabel("error of one reading as a fraction of it, % (log)")
    sec = ax.secondary_xaxis("top", functions=(lambda x: x * phot(1.0), lambda p: p / phot(1.0)))
    sec.set_xlabel(f"photons/s at 10 keV if MonC is at 5 µA/V (formula, site-mean gas; scales with the gain)", fontsize=8.5)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8, frameon=False, labelspacing=0.9,
              title="thin: one source each\nthick: combined, readings minutes (A),\nhours (B) and days (C) apart",
              title_fontsize=8, alignment="left")
    top = header(
        fig, 0.07,
        f"MonC at one energy: ~{100 * rel_hours(B, 2e4):.3f} % over hours above 20 kHz; across days the untested "
        f"density correction (≤ {100 * B['terms']['density (live P, T)']:.1f} %) dominates",
        "MonC normalisation error at 10 keV against count rate, one gain (5 µA/V darks)",
        "Each line is the error of ONE reading's net rate relative to the truth, after the common scale (which cancels) "
        "is removed.  A ratio of two readings carries both readings' errors.\n"
        f"Noise: sd of successive 1 s counts / √2 in each CAL step (it leaves out the slow settling within a step).  "
        f"Wander: what the grid repeats need beyond noise and dark (unc10_check).\n"
        "The dark lines are for 5 µA/V; other gains: elec5.  A gain change adds a step (F5.6, up to 0.62 % nominal, "
        "≤ 0.03 % with the measured factors), and a 1 mm beam move ~0.28 %: see unc10_summary.\n"
        f"MonC's chamber is {B['now']['input']}: these are the electronics with the chamber cabled (overnight 2026-11-12/13).",
        extra_in=0.55)
    gs.update(top=top)
    footer(fig, lg)
    return save(fig, "unc10_vs_rate.png")


# ---------------------------------------------------------------- figure 3: is it honest?
def make_check(lg, B):
    rep = B["rep"]
    e = np.abs([r["e"] for r in rep])
    s = np.array([r["stated"] for r in rep])
    dt = np.array([r["dt_h"] for r in rep])
    fig = plt.figure(figsize=(15, 7.8))
    gs = GridSpec(1, 2, figure=fig, wspace=0.28, left=0.07, right=0.97, bottom=0.11)
    a1, a2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    for d, col, lab in ((4.3, AQUA, "4.3 h apart (g2→g3, g3→g4)"), (8.6, BLUE, "8.6 h apart (g2→g4)")):
        m = np.abs(dt - d) < 1.5
        a1.plot(100 * s[m], 100 * e[m], "o", color=col, ms=6, mec="white", mew=0.5, label=lab)
    lim = np.array([1e-5, 0.1])
    a1.plot(lim, lim, "-", color=INK, lw=1, label="|change| = stated")
    a1.plot(lim, B["kc"] * lim, "--", color=INK2, lw=1, label=f"|change| = {B['kc']:.1f} × stated (k_cal)")
    a1.set_xscale("log")
    a1.set_yscale("log")
    a1.set_xlim(*lim)
    a1.set_ylim(1e-6, 0.1)
    a1.set_xlabel("stated short-term error of the change: noise + fresh dark, both grids, %")
    a1.set_ylabel("actual |change| of the same CAL step between grids, %")
    a1.legend(loc="upper left", fontsize=8)
    titled(a1, "Does the short-term error cover a repeat hours later?", "each point: one CAL step (gain, level) in two grids")
    k = np.linspace(0, 6, 300)
    a2.plot(k, [100 * coverage(rep, x) for x in k], "-", color=BLUE, lw=2, label="actual repeats")
    from math import erf, sqrt
    a2.plot(k, [100 * erf(x / sqrt(2)) for x in k], "-", color=GRAY, lw=1.2, label="if the stated error were right (Gaussian)")
    rep_w = [dict(r, stated=float(np.hypot(r["stated"], np.sqrt(2) * B["wander"]))) for r in rep]
    a2.plot(k, [100 * coverage(rep_w, x) for x in k], "--", color=AQUA, lw=1.6,
            label=f"with the wander {100 * B['wander']:.4f} % added to each grid (fitted here: not a test)")
    a2.axhline(100 * TARGET, color=INK2, lw=0.7, ls=":")
    a2.axvline(1, color=INK2, lw=0.7, ls=":")
    a2.set_xlim(0, 6)
    a2.set_ylim(0, 102)
    a2.set_xlabel("k: the error allowed is k × stated")
    a2.set_ylabel("share of repeats with |change| < k × stated, %")
    a2.legend(loc="lower right", fontsize=8)
    titled(a2, "How often is the change inside the stated error?", "coverage curve; target at k = 1 is 68 %")
    a2.text(0.98, 0.42, f"k = 1: {100 * B['cov1']:.0f} ± {100 * B['cov_se']:.0f} % covered (target 68 %)\n"
            f"k_cal = {B['kc']:.2f} ± {B['kc_se']:.2f}\n(block bootstrap over {B['nblk']} gain × grid-pair blocks)",
            transform=a2.transAxes, ha="right", fontsize=8.5, color=INK,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.9))
    verdict = "too small" if B["kc"] - 2 * B["kc_se"] > 1 else ("too large" if B["kc"] + 2 * B["kc_se"] < 1 else "about right")
    top = header(
        fig, 0.07,
        f"Noise and dark alone are {verdict} for readings hours apart (k_cal {B['kc']:.1f}): MonC also wanders by "
        f"~{100 * B['wander']:.3f} %, which is still tiny",
        "Check of MonC's relative (one-energy) error: grid-to-grid repeats of the same CAL step, 4–9 h apart",
        f"{len(rep)} repeats: every ladder point (gain × CAL level) measured in two of the overnight grids 2–4, 20 µA/V left "
        "out (its dark jumps inside a step, F9).  Each grid's own dark is subtracted (a fresh dark).\n"
        "Confound: the CAL current source is in both readings, so its drift is in the 'wander' too; it is an upper bound on "
        "the electronics' wander.  No beam (the CAL current only, chamber cabled): weather and beam position are not "
        "tested here.\n"
        "ABSOLUTE budget (±3.6 %): NOT CHECKED. There is no independent flux measurement to compare with (UNCERTAINTY.md §7); "
        "a calibrated diode or a pixel detector with foils would test it.",
        extra_in=0.45)
    gs.update(top=top)
    footer(fig, lg)
    return save(fig, "unc10_check.png")


# ---------------------------------------------------------------- figure 4: the old method against this repo
# The method before this repo (the user, 2026-11-17): raw counts, no dark subtracted, no pressure or temperature
# correction, and (implicitly) the nominal SR570 ratio across a gain change. This repo: dark subtracted (measured after
# the last gain change), live density (airport pressure, tools/asos_pressure.py, hourly reports; hutch Sensor2), and
# the measured per-gain factors (calc/monc_gain_cal.py: a DRAFT, not installed).
LAGS_S = np.array([1, 10, 60, 600, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 86400, 2 * 86400, 3 * 86400])
LEGACY_FLUX_STEP = 0.10          # a 10 % flux change between the two points, for the unsubtracted-dark case
MIN_STRETCH_S = 86400            # the offset record must span at least a day


def offset_lags(lg):
    """rms change of one 1 s count of S4 between two times τ apart, at one fixed setting (no A3 change), from the
    longest stretch after the last A3 change. It is the offset's own wander plus the noise of both counts, in Hz."""
    ch = sorted(t for pv in L.A3_STATE_PVS for t, *_ in lg.settings.get(pv, []) if t > lg.t_first + 0.5)
    t0 = ch[-1] + 120
    t1 = lg.t_last
    if t1 - t0 < MIN_STRETCH_S:
        return None
    hit = L.input_changes_during(t0, t1)
    if hit:
        t0 = hit[-1]["t1"] + 120
    st = L.settings_during(lg, t0, t1)
    m = (lg.scaler_t - 1 >= t0) & (lg.scaler_t <= t1)
    t, v = lg.scaler_t[m], lg.S4[m]
    grid = np.full(int(round(t[-1] - t[0])) + 1, np.nan)
    grid[np.round(t - t[0]).astype(int)] = v
    out = []
    for lag in LAGS_S:
        if lag < len(grid) // 2:
            d = grid[lag:] - grid[:-lag]
            d = d[np.isfinite(d)]
            out.append((lag, float(np.sqrt(np.mean(d ** 2))), len(d)))
    return dict(t0=t0, t1=t1, lags=np.array(out), mean=float(np.nanmean(grid)), input=L.input_state_at(t1),
                setting=f"{st['A3sens_num'][1]} {st['A3sens_unit'][1]}, {st['A3offset_cal'][1]} {st['A3offset_num'][1]} "
                        f"{st['A3offset_unit'][1]} {st['A3offset_on'][1]}")


def weather_median():
    """{hours: median raw-count change %} from pressure and hutch temperature, combined in quadrature (≈)."""
    tmed = {}
    for line in open(L.ROOT / "analysis" / "out" / "hutch_temperature.txt", encoding="utf-8"):
        m = re.match(r"\|change\| over\s+(\d+) h: median ([\d.]+) C", line)
        if m:
            tmed[int(m[1])] = 100 * float(m[2]) / (273.15 + T_C)
    pr, _ = weather()
    return {h: (pr[h][0], pr[h][1], tmed.get(h)) for h in pr}


def transfer_sigma_pct():
    vals = [float(m[1]) for line in open(L.ROOT / "analysis" / "out" / "asos_intercompare.txt", encoding="utf-8")
            if (m := re.search(r"1 sigma\(robust\) [\d.]+ hPa = ([\d.]+) %", line))]
    if not vals:
        raise SystemExit("REFUSED: station-transfer scatter not found in analysis/out/asos_intercompare.txt")
    return float(np.median(vals))


def events(B, f):
    """(label, old %, new %) for the cases where the two methods differ even at τ ≈ 0."""
    cal, g5 = B["cal"], B["cal"][S_OP]
    D5 = B["hold"]
    rows = [(f"flux changes by {100 * LEGACY_FLUX_STEP:.0f} % between the points (dark left in, {D5:.0f} Hz)",
             100 * LEGACY_FLUX_STEP * D5 / f, 100 * LEGACY_FLUX_STEP * B["s_same"] / f)]
    for S in sorted(s for s, v in cal.items() if v["measured"] and s != S_OP):
        v = cal[S]
        fa, fb = f, f * S_OP / S                            # the same flux read at the other gain
        if fb > F_MAX:                                      # would break the 400 kHz rule: put the other gain at f instead
            fa, fb = f * S / S_OP, f
        old = 100 * abs((1 + g5["dark"] / fa) / (1 + v["dark"] / fb) * (v["factor"] / g5["factor"]) - 1)
        new = 100 * np.sqrt(v["u"] ** 2 + g5["u"] ** 2 + (B["s_same"] / fa) ** 2 + (v["dark_sd"] / fb) ** 2)
        rows.append((f"gain change: 5 µA/V at {fa / 1e3:.0f} kHz ↔ {FE._rng(S)} at {fb / 1e3:.0f} kHz", old, new))
    return rows


def p2p_models(B, OL, f):
    """Point-to-point error (%) of the ratio of two readings τ apart, steady flux, same gain: old method vs this repo.
    Below 1 h the weather is NOT in the totals (hourly records can't resolve it); it is shown as a band '≤ 1-h value'.
    The repo's density residual is a band: low = report resolution (two readings) ⊕ report age (≤ 1 h of weather);
    high = √2 × station transfer ⊕ report age."""
    tau = OL["lags"][:, 0]
    elec = 100 * OL["lags"][:, 1] / f                       # offset wander + noise of both counts (measured)
    scale = np.where(tau >= 3600, 100 * np.sqrt(2) * B["wander"], 0.0)   # measured at 4.3 and 8.6 h; assumed from 1 h
    WM = B["wm"]
    hrs = np.array(sorted(WM))
    med = np.array([np.hypot(WM[h][0], WM[h][2] or 0) for h in hrs])
    long_ = tau >= 3600
    raw = np.where(long_, np.interp(np.log(np.maximum(tau / 3600, 1)), np.log(hrs), med), 0.0)
    lo_d = np.where(long_, B["dens_lo"], 0.0)
    hi_d = np.where(long_, B["dens_hi"], 0.0)
    base = np.hypot(elec, scale)
    return dict(tau=tau, elec=elec, scale=scale, raw=raw, old=np.hypot(base, raw), new_lo=np.hypot(base, lo_d),
                new_hi=np.hypot(base, hi_d), w1h=float(med[0]), long=long_)


def make_legacy(lg, B):
    OL = B["OL"]
    if OL is None:
        say("[unc10] unc10_legacy.png: not made (no stretch of a day at one setting)")
        return None
    fig = plt.figure(figsize=(16, 13))
    gt = GridSpec(1, 2, figure=fig, wspace=0.20, left=0.06, right=0.985)
    gb = GridSpec(1, 1, figure=fig, left=0.34, right=0.90, bottom=0.06, top=0.30)
    axes = [fig.add_subplot(gt[0, 0]), fig.add_subplot(gt[0, 1])]
    xt = [1, 60, 3600, 86400, 3 * 86400]
    xl = ["1 s", "1 min", "1 h", "1 day", "3 days"]
    bound = 100 * B["terms"]["density (live P, T)"]
    for ax, f in zip(axes, (F_TYP, F_LOW)):
        M = p2p_models(B, OL, f)
        tau, L_ = M["tau"], M["long"]
        S_ = ~L_                                            # below 1 h: electronics only (weather unresolved)
        tl = np.append(tau[S_], 3600.0)
        base_h = float(M["elec"][L_][0])                    # the scale wander starts at 1 h (assumed), so not before
        left = np.append(M["old"][S_], base_h)
        ax.plot(tl, left, "-", color=ORANGE, lw=2.8)
        ax.plot(tl, left, "-", color=BLUE, lw=1.0)
        ax.plot(tau[L_], M["old"][L_], "-", color=ORANGE, lw=2.8, label="BEFORE: raw counts, no dark subtracted, no P/T correction")
        ax.fill_between(tau[L_], M["new_lo"][L_], M["new_hi"][L_], color=BLUE, alpha=0.35, lw=0,
                        label="NOW: this repo (dark subtracted, live density): somewhere in this band")
        ax.plot(tau[L_], M["new_hi"][L_], "-", color=BLUE, lw=1.0)
        ax.plot(tau[L_], M["new_lo"][L_], "-", color=BLUE, lw=1.0)
        ax.plot([3600, 3600], [base_h, M["old"][L_][0]], ":", color=INK2, lw=0.8)
        ax.fill_between(tau[L_], M["new_hi"][L_], np.full(L_.sum(), bound), color=BLUE, alpha=0.07, lw=0,
                        label=f"… up to the {bound:.1f} % density bound (the correction is untested)")
        hrs = np.array(sorted(B["wm"]))
        ax.fill_between(hrs * 3600, [B["wm"][h][0] for h in hrs], [B["wm"][h][1] for h in hrs], color=ORANGE,
                        alpha=0.12, lw=0, label="pressure change in raw counts: median to 95th percentile")
        ax.plot(tau, M["elec"], "--", color=INK2, lw=1.2, label="electronics: offset wander + noise of both counts (measured; same in both)")
        ax.fill_between([1, 3600], [1e-6, 1e-6], [M["w1h"]] * 2, color=GRAY, alpha=0.12, lw=0,
                        label=f"below 1 h: + the weather, ≤ its 1-h median {M['w1h']:.3f} % (hourly records can't resolve it; "
                              "not corrected by either method)")
        k = int(np.argmin(np.abs(tau - 86400)))
        ax.annotate(f"1 day: {M['old'][k]:.2f} % → {M['new_lo'][k]:.2f}–{M['new_hi'][k]:.2f} %", (tau[k], M["new_hi"][k]),
                    xytext=(-175, -45) if f >= 1e5 else (-190, -70), textcoords="offset points", fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.6))
        j = int(np.argmin(np.abs(tau - 60)))
        ax.annotate(f"1 min: {M['old'][j]:.4f} % in both (+ ≤ {M['w1h']:.2f} % weather)", (tau[j], M["old"][j]),
                    xytext=(-20, 28), textcoords="offset points", fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.6))
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(1, tau[-1] * 1.2)
        ax.set_ylim(1e-4 if f >= 1e5 else 1e-3, 5)
        ax.set_xticks(xt)
        ax.set_xticklabels(xl)
        ax.set_xlabel("time between the two points")
        ax.set_ylabel("point-to-point error of the ratio, % (typical)")
        titled(ax, f"At {f / 1e3:.0f} kHz: how far apart can two points be?",
               f"steady flux, same gain (5 µA/V), 1 s readings; MonC at 5 µA/V: {phot(f):.1e} ph/s at 10 keV")
    h, l = axes[0].get_legend_handles_labels()
    # events
    ax = fig.add_subplot(gb[0])
    ev = events(B, F_TYP) + [(lab + " [at 10 kHz]", o, n) for lab, o, n in events(B, F_LOW)[:1]]
    lo_x = 1e-5
    for i, (lab, o, n) in enumerate(ev):
        nn = max(n, lo_x * 1.3)
        ax.plot([nn, o], [i, i], "-", color=GRAY, lw=1.0, zorder=1)
        ax.plot([o], [i], "o", color=ORANGE, ms=8, mec="white", zorder=3)
        ax.plot([nn], [i], "<" if n < lo_x * 1.3 else "o", color=BLUE, ms=8, mec="white", zorder=3)
        ax.text(1.01, i, f"{_fmt(o)} → {_fmt(n)}", transform=ax.get_yaxis_transform(), fontsize=8.5, va="center", color=INK)
    ax.set_yticks(range(len(ev)))
    ax.set_yticklabels([e[0] for e in ev], fontsize=8.5)
    ax.set_ylim(len(ev) - 0.5, -0.5)
    ax.set_xscale("log")
    ax.set_xlim(lo_x, 10)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("error of the ratio of the two points, % (orange: before; blue: now; ◀ below the axis)")
    titled(ax, "When something changes between two points, however far apart they are",
           f"at {F_TYP / 1e3:.0f} kHz unless marked; before: nominal SR570 ratio, offset-OFF darks left in (F5.1); "
           "now: measured per-gain factors (DRAFT slot, not installed) and a dark after the change")
    M2 = p2p_models(B, OL, F_TYP)
    kd = int(np.argmin(np.abs(M2["tau"] - 86400)))
    worst_gain = max(o for _, o, _ in events(B, F_TYP)[1:])
    top = header(
        fig, 0.06,
        f"Point to point, the old method is as good as this repo within an hour; across a day it is "
        f"{M2['old'][kd] / M2['new_hi'][kd]:.0f}–{M2['old'][kd] / M2['new_lo'][kd]:.0f}× worse, and a gain change costs up "
        f"to {worst_gain:.1f} %",
        "MonC at 10 keV, one energy: point-to-point error of the method before this repo, and of this repo",
        _wrap(
            "Point-to-point error = the error in the ratio of two MonC readings that normalise two data points, after "
            "everything common to both (absorption tables, W, collection length, the absolute gain) has cancelled. "
            "Typical size: rms for the electronics, median for the weather.  At a steady flux and one gain, a dark left in "
            "cancels in the ratio; it matters only when the flux or the gain changes (bottom panel).\n"
            f"Electronics: the rms change of one 1 s count of S4 τ apart, measured over {(OL['t1'] - OL['t0']) / 86400:.1f} "
            f"days at {OL['setting']}, {local(OL['t0']):%d %b %H:%M}–{local(OL['t1']):%d %b %H:%M}, input: {OL['input']}. It "
            "includes the CAL source, so it is an upper bound.  From 1 h on, the scale wander of the grid repeats "
            f"({100 * np.sqrt(2) * B['wander']:.4f} % per pair; measured at 4.3 and 8.6 h, assumed from 1 h) is added.\n"
            "Weather: 2025 airport pressure and the 2024–26 hutch temperature (analysis/out), medians, combined in quadrature "
            "(an approximation).  The live correction uses hourly airport reports and the hutch Sensor2: within an hour it "
            "corrects nothing, and when a new report arrives the corrected flux steps by that hour's change.  Its residual "
            f"between points hours apart lies between {B['dens_lo']:.3f} % (report resolution and age) and {B['dens_hi']:.3f} % "
            f"(√2 × the {B['transfer']:.3f} % station-to-site scatter, and age); it has not been tested (UNCERTAINTY.md §7).\n"
            "Not shown: a dark not re-measured after a gain change (flagged by status bit 2), state errors, a beam move "
            "(0.28 %/mm, either method).  MonC's chamber is unplugged (F7.2): these are the electronics; no beam was measured.",
            205),
        extra_in=0.45)
    gt.update(top=top, bottom=0.46)
    fig.legend(h, l, loc="center", bbox_to_anchor=(0.5, 0.375), ncol=2, fontsize=7.8, frameon=False)
    footer(fig, lg, "sources: raw logger, analysis/out/{pressure_climatology,hutch_temperature,asos_intercompare}.txt, "
                    "data/calibration/monc_sr570_ranges.csv")
    return save(fig, "unc10_legacy.png")


def make(lg):
    if "night" not in L.SWEEP_FILES:
        say("[unc10] no overnight step log: skipped")
        return
    B = gather(lg)
    say(f"[unc10] noise {B['noise_hz']:.2f} Hz per count; fresh dark {B['s_same']:.2f} Hz; wander {100 * B['wander']:.4f} %; "
        f"repeats n {len(B['rep'])}, rms 4.3 h {100 * B['rms_rep'][4.3]:.4f} %, 8.6 h {100 * B['rms_rep'][8.6]:.4f} %, "
        f"coverage at k=1 {100 * B['cov1']:.0f} +- {100 * B['cov_se']:.0f} %, k_cal {B['kc']:.2f} +- {B['kc_se']:.2f}; "
        f"c {100 * B['c_per_V']:+.4f} %/V; dlnPhi/dlnE {B['dlnE']:.2f}; sigma_s {100 * B['sigma_s']:.2f} %; "
        f"now: S4 {B['now']['S4']:.1f} Hz, {B['now']['setting']}, input {B['now']['input']}")
    for r in _rows(B):
        say(f"[unc10]   {r[0]:5s} {r[2]:9.5f} %" + (f" (10 kHz {r[3]:.5f} %)" if r[3] is not None else "") + f"  {r[1]}")
    q = 100 * 0.01 * 3386.389 / (P_KPA * 1e3) / np.sqrt(6)   # 0.01 inHg report resolution, two readings (uniform)
    B["dens_lo"] = float(np.hypot(q, B["pr"][1][0]))
    B["dens_hi"] = float(np.hypot(np.sqrt(2) * B["transfer"], B["pr"][1][0]))
    return [make_summary(lg, B), make_vs_rate(lg, B), make_check(lg, B), make_legacy(lg, B)]
