"""Read-only wiring probe for a 4-channel picoammeter (TetrAMM) feeding one ion chamber.

No PV names live here: they come from an untracked JSON config (--config).
  live    : monitor all channels + derived PVs for N seconds (CA monitor only, no writes),
            align by IOC timestamp, report per-channel mean/std, correlation matrix,
            and least-squares fits of each derived PV on the channels.
  archive : pull RAW (never mean_N) archiver data for the same PVs over a window, join by
            timestamp, and report per-window statistics and the same fits.
Usage:
  python estation_tetramm_wiring.py --config X.json live --seconds 60
  python estation_tetramm_wiring.py --config X.json archive --from 2026-11-11T17:00:00Z --to 2026-11-14T04:00:00Z
"""
import argparse, json, sys, time, urllib.parse, urllib.request
import numpy as np


def fits(names, X, derived):
    """X: dict name->array (aligned). Fit each derived on channels; report coefficients."""
    ch = [n for n in names if n in X]
    A = np.column_stack([X[c] for c in ch])
    out = {}
    for d, y in derived.items():
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        res = y - A @ coef
        # also exact-sum test: derived - sum(channels)
        out[d] = (dict(zip(ch, np.round(coef, 4))), float(np.std(res)),
                  float(np.mean(y - A.sum(axis=1))), float(np.std(y - A.sum(axis=1))))
    return out


def report(chn, X, derived, label):
    print('==', label, 'n =', len(next(iter(X.values()))))
    for c in chn:
        x = X[c]
        print('  %-4s mean % .5f  std %.5f  min % .4f  max % .4f' % (c, x.mean(), x.std(), x.min(), x.max()))
    for d, y in derived.items():
        print('  %-5s mean % .5f  std %.5f' % (d, y.mean(), y.std()))
    M = np.corrcoef(np.column_stack([X[c] for c in chn]).T)
    print('  channel correlation matrix:\n', np.round(M, 3))
    for d, (co, rs, mo, so) in fits(chn, X, derived).items():
        print('  fit %-5s = %s  resid std %.5f | (derived - sum4): mean % .5f std %.5f' % (d, co, rs, mo, so))


def live(cfg, seconds):
    import epics
    P = cfg['prefix']
    names = {('ch%d' % (i + 1)): P + c for i, c in enumerate(cfg['channels'])}
    names.update({k: P + v for k, v in cfg['derived'].items()})
    store = {k: [] for k in names}
    pvs = {}

    def cb(pvname=None, value=None, timestamp=None, key=None, **kw):
        store[key].append((timestamp, value))
    for k, n in names.items():
        pvs[k] = epics.PV(n, form='time', auto_monitor=True)
    for k, p in pvs.items():
        p.wait_for_connection(5)
        p.add_callback(cb, key=k)  # extra kwargs are passed through to the callback
    time.sleep(seconds)
    for k, p in pvs.items():
        print(k, 'updates', len(store[k]), 'connected', p.connected)
    # align by IOC timestamp (rounded to 1 ms)
    base = {k: {round(t, 3): v for t, v in store[k]} for k in store}
    common = sorted(set.intersection(*[set(b) for b in base.values()]))
    print('timestamps common to all PVs:', len(common), 'of', len(base['ch1']))
    if len(common) < 10:
        print('too few aligned samples; falling back to nearest-neighbour is NOT done (would blur the test)')
        return
    chn = ['ch%d' % (i + 1) for i in range(len(cfg['channels']))]
    X = {k: np.array([base[k][t] for t in common]) for k in base}
    report(chn, X, {d: X[d] for d in cfg['derived']}, 'live aligned')
    return X


def fetch_raw(host, pv, t0, t1):
    q = urllib.parse.urlencode({'pv': pv, 'from': t0, 'to': t1})
    url = 'http://%s/retrieval/data/getData.csv?%s' % (host, q)
    rows = []
    with urllib.request.urlopen(url, timeout=300) as r:
        for line in r.read().decode().splitlines():
            f = line.split(',')
            if len(f) >= 5:
                rows.append((float(f[0]) + float(f[4]) * 1e-9, float(f[1]), int(f[2])))
    return np.array(rows)


def archive(cfg, t0, t1):
    P = cfg['prefix']
    names = {('ch%d' % (i + 1)): P + c for i, c in enumerate(cfg['channels'])}
    arch = {k: v for k, v in cfg['derived'].items() if k in cfg.get('archived_derived', cfg['derived'])}
    names.update({k: P + v for k, v in arch.items()})
    D = {k: fetch_raw(cfg['archiver'], n, t0, t1) for k, n in names.items()}
    for k, a in D.items():
        dt = np.diff(a[:, 0])
        print(k, 'raw rows', len(a), 'median dt %.2f s' % np.median(dt), 'max gap %.0f s' % dt.max(),
              'sev!=0:', int((a[:, 2] != 0).sum()))
    # SCAN at 10 s on independent clocks: join on rounded-to-10s bins using a +-5 s window
    ref = D['ch1'][:, 0]
    X = {}
    for k, a in D.items():
        idx = np.searchsorted(a[:, 0], ref)
        idx = np.clip(idx, 1, len(a) - 1)
        near = np.where(np.abs(a[idx - 1, 0] - ref) < np.abs(a[idx, 0] - ref), idx - 1, idx)
        ok = np.abs(a[near, 0] - ref) < 5.0
        X[k] = np.where(ok, a[near, 1], np.nan)
    keep = np.all([~np.isnan(v) for v in X.values()], axis=0)
    X = {k: v[keep] for k, v in X.items()}
    t = ref[keep]
    print('joined samples', keep.sum(), 'of', len(ref))
    chn = ['ch%d' % (i + 1) for i in range(len(cfg['channels']))]
    report(chn, X, {d: X[d] for d in arch}, 'archive raw joined (single-sample 10 s SCAN, not averaged)')
    return t, X


def daily(t, X, chn):
    """Per-day robust summary: median and 5/95 percentile per channel, SumAll and the 4-ch sum check."""
    day = (t // 86400).astype(int)
    print('day(UTC)    n   ' + '  '.join('%-18s' % c for c in chn + ['SumAll']) + ' |SumAll-sum4|max')
    for d in np.unique(day):
        m = day == d
        cells = []
        for c in chn + ['SumAll']:
            q = np.percentile(X[c][m], [5, 50, 95])
            cells.append('%7.2f[%6.2f,%7.2f]' % (q[1], q[0], q[2]))
        chk = np.abs(X['SumAll'][m] - sum(X[c][m] for c in chn)).max()
        print('%s %5d  %s  %.3g' % (np.datetime64(int(d) * 86400, 's').astype('datetime64[D]'), m.sum(), '  '.join(cells), chk))


def ratio(npz, on_thresh=100.0, tol=0.01):
    """Split test on a saved joined archive: is ch4/ch3 (dark-subtracted) constant across beam level and days?
    Guards: dark = median of quiet samples (SumAll<10) within +-12 h, per channel; use only samples where
    SumAll equals the 4-channel sum to tol (rejects scan-time skew while the beam is moving)."""
    d = np.load(npz); t = d['t']; chs = ['ch1', 'ch2', 'ch3', 'ch4']
    quiet = np.abs(d['SumAll']) < 10
    tq = t[quiet]
    dark = {}
    for c in chs:
        vq = d[c][quiet]
        i0 = np.searchsorted(tq, t - 43200); i1 = np.searchsorted(tq, t + 43200)
        cs = np.concatenate([[0], np.cumsum(vq)])
        n = np.maximum(i1 - i0, 1)
        dark[c] = (cs[i1] - cs[i0]) / n   # moving mean of quiet samples (mean, not median: documented simplification)
        dark[c][i1 - i0 < 30] = np.nan
    net = {c: d[c] - dark[c] for c in chs}
    s4 = sum(net[c] for c in chs)
    ok = (d['SumAll'] - dark['ch1'] - dark['ch2'] - dark['ch3'] - dark['ch4'] > on_thresh) &          (np.abs(d['SumAll'] - sum(d[c] for c in chs)) < tol * np.abs(d['SumAll']))
    ok &= ~np.isnan(s4)
    print('beam-on, coincident, dark-subtractable samples:', int(ok.sum()))
    for c in chs:
        f = net[c][ok] / s4[ok]
        print('  fraction of net sum on %s: median % .4f  p5 % .4f  p95 % .4f' % (c, np.median(f), *np.percentile(f, [5, 95])))
    r = net['ch4'][ok] / net['ch3'][ok]
    lvl = s4[ok]
    print('ch4/ch3 overall median %.4f  p5 %.4f p95 %.4f' % (np.median(r), *np.percentile(r, [5, 95])))
    for lo, hi in [(100, 300), (300, 1000), (1000, 2000), (2000, 3000), (3000, 6000)]:
        m = (lvl >= lo) & (lvl < hi)
        if m.sum() > 20:
            print('  net sum %4d-%4d nA: n %5d  ch4/ch3 median %.4f  sd %.4f' % (lo, hi, m.sum(), np.median(r[m]), np.std(r[m])))
    days = (t[ok] // 86400).astype(int)
    for dd in np.unique(days):
        m = days == dd
        if m.sum() > 100:
            print('  %s n %5d  ch4/ch3 median %.4f  p5-p95 [%.4f, %.4f]  mean net sum %.0f nA' % (
                np.datetime64(int(dd) * 86400, 's').astype('datetime64[D]'), m.sum(), np.median(r[m]), *np.percentile(r[m], [5, 95]), lvl[m].mean()))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    sub = ap.add_subparsers(dest='mode', required=True)
    a = sub.add_parser('live'); a.add_argument('--seconds', type=float, default=60)
    b = sub.add_parser('archive'); b.add_argument('--from', dest='t0', required=True); b.add_argument('--to', dest='t1', required=True)
    b.add_argument('--daily', action='store_true'); b.add_argument('--save', help='write joined arrays to this .npz')
    c = sub.add_parser('ratio'); c.add_argument('--npz', required=True)
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    if args.mode == 'ratio':
        ratio(args.npz); sys.exit(0)
    if args.mode == 'live':
        live(cfg, args.seconds)
    else:
        t, X = archive(cfg, args.t0, args.t1)
        if args.save:
            np.savez(args.save, t=t, **X)
        if args.daily:
            daily(t, X, ['ch%d' % (i + 1) for i in range(len(cfg['channels']))])
