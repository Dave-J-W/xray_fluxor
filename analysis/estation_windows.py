"""Beam-on plateaus of a split-electrode ion chamber read on two picoammeter channels, with context from the archive.

No PV names here: the context PVs come from an untracked JSON config (--config), key 'context' = {label: pv name}.
Input: the joined npz written by estation_tetramm_wiring.py archive --save (t, ch1..ch4, SumAll).
For each plateau (continuous beam-on run) it reports duration, net ch3 and ch4 (dark-subtracted), the dark for
ch3/ch4 before and after (median of quiet samples, |SumAll|<10, within +-12 h), and for every context PV the
step-function value (last archived value at or before each sample, right for MONITOR-archived PVs): median, min, max.
Guards: a plateau needs >= --min-minutes of samples spaced <= 60 s apart whose net sum stays within +-10 % of its
median; samples where SumAll differs from the 4-channel sum by > 1 % are dropped (scan-time skew while ramping).
Usage: python estation_windows.py --config X.local.json --npz joined.npz [--min-minutes 30] [--csv out.csv]
"""
import argparse, json, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('analysis', 1)[0] + 'analysis')
from estation_tetramm_wiring import fetch_raw


def utc(t):
    return str(np.datetime64(int(t), 's')).replace('T', ' ')


def step_value(a, t):
    i = np.searchsorted(a[:, 0], t, side='right') - 1
    v = np.where(i >= 0, a[np.clip(i, 0, None), 1], np.nan)
    return v


def write_clean(rows, path, since):
    """Clean = E-station energy (label sbm_E) span < 0.02 keV, JJ slits and white-beam slits constant (where archived),
    net sum >= 500 nA, darks on both sides. Energy is the side-bounce monochromator readback, NOT the DCM."""
    def const(r, k):
        lo, hi = r.get(k + '_min'), r.get(k + '_max')
        return lo is not None and (np.isnan(lo) or abs(hi - lo) < 1e-3)
    out = []
    for r in rows:
        if r['start'] < since or np.isnan(r['net3']) or np.isnan(r['dark3_before']) or np.isnan(r['dark3_after']):
            continue
        if np.isnan(r['sbm_E_med']) or r['sbm_E_max'] - r['sbm_E_min'] >= 0.02:
            continue
        if not all(const(r, k) for k in ('jje_hsize', 'jje_vsize', 'wb_hsize', 'wb_vsize')):
            continue
        if r['net3'] + r['net4'] < 500:
            continue
        out.append(r)
    cols = ('start_utc,minutes,energy_kev,net_ch3_nA,net_ch4_nA,slits_mm,dark3_before,dark3_after,dark4_before,dark4_after,'
            'energy_span_kev,energy_dcm_kev_not_estation,slit_h_mm,slit_v_mm,slit_h_centre_mm,slit_v_centre_mm')
    head = [
        '# E-station beam-on windows (analysis/estation_windows.py --clean-csv; PV names only in the local note)',
        '# Clean = E-station energy span < 0.02 keV, JJ and white-beam slits constant, net >= 500 nA, darks on both sides.',
        '# energy_kev = side-bounce monochromator readback (the E-station energy, per the user). energy_dcm_kev_not_estation = the other DCM, kept only to show it differs.',
        '# slits_mm = E-hutch JJ slits HxV; slit_h/v_mm = white-beam slit WB_SL2 size readback, centre = its centre readback (mm).',
        '# net_* are net of the mean of the before/after darks; dark_* are medians of quiet samples within +-12 h. Currents in nA (unit assumed from the IOC scale).',
    ]
    g = lambda v: '%.4g' % v
    lines = head + [cols]
    for r in out:
        lines.append(','.join([r['start'].replace(' ', 'T')[:16], '%.0f' % r['minutes'], '%.3f' % r['sbm_E_med'], '%.0f' % r['net3'], '%.0f' % r['net4'],
                               '%sx%s' % (g(r['jje_hsize_med']), g(r['jje_vsize_med'])),
                               '%.2f' % r['dark3_before'], '%.2f' % r['dark3_after'], '%.2f' % r['dark4_before'], '%.2f' % r['dark4_after'],
                               '%.4f' % (r['sbm_E_max'] - r['sbm_E_min']), '%.3f' % r['dcm_E_med'],
                               '%.4f' % r['wb_hsize_med'], '%.4f' % r['wb_vsize_med'], '%.4f' % r['wb_hcen_med'], '%.4f' % r['wb_vcen_med']]))
    with open(path, 'w') as f:
        f.write(chr(10).join(lines) + chr(10))
    print('clean windows written:', len(out), '->', path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True); ap.add_argument('--npz', required=True)
    ap.add_argument('--min-minutes', type=float, default=30); ap.add_argument('--csv')
    ap.add_argument('--clean-csv', help='numbers-only CSV of the clean windows (needs context labels sbm_E, dcm_E, jje_*, wb_*)')
    ap.add_argument('--since', default='0000', help='with --clean-csv: only windows starting at or after this UTC date')
    a = ap.parse_args()
    cfg = json.load(open(a.config)); d = np.load(a.npz); t = d['t']
    ch = ['ch1', 'ch2', 'ch3', 'ch4']
    quiet = np.abs(d['SumAll']) < 10
    coinc = np.abs(d['SumAll'] - sum(d[c] for c in ch)) < 0.01 * np.maximum(np.abs(d['SumAll']), 1.0)
    on = (d['SumAll'] > 500) & coinc
    idx = np.where(on)[0]
    # split into runs by time gap > 60 s
    cut = np.where(np.diff(t[idx]) > 60)[0] + 1
    runs = np.split(idx, cut)
    ctx = {}
    t0, t1 = utc(t[0] - 3600).replace(' ', 'T') + '.000Z', utc(t[-1] + 3600).replace(' ', 'T') + '.000Z'
    for k, pv in cfg['context'].items():
        try:
            ctx[k] = fetch_raw(cfg['archiver'], pv, t0, t1)
        except Exception as e:
            print('context', k, 'not retrievable:', e)
    rows = []
    for r in runs:
        if len(r) < a.min_minutes * 6:
            continue
        tr = t[r]; s = d['SumAll'][r]
        med = np.median(s)
        # keep only the part within +-10 % of the run median: trim to the longest such stretch
        good = np.abs(s - med) < 0.1 * med
        if good.sum() < a.min_minutes * 6:
            continue
        r = r[good]; tr = t[r]
        def dark(c):
            lo, hi = tr[0], tr[-1]
            b = quiet & (t > lo - 43200) & (t < lo)
            f = quiet & (t > hi) & (t < hi + 43200)
            return (np.median(d[c][b]) if b.sum() > 30 else np.nan, np.median(d[c][f]) if f.sum() > 30 else np.nan)
        d3, d4 = dark('ch3'), dark('ch4')
        dk3 = np.nanmean(d3); dk4 = np.nanmean(d4)
        n3 = d['ch3'][r] - dk3; n4 = d['ch4'][r] - dk4
        row = dict(start=utc(tr[0]), end=utc(tr[-1]), minutes=(tr[-1] - tr[0]) / 60, n=len(r),
                   net3=n3.mean(), net3_sd=n3.std(), net4=n4.mean(), net4_sd=n4.std(), frac3=n3.mean() / (n3.mean() + n4.mean()),
                   dark3_before=d3[0], dark3_after=d3[1], dark4_before=d4[0], dark4_after=d4[1])
        for k, arr in ctx.items():
            v = step_value(arr, tr)
            row[k + '_med'] = np.nanmedian(v); row[k + '_min'] = np.nanmin(v); row[k + '_max'] = np.nanmax(v)
        rows.append(row)
    keys = list(rows[0].keys()) if rows else []
    print('plateaus found:', len(rows))
    for r in rows:
        print(' | '.join('%s=%s' % (k, ('%.4g' % v if isinstance(v, float) else v)) for k, v in r.items()))
    if a.clean_csv:
        write_clean(rows, a.clean_csv, a.since)
    if a.csv and rows:
        with open(a.csv, 'w') as f:
            f.write(','.join(keys) + '\n')
            for r in rows:
                f.write(','.join(str(r[k]) for k in keys) + '\n')


if __name__ == '__main__':
    main()
