# MonC bench tools: handoff

## Design
- `ca_logger.py` (written 2026-11-12 by a subagent; tested 188/188 counts, no gaps or duplicates): event-driven pyepics monitors, one CSV row per event, flushed per row.
  - Scaler channels `.S<n>` are subscribed with **DBE_LOG only**. The scaler record posts DBE_LOG once per completed count, with that count's timestamp. Its DBE_VALUE posts arrive ~1 s late carrying the *previous* count's timestamp. Any tool using default monitors on S3/S4 pairs values with the wrong timestamps.
  - Settings PVs use default monitors (on change, plus once at start).
- `monc_sweep.py`: reads a plan CSV (`step,block,writes,dwell_s,expected_Hz,question`; writes are `field=value;…` with enum labels). It validates the whole plan before the first write and writes only fields in `ALLOWED` on `15IDC:A3`. Each write is read back. The baseline is restored in `finally`, in `RESTORE_ORDER`. S4 is read by direct CA gets (correct timestamps), one value per new timestamp.

## Rules
- Writes to the MonC SR570 need the user's approval of the plan (CLAUDE.md; PLAN.md change rows 2026-11-12).
- Never write `15IDC:A2*` (MonP), `A3reset` or `A3init` from the runner. `A3init` re-sends every EPICS setting to the unit. It was run once by hand after the unit was powered on, with the user's approval.
- The SR570 RS-232 is listen-only. EPICS values are what was last *sent*, not what the unit holds. After a power cycle the unit restores its own last settings (or defaults if its backup battery is flat) until `A3init` is run.

## Files
| Path | What |
|---|---|
| `tools/ca_logger.py`, `tools/monc_sweep_pvs.txt` | logger and its PV list |
| `tools/monc_sweep.py` | sweep runner |
| `data/sweeps/monc_A3_baseline_2026-11-12.csv` | baseline (restore point) |
| `data/sweeps/monc_sweep*_plan.csv`, `monc_sweep_steps_*.csv` | plans and per-step means |
| `data/sweeps/monc_sweep1_results.md` | results and interpretation |
| `ELECTRONICS_CONCLUSIONS.md` | summary: what the electronics contribute to the flux uncertainty, and what's unknown (MonP) |
| `data/sweeps/monc_sweep_steps_20261112_154045.csv` | overnight step log (copied into git 2026-11-13: the calibration's source) |
| `analysis/make_monc_calibration.py` → `data/calibration/monc_sr570_ranges.csv` | per-gain calibration table (factor, u, dark, dark sd) for the live calc. Deterministic: regenerate, then `git diff --exit-code` on the CSV |
| `analysis/monc_interim_watch.py` | per-5-min S4 statistics and A3 setting events since a time (finds state changes such as an unplugged chamber) |
| `analysis/monc_leak.py`, `data/sweeps/monc_leak_plan.csv`, `monc_sweep_steps_20261113_120911.csv` | leakage run 2026-11-13: dark passes with and without the chamber, fit of an offset + current |
| `calc/monc_gain_cal.py` | DRAFT utilioc userArrayCalc lookup of that table, with self-test and `--print` install lines; nothing installed |
| `tools/monc_hold.py` | applies a named MonC configuration with readback (interim, baseline, dark monitor) |
| `analysis/make_night_plan.py`, `data/sweeps/monc_night_plan.csv` | overnight program generator and plan |
| `analysis/monc_grid.py` | per-grid darks, blanked readings and joint ladder fit |
| `analysis/monc_passes.py`, `data/sweeps/monc_night_passes_20261112.csv` | dark-pass drift summary and per-pass table |
| `xray_fluxor-data/ca_logger/*.csv` (outside git) | raw 1 s records |

## Environment and traps
- Python: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I`. That `python.exe` is a launcher that starts a child process; stop **both** PIDs, e.g.
  `Get-CimInstance Win32_Process | ? { $_.CommandLine -like '*ca_logger.py*' } | % { Stop-Process -Id $_.ProcessId }`.
  Never stop processes by image name: other agents run Python on this PC.
- PowerShell sessions may set `PYTHONIOENCODING=utf-8:surrogateescape`, which breaks pyepics PV creation. Both scripts set `PYEPICS_ENCODING=utf-8` first.
- From a git worktree, `ca_logger.py`'s default output folder resolves relative to the script. Pass `--outdir` explicitly.
- The logger does not survive a reboot (open item).

## Decisions (dated)
- 2026-11-12: archive SCAN period 5 s (user); MonC lent for sweeps, MonP untouched (user); 2 s settle + 5 s counting per step (user: "change to offset takes less than 2 seconds… 5 seconds of counting is enough").
- 2026-11-12 15:31 to 2026-11-13 08:31: standing MonC grant (user: "you are free to experiment with monc… for the next 17 hours"). The overnight run stopped at ~08:10: its next 8 min hold would have run past the 08:15 deadline. It restored the interim setting, which was read back just after 08:10 (S4 58.6 Hz). From 08:31 every MonC write again needs the user's OK.

- 2026-11-13: write-up and live uncertainties are separate (user: "there is a write-up uncertainty, and a live-beamline-calc uncertainty, I consider them separate"). The calibration table is valid only for MonC's SR570 unit as installed; re-measure (one grid, `analysis/make_night_plan.py`) after a swap or repair, then regenerate the table.

## Open items
- `calc/monc_gain_cal.py` is untested on an IOC. Before install, check on a bench aCalcout: `AA@A` is 0-based; OVAL follows OCAL with DOPT "Use OCAL" and OOPT "Every Time"; autosave keeps the arrays. Slot and install need the user.
- Logger auto-restart after reboot (scheduled task?): ask the user.
- `off_u_put` gets rewritten by the IOC database when the sign or CAL mode changes. Seen; not yet explained.
- MonC's baseline (vernier +6) sits ~15 Hz above the V2F clip. A dark-drift record taken at baseline can hide a downward drift.

## Trap found 2026-11-12 (finding F1, figure session review)
- In UNCAL the IOC couples `offset_sign` and `off_u_put`:
  - writing the sign sets u to ±|u|;
  - writing u sets the sign to u's sign.
- A per-write readback therefore passes while the step ends in a different state from the one intended.
- `monc_sweep.py` now re-reads all written fields at the end of each step: step-log columns `state_end` and `changed`, plus a printed WARNING. This check has not yet run on live hardware.
- Command order also changes the hardware state without any visible EPICS difference: 1.39 % at u = +100. EPICS can't show which state the unit holds.
