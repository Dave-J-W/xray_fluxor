"""Read-only loaders for the MonC figure pipeline.

Everything here reads files and nothing else: no EPICS, no network. The logger CSV is still
being appended by a running process, so it is opened read-only and a partial last line is
dropped rather than parsed.

Raw-file formats
----------------
ca_logger long format: host_time_iso,pv,value,as_string,ioc_timestamp,severity,status
  - scaler rows (15IDC:scaler1.S1/.S3/.S4): one row per completed count, all three channels of
    one count share an ioc_timestamp (end of the count).
  - setting rows (15IDC:A3*): written on change; enums carry the index in `value` and the
    label in `as_string`.
  - rows with as_string == CONNECTED and an empty value are connection events, not data.
  - the first update of each setting PV carries ioc_timestamp 0 (record never processed since
    IOC boot); it is kept as the initial state and placed at the logger start time.

step logs (data/sweeps/monc_sweep_steps_*.csv): step,t_start,t_settled,t_end,writes,n,mean_S4,sd_S4
plans    (data/sweeps/monc_sweep*_plan.csv):    step,block,writes,dwell_s,expected_Hz,question
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SWEEPS = ROOT / "data" / "sweeps"
DATA_ROOT = ROOT.parent / "xray_fluxor-data"            # outside git, sibling of the repo
# Worktrees live under <repo>/.claude/worktrees/<name>; the data dir is a sibling of <repo>,
# so walk up until it is found.
for _p in (ROOT, *ROOT.parents):
    if (_p / "xray_fluxor-data").is_dir():
        DATA_ROOT = _p / "xray_fluxor-data"
        break
DEFAULT_LOGGER = DATA_ROOT / "ca_logger" / "20261112_130858_monc_sweep1_then_dark.csv"

CLOCK_HZ = 1e7          # scaler1 FREQ; S1 counts 1e7 per 1 s count
UTC_OFFSET_H = -6       # CST on 2026-11-12 (checked against host_time_iso in load_logger)


@dataclass
class Logger:
    path: Path
    t_first: float                       # epoch s of the first data row (host clock)
    t_last: float                        # epoch s of the last scaler count (IOC clock)
    scaler_t: np.ndarray                 # IOC time of each completed count, epoch s
    host_t: np.ndarray                   # host arrival time of that count's S4 row, epoch s
    S1: np.ndarray
    S3: np.ndarray
    S4: np.ndarray
    ring_t: np.ndarray
    ring_mA: np.ndarray
    settings: dict = field(default_factory=dict)   # pv -> list of (t, value, label), time-sorted
    n_rows: int = 0
    n_partial_dropped: int = 0

    def rate(self, ch: str) -> np.ndarray:
        """Count rate in Hz = counts / (S1 / 1e7 Hz). Raw counts stay available as self.S4 etc."""
        return getattr(self, ch) / (self.S1 / CLOCK_HZ)


def _iso_to_epoch(s: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(s).timestamp()


def load_logger(path: Path = DEFAULT_LOGGER) -> Logger:
    path = Path(path)
    with open(path, "r", newline="", encoding="utf-8") as fh:   # read-only
        text = fh.read()
    lines = text.splitlines()
    dropped = 0
    if text and not text.endswith("\n"):
        lines = lines[:-1]          # the logger is mid-write on this line
        dropped = 1
    rdr = csv.reader(lines)
    header = next(rdr)
    want = ["host_time_iso", "pv", "value", "as_string", "ioc_timestamp", "severity", "status"]
    if header != want:
        raise ValueError(f"{path.name}: unexpected header {header}")

    counts: dict[float, dict[str, float]] = {}
    ring_t, ring_v = [], []
    settings: dict[str, list] = {}
    t_first = None
    offsets = set()
    n = 0
    for row in rdr:
        if len(row) != 7:
            dropped += 1
            continue
        n += 1
        host, pv, value, label, ts, sev, stat = row
        if t_first is None:
            t_first = _iso_to_epoch(host)
        offsets.add(host[-6:])
        if value == "":          # CONNECTED / DISCONNECTED events
            continue
        t = float(ts)
        if pv.startswith("15IDC:scaler1.S") and pv[-2:] in ("S1", "S3", "S4"):
            c = counts.setdefault(t, {})
            c[pv[-2:]] = float(value)
            if pv.endswith("S4"):
                c["host"] = _iso_to_epoch(host)
        elif pv == "S:SRcurrentAI":
            ring_t.append(t)
            ring_v.append(float(value))
        elif pv.startswith("15IDC:A3"):
            if t < 1e9:          # never processed since IOC boot: initial state
                t = t_first
            settings.setdefault(pv.split(":", 1)[1], []).append((t, float(value), label))
    if offsets - {"-06:00"}:
        raise ValueError(f"host_time_iso offsets {offsets}: UTC_OFFSET_H={UTC_OFFSET_H} is wrong")

    ts = np.array(sorted(t for t, c in counts.items() if len(c) == 4))
    host_t = np.array([counts[t]["host"] for t in ts])
    S1 = np.array([counts[t]["S1"] for t in ts])
    S3 = np.array([counts[t]["S3"] for t in ts])
    S4 = np.array([counts[t]["S4"] for t in ts])
    for k in settings:
        settings[k].sort(key=lambda r: r[0])
    return Logger(path=path, t_first=t_first, t_last=float(ts[-1]), scaler_t=ts, host_t=host_t,
                  S1=S1, S3=S3, S4=S4, ring_t=np.array(ring_t), ring_mA=np.array(ring_v),
                  settings=settings, n_rows=n, n_partial_dropped=dropped)


def setting_at(lg: Logger, pv: str, t: float):
    """(value, label) of setting `pv` in force at time t (last update at or before t)."""
    rows = lg.settings.get(pv, [])
    cur = None
    for tr, v, lab in rows:
        if tr <= t:
            cur = (v, lab)
        else:
            break
    return cur


A3_STATE_PVS = ("A3sens_num", "A3sens_unit", "A3offset_num", "A3offset_unit", "A3off_u_put",
                "A3offset_sign", "A3offset_on", "A3offset_cal", "A3blank_on")


# Changes to what MonC's SR570 input is connected to. These are made by hand, so no PV records
# them and the logger's A3 readbacks can't show them. Each entry has: the handling interval
# (epoch s, CST), the input state before and after, and its source.
# Window statistics must never span one of these (enforced in settings_during).
INPUT_CHANGES = [
    dict(tag="C1", t0=1794586395.0, t1=1794586479.0,      # 2026-11-13 10:13:15-10:14:39 CST
         short="MonC chamber disconnected",
         before="chamber cabled, no beam (the user: \"fully connected\")",
         after="BNC cable only, far end open (chamber taken to the user's office)",
         source=("the user, 2026-11-13: \"Up until i started measuring the monc chamber in my office it was fully "
                 "connected, but no beam going through. Right now nothing is at the end of the monc BNC cable\"; "
                 "handling interval from the noise in S4 (Experimenter, monc-dark; re-checked here: S4 59-60 Hz "
                 "before, 27-79 Hz during, 37-39 Hz after, no A3 change)")),
]


def input_changes_during(t0: float, t1: float) -> list[dict]:
    return [c for c in INPUT_CHANGES if c["t0"] <= t1 and c["t1"] >= t0]


def input_state_at(t: float) -> str:
    """What MonC's SR570 input was connected to at time t, from INPUT_CHANGES."""
    past = [c for c in INPUT_CHANGES if c["t1"] < t]
    if past:
        return past[-1]["after"]
    return INPUT_CHANGES[0]["before"] if INPUT_CHANGES else "unknown"


def settings_during(lg: Logger, t0: float, t1: float, pvs=A3_STATE_PVS) -> dict:
    """EPICS readback of each setting over [t0, t1]: pv -> (value, label).

    Guard: raises if any of them changed inside the window, because then the window's counts
    do not belong to a single setting. Also raises if the window overlaps a hand-made change
    of what the input is connected to (INPUT_CHANGES), which no readback shows."""
    hit = input_changes_during(t0, t1)
    if hit:
        raise ValueError(f"window {t0:.1f}-{t1:.1f} overlaps input change {hit[0]['tag']} ({hit[0]['short']})")
    out = {}
    for pv in pvs:
        changes = [r for r in lg.settings.get(pv, []) if t0 < r[0] <= t1]
        if changes:
            raise ValueError(f"{pv} changed inside window {t0:.1f}-{t1:.1f}: {changes}")
        out[pv] = setting_at(lg, pv, t0)
    return out


def sens_nA_per_V(state: dict) -> float:
    """SR570 sensitivity from the readback labels, in nA/V."""
    num = float(state["A3sens_num"][1])
    unit = state["A3sens_unit"][1]
    return num * {"pA/V": 1e-3, "nA/V": 1.0, "uA/V": 1e3, "mA/V": 1e6}[unit]


def offset_level_nA(state: dict) -> float:
    num = float(state["A3offset_num"][1])
    unit = state["A3offset_unit"][1]
    return num * {"pA": 1e-3, "nA": 1.0, "uA": 1e3, "mA": 1e6}[unit]


@dataclass
class Step:
    sweep: str
    step: str
    block: str
    writes: str
    expected: str
    t_start: float
    t_settled: float
    t_end: float
    n_log: int
    mean_log: float
    sd_log: float


def _read_csv(path: Path) -> list[dict]:
    """Read a CSV, dropping a last line the writer has not finished (file still growing)."""
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    if text and not text.endswith("\n"):
        text = text[: text.rfind("\n") + 1]
    import io
    return list(csv.DictReader(io.StringIO(text)))


RAW_SWEEPS = DATA_ROOT / "sweeps"   # step logs the runner writes outside git (e.g. the overnight program)


# Step logs and plans produced on another branch are read with `git show <ref>:<path>` (read-only;
# that branch is never checked out or edited here). A copy in this worktree, e.g. after a merge,
# takes precedence.
OTHER_REF = "monc-dark"
SOURCES: dict[str, str] = {}      # file name -> where it was read from (for the provenance footer)


EXTRA_DIR: Path | None = None    # --extra-sweeps-dir: read-only, uncommitted files (testing only)
_CSV_CACHE: dict[str, list[dict]] = {}


def sweep_csv(name: str) -> list[dict]:
    if name in _CSV_CACHE:
        return _CSV_CACHE[name]
    _CSV_CACHE[name] = rows = _sweep_csv(name)
    return rows


def _sweep_csv(name: str) -> list[dict]:
    local_p = SWEEPS / name
    if local_p.exists():
        SOURCES[name] = "this branch"
        return _read_csv(local_p)
    import io
    import subprocess
    if name.startswith("monc_sweep_steps_") and (RAW_SWEEPS / name).exists():
        r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{OTHER_REF}:data/sweeps/{name}"],
                           capture_output=True, timeout=10)
        if r.returncode != 0:                        # not committed anywhere: the raw, growing file
            SOURCES[name] = f"raw {RAW_SWEEPS.parent.name}/{RAW_SWEEPS.name}/ (outside git)"
            return _read_csv(RAW_SWEEPS / name)
    if EXTRA_DIR is not None and (EXTRA_DIR / name).exists():
        try:
            r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{OTHER_REF}:data/sweeps/{name}"],
                               capture_output=True, timeout=10)
            committed = r.returncode == 0
        except Exception:
            committed = False
        if not committed:
            SOURCES[name] = f"UNCOMMITTED {EXTRA_DIR.name}/"
            return _read_csv(EXTRA_DIR / name)
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{OTHER_REF}:data/sweeps/{name}"],
                       capture_output=True, timeout=20)
    if r.returncode != 0:
        raise FileNotFoundError(f"{name}: not in this branch and not on {OTHER_REF} "
                                f"({r.stderr.decode(errors='replace').strip()})")
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", OTHER_REF],
                         capture_output=True, text=True, timeout=10).stdout.strip()
    SOURCES[name] = f"{OTHER_REF}@{sha}"
    return list(csv.DictReader(io.StringIO(r.stdout.decode("utf-8"))))


# Which plan goes with which step log. Keyed by the step-log file, because sweep 1 was split
# into two runs (B0-V6 at 60 s counts, V7-R at 5-6 counts) with separate plans.
SWEEP_FILES = {
    "sweep1":  ("monc_sweep_steps_20261112_130916.csv", "monc_sweep1_plan.csv"),
    "sweep1b": ("monc_sweep_steps_20261112_131942.csv", "monc_sweep1b_plan.csv"),
    "sweep2":  ("monc_sweep_steps_20261112_133745.csv", "monc_sweep2_plan.csv"),
    # Experimenter, branch monc-dark (commit 6d95ee3): experiment set 3 and the sweep-1 re-run.
    "set3":    ("monc_sweep_steps_20261112_134949.csv", "monc_set3_plan.csv"),
    "rerun1":  ("monc_sweep_steps_20261112_140106.csv", "monc_sweep1_rerun_plan.csv"),
}
# SR570 state per sweep. Sweep 1 and 1b ran with MonC's SR570 switched off (user switched it on
# at 13:29:56; see data/sweeps/monc_sweep1_results.md); their S4 is the V2F zero-input floor.
SR570_STATE = {"sweep1": "SR570 OFF", "sweep1b": "SR570 OFF", "sweep2": "SR570 live",
               "set3": "SR570 live", "rerun1": "SR570 live"}
UNMATCHED: list[str] = []        # discovered step logs with no unique plan (printed by the CLI)
T_POWER_ON_EPOCH = 1794511796.0  # 13:29:56 CST; see common.T_POWER_ON


def _list_names() -> set[str]:
    import subprocess
    names = {p.name for p in SWEEPS.glob("*.csv")}
    r = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "--name-only", f"{OTHER_REF}", "data/sweeps/"],
                       capture_output=True, text=True, timeout=20)
    if r.returncode == 0:
        names |= {Path(x).name for x in r.stdout.split()}
    if EXTRA_DIR is not None:
        names |= {p.name for p in EXTRA_DIR.glob("*.csv")}
    if RAW_SWEEPS.is_dir():
        names |= {p.name for p in RAW_SWEEPS.glob("monc_sweep_steps_*.csv")}
    return names


def discover_sweeps() -> list[str]:
    """Add step logs not yet in SWEEP_FILES, each matched to the one plan with the same step list.

    A log matching no plan, or more than one, is not added (listed in UNMATCHED). A log that starts
    before the SR570 power-on is refused (it would need SR570_STATE 'OFF' set by hand)."""
    known = {v[0] for v in SWEEP_FILES.values()}
    names = _list_names()
    plans = sorted(n for n in names if n.endswith("_plan.csv"))
    plan_steps = {p: [r["step"] for r in sweep_csv(p)] for p in plans}
    added = []
    for log in sorted(n for n in names if n.startswith("monc_sweep_steps_") and n not in known):
        rows = sweep_csv(log)
        steps = [r["step"] for r in rows]
        m = [p for p, s in plan_steps.items() if s == steps]
        if not m:      # a log that is still growing is a prefix of its plan
            m = [p for p, s in plan_steps.items() if len(steps) >= 5 and s[: len(steps)] == steps]
        if len(m) != 1 or not rows:
            UNMATCHED.append(f"{log}: {len(m)} matching plans {m}")
            continue
        if float(rows[0]["t_start"]) < T_POWER_ON_EPOCH:
            UNMATCHED.append(f"{log}: starts before SR570 power-on; add by hand with its SR570 state")
            continue
        key = m[0].removeprefix("monc_").removesuffix("_plan.csv")
        if key in SWEEP_FILES:
            key = log.removeprefix("monc_sweep_steps_").removesuffix(".csv")
        SWEEP_FILES[key] = (log, m[0])
        SR570_STATE[key] = "SR570 live"
        added.append(key)
    return added


def load_steps(sweep: str) -> list[Step]:
    log_name, plan_name = SWEEP_FILES[sweep]
    plan = sweep_csv(plan_name)
    out = []
    log = sweep_csv(log_name)
    if len(log) > len(plan):
        raise ValueError(f"{sweep}: step log has {len(log)} rows, plan only {len(plan)}")
    for r, p in zip(log, plan):    # by position: step names may repeat within a plan
        if p["step"] != r["step"]:
            raise ValueError(f"{sweep}: log step {r['step']!r} where the plan has {p['step']!r}")
        if p["writes"] != r["writes"] and not p["writes"].endswith("off_u_put=P"):
            raise ValueError(f"{sweep} {r['step']}: plan writes {p['writes']!r} != log {r['writes']!r}")
        out.append(Step(sweep, r["step"], p["block"], r["writes"], p.get("expected_Hz", ""),
                        float(r["t_start"]), float(r["t_settled"]), float(r["t_end"]),
                        int(r["n"]), float(r["mean_S4"]), float(r["sd_S4"])))
    return out


@dataclass
class StepStat:
    step: Step
    n: int
    mean: float          # counts per count (S4); also Hz because every count here is 1.000 s
    sd: float
    sem: float
    clipped_frac: float  # fraction of counts with S4 <= CLIP_COUNTS
    values: np.ndarray


CLIP_COUNTS = 1.0        # unipolar V2F: S4 <= 1 count means the input was at or below zero


COUNT_S = 1.0           # every count in this record is 1.000 s (S1 = 1e7, checked per window)

# V2F zero-input rate: S4 while MonC's SR570 was switched off (logger start to 1 s before power-on).
# Experimenter, analysis/v2f_zero.py on monc-dark: 8.4 Hz. Recomputed here and checked against it.
V2F_ZERO_REF_HZ = 8.4


def v2f_zero(lg: "Logger", t_power_on: float = 1794511796.0) -> dict:
    m = lg.scaler_t < t_power_on - 1
    v = lg.S4[m]
    if len(v) < 100:
        raise ValueError("V2F zero: fewer than 100 counts before power-on")
    z = dict(mean=float(v.mean()), sd=float(v.std(ddof=1)), n=int(len(v)),
             t0=float(lg.scaler_t[m][0]), t1=float(lg.scaler_t[m][-1]))
    if abs(z["mean"] - V2F_ZERO_REF_HZ) > 0.1:
        raise ValueError(f"V2F zero {z['mean']:.3f} Hz disagrees with the Experimenter's {V2F_ZERO_REF_HZ} Hz")
    return z


def step_window(lg: Logger, st: Step) -> np.ndarray:
    """Boolean mask of the counts used for a step: counts that STARTED after the step settled
    (IOC end time - 1 s >= t_settled) and ended by t_end.

    This is stricter than the sweep runner, which polled S4 at 4 Hz from t_settled and so also
    took the count already completed at t_settled (it began up to 1 s before settling). The
    runner's polling cannot be reproduced count-for-count from the logger (it occasionally
    missed a count), so the figures use this rule and check_against_log bounds the difference.
    t_settled/t_end are host clock; the IOC clock leads host arrival by ~0.09 s, negligible here.
    """
    return (lg.scaler_t - COUNT_S >= st.t_settled) & (lg.scaler_t <= st.t_end)


def step_stats(lg: Logger, st: Step) -> StepStat:
    """Recompute a step's S4 statistics from the raw 1 s record (window: step_window)."""
    m = step_window(lg, st)
    v = lg.S4[m]
    s1 = lg.S1[m]
    if len(v) and np.any(np.abs(s1 - CLOCK_HZ) > 0.5):
        raise ValueError(f"{st.sweep} {st.step}: a count in the window is not 1.000 s (S1={s1})")
    n = len(v)
    sd = float(v.std(ddof=1)) if n > 1 else float("nan")
    return StepStat(st, n, float(v.mean()) if n else float("nan"), sd,
                    sd / np.sqrt(n) if n > 1 else float("nan"),
                    float(np.mean(v <= CLIP_COUNTS)) if n else float("nan"), v)


def check_against_log(stats: list[StepStat], abs_tol=1.0, rel_tol=1e-3) -> list[str]:
    """Guard: each raw-recomputed step mean must agree with the sweep runner's logged mean
    within max(1 count, 0.1 %, 3 x sd/sqrt(n)). The windows differ by one count at the start
    (see step_window), so noisy steps legitimately differ by about one sd/sqrt(n). A larger gap
    means the logger and the runner did not see the same counts (wrong file, clock error, a
    transition inside the window). Returns mismatches."""
    bad = []
    for s in stats:
        st = s.step
        stat_tol = 3 * max(s.sd if s.n > 1 else 0, st.sd_log if st.n_log > 1 else 0) / np.sqrt(max(1, min(s.n, st.n_log)))
        if not (s.n >= 3 and abs(s.mean - st.mean_log) <= max(abs_tol, rel_tol * abs(st.mean_log), stat_tol)):
            bad.append(f"{st.sweep} {st.step}: raw n={s.n} mean={s.mean:.4f} vs log n={st.n_log} "
                       f"mean={st.mean_log:.4f}")
    return bad
