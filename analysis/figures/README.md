# MonC figures

Regenerate-from-raw figures for the MonC SR570 sweeps (15IDC:A3), the 1 s logger record
and its dark-drift tail. Read-only: the code reads files and writes PNGs. It never touches EPICS.

## Run
```
<bluesky venv>\Scripts\python.exe -I analysis/figures/make_figures.py
<bluesky venv>\Scripts\python.exe -I analysis/figures/make_figures.py --only sweeps
<bluesky venv>\Scripts\python.exe -I analysis/figures/make_figures.py --logger <other ca_logger csv>
```
Bare `python` is a broken stub on this PC. Output goes to `analysis/figures/out/`, which is
gitignored: the logger file is still growing, so the PNGs are regenerated rather than committed.
Every PNG carries a footer with the raw file, its last count time and the code revision.

## Figures
| File | What it shows |
|---|---|
| `sweep2_response.png` | Sweep 2 (SR570 live) by block: (a) UNCAL vernier with its fit, residuals and a zoom near the clip; (b) gain series vs nominal 1e5 Hz/V × I/S, with ratio panel; (c) offset-OFF dark vs S; (d) UNCAL level groups; (e) CAL vs nominal; (f) the sign block, written vs read back. Sweep 1/1b (SR570 OFF) is the grey control. |
| `set3_response.png` | Experiment set 3 and the sweep-1 re-run (Experimenter): (a) CAL linearity at 50 nA/V (10 nA level −1.16 %); (b) gain per range from CAL; (c) UNCAL vernier transfer with fit, residuals and zoom (zero at u = +5.68); (d) UNCAL slope per level group; (e) sign A/B per count with the EPICS readback; (f) near-clip recovery per count (H block). |
| `darks_by_range.png` | Offset-OFF dark vs minutes since power-on for **every range on one axis** (log y), all live runs. Hue = decade of the sensitivity, marker = mantissa (1/2/5), legend plus a direct label per series. Solid lines join clean neighbours < 15 min apart; dotted lines join all points of a range. Open markers: clipped, part-clipped or a labelled anomaly. Dashed: dark-equivalent from the CAL holds. Replaced `darks_over_time.png` (one panel per range) on 2026-11-12 at the user's request. |
| `darks_vs_range.png` | Offset-OFF dark vs sensitivity (log–log), one series per run and per sweep direction (re-run up/down). Solid lines join neighbouring ranges on the 1-2-5 ladder; dotted lines cross a skipped or clipped range. Includes a pure-input-current (∝ 1/S) reference. |
| `cal_ladders.png` | (S4 − dark)/nominal − 1 for every CAL point (sign +, ON) against SR570 output voltage, every range on one axis, same encoding. Dark = mean of the nearest offset-OFF steps before and after at the same range in the same run (as `monc_ladders.py` on monc-dark). |
| `logger_overview.png` | The whole 1 s record: S4 (log), A3 readbacks (u, ON/CAL/sign lanes, sens, offset level), MonP S3 and ring current as read-only context. Step windows shaded, power-on and A3init marked, unlogged A3 changes hatched. In a window longer than 45 min the hatched spans are tagged U1, U2 … above the top panel and described in a key in the header (time, number of changes, who made them where known), instead of in-panel notes that would overprint. Hand-made input changes (C1 …, purple) are marked the same way; see the guards. |
| `logger_poweron_sweep2.png` | Same layout, 13:25 to A3init + 10 min: power-on transient, warm-up, sweep 2. |
| `logger_dark_<hold>.png` | One figure per dark-record window ("hold"), defined as data in `fig_logger.HOLDS`. Each window starts 12 s after its event, ends at the next A3 change, and is refused if the readback doesn't match the hold's expected state. Windows: `after_sweep2`, `after_rerun1` (baseline UNCAL u = +6); `cal1nA_hold` (CAL 1 nA at 50 nA/V from 14:14:49, dark-equivalent = S4 − 2000 Hz on the right axis, CAL drift confound stated); `cal1nA_latest` (the latest uninterrupted stretch in that state); `interim_5uA_cal2nA` (5 µA/V CAL +2 nA from 15:20:44, dark-equivalent = S4 − 40 Hz). The open window is marked PROVISIONAL. |
| `night_darks.png` | Overnight program (Experimenter, 2026-11-12 15:40 to 11-13 08:10): offset-OFF dark per range vs time, every range on one log axis, blanked readings (SR570 output blank ON) as × series. Hutch temperature panel below. The header says whether the step log is still running, complete, or ended short of its plan. |
| `elec1_linearity.png` | MonC CAL-ladder linearity from the overnight grids g1–g4 (`fig_electronics.py`, for the Experimenter's `ELECTRONICS_CONCLUSIONS.md`). The monc_grid.py joint fit ln(ratio) = range + level + c·V, re-implemented on strict windows, as two candidate fits: without 20 µA/V (whose dark wanders inside a step) with its output-voltage term drawn, its residuals, and the all-range residuals. |
| `elec2_range_scale.png`, `elec3_cal_levels.png` | Range scale factors and CAL level factors per grid, one small panel per range or level with the same y span around each panel's g2–g4 centre. Both fits shown; the fit without 20 µA/V is re-referenced to the CAL levels both share (`align`), because mean(b) = 0 runs over different level sets. |
| `elec4_dark_scatter.png` | Overnight pass darks per range minus their mean, with slope ± se and detrended lag-1 r per row; summary of the step-mean sd, the within-step sd, the pass-to-pass sd and the 95th-percentile within-step wander. |
| `elec5_dark_error.png` | Dark error ÷ signal vs count rate (100 Hz–1 MHz): (a) no subtraction at the interim setting, (b) a dark at the same 5 µA/V selection (pairs 2nd `_d` → `_ub` in each pass), (c) a dark from an earlier selection (pass-to-pass sd per range). 400 cps and 400 kHz rules marked. The header breaks (a) down using the C1 disconnection. `interim_before_after`: the interim S4 just before and just after C1, with the same EPICS state, each window ≥ 30 min, ± from 5-min means. It fell by 20.6 ± 0.1 Hz on 2026-11-13. `leak_fit`: the Experimenter's leak run (chamber unplugged) against the last 10 overnight passes, range by range. The fit is drop = c + 1e5·I/S over the ranges where neither side clips, leaving out 20 µA/V (F9). It gave c = 21.2 ± 2.8 Hz and I = −1 ± 10 pA. So the drop is **not a current**. It is an offset of about 21 Hz that doesn't depend on the gain. It also survives blanking the output, so it doesn't enter at the SR570 input. (An earlier version of this figure called it a 1.03 nA chamber current, which was wrong.) The rest isn't separated into the V2F zero, the SR570 output offset and the CAL. (b) and (c) were measured with the chamber cabled. |
| `unc10_summary.png` | MonC's uncertainty at a fixed 10 keV, every source on one log axis. The absolute budget is read from `calc/quality_slots.py` SYMMETRIC_TERMS (σ_s 3.58 %), with the energy-readback sensitivity at 10 keV computed from `calc/monp_transform.full_physics`. Next, the error of one normalisation reading at one gain: minutes apart (noise plus a fresh dark), hours apart (adds the measured wander, unc10_check) and days apart (adds the 0.2 % density bound). Last, what spoils normalisation, each source on its own: raw-count weather (`analysis/out/pressure_climatology.txt`, `hutch_temperature.txt`), a gain change (nominal or measured factors, `data/calibration/monc_sr570_ranges.csv`), a stale or unsubtracted dark, linearity, and a 1 mm beam move (`analysis/out/collection_length_cmc.csv`). Rate-dependent rows are shown at 200 kHz and 10 kHz. The header gives the chamber state and MonC's last hour in the logger. |
| `unc10_vs_rate.png` | The same normalisation error against count rate, 1–400 kHz, for 5 µA/V darks. It shows the measured noise per CAL step (sd of successive 1 s counts ÷ √2), the fresh, stale and unsubtracted darks, the linearity against 200 kHz, and the combined A (minutes), B (hours) and C (days, live photons/s) curves. The top axis is photons/s at 10 keV for 5 µA/V. |
| `unc10_check.png` | Coverage check of the relative error (uncertainty-budget skill). Grid-to-grid repeats of the same CAL step (grids 2–4, 4.3 and 8.6 h apart, 20 µA/V left out) are compared with noise + fresh dark. It gives k = 1 coverage, k_cal and a block bootstrap over gain × grid-pair blocks. The absolute budget is marked NOT CHECKED: there is no independent reference. |
| `night_hold.png` | The interim setting during its 480 s holds: S4 − 40 Hz per count (grey) and per hold (mean ± sd), on the same axis as the 5 µA/V offset-OFF pass darks. Blanked 5 µA/V readings are named off scale. Hutch temperature panel below. |

## Inputs
- Raw logger CSV (outside git): `xray_fluxor-data/ca_logger/20261112_130858_monc_sweep1_then_dark.csv`,
  found by walking up from the repo. Long format, see `loaders.py`.
- Step logs and plans: `data/sweeps/`, mapped explicitly in `loaders.SWEEP_FILES`. A new sweep is
  added there (step log + plan + `SR570_STATE`) and to `SWEEP_SHADE` in `fig_logger.py`.
- **New step logs are found automatically** (`loaders.discover_sweeps`). Any `monc_sweep_steps_*.csv` on
  this branch or committed on monc-dark that isn't in `SWEEP_FILES` is matched to the one plan with the
  identical step list, and named after it (`monc_set4_plan.csv` → `set4`). If it matches no plan or more than one,
  it is not used, and the CLI prints `NOT ADDED`. Committed files and the raw step logs (below) are used;
  `--extra-sweeps-dir` adds another folder for testing only (the subtitle then says UNCOMMITTED).
- A file that isn't on this branch is read read-only with `git show monc-dark:data/sweeps/<name>`
  (`loaders.OTHER_REF`). A local copy, e.g. after a merge, takes precedence. The figure subtitle names
  the source and commit.
- **Raw step logs outside git** (`loaders.RAW_SWEEPS` = `xray_fluxor-data/sweeps/`) are used when the file is not
  committed anywhere, e.g. the overnight log while it was being written. Such a log may be a **prefix** of its plan;
  steps are paired with the plan by position (the night plan repeats step names), and an unfinished last line is
  dropped. The subtitle says "raw … (outside git)".
- **Hutch temperature** (`temperature.py`): raw archiver pulls of `15ID:Sensor1..5:Temperature` (SCAN 60 s), no
  binning operator, saved outside git in `archiver-pulls/xray_fluxor/`. Pull them with
  `<bluesky venv>\Scripts\python.exe -I analysis/figures/temperature.py pull [--from ISO] [--to ISO]` (read-only
  HTTP GET); the figures only read the saved files. The archiver address is in the gitignored `site.env`
  (`ARCHIVER_RETRIEVAL=host:port`; copy `site.env.template`). Readings outside 5–45 °C or with nonzero severity are
  dropped, so Sensor3/4 (0.0 °C, no sensor) are left out and named as not shown.
- Dark windows start 12 s after their event, which skips the near-clip recovery the Experimenter
  measured (~10 s). (`logger_dark.png` was renamed to `logger_dark_<hold>.png` on 2026-11-12.)

## Titles
Every figure and every panel has a plain-language (ELI5) headline in bold, with the technical title
underneath (requested by the user 2026-11-12). Helpers in `common.py`:
- `header` lays out the figure headline, technical title and notes from the top, in inches, and returns the
  space left for the axes;
- `titled` gives a panel its two-line title;
- `inlabel` puts the headline inside stacked time-series panels, where there is no room between panels.

`save()` runs `check_titles`, which prints `WARNING headline wider than its panel` when a headline could run
into its neighbour. A run with no warnings is part of the check.

## Colour
`fig_ranges.py` uses the first five slots of the dataviz reference palette, in fixed order (blue, orange, aqua,
yellow, magenta), one per decade of sensitivity. The palette documents these as passing on adjacent pairs, but not
all-pairs, and yellow and magenta are below 3:1 contrast on white. So every series also has its own marker and a
direct label, and colour is never the only cue. (The palette validator needs node, which isn't installed on this PC.)

## Rules built into the code (guards)
- **Step windows** use only counts that *started* after the step settled (`loaders.step_window`).
  The sweep runner polled at 4 Hz and also took the count already complete at `t_settled`, so its
  means can differ by about one count; `check_against_log` refuses the figure if any step differs
  by more than max(1 count, 0.1 %, 3·sd/√n).
- **Settings** are EPICS readbacks from the logger during the window, not the plan. The IOC rewrites
  `offset_sign` to follow the vernier sign, so the plan is not the state. `settings_during` refuses a
  window in which any A3 setting changed.
- **Changes to what the input is connected to** (`loaders.INPUT_CHANGES`) are made by hand, so no PV records them.
  Each one is entered with its handling interval, the state before and after, and its source.
  - `settings_during` refuses any window that overlaps one, and a dark-record window ends at one.
  - Every time-series panel draws the handling interval shaded purple with a solid line at its end. The top panel is
    tagged C1, C2 …, and the header says what changed.
  - C1, 2026-11-13 10:13:15–10:14:39: MonC's chamber was disconnected. Before it, the chamber was cabled with no beam
    (the user: "fully connected"); after it, the SR570 input is the BNC cable with its far end open. The interval
    comes from the handling noise in S4 (Experimenter), re-checked here.
  - The pooled one-axis range figures (darks_by_range, darks_vs_range, cal_ladders) show only runs with the original
    input, the chamber cabled. Any other run is named in a NOT SHOWN line (`fig_ranges.not_shown`); on 2026-11-13
    that is the leak run.
  - **Enter the next change** (chamber back, a cap on the cable, HV off) **in `INPUT_CHANGES` before regenerating**.
    Otherwise the figures will treat the counts on both sides as one state.
- **V2F zero-input rate** (`loaders.v2f_zero`): the mean S4 while MonC's SR570 was off (logger start to 1 s before
  the 13:29:56 power-on). That is 8.40 Hz (n = 1258), and it is checked against the Experimenter's 8.4 Hz
  (`analysis/v2f_zero.py` on monc-dark); the figure is refused if they differ by more than 0.1 Hz. It is drawn as a
  grey dash-dot line (`common.zero_line`), distinct from the red dashed 1-count clip. A reading between 1 count and
  8.4 Hz means the SR570 output is slightly below 0 V, but not clipped.
- **Clipping:** S4 ≤ 1 count = the unipolar V2F floor (output well below 0 V). Clipped points get their own marker,
  are never fitted, and running means skip any window containing one.
- **Excursions** in the dark record (|S4 − median| > max(10 counts, 10 × 1.4826·MAD)) are drawn at the
  top edge with their values, listed, and excluded from averages.
- **No drift rate** is quoted from the dark record: it is a warm-up. A first-vs-last 10 min
  difference is shown only once ≥ 30 min have elapsed since the last setting change.
- **Events:** the power-on transient and A3init are located in the data and checked against the
  constants in `common.py`; the figure is refused if they disagree.
- **No temperature verdict from a quiet room:** if the largest hutch swing in the window is < 1 °C peak to peak, the
  temperature panel says it is too small to judge whether the darks follow temperature (2026-11-12/13: 0.15 °C).
- **Run status:** a step log short of its plan is "PROVISIONAL, still running" unless it has been silent for 20 min
  while the logger kept recording; then the header says "run ended after N of M planned steps".
- **Dates on time axes** (`common.time_axis`): ticks are HH:MM, a tick at midnight is written as the new date
  (e.g. "13 Nov"), and the axis label gives the dates the window covers. Nothing hard-codes the date.
- Console output is ASCII only (`common.say`); figure text keeps its glyphs.

## Files
`make_figures.py` (CLI), `loaders.py` (raw readers, windows, guards), `common.py` (style,
constants, provenance footer), `fig_sweeps.py`, `fig_set3.py`, `fig_ranges.py`, `fig_logger.py`, `fig_night.py`, `fig_electronics.py`, `fig_unc10.py`,
`temperature.py` (archiver pull and reader), and `check_steplog.py`. That last one
cross-checks any step log against the raw record: readback sign/u per window, strict vs runner means,
a requested sign that is not in the readback, and the ~1460-count re-send spikes.

Findings from these checks, for the Experimenter: `data/sweeps/review_by_figure_man.md`.
