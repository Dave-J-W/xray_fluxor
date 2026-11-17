"""Run a MonC SR570 (15IDC:A3) settings sweep from a plan CSV, then restore the baseline.

WRITES HARDWARE SETTINGS. Run it only with the user's approval of the exact plan file
(CLAUDE.md: changing SR570 gain and offset always needs the user).

Guards:
- Writes only the 15IDC:A3 fields in ALLOWED. Any other PV, including anything on 15IDC:A2
  (MonP), stops the run before the first write.
- The offset unit may be written (added 2026-11-12, set 3, for pA levels), and so may the
  sensitivity unit (added 2026-11-12, set 4, for the uA/V ranges MonC normally runs at). Both are
  restored. The restore first turns the offset OFF, so no unit change passes through an overload.
- Every write is read back. A mismatch stops the sweep, and then the baseline is restored.
- The baseline is restored in `finally`, from the snapshot CSV, even after an error or Ctrl-C.

Each step's mean S4 (counts per 1 s count) is printed, and also written to a step log. The 1 s
data itself comes from tools/ca_logger.py, which runs alongside.

Usage: monc_sweep.py <plan.csv> <baseline.csv> <steplog_dir> [--dry-run] [--settle=S]
                     [--restore=<monc_hold config>] [--deadline=YYYY-mm-ddTHH:MM]
(default settle 10 s; the user measured that an offset change settles in under 2 s)
--restore: restore that tools/monc_hold.py configuration at the end instead of the baseline CSV.
--deadline: local time; no step starts after it, so the run ends (and restores) by then.
"""
import csv, datetime, os, statistics, sys, time

PREFIX = "15IDC:A3"
ALLOWED = ("sens_unit", "sens_num", "offset_num", "offset_unit", "offset_sign", "offset_on", "offset_cal",
           "off_u_put", "blank_on")
RESTORE_ORDER = ("sens_unit", "sens_num", "offset_cal", "offset_unit", "offset_num", "offset_sign", "off_u_put",
                 "offset_on")
S4 = "15IDC:scaler1.S4"
SETTLE_S = 10


def parse_writes(s):
    out = []
    for item in filter(None, (x.strip() for x in s.split(";"))):
        k, v = item.split("=", 1)
        if k not in ALLOWED:
            raise SystemExit(f"refused: field {k!r} not in ALLOWED")
        out.append((k, v.strip()))
    return out


def main():
    plan_path, base_path, logdir = sys.argv[1:4]
    dry = "--dry-run" in sys.argv
    global SETTLE_S
    restore_cfg, deadline = None, None
    for a in sys.argv[4:]:
        if a.startswith("--settle="):
            SETTLE_S = float(a.split("=", 1)[1])
        elif a.startswith("--restore="):
            restore_cfg = a.split("=", 1)[1]
        elif a.startswith("--deadline="):
            deadline = datetime.datetime.fromisoformat(a.split("=", 1)[1]).timestamp()
    plan = list(csv.DictReader(open(plan_path)))
    for row in plan:
        parse_writes(row["writes"])  # validate everything before any write
    if restore_cfg:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from monc_hold import CONFIGS
        baseline = [("blank_on", "OFF"), ("offset_on", "OFF")] + list(CONFIGS[restore_cfg])
        assert all(f in ALLOWED for f, _ in baseline)
    else:
        base = {r["pv"]: r["as_string"] for r in csv.DictReader(open(base_path))}
        baseline = [("blank_on", "OFF"), ("offset_on", "OFF")] + [(f, base[f"{PREFIX}{f}"]) for f in RESTORE_ORDER]
    if dry:
        for row in plan:
            print(row["step"], parse_writes(row["writes"]), row["dwell_s"], "s")
        print("restore:", baseline)
        return

    os.environ.setdefault("PYEPICS_ENCODING", "utf-8")  # see ca_logger.py: PYTHONIOENCODING trap
    import epics
    pvs = {}

    def put(field, value):
        name = f"{PREFIX}{field}"
        assert name.startswith("15IDC:A3") and field in ALLOWED
        pv = pvs.setdefault(field, epics.PV(name))
        pv.wait_for_connection(3)
        pv.get_ctrlvars()
        target = pv.enum_strs.index(value) if pv.enum_strs else int(value)
        pv.put(target, wait=True, timeout=5)
        time.sleep(0.3)
        rb = pv.get(use_monitor=False)
        if rb != target:
            raise RuntimeError(f"readback {name} = {rb}, wanted {target} ({value})")
        return target

    s4 = epics.PV(S4, form="time", auto_monitor=False)
    s4.wait_for_connection(3)
    os.makedirs(logdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log = open(os.path.join(logdir, f"monc_sweep_steps_{stamp}.csv"), "w", newline="")
    w = csv.writer(log)
    w.writerow(["step", "t_start", "t_settled", "t_end", "writes", "n", "mean_S4", "sd_S4", "state_end", "changed"])
    means = {}

    def state():
        # The IOC rewrites some fields when others are written (e.g. in UNCAL, offset_sign <-> the sign
        # of off_u_put; finding F1, 2026-11-12), so the per-write readback is not enough: re-read all.
        return {f: str(epics.caget(f"{PREFIX}{f}", as_string=True, use_monitor=False)).strip() for f in ALLOWED}
    try:
        for row in plan:
            if deadline and time.time() + float(row["dwell_s"]) > deadline:
                print(f"deadline reached before step {row['step']}; stopping", flush=True)
                break
            writes = parse_writes(row["writes"])
            if any(v == "P" for _, v in writes):  # resolve: the vernier sign that counted
                p = "50" if means.get("V3", 0) >= means.get("V6", 0) else "-50"
                writes = [(k, p if v == "P" else v) for k, v in writes]
            t0 = time.time()
            for k, v in writes:
                put(k, v)
            time.sleep(SETTLE_S)
            t1 = time.time()
            vals, last_ts = [], None
            while time.time() - t1 < float(row["dwell_s"]) - SETTLE_S:
                v = s4.get(use_monitor=False, timeout=2)
                if v is not None and s4.timestamp != last_ts:  # one value per completed count
                    vals.append(v); last_ts = s4.timestamp
                time.sleep(0.25)
            m = statistics.mean(vals) if vals else float("nan")
            sd = statistics.stdev(vals) if len(vals) > 1 else float("nan")
            means[row["step"]] = m
            st = state()
            final = dict(writes)  # last write per field wins (a step may write offset_on OFF ... ON)
            changed = [f"{k}={st[k]}(wrote {v})" for k, v in final.items() if st[k] != v]
            w.writerow([row["step"], t0, t1, time.time(), ";".join(f"{k}={v}" for k, v in writes), len(vals), m, sd,
                        ";".join(f"{k}={x}" for k, x in st.items()), ";".join(changed)])
            log.flush()
            flag = f"  WARNING IOC changed: {changed}" if changed else ""
            print(f"{row['step']:3s} {writes} n={len(vals)} S4 mean={m:.1f} sd={sd:.1f}{flag}", flush=True)
    finally:
        for k, v in baseline:
            put(k, v)
        print("restored:", [(k, epics.caget(f"{PREFIX}{k}", as_string=True)) for k in RESTORE_ORDER], flush=True)
        log.close()


if __name__ == "__main__":
    main()
