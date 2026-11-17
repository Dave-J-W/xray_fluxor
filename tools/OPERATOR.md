# MonC bench tools: operator guide

Two scripts for studying the MonC ion-chamber electronics (SR570 current preamp → V2F → scaler1 channel 4).

| Tool | What it does | Touches hardware? |
|---|---|---|
| `tools/ca_logger.py` | Records every 1 s scaler count (MonP S3, MonC S4, clock S1), every MonC SR570 setting change, and ring current, to a CSV | No: read-only |
| `tools/monc_sweep.py` | Steps the MonC SR570 through a plan of settings, prints the mean count per step, then puts the baseline back | **Yes: writes MonC SR570 settings.** Run only with the user's approval of that plan |

MonP (`15IDC:A2`) is never written by either tool.

## Running the logger
From the repo root, in PowerShell:
```
$p = Start-Process -FilePath "%USERPROFILE%\.venvs\bluesky\Scripts\python.exe" -ArgumentList '-I','tools\ca_logger.py','--pv-file','tools\monc_sweep_pvs.txt','--label','<label>','--outdir','%USERPROFILE%\Documents\Claude Locals\xray_fluxor-data\ca_logger' -WindowStyle Hidden -PassThru; $p.Id
```
- Output: `xray_fluxor-data\ca_logger\<date>_<time>_<label>.csv`, one row per event.
- To stop it: stop **both** its processes, by PID only (the venv launcher starts a child). See HANDOFF.md.
- If the PC reboots, the logger stops and does not restart on its own. The archiver's 5 s record still covers the gap.

## Running a sweep
```
%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I tools\monc_sweep.py <plan.csv> data\sweeps\monc_A3_baseline_2026-11-12.csv <steplog_dir> --settle=2
```
- Add `--dry-run` first: it checks the plan and prints every write without touching anything.
- Each step: write → wait 2 s → average the counts for the rest of the step (5 s gives 5 counts).
- At the end, and after any error or Ctrl-C, the baseline is written back and read back.

## Reading the numbers
- S4 is counts per 1 s count, so it equals Hz.
- **S4 ≤ 1 means "clipped"**: the SR570 output is at or below 0 V, and the V2F counts only positive voltages. A clipped value is not a dark level.
- **S4 ≈ 8.4 Hz, flat whatever the settings:** the MonC SR570 is off or not connected, and this is the V2F's own zero-input rate. Measured 2026-11-12 over 47 min: 8.40–8.46 Hz.
- **S4 = 1 exactly:** the SR570 output is negative. This is a different floor from the 8.4 Hz zero.
- MonC baseline: 50 nA/V, offset 20 nA, UNCAL, vernier +6. It reads ~15 Hz, only just above clipping.

## What the error messages mean
| Message | Meaning | Action |
|---|---|---|
| `refused: field … not in ALLOWED` | The plan asks for a field the runner may not write | Fix the plan; nothing was written |
| `readback … wanted …` | A write didn't stick | The runner restores the baseline and stops; check the IOC |
| `ca_logger: … not connected after 5 s` | A PV is unreachable | The logger keeps running; check the IOC or the network |

## Near-zero readings (added 2026-11-12, from the MonC sweeps)
- After MonC has been clipped (S4 ≤ 1), a small positive level takes **~10 s** to appear. Discard ≥ 12 s of counts before reading a dark or baseline level.
- MonC's offset-off dark depends on the range and doesn't scale as 1/gain. It is stable at 20, 50 and 100 nA/V. It drifts by tens of Hz at 1, 200 and 500 nA/V in the first hour after power-on. Details: `data/sweeps/monc_sweep1_results.md`.
- After the SR570 is power-cycled, run `A3init` (with the user's OK) so the unit holds the EPICS settings.
- **Measure a dark after the last gain change.** Each time a gain is selected its dark lands somewhere different. Pass to pass (sd) the spread is 7.8 Hz at 500 nA/V, 3.8 Hz at 1 µA/V, 2.5 Hz at 2 µA/V, 1.0 Hz at 5 µA/V, 0.6 Hz at 10 µA/V and 18.9 Hz at 20 µA/V (21.6 Hz at 200 nA/V; CHAMBER_FACTS F5.2, from `data/calibration/monc_sr570_ranges.csv`). Once selected, it holds. Over 16 h the darks did not drift by more than 2 Hz/h at any gain.

## Current MonC setting: interim operation (CHAMBER_FACTS §7)
- **MonC's chamber is DETACHED** (unplugged 2026-11-13 10:13; the user confirmed it still detached at ~16:55 on 2026-11-13; F7.2). MonC sees no beam until it is reconnected. Update F7.2 when it is.
- MonC is at **5 µA/V (its standard gain), offset CAL +2 nA, ON** (F7.1; re-set 2026-11-13 08:10, first set 2026-11-12 15:20:44). With no beam it reads **≈38.5 Hz detached** (F7.3) and **≈59 Hz cabled** (F7.4). Cabled, that is the V2F's own zero rate (≈8.4 Hz, F8.1), plus the chamber connection's +21.5 Hz (F6.2), plus the calibrated 40 Hz CAL offset, plus about −10 Hz SR570 output offset. It is set for the old software, which uses MonC with no background subtraction. The user asked for under 120 Hz.
- With beam, the +40 Hz is 0.02 % of a typical 2×10⁵ cps.
- Commands (all write the SR570, so each needs the user's OK):
  - `tools/monc_hold.py interim_5uA_cal2nA`: this setting;
  - `tools/monc_hold.py baseline`: the 50 nA/V restore point;
  - `tools/monc_hold.py dark_monitor_cal1nA`: the earlier drift-monitor hold, 14:14–15:05.
- Overnight 2026-11-12/13 it read **60.2 ± 0.6 Hz** (91 holds of 8 min, range 58.9–61.3), with no drift.
- The ~21 Hz between detached and cabled is the chamber connection, the same at every gain (F6.2). It is not a leakage current: that measured −2.6 ± 12.8 pA (F6.1). Expect ≈59 Hz again once the chamber is reconnected.
- If MonC's dark-time counts leave roughly 20–120 Hz, something changed: the SR570 was power-cycled (run `A3init`), or the settings were changed.
- **The 120 Hz limit holds only at 5 and 10 µA/V.** The +2 nA offset adds 1e5 × 2 nA / S. If MonC's gain is changed, the expected no-beam counts are:

  | Gain | Expected no-beam counts |
  |---|---|
  | 1 µA/V | ~315 Hz |
  | 2 µA/V | ~190 Hz |
  | 5 µA/V | ~59 Hz |
  | 10 µA/V | ~33 Hz |
  | 20 µA/V | ~610 Hz (its dark alone is ~600 Hz) |

  At other gains, the offset needs choosing again.
