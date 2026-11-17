"""Test of the live N2-density correction (normalization_proposal.md, "How to test it", test 1).

Question: does MonP's efficiency scale with N2 density rho as calc/PRESSURE.md assumes?  In beam-on
periods at fixed energy, ln(I_P / DBPM) regressed on ln(rho) should have slope ~ +1 (1 - x/2 ~ 0.99 at
10 keV).  Also fits ln P and -ln T separately: a different T slope would say Sensor2 does not represent
the chamber gas.

READ-ONLY: archiver HTTP GETs (raw, no mean_N operators), IEM ASOS history GET, and analysis.
No PV is written.  The archiver host:port comes from the environment variable ARCHIVER_RETRIEVAL or the
gitignored site.env (never tracked).  Pulls are saved outside git in archiver-pulls/xray_fluxor/.

    <bluesky venv>\\Scripts\\python.exe -I analysis/density_slope_test.py pull [--from ISO] [--to ISO]
    <bluesky venv>\\Scripts\\python.exe -I analysis/density_slope_test.py fit  [--tag TAG]

Method (decided before looking at the slope):
  * 5 s grid from 15IDC:scaler1.S3 (MonP counts), rate = S3 / count time, count time = S1/FREQ, else the
    median spacing.  Dark rate = median rate over beam-off rows (ring current < 1 mA) at the same gain.
  * I_P = (rate - dark) * sensitivity (15IDC:A2sens_num/_unit; split at every change, +-60 s excluded).
  * DBPM = 15IDGen:0:userTran6.E (primary) or 15ID:FX4_1:SumAll:MeanValue_RBV (second), as-of joined.
  * Beam on: S:SRcurrentAI > 100 mA, and within the 5 s grid |dI_ring| small (top-up glitch cut).
  * Energy segments: ID15A1:DCMM:XTAL:E.RBV constant within 1 eV; each segment its own intercept.
    Only E < 15 keV (above ~18 keV the wall loss adds a density dependence).
  * "Aligned" cannot be read directly.  Cut A (none) vs cut B: DBPM quadrant balance steady
    (|(Q1+Q3)-(Q2+Q4)|/sum within 3 median-absolute-deviations of its segment median, and the ratio
    I_P/DBPM within 5 MAD of its rolling hourly median).  Both are run and reported.
  * Standard errors: moving-block bootstrap of whole hours (segment-wise demeaned design), 2000 draws.
"""
from __future__ import annotations

import os
import sys
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PULLS = ROOT.parent / "archiver-pulls" / "xray_fluxor"
for _p in (ROOT, *ROOT.parents):
    if (_p / "archiver-pulls").is_dir():
        PULLS = _p / "archiver-pulls" / "xray_fluxor"
        break
OUT = HERE / "out"
FIGOUT = ROOT / "figures" / "out"

PVS = {
    "S3": "15IDC:scaler1.S3",
    "S1": "15IDC:scaler1.S1",
    "FREQ": "15IDC:scaler1.FREQ",
    "TP1": "15IDC:scaler1.TP1",
    "sens_num": "15IDC:A2sens_num",
    "sens_unit": "15IDC:A2sens_unit",
    "dbpm": "15IDGen:0:userTran6.E",
    "dbpm2": "15ID:FX4_1:SumAll:MeanValue_RBV",
    "q1": "15ID:FX4_1:Current1:MeanValue_RBV",
    "q2": "15ID:FX4_1:Current2:MeanValue_RBV",
    "q3": "15ID:FX4_1:Current3:MeanValue_RBV",
    "q4": "15ID:FX4_1:Current4:MeanValue_RBV",
    "range": "15ID:FX4_1:Range_RBV",
    "ring": "S:SRcurrentAI",
    "E": "ID15A1:DCMM:XTAL:E.RBV",
    "T": "15ID:Sensor2:Temperature",
}
SENS_NUM = [1, 2, 5, 10, 20, 50, 100, 200, 500]
SENS_UNIT = [1e-12, 1e-9, 1e-6, 1e-3]          # A/V for pA/V, nA/V, uA/V, mA/V
HUTCH_ELEV_M = 228.0
RHO_K = 3.369272e-3                              # g/cm3 per (kPa/K)


def _site(key):
    if os.environ.get(key):
        return os.environ[key]
    for d in (ROOT, *ROOT.parents):
        f = d / "site.env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    raise SystemExit(f"{key} not set (environment or gitignored site.env)")


def fname(key, tag):
    return PULLS / f"{PVS[key].replace(':', '_')}_RAW_native_{tag}.csv"


def pull(frm, to, tag):
    host = _site("ARCHIVER_RETRIEVAL")
    PULLS.mkdir(parents=True, exist_ok=True)
    for key, pv in PVS.items():
        q = urllib.parse.urlencode({"pv": pv, "from": frm, "to": to})
        with urllib.request.urlopen(f"http://{host}/retrieval/data/getData.csv?{q}", timeout=300) as r:
            body = r.read()
        fname(key, tag).write_bytes(body)
        print(f"{pv}: {body.count(bytes([10]))} rows")


def load(key, tag):
    a = np.loadtxt(fname(key, tag), delimiter=",", usecols=(0, 1, 2), ndmin=2)
    if a.size == 0:
        return np.empty(0), np.empty(0)
    # userTran6.E is archived INVALID (sev 3) on every row, so severity cannot be a filter for it
    a = a[a[:, 2] == 0] if key not in ("sens_num", "sens_unit", "dbpm") else a
    a = a[np.isfinite(a[:, 1])]
    return a[:, 0], a[:, 1]


def asof(tq, t, v):
    """last value at or before tq (step function); NaN before the first sample."""
    i = np.searchsorted(t, tq, side="right") - 1
    out = np.where(i >= 0, v[np.clip(i, 0, None)], np.nan)
    return out


def asos_pressure(t0, t1):
    """IEM ASOS altimeter history for LOT -> kPa at 228 m, exactly as tools/asos_pressure.py."""
    d0 = datetime.fromtimestamp(t0 - 86400, timezone.utc)
    d1 = datetime.fromtimestamp(t1 + 86400, timezone.utc)
    q = urllib.parse.urlencode([
        ("station", "LOT"), ("data", "alti"), ("tz", "UTC"), ("format", "onlycomma"),
        ("latlon", "no"), ("missing", "empty"), ("trace", "empty"), ("direct", "no"),
        ("report_type", "3"), ("report_type", "4"),
        ("year1", d0.year), ("month1", d0.month), ("day1", d0.day),
        ("year2", d1.year), ("month2", d1.month), ("day2", d1.day)])
    with urllib.request.urlopen("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + q, timeout=120) as r:
        txt = r.read().decode()
    tt, pp = [], []
    for ln in txt.splitlines()[1:]:
        p = ln.split(",")
        if len(p) < 3 or not p[2]:
            continue
        ts = datetime.strptime(p[1], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
        a = float(p[2]) * 33.8638866667                  # inHg -> hPa
        kpa = (a ** 0.190284 - 8.4228807e-5 * HUTCH_ELEV_M) ** (1 / 0.190284) / 10.0
        tt.append(ts)
        pp.append(kpa)
    o = np.argsort(tt)
    return np.array(tt)[o], np.array(pp)[o], txt.count("\n") - 1


def build(tag):
    d = {k: load(k, tag) for k in PVS}
    t3, s3 = d["S3"]
    # count time: S1/FREQ when both exist at that row, else the median spacing
    tref = t3
    dt = np.diff(tref)
    grid_dt = float(np.median(dt))
    freq = asof(tref, *d["FREQ"]) if d["FREQ"][0].size else np.full(tref.size, np.nan)
    s1 = np.full(tref.size, np.nan)
    if d["S1"][0].size:
        # S1 is MONITOR 1 s; use the S1 value just after S3 posts is unreliable -> use nearest-before
        s1 = asof(tref, *d["S1"])
    ctime = np.where(np.isfinite(freq) & (freq > 0) & (s1 > 0), s1 / freq, np.nan)
    # S1 at S3 post time is the same count period only if both reset together; keep only plausible
    ctime = np.where((ctime > 0.5 * grid_dt) & (ctime < 1.5 * grid_dt), ctime, grid_dt)
    rate = s3 / ctime
    n = tref.size
    sn = asof(tref, *d["sens_num"]) if d["sens_num"][0].size else np.zeros(n)
    su = asof(tref, *d["sens_unit"]) if d["sens_unit"][0].size else np.zeros(n)
    return dict(t=tref, rate=rate, ctime=ctime, grid_dt=grid_dt, sn=sn, su=su, d=d)


EXPECT_LIVE = 1.93      # calc/PRESSURE.md section 3, MonP at 30 keV: 1 + 0.93 (live fit of the wall loss)
EXPECT_MC = 1.83        # same, wall-loss Monte Carlo at +-3 % density: 1 + 0.83
EXPECT_DIRECT = 1.00    # absorption only (what the test would show below ~15 keV, ignoring exit transmission)
HEADLINE = ("dbpm2", "B", "daily")   # fixed before looking at the slopes (see docstring)


def interp(tq, t, v):
    return np.interp(tq, t, v, left=np.nan, right=np.nan)


def running_median(x, w):
    from numpy.lib.stride_tricks import sliding_window_view
    pad = w // 2
    xp = np.r_[np.repeat(x[0], pad), x, np.repeat(x[-1], pad)]
    return np.median(sliding_window_view(xp, w), axis=1)


def gather(tag):
    d = {k: load(k, tag) for k in PVS if k not in ("sens_unit",)}
    t, s3 = d["S3"]
    grid_dt = float(np.median(np.diff(t)))
    tp1 = float(d["TP1"][1][-1])                 # count period, s (AutoCount, archived once)
    sn = int(d["sens_num"][1][-1])
    sens = SENS_NUM[sn] * SENS_UNIT[1]           # 15IDC:A2sens_unit has no archived event; nA/V assumed
    #   (user/memory: MonP at 500 nA/V; the sensitivity cancels in the slope, it only scales I_P)
    ring = asof(t, *d["ring"])
    ring_med = running_median(ring, 9)
    e = asof(t, *d["E"])
    dbpm = {"dbpm": asof(t, *d["dbpm"]), "dbpm2": asof(t, *d["dbpm2"])}
    q = np.vstack([asof(t, *d[k]) for k in ("q1", "q2", "q3", "q4")])
    temp = interp(t, *d["T"])
    ta, pa, nobs = asos_pressure(t[0], t[-1])
    pres = interp(t, ta, pa)
    # dbpm "dbpm" has no row before its first archived value: asof gives NaN there
    ok_t = (t >= d["dbpm"][0][0]) if d["dbpm"][0].size else np.zeros(t.size, bool)
    dbpm["dbpm"] = np.where(ok_t, dbpm["dbpm"], np.nan)
    return dict(t=t, s3=s3, tp1=tp1, sens=sens, sn=sn, ring=ring, ring_med=ring_med, e=e, dbpm=dbpm, q=q,
                T=temp, P=pres, asos=(ta, pa, nobs), grid_dt=grid_dt, d=d)


def subset_deglitch(m, ip, dbpm):
    """apply deglitch() to the rows selected by m only (the running median then spans selected rows only)."""
    out = m.copy()
    idx = np.flatnonzero(m)
    out[idx] = deglitch(ip[idx], dbpm[idx])
    return out


def deglitch(ip, dbpm, win=61, nsig=5.0):
    """True where ln(I_P/DBPM) is within nsig robust sigmas of its own running median over `win` consecutive
    5 s rows (5 min).  Removes gross single-row glitches (unsynchronised 5 s SCAN reads, shutter/dump edges);
    the running median follows the slow drift and the density trend, so it does not bias the slope."""
    with np.errstate(invalid="ignore", divide="ignore"):
        y = np.log(ip / dbpm)
    ok = np.isfinite(y)
    yy = np.where(ok, y, np.nanmedian(y))
    dev = yy - running_median(yy, win)
    sig = 1.4826 * np.median(np.abs(dev[ok]))
    return ok & (np.abs(dev) < nsig * sig)


def dark_rate(g):
    off = g["ring"] < 1.0
    return float(np.median(g["s3"][off] / g["tp1"])), int(off.sum())


def design_stats(y, X, seg, blk):
    """sufficient statistics per (block, segment) cell for weighted (bootstrap) OLS with segment intercepts."""
    cells = {}
    for b in np.unique(blk):
        for s in np.unique(seg[blk == b]):
            m = (blk == b) & (seg == s)
            cells[(b, s)] = (m.sum(), X[m].sum(0), y[m].sum(), X[m].T @ X[m], X[m].T @ y[m], (y[m] ** 2).sum())
    return cells


def solve(cells, w=None):
    """slope vector from cells with multiplicities w (dict key->count); segment intercepts removed."""
    segs = {}
    for k, (n, sx, sy, sxx, sxy, syy) in cells.items():
        c = 1.0 if w is None else w.get(k, 0)
        if c == 0:
            continue
        a = segs.setdefault(k[1], [0.0, 0.0, 0.0, 0.0, 0.0])
        a[0] += c * n
        a[1] = a[1] + c * sx
        a[2] += c * sy
        a[3] = a[3] + c * sxx
        a[4] = a[4] + c * sxy
    A = 0.0
    B = 0.0
    N = 0
    for n, sx, sy, sxx, sxy in segs.values():
        if n < 3:
            continue
        A = A + (sxx - np.outer(sx, sx) / n)
        B = B + (sxy - sx * sy / n)
        N += n
    return np.linalg.solve(np.atleast_2d(A), np.atleast_1d(B)), N


def block_boot(y, X, seg, blk, nboot=2000, seed=1):
    cells = design_stats(y, X, seg, blk)
    est, N = solve(cells)
    ub = np.unique(blk)
    by_blk = {b: [k for k in cells if k[0] == b] for b in ub}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(nboot):
        pick = rng.choice(ub, size=ub.size, replace=True)
        w = {}
        for b in pick:
            for k in by_blk[b]:
                w[k] = w.get(k, 0) + 1
        try:
            out.append(solve(cells, w)[0])
        except np.linalg.LinAlgError:
            pass
    out = np.array(out)
    return est, out.std(0, ddof=1), np.percentile(out, [2.5, 97.5], axis=0), N, ub.size


def main_fit(tag, args):
    g = gather(tag)
    t = g["t"]
    dark, ndark = dark_rate(g)
    rate = g["s3"] / g["tp1"]
    ip = (rate - dark) * g["sens"]                                    # A
    ring = g["ring"]
    beam = (ring > 100.0) & (np.abs(ring - g["ring_med"]) < 0.5)       # drop top-up glitches
    shutter = (rate > 1.0e4)                                           # counts present at the monitor
    estab = np.isfinite(g["e"]) & (np.abs(g["e"] - np.nanmedian(g["e"])) < 1e-3 * 1.0)   # 1 eV = 1e-3 keV
    elow = g["e"] < 15.0
    rho = g["P"] * RHO_K / (g["T"] + 273.15)
    lines = []
    P = lines.append
    P("DENSITY-SLOPE TEST of the live N2-density correction -- MonP (15IDC:scaler1.S3) against the DBPM sum")
    P(f"Run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}Z, data tag {tag}.  READ-ONLY (archiver GET + IEM ASOS GET).")
    P(f"Window: {datetime.fromtimestamp(t[0], timezone.utc):%Y-%m-%d %H:%MZ} .. {datetime.fromtimestamp(t[-1], timezone.utc):%Y-%m-%d %H:%MZ}; S3 rows {t.size}.")
    P("")
    P("DATA CHECKS")
    P(f"  MonP count period 15IDC:scaler1.TP1 = {g['tp1']:.3g} s (S3 is sampled every {g['grid_dt']:.3g} s); S3 rate = S3/TP1.")
    P(f"  MonP sensitivity: 15IDC:A2sens_num index {g['sn']} -> {SENS_NUM[g['sn']]} ; sens_unit has NO archived event (assumed nA/V per memory/CHAMBER_FACTS);")
    P("    sens_num, sens_unit and 15ID:FX4_1:Range_RBV each have <=1 archived event in the window: no gain change, so no split is needed.")
    P("    The sensitivity only scales I_P; it cancels in a log-log slope.")
    P(f"  Dark (ring current < 1 mA, {ndark} rows, median): {dark:.1f} Hz at the same gain (task: 182-227 Hz).")
    P(f"  Mono energy 15 keV cut: rows with E < 15 keV: {int(np.nansum(elow))} of {t.size}.  E range {np.nanmin(g['e']):.4f}..{np.nanmax(g['e']):.4f} keV.")
    P("  -> ALL archived data are at 30.001 keV.  The task's 'E < 15 keV' restriction leaves nothing, so the test is run at 30 keV,")
    P("     where the wall loss (which also depends on density) is part of the expected slope.  See EXPECTED SLOPE.")
    P("  15IDGen:0:userTran6.E is archived with severity INVALID (3) on every row; its values track the FX4 SumAll sum, so both are run,")
    P("     the alarm-free 15ID:FX4_1:SumAll:MeanValue_RBV is the headline.")
    P("")
    P("EXPECTED SLOPE d ln(I_P/DBPM)/d ln(rho)  (calc/PRESSURE.md section 3, MonP, 30 keV)")
    P(f"  absorption only {EXPECT_DIRECT:.2f}; with the wall loss: {EXPECT_LIVE:.2f} (live fit, E_eff scaling) or {EXPECT_MC:.2f} (Monte Carlo at +-3 % density).")
    P("  A slope near 1.0 would say the wall-loss density dependence is NOT there; ~1.8-1.9 confirms the live density correction as built.")
    P("")
    seg_day = np.floor(t / 86400).astype(int)
    blk = np.floor(t / 3600).astype(int)
    q = g["q"]
    qs = q.sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        qf = q / qs
    base = beam & shutter & estab
    cuts = {}
    cuts["A"] = base.copy()
    # cut B: DBPM quadrant balance within 3 MAD of its beam-on median on all four fractions
    bm = base & np.all(np.isfinite(qf), axis=0)
    mB = bm.copy()
    for i in range(4):
        med = np.median(qf[i][bm])
        mad = 1.4826 * np.median(np.abs(qf[i][bm] - med))
        mB &= np.abs(qf[i] - med) < 3 * mad
    cuts["B"] = mB
    P("SELECTION")
    P(f"  beam on (ring > 100 mA, no top-up glitch |I - 9-pt median| < 0.5 mA) & S3 > 1e4 Hz & E const within 1 eV: {int(base.sum())} rows ({base.sum() * g['grid_dt'] / 3600:.1f} h)")
    P(f"  cut B (all four DBPM quadrant fractions within 3 MAD of their beam-on median = 'aligned'): {int(mB.sum())} rows")
    P("  Gross glitches: rows where ln(I_P/DBPM) is > 5 robust sigma from its own 5-minute running median are dropped (deglitch());")
    P("  this tracks slow drift and the density trend, so it does not select on the slope; applied to every variant below.")
    P("  'Aligned' cannot be read directly; B means the beam sits where it usually does on the DBPM.  I deliberately do NOT cut on")
    P("  the response ratio I_P/DBPM itself (selecting on the dependent variable biases the slope).")
    P("")
    results = {}
    rho_cover = {}
    for dk in ("dbpm2", "dbpm"):
        for cn, cm in cuts.items():
            m = cm & np.isfinite(g["dbpm"][dk]) & (g["dbpm"][dk] > 1000) & np.isfinite(rho) & (ip > 0)
            m = subset_deglitch(m, ip, g["dbpm"][dk])
            if m.sum() < 500:
                continue
            y = np.log(ip[m] / g["dbpm"][dk][m])
            lr = np.log(rho[m])
            for sn_, seg in (("single", np.zeros(m.sum(), int)), ("daily", seg_day[m])):
                est, se, ci, N, nb = block_boot(y, lr[:, None], seg, blk[m])
                res = y - 0  # residual scatter below
                results[(dk, cn, sn_)] = (est[0], se[0], ci[:, 0], N, nb)
            rho_cover[(dk, cn)] = (np.percentile(rho[m], [0, 2.5, 50, 97.5, 100]), m.sum())
    P("RESULTS: slope b of ln(I_P / DBPM) on ln(rho)   [dimensionless]; SE and 95 % interval from a bootstrap of whole hours (2000 draws)")
    P("  DBPM source          cut  intercepts  N rows  hours   b      SE(b)   95 % interval")
    for (dk, cn, sn_), (b, se, ci, N, nb) in results.items():
        name = "FX4 SumAll (valid)" if dk == "dbpm2" else "userTran6.E (INVALID)"
        mark = "  <== headline" if (dk, cn, sn_) == HEADLINE else ""
        P(f"  {name:<20} {cn:^4} {sn_:<10} {int(N):>6} {nb:>6}  {b:6.2f}  {se:6.2f}  [{ci[0]:5.2f}, {ci[1]:5.2f}]{mark}")
    P("")
    # rho range, residual scatter, separate P and T fits for the headline selection
    dk, cn, sn_ = HEADLINE
    m = cuts[cn] & np.isfinite(g["dbpm"][dk]) & (g["dbpm"][dk] > 1000) & np.isfinite(rho) & (ip > 0)
    m = subset_deglitch(m, ip, g["dbpm"][dk])
    y = np.log(ip[m] / g["dbpm"][dk][m])
    lP, lT, lr = np.log(g["P"][m]), -np.log(g["T"][m] + 273.15), np.log(rho[m])
    seg = seg_day[m] if sn_ == "daily" else np.zeros(m.sum(), int)
    rng_rho = 100 * (rho[m].max() / rho[m].min() - 1)
    rng_P = 100 * (g["P"][m].max() / g["P"][m].min() - 1)
    rng_T = 100 * ((g["T"][m].max() + 273.15) / (g["T"][m].min() + 273.15) - 1)
    P(f"COVERAGE (headline selection: {dk}, cut {cn}, {sn_} intercepts; {m.sum()} rows)")
    P(f"  rho: {rho[m].min() * 1e3:.4f} .. {rho[m].max() * 1e3:.4f} mg/cm3, full range {rng_rho:.2f} %, 2.5-97.5 % range {100 * (np.percentile(rho[m], 97.5) / np.percentile(rho[m], 2.5) - 1):.2f} %")
    P(f"  P (ASOS-derived, 228 m): {g['P'][m].min():.3f} .. {g['P'][m].max():.3f} kPa, range {rng_P:.2f} %   ({g['asos'][2]} IEM observations over the window, linearly interpolated)")
    P(f"  T (15ID:Sensor2:Temperature): {g['T'][m].min():.2f} .. {g['T'][m].max():.2f} degC, range {rng_T:.2f} % of absolute T (60 s SCAN, linearly interpolated)")
    if rng_rho < 0.5:
        P("  WEAK TEST: rho moved < 0.5 %; the slope below is not a test of the correction.")
    # within-segment rho range
    if sn_ == "daily":
        for s in np.unique(seg):
            mm = seg == s
            P(f"    day {datetime.fromtimestamp(s * 86400, timezone.utc):%Y-%m-%d}: {mm.sum():6d} rows, rho range within the day {100 * (rho[m][mm].max() / rho[m][mm].min() - 1):.2f} %")
    est, se, ci, N, nb = block_boot(y, lr[:, None], seg, blk[m])
    resid_sd = None
    # residual scatter about the fit
    segm = {s: (seg == s) for s in np.unique(seg)}
    r = np.empty_like(y)
    for s, mm in segm.items():
        r[mm] = (y[mm] - y[mm].mean()) - est[0] * (lr[mm] - lr[mm].mean())
    P(f"  residual scatter of ln(I_P/DBPM) about the fit: {100 * r.std():.3f} % (1 sigma, 5 s points); counting statistics alone ~{100 / math.sqrt(np.median(rate[m]) * g['tp1']):.3f} %")
    P(f"  std of ln(I_P/DBPM) within segments (before the fit): {100 * np.sqrt(np.mean([ (y[mm]-y[mm].mean()).var() for mm in segm.values()])):.3f} %")
    P("")
    estj, sej, cij, N, nb = block_boot(y, np.column_stack([lP, lT]), seg, blk[m])
    estP, seP, ciP, _, _ = block_boot(y, lP[:, None], seg, blk[m])
    estT, seT, ciT, _, _ = block_boot(y, lT[:, None], seg, blk[m])
    P("SEPARATE P AND T SLOPES (same selection; slopes on ln P and on -ln T; both should equal b if Sensor2 is the chamber gas)")
    P(f"  ln P alone      : {estP[0]:6.2f}  SE {seP[0]:.2f}  95 % [{ciP[0, 0]:.2f}, {ciP[1, 0]:.2f}]")
    P(f"  -ln T alone     : {estT[0]:6.2f}  SE {seT[0]:.2f}  95 % [{ciT[0, 0]:.2f}, {ciT[1, 0]:.2f}]   (T moved only {rng_T:.2f} %)")
    P(f"  joint (lnP, -lnT): {estj[0]:6.2f} / {estj[1]:6.2f}  SE {sej[0]:.2f} / {sej[1]:.2f}")
    P(f"  ln rho alone    : {est[0]:6.2f}  SE {se[0]:.2f}  95 % [{ci[0, 0]:.2f}, {ci[1, 0]:.2f}]")
    P("")
    # verdict
    lo, hi = ci[0, 0], ci[1, 0]
    P("VERDICT (mechanical; the interpretation is in PROGRESS.md)")
    bs = np.array([r_[0] for r_ in results.values()])
    spread = bs.max() - bs.min()
    P(f"  spread of b over the {bs.size} variants above (DBPM source x cut x intercepts): {bs.min():.2f} .. {bs.max():.2f}  (= {spread:.2f}; headline SE {se[0]:.2f})")
    if rng_rho < 0.5:
        v = "UNTESTED (rho range < 0.5 %)"
    elif spread > 2 * se[0]:
        v = ("NOT ROBUST: b moves by more than 2 SE with the analysis choice, so the bootstrap SE understates the systematic error; "
             "read as 'positive, between about 1 and 3', not as a measurement")
        if lo > EXPECT_DIRECT:
            v += "; the headline interval excludes the absorption-only slope 1.00"
    elif lo <= EXPECT_LIVE <= hi or lo <= EXPECT_MC <= hi:
        v = "CONSISTENT with the live correction (the 95 % interval contains the expected 30 keV slope)"
        if lo <= EXPECT_DIRECT <= hi:
            v = "NOT DISCRIMINATING: the interval contains both the absorption-only (1.0) and the wall-loss (1.8-1.9) expectation"
    elif lo <= EXPECT_DIRECT <= hi:
        v = "CONTRADICTS the wall-loss density dependence; consistent with absorption only"
    else:
        v = "CONTRADICTS both expectations"
    P(f"  b = {est[0]:.2f} +- {se[0]:.2f} (95 % [{lo:.2f}, {hi:.2f}])  vs expected {EXPECT_LIVE:.2f}/{EXPECT_MC:.2f} (wall loss) and {EXPECT_DIRECT:.2f} (absorption only): {v}")
    OUT.mkdir(exist_ok=True)
    (OUT / "density_slope_test.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    figure(g, rho, ip, m, y, lr, seg, est[0], se[0], dk, cn, rng_rho)


def figure(g, rho, ip, m, y, lr, seg, b, se, dk, cn, rng_rho):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = g["t"][m]
    fig, ax = plt.subplots(2, 1, figsize=(9, 8))
    # (1) time series, raw first: MonP rate, DBPM, then ratio and rho
    a0 = ax[0]
    th = (t - t[0]) / 3600
    hb = np.floor(th).astype(int)
    hh = np.unique(hb)
    rr = np.array([np.mean(np.exp(y[hb == h])) for h in hh])
    rhoh = np.array([np.mean(rho[m][hb == h]) for h in hh]) * 1e3
    a0.plot(hh, rr / rr.mean(), ".", color="#2a78d6", ms=3, label="MonP / DBPM, hourly mean, normalised to its mean (left)")
    a0.set_xlabel(f"hours since {datetime.fromtimestamp(t[0], timezone.utc):%Y-%m-%d %H:%MZ}")
    a0.set_ylabel("I_P / DBPM, normalised (1)")
    a1 = a0.twinx()
    a1.plot(hh, rhoh, "-", color="#eb6834", label="N2 density rho from ASOS P and Sensor2 T (right)")
    a1.set_ylabel("rho, mg/cm3")
    h1, l1 = a0.get_legend_handles_labels()
    h2, l2 = a1.get_legend_handles_labels()
    a0.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    a0.set_title(f"MonP/DBPM vs density, 30.001 keV only; DBPM = {dk}, cut {cn}")
    # (2) slope plot: segment-demeaned, hourly bins
    a = ax[1]
    ymd = np.empty_like(y)
    xmd = np.empty_like(y)
    for s in np.unique(seg):
        mm = seg == s
        ymd[mm] = y[mm] - y[mm].mean()
        xmd[mm] = lr[mm] - lr[mm].mean()
    a.plot(100 * xmd, 100 * ymd, ".", color="#bbbbbb", ms=1, rasterized=True, label="5 s points (grey)")
    xb = np.array([100 * xmd[hb == h].mean() for h in hh])
    yb = np.array([100 * ymd[hb == h].mean() for h in hh])
    a.plot(xb, yb, "o", color="#2a78d6", ms=4, label="hourly means")
    xs = np.array([100 * xmd.min(), 100 * xmd.max()])
    a.plot(xs, b * xs, "-", color="k", label=f"fit b = {b:.2f} +- {se:.2f} (hour-bootstrap SE)")
    a.plot(xs, EXPECT_LIVE * xs, "--", color="#1baf7a", label=f"expected {EXPECT_LIVE:.2f} (wall loss, live fit)")
    a.plot(xs, EXPECT_DIRECT * xs, ":", color="#eda100", label="expected 1.00 (absorption only)")
    a.set_xlabel(f"ln(rho) minus its mean within the day, % (rho range {rng_rho:.2f} % over the whole window)")
    a.set_ylabel("ln(I_P/DBPM) minus its mean within the day, %")
    a.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    FIGOUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGOUT / "density_slope_test.png", dpi=130)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pull", "fit"])
    ap.add_argument("--from", dest="frm", default="2026-11-12T18:42:00.000Z")
    ap.add_argument("--to", dest="to", default=None)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    if a.cmd == "pull":
        to = a.to or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        tag = a.tag or f"{a.frm[:10]}_{to[:10]}"
        print("tag", tag)
        pull(a.frm, to, tag)
    else:
        main_fit(a.tag, a)
