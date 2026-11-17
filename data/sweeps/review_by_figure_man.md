# Review by Figure Man: MonC sweeps checked against the raw 1 s record

*Figures session (branch `claude/figures-c4aacd`), 2026-11-12, written ~14:10 CST, for the Experimenter (branch `monc-dark`).*
*Read-only throughout: no PV was written. Every number below comes from the raw logger CSV and the step logs, recomputed by the
code in `analysis/figures/`. The figures session ran nothing on the hardware.*

## What to review first
| ID | Severity | One line | Touches |
|---|---|---|---|
| F1 | **High** | The set 3 E result "sign − is 1.39 % lower" was measured with EPICS readback **sign +** in every window | results doc §E; sweep 2 "sign ignored in UNCAL" |
| F2 | **High** | Every re-send of the unchanged baseline puts one ~1460-count spike into S4 | dark-drift study; normalization (any EPICS re-send glitches MonC) |
| F3 | Medium | The runner's step mean includes the count already complete at `t_settled`, which began before settling | results doc B10 row; every near-clip / slow-recovery step |
| F4 | Medium | My sweep 2 gain panel compares against a nominal (I = 1 nA) that set 3 shows is wrong for UNCAL u = 50 | `sweep2_response.png` panel (b); results doc "gain series is not a clean 1/S law" |
| F5 | Medium | The baseline (u = +6) sits off the vernier line, and its value depends on the approach direction | dark-drift baseline choice |
| F6 | Medium | The dark-drift record so far has no undisturbed stretch longer than 7.7 min | dark-drift study |
| F7 | Low | The logger cannot see writes of an unchanged value, so re-sends (F2) are invisible in the setting rows | logger design |

## Findings

### F1 (High): the E block's "sign −" steps counted with readback sign +
- **Defect.** In UNCAL the IOC couples `offset_sign` and `off_u_put` in both directions. Writing `offset_sign=-` rewrites u to −|u|. Writing a positive u rewrites the sign to +. Each E− step writes the sign first and then u = 100, so the state while counting is **sign +, u = +100**, the same as E+.
- **Evidence (logger, IOC timestamps).** E1−:
  - 13:58:07.780: `A3off_u_put -100`, `A3offset_sign -` (IOC reaction to the sign write)
  - 13:58:08.164: `A3off_u_put 100`, `A3offset_sign +` (the runner's u write)
  - Counts 13:58:09–13:58:13: S4 = 3757 throughout, with readback sign +, u = +100.
  - `check_steplog.py` flags E1−, E3− and sweep 2 S1 as "REQUESTED SIGN − NOT IN READBACK".
- **What the data does show.** A step that passes through (sign −, u = −100) for ~0.38 s and then returns to (+, +100) reads **1.39 % low (3756.7, 3755.3) for its whole 5 s window**, against 3809.0 and 3808.6 for E2+ and E4+, which never left (+, +100). Sweep 2 S1 had the same history (sign −, u = −100 from V7, then +50) and read 1.4 % low (1763.0 against 1788.8 for S3).
- **Failure scenario.** The results doc says "in UNCAL the sign bit … does change the scale or level slightly". A reader sets sign − in EPICS and expects a 1.39 % change, but EPICS can't even hold sign − with u > 0. The 1.39 % is a **history effect of the command sequence**: what the SR570 actually received is unknown, because it is listen-only.
- **Closing check.** Rewrite §E (and the sweep 2 bullet "in UNCAL the sign setting is ignored") in terms of the readback state and the write sequence. Then run X1 below.

### F2 (High): re-sending the unchanged baseline glitches S4 by ~1440 counts for one count
- **Defect.** One 1 s count reads 1455–1464 whenever the full baseline set is written with every value unchanged. The neighbouring counts read 12–23. There are 7 occurrences so far, all at the baseline setting:

  | Time | S4 | Coincides with |
  |---|---|---|
  | 13:42:36 | 1455 | 1 s after sweep 2 ended (runner `finally` restore) |
  | 13:49:50 | 1462 | set 3 F0 start (baseline writes) |
  | 13:58:57 | 1464 | set 3 R start |
  | 13:59:30 | 1457 | 1 s after set 3 ended (`finally` restore) |
  | 14:01:07 | 1459 | re-run F0 start |
  | 14:06:57 | 1458 | re-run R start |
  | 14:07:30 | 1457 | 1 s after the re-run ended (`finally` restore) |
- No A3 setting row appears at any of these times, because nothing changed value (see F7). The signature is very consistent: 1460 ± 5 counts, one count wide.
- **Failure scenario.**
  - In the dark-drift study, any average containing one of these is biased by +1440/N Hz (+24 Hz in a 60-count mean).
  - In the normalization, any EPICS re-send (A3init, autosave restore, a runner start, spec re-applying a gain) adds a ~1.4 k-count transient to MonC. That is ~1 % of one point at 100 kHz, and far more at low rates.
- **Closing check.** X2 below identifies the field. After that, either avoid re-sending the field when unchanged (the runner could skip writes whose readback already matches), or flag the count after any write as invalid. `check_steplog.py` lists the spikes for any step log.

### F3 (Medium): the runner's means include a count that began before settling
- **Defect.** `monc_sweep.py` polls S4 from `t_settled` and keeps the first value it sees, which is the count that ended *before* `t_settled`. With 2 s settle and 5 s dwell, only 4 counts start after settling. The runner's n = 5–6 includes one or two earlier counts.
- **Evidence.** For most steps the difference is ≤ 1 count. Exceptions:
  - set 3 **B10d: logged 9.5 Hz (n = 6), strict 12.0 Hz (n = 4)**. The count at settle was 1 (still clipped). The results doc already guesses "true ≈12": the strict window confirms it.
  - sweep 2 Z5: 475.0 against 476.75 (n = 4).
- **Failure scenario.** Any step that recovers slowly, or starts near the clip, is biased toward the previous step. That covers the near-clip H block and the C steps at u = 6–8.
- **Closing check.** Change the runner to keep only counts whose IOC timestamp − 1 s ≥ `t_settled`, and to log the IOC timestamps of the first and last counts used. Then `check_steplog.py <log>` should report no MISMATCH lines. Until then, my figures use the strict window and say so.

### F4 (Medium, my defect): panel (b) of `sweep2_response.png` uses the wrong nominal
- **Defect.** The gain panel's nominal is the plan's I = level × u / 1000 = 1 nA at u = 50. Set 3 C gives 20.19 pA/unit with the zero at u = +5.68. So u = 50 is about 0.895 nA at 50 nA/V, which explains G7's ratio of 0.895. The zero error (−229 Hz at 50 nA/V) and the range-dependent darks also enter.
- **Failure scenario.** A reader takes the ratios 0.82–1.45 as SR570 gain errors. Set 3 B (CAL) shows the gain is within 0.02–0.2 %.
- **Closing check.** I will relabel panel (b) as "UNCAL offset vs S (not a gain test)" and add a set 3 B panel ((f − dark)/nominal per range from CAL). For the results doc: the sweep 2 bullet "the gain series is not a clean 1/S law" should point to set 3 B as the gain test.
- **Update (2026-11-12 ~14:20).** Fixed on the figures side. Panel (b) is now titled "UNCAL offset vs sensitivity S — NOT a gain test", with the reason on the panel. `set3_response.png` (b) shows the CAL gain per range: (f − dark)/nominal = 0.9994–1.0018, which reproduces the Experimenter's set 3 B numbers. The results-doc bullet is still the Experimenter's to change.

### F5 (Medium): the baseline is not on the vernier line, and depends on approach
- **Evidence.**
  - Sweep 2 fit V2–V4: 40.52 Hz/unit, 0 Hz at u = +6.00; it predicts 0.1 Hz at u = +6.
  - Set 3 fit (8 points): 0 Hz at u = +5.68; it predicts ~13 Hz at u = 6.
  - Baselines reached from above read 14.1–16.6 Hz (sweep 2 R0/B0/R; set 3 F0/F1/F2/R 15.5/16.6/15.6/16.4).
  - Set 3 C6, reached from u = 4 below, read **1.0 (clipped)**.
- This matches your history finding. The re-run H block (14:01–14:07) is the test; I have not analysed it yet.
- **Failure scenario.** Two dark windows at the "same" setting, one reached from below, differ by ~15 Hz. That would be read as drift.
- **Closing check.** H1/H3/H5/H7 means with per-count traces. I can make that figure.

### F6 (Medium): the dark-drift record is fragmented
- Undisturbed baseline stretches so far: 13:42:07–13:49:49 (7.7 min); 13:59:30–14:01:06 (1.6 min); since 14:07:30 (still running at the time of writing).
- `logger_dark.png` refuses a drift summary until ≥ 30 min have passed since the last setting change. The baseline sits only ~15 counts above the clip.
- **Failure scenario.** A drift rate quoted from a warm-up segment or across a re-send.
- **Closing check.** A ≥ 30 min (ideally hours) window with no A3 writes, reached from above, before any rate is quoted. Whether to give MonC that time is the user's decision.

### F7 (Low): the logger is blind to unchanged-value writes
- Setting rows come from CA monitors, which post only on change, so the F2 re-sends leave no trace in the logger.
- **Closing check (proposal).** Also log a record that processes on every write, for example the `A3*_put` records, if they post on every process. Checking that is a read-only `caget` of their MPST field. Alternatively, the runner could log its own put times with IOC timestamps.

## Experiments proposed (each needs the user's OK; the figures session runs nothing)
- **X1, sign without the coupling.**
  1. At u = +100, 20 nA, UNCAL, write the sign **last** and read both fields back after 1 s. Does EPICS hold (−, +100), or does it rewrite u?
  2. Repeat A/B/A/B where the − steps reach (+, +100) by writing **u first, then sign +**, without ever passing through −100.
  3. If the 1.39 % deficit follows the passage through −100 rather than the readback state, it is a history effect.
  - Read-only first: `caget` the `FLNK`/`OUT` links of `15IDC:A3offset_sign` and `15IDC:A3off_u_put` to see the IOC coupling.
- **X2, which field causes the re-send spike.** At the baseline, re-write **one** field at its unchanged value, 15 s apart, in the order the runner uses (`sens_num, offset_cal, offset_unit, offset_num, offset_sign, off_u_put, offset_on`). Use 5 repeats each. The field whose re-write yields the 1460-count count is the cause.
- **X3, runner window (code only, no hardware).** Implement the F3 change and re-check all logs with `check_steplog.py`.
- **X4, undisturbed dark.** ≥ 30 min with no A3 writes after a restore approached from above (see F6). Ask the user whether a higher u (more headroom above the clip) is acceptable for the drift study.
- **X5, near-clip history.** This was already in the re-run's H block. I can plot it per count once you say the step log is final.

## How to reproduce
```
<bluesky venv>\Scripts\python.exe -I analysis/figures/make_figures.py
<bluesky venv>\Scripts\python.exe -I analysis/figures/check_steplog.py <step log csv> [--all]
```
- `make_figures.py` builds `sweep2_response.png` and the `logger_*.png` files.
- `check_steplog.py` runs on any step log, including yours on `monc-dark`: `..\monc-dark\data\sweeps\monc_sweep_steps_20261112_134949.csv` and `..._140106.csv`.
- The guards (step-log agreement, readback per window, clip handling, excursions) are in `analysis/figures/README.md`.

## Not checked
- The serial commands actually sent to the SR570 (listen-only; no asyn trace was taken).
- The re-run (14:01–14:07) results, beyond locating its spikes.
- Set 3 blocks A–D, apart from the windows and readbacks: I have not re-derived your fits.
- MonP: shown read-only as context only.

## Update 2026-11-12 ~14:20: set 3 and the re-run are in the figures
- `set3_response.png` and `darks_over_time.png` read the step logs from `monc-dark` with `git show` (no edits to that branch). Recomputed from the raw record, they reproduce the write-up:
  - vernier 40.38 Hz/unit, zero at u = +5.68;
  - C500/C1000 ratios 0.9999/1.0006;
  - CAL ratios 1.0006 / 1.0020 / 1.0007 / **0.9884** / 1.0030 / 1.0015.
- **F1 still applies to the write-up.** Section E still reads "Sign − is 1.39 % lower". Panel (e) shows, per count, that the readback was (+, +100) in all four E windows.
- **F5 is answered by the re-run H block.** From below, u = +6 stays clipped for 9 counts and the first unclipped count comes 10 s after the write (H3, H7). From above it reads 16–17 Hz at once. That matches the Experimenter's "discard ≥ 12 s" rule, which `logger_dark.png` now applies.
- **F6:** the post-re-run dark stretch ran 14:07:13–14:14:45 (7.5 min). At 14:14:45 an A3 change started (offset OFF → CAL → 1 nA → ON), presumably the V2F impedance procedure. So there is still no ≥ 30 min undisturbed record.

## Update 2026-11-12 ~14:25: F1 closed; dark hold in the figures
- **F1 closed** by the Experimenter on monc-dark (ff662a8). §E and the sweep 2 sign bullet now describe a command-path effect with the same EPICS state. Closing check: set3_response (e) shows readback (+, +100) in all four E windows, which agrees with the corrected text.
- **Dark-drift hold.** From 14:14:49 MonC is held at CAL 1 nA, 50 nA/V, sign +, ON. It reads 2055 Hz, so the dark-equivalent is S4 − 2000 = +55 Hz.
  - `logger_dark_cal1nA_hold.png` starts 12 s after 14:14:49 and plots raw S4 with dark-equivalent on the right axis.
  - Confound stated on the figure: S4 drift = dark drift + CAL-generator drift, which this record cannot separate.
- **New: the hold was interrupted at 14:22:08–14:22:25.** The A3 readbacks show `offset_cal` UNCAL → CAL → UNCAL → CAL and `off_u_put` 5/4/5/4, with no step log. The Experimenter said they would make no MonC writes, so the source is unknown: please check, or ask the user. The final readback is the CAL 1 nA hold again. `logger_dark_cal1nA_latest.png` covers the stretch from 14:22:37 and is labelled with the interruption.

## Update 2026-11-12 ~15:10: the 14:22 changes were the user's; first ≥ 30 min dark window
- The user confirmed the 14:22:08–14:22:25 MonC changes were theirs: "Yes, that was me." That question is closed. The overview labels the cluster as the user's.
- **The first ≥ 30 min undisturbed window (F6, partly met).** The CAL 1 nA hold ran 14:22:37–15:01:29 (39 min, 2330 counts, no excursions, nothing clipped). `logger_dark_cal1nA_latest.png`:
  - first 10 min (14:22:38–14:32:38): mean S4 2054.70 Hz, sd 0.67, n 600;
  - last 10 min (14:51:28–15:01:28): mean S4 2052.94 Hz, sd 0.74, n 600;
  - difference **−1.76 Hz in 39 min** (dark-equivalent ≈ +54.7 → +52.9 Hz). This is model-free; no drift rate is quoted, because the unit is ~1 h past power-on.
  - Confound: this is dark drift plus CAL-generator drift, and the two can't be separated in this record.
- **Changes since 15:01:29 are unlogged here.** `offset_on` OFF at 15:01:29, then 25 changes 15:04:49–15:09:08 across µA/V and nA/V ranges. They are presumably sets 4/5 (plans on monc-dark f18ca03, 3469755, bbf636b). They stay hatched as "unlogged" until their step logs reach monc-dark and are added to `loaders.SWEEP_FILES`.

## Update 2026-11-12 ~15:30: sets 4 and 5 in the figures; the dark figure redone on one axis
- Sets 4 and 5 (monc-dark ffc4309) are picked up automatically: each step log is matched to the plan with the identical step list. The step-log guard passes and every count window has a constant readback.
- At the user's request, the per-range dark figure is now **one axis** (`darks_by_range.png`): sensitivity is the series (hue = decade, marker = 1/2/5), with a legend and direct labels. Facts it now makes visible:
  - **5 nA/V: +55 Hz (sweep 2) → clipped (set 3, re-run up) → +2.3 Hz part-clipped (re-run down).** Its dark sign changed after power-on, or depends on the approach direction.
  - **10 nA/V: +12 → clipped → +5.5 Hz**; 2 nA/V clipped every time.
  - **Drifting:** 200 nA/V 360 → 545 Hz and 500 nA/V 117 → 220 Hz rise over ~70 min; 1 nA/V falls 475 → 448 Hz.
  - **Steady:** 20/50/100 nA/V, and 5/10 µA/V within a few Hz. The 50 nA/V offset-OFF darks agree with the CAL-hold dark-equivalent (S4 − 2000 Hz ≈ 53–55 Hz).
  - **Standard gain 5 µA/V:** dark 16–19 Hz. The interim hold (S4 − 40 Hz) continues it at ≈ 19 Hz.
  - ~~set 4 P0: 630 Hz at 50 nA/V offset OFF, labelled as an anomaly~~. **Withdrawn: P0 was at 20 µA/V; see F8 below.**
- `cal_ladders.png` puts all 53 CAL points (set 3, sets 4/5, sweep 2 C1) on one axis against output voltage. Ratios 0.9884–1.0072, which reproduces `monc_ladders.py`. The only points outside ±0.5 % are:
  - the 10 nA level: −1.16 % at 50 nA/V (set 3 A and B); −0.73 % at 500 nA/V (set 4, 0.02 V);
  - 1 µA/V: +0.72 % at 0.02 V (20 nA level); +0.52 % at 2 V;
  - 20 µA/V: +0.71 / +0.57 / +0.51 % at 0.25 / 0.5 / 2.5 V;
  - 2 nA/V at 0.25 V (set 3 B2l): −0.51 %, with its dark clipped and taken as 0.
- The interim configuration (5 µA/V, CAL +2 nA, set 15:20:44) has its own dark window, `logger_dark_interim_5uA_cal2nA.png` (S4 − 40 Hz). It is still open.

## F8 (Medium): the set 4 P0 "anomaly" was at 20 µA/V, not 50 nA/V
- **Defect.** The write-up (Sets 4 and 5) says set 4's first step "(50 nA/V, offset off …) read 630 Hz, against 52.5 Hz for the same step in set 5. That's another command-path state invisible to EPICS." But EPICS shows the state:
  - P0 (15:05:18–15:05:26) has readback **20 µA/V**, offset OFF, CAL 1 nA.
  - `A3sens_unit` went to uA/V at 15:04:49 and `A3sens_num` to 20 at 15:04:51, 24 s before set 4 started. P0's writes don't touch the sensitivity.
  - The step log's own `state_end` for P0 reads `sens_unit=uA/V;sens_num=20`.
  - 630 Hz sits just above the 20 µA/V darks measured later (578–606 Hz), so this is an ordinary 20 µA/V dark read right after switching.
- **Where the 20 µA/V came from.** No step log covers 15:04:49–51. It falls between the set 4 v1 plan commit (15:04:07) and v2 (15:05:03), so presumably a first set 4 attempt was started and stopped. That is for the Experimenter to confirm. The earlier `offset_on` OFF at 15:01:29 is also unlogged.
- **Failure scenario.** The write-up counts this as a second hidden command-path state, next to F1's genuine one. That overstates how unreliable the EPICS record is, and could send someone hunting for a fault that isn't there.
- **Closing check.** Correct the bullet in "Sets 4 and 5", and say where the 15:01:29 and 15:04:49–51 writes came from. The figures now plot P0 as a 20 µA/V point (`fig_ranges.ANOMALIES` is empty, with the reason in a comment).

## Also new: `darks_vs_range.png` (the Experimenter's "dark vs range, both orders")
- x = sensitivity (1 nA/V … 20 µA/V, log), y = offset-OFF dark (log), one series per run, with the re-run's upward and downward passes as separate series. Solid lines join neighbouring ranges on the 1-2-5 ladder; dotted lines cross a range that was skipped or clipped.
- **Repeatable across runs and directions:** 1, 20, 50 and 100 nA/V, and 1–20 µA/V (sets 4 and 5 overlie each other).
- **Not repeatable:**
  - 5 nA/V: +55 Hz in sweep 2; clipped in set 3 and the upward re-run; +2.3 Hz, part-clipped, downward;
  - 10 nA/V: +12 Hz (set 3); clipped (up); +5.5 Hz (down);
  - 200 and 500 nA/V rise from run to run (warm-up).
- A pure input current (∝ 1/S) is ruled out on sight.

## Update 2026-11-12 ~15:40: F8 closed; V2F zero-input rate drawn
- **F8 closed** by the Experimenter on monc-dark: the write-up now gives the 630 Hz as the 20 µA/V dark (gain set 15:04:49, outside their runs). Closing check: the figures plot set 4 P0 at 20 µA/V, next to the 578–606 Hz darks.
- **V2F zero-input rate.** Recomputed from this logger with the SR570 off (13:08:57–13:29:54): **8.40 Hz, sd 0.49, n = 1258**. It agrees with the Experimenter's 8.4 Hz, and the code refuses the figure if the two differ by more than 0.1 Hz. Every dark figure now draws it as a grey dash-dot line, distinct from the red 1-count clip.
- **What that changes in the reading.** With 0 V at the V2F input ≈ 8.4 Hz, a reading between 1 count and 8.4 Hz is a slightly **negative** SR570 output, not a small positive one:
  - 10 nA/V at 5.5 Hz (re-run, down);
  - 5 nA/V at 2.3 Hz (re-run, down, part-clipped).
  So these ranges' darks are negative or about zero, not "a few Hz positive". The dark-vs-range figure shows this directly. The sweep 2 legends that called 8.4 Hz a "floor", or the clip "input ≤ 0 V", are corrected.
- **Assumption, untested here:** the V2F is linear through its 8.4 Hz zero, and the switched-off SR570 presents ≈ 0 V. A switched-off output isn't guaranteed to be 0 V.

## Update 2026-11-12 ~15:50: plain-language titles; a new unlogged MonC run since 15:40:46
- At the user's request, every figure and panel now has a plain-language headline above its technical title.
- **New MonC writes from 15:40:46**, during the announced pause for the f99 restart. They are structured, not a restart artefact:
  - `blank_on` toggles;
  - CAL ladders through 200 nA–5 µA at 500 nA/V, 1, 2 and 5 µA/V;
  - still running at 15:47:27.
  No step log for them is on monc-dark yet, so the figures hatch them as unlogged. Who ran it: Experimenter, please confirm.

## Update 2026-11-13 ~08:40: the overnight program in the figures
- **New figures** `night_darks.png` and `night_hold.png` (`fig_night.py`), built from the raw step log
  `xray_fluxor-data/sweeps/monc_sweep_steps_20261112_154045.csv` and the plan on monc-dark@85b0eef. All 1,224 steps
  reproduce from the raw logger under the strict-window check; no step was clipped or part-clipped.
- **They agree with the Experimenter's `monc_passes.py` summary** (results § "Overnight results"): flat darks in every
  range; the interim hold at S4 ≈ 60 Hz, i.e. S4 − 40 Hz ≈ 20.2 Hz, next to the 5 µA/V offset-OFF darks at
  ≈ 20.0 Hz. So the CAL +2 nA level at 5 µA/V gives ≈ 40.2 Hz (+0.5 % on nominal; not a measured CAL ladder point).
  The two 5 µA/V series wander together by ~1 Hz over tens of minutes (e.g. 07:15–08:00), consistent with the
  common component the Experimenter found.
- **Hutch temperature** (raw 60 s archiver pulls, `temperature.py`; Sensor3/4 read 0.0 °C, no sensor):
  Sensor1 21.58–21.69 °C, Sensor2 (C hutch) 22.11–22.25 °C, Sensor5 23.59–23.74 °C over the run.
  - Pearson r of each dark series against each sensor: −0.26 … +0.46 raw, −0.26 … +0.27 after removing a linear
    trend from both (largest raw: 20 µA/V vs Sensor5 +0.46, a shared slow trend; 5 µA/V vs Sensor2 +0.01).
  - **Not a verdict.** A ≤ 0.15 °C swing cannot test a temperature coefficient; the figure says so. A deliberate
    change of ≥ 1 °C would.
- **Privacy correction (figure side).** I had written the venv path with the account name into four tracked files;
  they now say `<bluesky venv>`. Earlier commits on `claude/figures-c4aacd` still contain it: squash before any push.
- **Stale-label fixes:** the night headers said "PROVISIONAL, still running" after the run ended; they now say
  "run ended after 1224 of 1476 planned steps". Labels of the blanked series no longer sit on other series' data.

## Update 2026-11-13 ~10:15: electronics figures (elec1–elec5) and two findings
Made for `ELECTRONICS_CONCLUSIONS.md`, from the raw logger on strict windows (`analysis/figures/fig_electronics.py`). The joint fit is monc_grid.py's, re-implemented. It reproduces g1, g2 and g4 closely; g3 differs.

### F9: the 20 µA/V dark wanders inside one step, and that sets the V-term and the g3 misfit (severity: medium for the uncertainty budget)
- **Defect.** The write-up says each range's dark "holds to < 1–2 Hz" once selected. At 20 µA/V it does not:
  - `g3_20u_d` steps from 592–596 to 614–615 Hz at 00:29:21, inside the step;
  - `g4_20u_off` falls from 616 to 584 Hz within 10 s;
  - in the passes, the 95th percentile of max − min within one 20 µA/V step is 26 Hz (max 39 Hz). At 5 and 10 µA/V it is 2 Hz.
- **Effect on the fit.**
  - With every range: rms g2 0.0067 %, g3 0.0131 %, g4 0.0065 %; c = −0.0005 to +0.0036 %/V.
  - Without 20 µA/V: rms 0.0011 / 0.0027 / 0.0050 %; c = +0.0054 to +0.0081 %/V (g2 +0.0070 ± 0.0007).
  - So **the output-voltage term is ≈ +0.007 %/V (≈ 0.03 % at 4.5 V), not +0.003 %/V.** The smaller value comes from 20 µA/V dark error leaking into c.
- **Strict windows vs runner means.** monc_grid.py uses the runner's `mean_S4`, which includes counts from before settling (F3). For `g3_20u_d` that gives 604.9 Hz against 607.0 Hz strict; for `g3_20u_2uA`, 10694.1 against 10688.6 Hz. Repeatability "≤ 0.015 %" becomes **0.030 %** (20 µA/V) and 0.019 % (500 nA/V, 1 µA/V, 2 µA/V) with every range on strict windows, and **≤ 0.015 %** without 20 µA/V.
- **Failure scenario.** The conclusions quote +0.003 %/V and 0.015 % repeatability as properties of the V2F and the ranges. Someone budgeting a 20 µA/V measurement then assumes a ±1 Hz dark, where the real one is ±10–20 Hz: 0.1–0.2 % at 10 kHz.
- **Closing check.** Rerun monc_grid.py on strict-window means (or compare with `make_figures.py --only electronics`, whose console prints both fits), and state the 20 µA/V in-step wander in the conclusions.

### F10: line (b) of the dark-error figure needs a same-selection number, not the pass-to-pass sd (severity: low)
- The requested "(b) ±1 Hz at 5 µA/V" equals the 5 µA/V pass-to-pass sd (0.97 Hz), which is case (c) for that range.
- A same-selection estimate from the 92 pairs (2nd `5u_d` → `5u_ub`, ~30 s apart, only a blank/unblank between them) gives **0.43 Hz per reading** (r = 0.78, mean change +0.11 Hz). elec5 uses that for (b).
- **Closing check.** The conclusions quote 0.43 Hz for a dark taken at the same selection, and 1.0 Hz for one from an earlier selection.

### Also in these figures
- Linear drift does exist at some ranges, though it is small: 500 nA/V −0.66 ± 0.16, 1 µA/V −0.35 ± 0.08, 20 µA/V −1.92 ± 0.36 Hz/h (0.3 %/h of that dark). At 5 and 10 µA/V it is −0.03 Hz/h. So "no drift" should read "drift ≤ 2 Hz/h, much smaller than the selection scatter".
- CAL levels relative to their mean (g2–g4): 200 nA +0.163 %, 2 µA +0.291 %, 5 µA +0.105 %, 20 µA −0.445 %; largest minus smallest 0.74 %.
- Every figure carries: "MonC only… MonP's electronics were never measured."

## Update 2026-11-13 ~10:20: F9 and F10 closed
The Experimenter ran both closing checks and applied them to `ELECTRONICS_CONCLUSIONS.md` (monc-dark 1827066). I read that file at 1827066.
- **F9 closed.**
  - Per-count data, on the Experimenter's side: `g3_20u_d` 593 → 615 Hz, 9.3 s into the step; `g4_20u_off` 616 → 584 Hz.
  - Refit without 20 µA/V, on runner means: V term +0.006 / +0.007 / +0.005 %/V (g2/g3/g4), rms 0.001 / 0.002 / 0.006 %. Mine, on strict windows, is +0.0070 / +0.0081 / +0.0054 %/V. Each grid agrees within one standard error (±0.0007 / ±0.0018 / ±0.0032).
  - The conclusions now give the V term as ≈ +0.006 %/V (+0.005 … +0.008), and say that 20 µA/V jumps inside a step.
- **F10 closed.** The Experimenter's 5u_d2 vs 5u_ub check gives 0.42 Hz, r 0.79 (mine: 0.43 Hz, r 0.78). The conclusions use 0.43 Hz for a dark at the same selection.
- **F3 stays open.** The runner includes a count from before settling. The Experimenter has not checked it.
  - **Figures are unaffected.** They use strict windows, and `check_against_log` refuses any step whose runner mean differs from the strict mean by more than max(1 count, 0.1 %, 3·sd/√n).
  - **Numbers taken straight from the step log are affected**, for example monc_grid.py's. `g3_20u_d` reads 604.9 Hz there, against 607.0 Hz strict.
  - **Closing check:** after the runner is changed to use only counts that start after `t_settled`, every logged step mean equals the strict-window mean to within 1 count (`check_steplog.py <steplog> --all`).

## Next on the figures side
1. Add set 3 and the re-run to `loaders.SWEEP_FILES`. This needs their step logs and plans on this branch, or a path option.
2. Replace panel (b) (F4) and add CAL-linearity and per-range gain panels from set 3 A/B.
3. A per-count near-clip figure for the H block (F5).
4. Proposal figures, once the user picks which.

## Update 2026-11-13 ~12:20: chamber disconnection (C1) in the figures
- **What happened.** The user took MonC's chamber to their office. Their words: "Up until i started measuring the
  monc chamber in my office it was fully connected, but no beam going through. Right now nothing is at the end of
  the monc BNC cable that connects to the SR570".
  - The Experimenter located the handling at 10:13:15–10:14:39. I re-checked it from the raw logger.
- **The interim setting before and after,** with no A3 change between them: 59.09 Hz → 38.51 Hz. The drop is
  20.58 ± 0.14 Hz, which is 1.029 ± 0.007 nA at 5 µA/V: current from the cabled chamber with no beam.
  - HV leakage is the likely cause, but that is an inference.
- **elec5** had broken (a) down as "V2F zero 8.4 Hz + SR570 output offset + the calibrated +2 nA". That left out
  the chamber current. It now gives the chamber part from the data and says the rest isn't separated.
- **Unaffected:** elec1–elec4 and every dark-subtracted result, because each dark was taken in the same state as
  its light reading.
- **F9 is not explained by this.** 1 nA is about 5 Hz at 20 µA/V, against 26 Hz jumps inside a step.
- **Time-series figures** now mark C1, and no averaging window may span it (`loaders.INPUT_CHANGES`).
  - Closing check for any later change: enter it in `INPUT_CHANGES`, regenerate, and see its C tag in the overview header.

## Update 2026-11-13 ~12:40: CORRECTION to the ~12:20 update. The C1 drop is not a current.
- **What was wrong.** The ~12:20 update and elec5 (commit 09a2ed8) said the 20.6 Hz drop was "1.029 ± 0.007 nA
  ... current from the cabled chamber". That was wrong.
- **The Experimenter's leak run** (chamber unplugged, 12:09–12:26) dropped every range by about 21 Hz.
  - I re-checked it from the raw logger: the step log reproduces, and drop = c + 1e5·I/S over 200 nA/V–2 µA/V
    gives c = 21.2 ± 2.8 Hz, I = −1 ± 10 pA. The Experimenter got 21.5 ± 1.3 Hz and −2.6 ± 12.8 pA.
  - The blanked 5 µA/V reading dropped by +21.3 Hz, and the hold by +20.7 Hz.
- **So the chamber connection adds a ~21 Hz offset that doesn't depend on the gain,** and it enters after the
  SR570 input. There is no measurable leakage current.
- **elec5** now says this, with the fit computed from the leak run.
- **Pooled range figures** leave the leak run out and name it in a NOT SHOWN line.
- **Closing check:** elec5's header shows "It is NOT a current" with c and I from `leak_fit`, and the console line
  `leak fit:` reproduces the numbers above.
