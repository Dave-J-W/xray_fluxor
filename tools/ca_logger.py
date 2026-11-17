"""Read-only EPICS Channel Access logger: one long-format CSV row per PV event, flushed per row.

READ-ONLY BY CONSTRUCTION: this file never writes to a PV. Check with
    grep -ni "[p]ut" tools/ca_logger.py      (expected: no match; the brackets keep this line out)

How each PV is captured (measured 2026-11-12 on 15IDC:scaler1):
- Scaler channels (names ending in .S<n>) are subscribed with mask DBE_LOG only. The scaler record
  posts DBE_LOG once per completed count, even when the value is unchanged, with that count's IOC
  timestamp. Its DBE_VALUE posts arrive ~1 s late and carry the PREVIOUS count's timestamp, so
  they are not subscribed. No polling, so no aliasing against the count period.
- Every other PV uses the pyepics default mask (DBE_VALUE | DBE_ALARM): one row on each change,
  and one row at start (the initial monitor callback).
- Enums: `value` is the raw index and `as_string` is the state string.
- Connection changes give a row with as_string CONNECTED / DISCONNECTED and an empty value;
  a PV still unconnected 5 s after start gives one NEVER_CONNECTED row.
- Identical repeats (same pv, IOC timestamp, value, severity and status) are written once.

Usage:
    python -I tools/ca_logger.py --pv-file tools/monc_sweep_pvs.txt --label sweep1 [--duration 180]
Stops on Ctrl-C, Ctrl-Break, SIGTERM or at --duration. A hard kill leaves a valid CSV (at worst
the last row is cut short). File: <outdir>/<YYYYmmdd_HHMMSS>_<label>.csv (local start time).
"""
import argparse
import collections
import csv
import datetime as dt
import os
import re
import signal
import sys
import time
from pathlib import Path

# pyepics takes its PV-name codec from PYTHONIOENCODING; a value like "utf-8:surrogateescape"
# (seen in some PowerShell sessions) makes every PV creation fail with LookupError.
os.environ.setdefault("PYEPICS_ENCODING", "utf-8")
import epics  # noqa: E402
from epics import dbr

DEFAULT_OUTDIR = Path(__file__).resolve().parents[2] / "xray_fluxor-data" / "ca_logger"
COLUMNS = ["host_time_iso", "pv", "value", "as_string", "ioc_timestamp", "severity", "status"]
SCALER_CHANNEL = re.compile(r"\.S\d+$")


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def read_pv_names(files, names):
    out = []
    for f in files or []:
        for line in Path(f).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line)
    out += names or []
    return list(dict.fromkeys(out))  # de-duplicate, keep order


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pvs", nargs="*", help="PV names (added to any --pv-file list)")
    ap.add_argument("--pv-file", action="append", help="file with one PV per line ('#' comments)")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR), help="directory for the CSV")
    ap.add_argument("--label", default="run", help="run label used in the file name")
    ap.add_argument("--duration", type=float, default=None, help="stop after this many seconds")
    ap.add_argument("--period", type=float, default=1.0,
                    help="main-loop wake-up period for the stop checks, s (rows are written as "
                         "events arrive, not sampled)")
    args = ap.parse_args()

    names = read_pv_names(args.pv_file, args.pvs)
    if not names:
        ap.error("no PVs given")
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.label)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{label}.csv"
    fh = open(path, "x", newline="", encoding="utf-8")  # "x": never overwrite an earlier run
    writer = csv.writer(fh)
    writer.writerow(COLUMNS)
    fh.flush()
    print(f"ca_logger: writing {path}", flush=True)

    events = collections.deque()  # append/popleft are thread-safe; CA callbacks only append
    stop = []

    def on_signal(signum, frame):
        stop.append(signum)

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), on_signal)

    def on_value(pvname=None, value=None, char_value=None, timestamp=None, severity=None,
                 status=None, **kw):
        events.append((now_iso(), pvname, value, char_value, timestamp, severity, status))

    def on_conn(pvname=None, conn=None, **kw):
        events.append((now_iso(), pvname, "", "CONNECTED" if conn else "DISCONNECTED", None, "", ""))

    pvs = [epics.PV(n, form="time", callback=on_value, connection_callback=on_conn,
                    auto_monitor=dbr.DBE_LOG if SCALER_CHANNEL.search(n) else True)
           for n in names]
    by_name = {p.pvname: p for p in pvs}
    t0 = time.monotonic()
    checked, last, nrows = False, {}, 0
    while not stop:
        if args.duration is not None and time.monotonic() - t0 >= args.duration:
            break
        if not checked and time.monotonic() - t0 > 5:
            checked = True
            for p in pvs:
                if not p.connected:
                    events.append((now_iso(), p.pvname, "", "NEVER_CONNECTED", None, "", ""))
                    print(f"ca_logger: {p.pvname} not connected after 5 s", file=sys.stderr)
        if not events:
            time.sleep(min(args.period, 0.05))
            continue
        host, pv, value, as_str, ts, sev, stat = events.popleft()
        if ts is not None:
            key = (ts, repr(value), sev, stat)
            if last.get(pv) == key:
                continue
            last[pv] = key
            p = by_name[pv]
            if p.type.endswith("enum"):  # callbacks only give the index; strings via ctrl get
                strs = p.enum_strs or p.get_ctrlvars(timeout=2) and p.enum_strs
                if strs and 0 <= value < len(strs):
                    as_str = strs[value]
        writer.writerow([host, pv, value, as_str, "" if ts is None else f"{ts:.6f}", sev, stat])
        fh.flush()
        nrows += 1
    for p in pvs:
        p.clear_callbacks()
        p.disconnect()
    fh.close()
    why = f"signal {stop[0]}" if stop else "duration reached"
    print(f"ca_logger: stopped ({why}), {nrows} rows in {path}", flush=True)


if __name__ == "__main__":
    main()
