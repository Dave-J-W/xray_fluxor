"""Read-only snapshot of a PV list (CA gets, no writes) to a timestamped JSON, as a cheap config archive.
Names come from an untracked JSON config: keys 'prefix', 'snapshot' (names under the prefix),
'extra_full_names' (absolute names). Output file name is given by --out (keep it gitignored: it names PVs).
Usage: python snapshot_pvs.py --config X.local.json --out snap.local.json
"""
import argparse, datetime, json, time
import epics

ap = argparse.ArgumentParser(); ap.add_argument('--config', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
cfg = json.load(open(a.config))
names = [cfg['prefix'] + n for n in cfg['snapshot']] + cfg.get('extra_full_names', [])
pvs = {n: epics.PV(n, auto_monitor=False) for n in names}
time.sleep(3)
out = {'taken_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pvs': {}}
for n, p in pvs.items():
    if not p.connected:
        out['pvs'][n] = {'connected': False}; continue
    v = p.get(timeout=3)
    e = {'connected': True, 'value': v, 'type': p.type, 'units': p.units}
    if p.type.endswith('enum'):
        e['enum_strs'] = list(p.enum_strs or []); e['text'] = p.get(as_string=True, timeout=3)
    e['timestamp'] = p.timestamp
    out['pvs'][n] = e
json.dump(out, open(a.out, 'w'), indent=1, default=str)
print('connected %d / %d -> %s' % (sum(v['connected'] for v in out['pvs'].values()), len(names), a.out))
