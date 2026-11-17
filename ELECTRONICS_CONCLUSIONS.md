# Ion-chamber electronics: conclusions and uncertainty (2026-11-13)

Signal chain: SR570 current preamp → N101VTF V2F (1e5 Hz/V) → Joerger scaler1, 1 s counts.
Measured on **MonC only** (`15IDC:A3`, scaler1 S4), 2026-11-12 13:00 to 2026-11-13 08:10.
The measurements:
- seven sweeps and sets;
- four calibration grids;
- 92 dark passes;
- a hutch-temperature comparison.

Details and evidence: `data/sweeps/monc_sweep1_results.md`. **MonP's electronics were never measured** ("Do not touch MonP").

## In one paragraph
**On the absolute flux number, the analogue electronics are a small term and not the limiting one.**
- MonC's chain, measured end to end against the SR570's own calibrated offset current:
  - is linear to ~0.03 % from 10 to 450 kHz;
  - repeats to 0.015 % over 9 h (0.03 % including 20 µA/V);
  - each range is within −0.17 … +0.6 % of nominal.
- That is about the SR570's ±0.5 % spec, with one range beyond it. It can't tighten the term for MonP, because MonP is a different unit, and the chain's absolute scale isn't traceable to an outside reference. **`RESULT.md` now carries ±0.7 % for the SR570 gain × V2F scale** (user, 2026-11-13: "Yes, widen it").
- The dark offset matters only at low count rates, or when the dark comes from an earlier gain selection.
- **The real electronics risk isn't a percentage, it's a state error: the unit not doing what EPICS says.** On 2026-11-12 a whole sweep ran on a switched-off SR570 while EPICS accepted every write, and the gain was once changed outside the run. Those are gross errors (100 %, or a factor of 2–4), and no uncertainty budget covers them. Only a cross-check does, such as MonP/MonC ratio continuity.

## 1. What was measured (MonC), with the evidence
| Property | Result | Evidence |
|---|---|---|
| **Linearity, V2F + SR570 output, 0.1–4.5 V (10–450 kHz)** | output-voltage term **≈ +0.006 %/V (+0.005 … +0.008)**, i.e. **≈0.03 % at 4.5 V**. Joint-fit rms residual 0.001–0.006 % without 20 µA/V. Fits that include 20 µA/V give +0.003 %/V, but they are distorted by that range's dark jumping inside a step (finding F9, figure session; checked here) | grids g2–g4; `analysis/monc_grid.py <steplog> g<N> 20u`; figure elec1 |
| Linearity below 10 kHz | ratios 1.001–1.007 at 2–2.5 kHz (0.02 V): up to +0.7 %, i.e. ~14 Hz. That is the size of a dark error, but set 4 ran only 1.5 h after power-on and these points weren't repeated after warm-up (the grids start at 0.1 V). **Not settled** | set 4 ladders |
| **Range-to-range gain** (relative to 5 µA/V, g2–g4 mean) | 500 nA/V +0.08 %, 1 µA/V **+0.24 %**, 2 µA/V −0.12 %, 10 µA/V +0.15 %, 20 µA/V **+0.62 %** (CHAMBER_FACTS F5.6; per-gain factors and u F5.4, F5.5) | `monc_grid.py`; ranges relative to the mean CAL level |
| Repeatability of those factors | ≤ 0.015 % over 8.7 h (g2–g4) for 500 nA/V–10 µA/V; 0.03 % for 20 µA/V. Grid 1, 2.5 h after power-on, differs by up to 0.04 % | grids g1–g4; figure elec2 |
| **Absolute chain scale** (gain × V2F × CAL current) | each range within −0.17 … +0.6 % of the nominal 1e5·I/S, 1 nA/V–20 µA/V (set 3 B, grids) | not traceable: it rests on the SR570's internal current source. Its accuracy spec was not checked here. 8 levels × 6 ranges agree with the nominal V2F scale, so a large common error is unlikely, but not excluded |
| V2F input loading (SR570 50 Ω into V2F R_in) | included in the end-to-end numbers above | the R_in procedure (`procedures/v2f_input_impedance.md`) is not needed for the budget |
| CAL offset levels as a current source | ±0.3 % except **10 nA −1.16 %**, **20 µA −0.45 %**, **2 µA +0.29 %** (0.74 % from largest to smallest of the grid levels) | set 3 A, grids; figure elec3. Matters only if the SR570 CAL offset is used as a reference |
| **Electronics noise at signal** | sd of 1 s counts: **0.003 %** at 25 kHz, **0.0012 %** at 200 kHz. That plain sd includes the settling inside a step; the sd of successive 1 s counts ÷ √2, which leaves it out, is a median 0.53 Hz over all CAL steps (0.0003 % at 200 kHz), rising to ~0.8 Hz above 200 kHz (`unc10_vs_rate`, 2026-11-17). Quote one or the other, never mix them. V2F counts are not Poisson, so **√N error bars are wrong**: √N gives 0.22 % at 200 kHz, ~190× too large for the electronics | grid ladder steps (CAL current source, no beam) |
| Dark (offset off) at the operating gains | 1 µA/V 112, 2 µA/V 95, **5 µA/V 20.0**, 10 µA/V 13.6, 20 µA/V 605 Hz (includes the V2F's own 8.4 Hz zero). **These include +21.5 ± 1.3 Hz (≈0.21 mV) from the cabled chamber, the same at every gain and when blanked:** an output-side offset, probably grounding, not a current. Without the chamber the 5 and 10 µA/V offset-off darks clip | 92 passes; leakage run 2026-11-13 |
| **Chamber leakage current** (chamber cabled, no beam, HV probably on) | **−2.6 ± 12.8 pA, i.e. below ~25 pA in size (2σ)**: zero within the errors. 25 pA is 0.5 Hz at 5 µA/V | `analysis/monc_leak.py`; results § "Leakage run". An earlier "~1 nA" reading of the same day was wrong (struck through in the results) |
| Dark drift overnight | small but not zero: 500 nA/V −0.66 ± 0.16, 1 µA/V −0.35 ± 0.08, **20 µA/V −1.9 ± 0.4 Hz/h**; **−0.03 Hz/h at 5 µA/V** | 92 passes; figure elec4 |
| **Dark scatter per gain selection** | each selection lands on a new dark. Pass-to-pass sd: 1 µA/V 3.8, 2 µA/V 2.5, 5 µA/V 1.0, 10 µA/V 0.6, **20 µA/V 19**, 500 nA/V 7.8 Hz | lag-1 r ≈ 0, so it isn't drift |
| Dark within one selection | 5 µA/V: **0.43 Hz** per reading (92 pairs ~30 s apart, only a blank between; finding F10). 5 and 10 µA/V: in-step max−min ≤ 2 Hz (95th percentile). **20 µA/V jumps by 20–30 Hz inside a step** (593 → 615 Hz at 00:29:21; 95th-percentile max−min 26 Hz; finding F9, seen in the per-count data here) | passes; `analysis/step_counts.py` |
| Interim setting (5 µA/V, CAL +2 nA) | **60.2 ± 0.6 Hz** all night | 91 holds of 8 min |
| Temperature | none resolved. Bounds: interim +5.6 ± 2.5 Hz/°C, 5 µA/V dark +1.7 ± 4.6 Hz/°C. Only 0.1 °C of hutch change overnight | `analysis/monc_passes_temp.py` |
| Settling | < 2 s after a change; **~10 s** to leave the clipped state near zero | sweep-1 re-run H block |
| Warm-up after power-on | darks drift tens of Hz in the first ~1 h; range factors move 0.04 % within ~2.5 h | sweep-1 re-run; grid 1 vs g2–g4 |
| Floors | V2F zero input ≈ **8.4 Hz**; negative SR570 output = **1 count** (clipped) | SR570-off record, 47 min |

## 2. Budget for the absolute number (MonP → photons/s, `RESULT.md`)
*Which of these terms matter for absolute flux, and which for normalising (relative flux at one energy, or across energies), is sorted in `UNCERTAINTY.md`.*

`RESULT.md` and the live calc carry the electronics as SR570 gain × V2F scale (incl. V2F input loading) **±0.7 %** (CHAMBER_FACTS F5.3; before 2026-11-13 it was "SR570 gain ±0.5 %, manual spec"). With μ_en/ρ ±3 %, W ±0.6 %, the live density ±0.2 %, the cross-section fit ±0.9 %, the guarded collection length ±1.4 % and the energy readback ±0.4 % (F9.7, since 2026-11-17), the live total is **±3.58 %**, and the bound factors are ×1.036 / ×0.964 (F9.5, F9.6; `calc/quality_slots.py` SYMMETRIC_TERMS). The electronics are about 4 % of the variance.

| Electronics term | Honest size for MonP | Basis |
|---|---|---|
| SR570 gain × V2F scale, absolute | **±0.7 %** (type B; adopted in `RESULT.md` 2026-11-13) | manual spec. MonC's own ranges reach +0.6 %, and MonP's unit may be similar or worse. The V2F scale (datasheet 1e5 Hz/V) has no separate line in `RESULT.md`, and in MonC's chain it can't be separated from the gain |
| V2F / output non-linearity | ≤ 0.03 % (10–450 kHz) | measured on MonC's V2F channel. MonP's channel is assumed similar |
| Electronics noise | < 0.003 % per 1 s count | MonC |
| Scaler gate and clock | not measured. A crystal time base, expected to be far below the other terms | S1 = 1e7 every count |
| MonP dark (UNCAL offset, not subtracted) | `RESULT.md` first took 50–100 Hz. **MonP read 190–284 cps on 2026-11-12 13:09–13:23** (beam state then not verified), and `RESULT.md` now gives 182–227 Hz (CHAMBER_FACTS F13.1). The live calc subtracts the measured dark, so what remains is that dark's own error | **MonP's UNCAL offset can depend on write order** (finding F1: 1.39 % of the offset on MonC), so measure the dark with beam off after the last change |

**Conclusion:** the electronics add ±0.7 % in quadrature to ±3 % (μ_en/ρ), ±0.2 % (density, live P and T; ±0.8 % with fixed site-mean constants), ±0.9 % (cross-section fit), ±0.6 % (W), ±1.4 % (collection length) and ±0.4 % (energy readback, F9.7). The total is **±3.56 %**, symmetric (F9.5). Since the chamber was measured on 2026-11-13 there is no one-sided collection-length term. Improving the electronics won't change the final number much. Characterising MonP's own unit in the same way would turn ±0.5–0.7 % into a measured factor of ~±0.05 %, but with this method only relative to its CAL source (see 5).

## 3. Budget for MonC as a relative normaliser
Within a fixed gain, MonC's electronics are excellent: noise 0.001–0.003 %, dark drift −0.03 Hz/h at 5 µA/V (≤2 Hz/h at any gain). The terms are gain changes and the dark.

**Gain changes.** If a scan crosses a MonC gain change and the nominal ratio is used, the normaliser steps by the range factor (CHAMBER_FACTS F5.6):
- 5 → 20 µA/V: **+0.62 %**;
- 5 → 1 µA/V: +0.24 %;
- 5 → 10 µA/V: +0.15 %;
- 5 → 2 µA/V: −0.12 %.

With the measured factors (§1) the error is ~0.02 %. Those factors hold for MonC's unit as it is now, and should be re-measured if the unit is changed or repaired.

**Dark.** The error as a fraction of the MonC rate f:

| Dark handling | 1 kHz | 10 kHz | 100 kHz | 1 MHz |
|---|---|---|---|---|
| Not subtracted, interim setting (60.2 Hz) | **6 %** | 0.6 % | 0.06 % | 0.006 % |
| 5 µA/V, dark from the same selection (±0.43 Hz, F10) | 0.04 % | 0.004 % | 0.0004 % | — |
| 5 µA/V, dark from an earlier selection (±1.0 Hz) | 0.1 % | 0.01 % | 0.001 % | — |
| 1 µA/V, dark from an earlier selection (±3.8 Hz) | 0.4 % | 0.04 % | 0.004 % | — |
| 20 µA/V, dark from the same selection (±~15 Hz: it jumps 20–30 Hz inside a step, F9) | 1.5 % | 0.15 % | 0.015 % | 0.0015 % |
| 20 µA/V, dark from an earlier selection (±19 Hz) | 1.9 % | 0.19 % | 0.02 % | 0.002 % |

- At the typical 2×10⁵ cps the dark is negligible however it is handled.
- Below ~10 kHz it isn't, and the old software subtracts nothing.
- Measuring the dark after the last gain change gains a factor of ~2 at 5 µA/V, and more at 1 µA/V and at 500 nA/V and below.
- **At 20 µA/V even a fresh dark is uncertain by ~15 Hz.** That gain is used at high flux, where it is ≤0.015 % above 100 kHz.
- Figure elec5 plots these cases against rate.

## 3a. Write-up uncertainty and live uncertainty (kept separate, user 2026-11-13)
- **Write-up** (`RESULT.md`): one statement for any gain and for MonP's unit. Electronics ±0.7 %, type B.
- **Live beamline calculation:** per gain, from the measured table `data/calibration/monc_sr570_ranges.csv`. The table is regenerated by `analysis/make_monc_calibration.py`, deterministically; its header holds the source's SHA-256.
  - Correction factor per MonC gain, with its repeatability.
  - Dark sd per gain, divided by the live rate.
  - Gains never measured carry u = 0.7 %, as a visible flag.
  - The common CAL-current scale is added only for absolute flux.
  - Draft utilioc slot: `calc/monc_gain_cal.py` (self-test PASS; not installed; three bench checks listed in it).
  - At 5 µA/V the live electronics uncertainty is 0.044 % at 1 kHz and 0.013 % above 10 kHz.

## 4. Errors no budget covers (state, not accuracy)
1. **EPICS shows what was sent, not what the SR570 holds.** The RS-232 link is listen-only.
   - Sweep 1 ran with MonC's SR570 switched off. EPICS accepted every write, and S4 read the V2F's 8.4 Hz zero.
   - After a power cycle the unit restores its own last settings, or defaults if its battery is flat, until `A3init`/`A2init` re-sends them.
2. **Someone else changes the gain** (F8, 2026-11-12 15:04). The number is then wrong by a factor of 2–10 unless the archived setting is used. All A2/A3 settings are now archived as MONITOR.
3. **Command-path states invisible to EPICS** (F1). In UNCAL, the same EPICS state gave offsets 1.39 % apart, depending on the write order. This affects the offset, not the gain. It is harmless if the dark is measured, harmful if a fixed dark is assumed.
4. **Dark/light classification at 400 cps fails at some gains.** The offset-off dark is 539 Hz at 200 nA/V and 605 Hz at 20 µA/V, and the blanked readings reach 3.5 kHz.
5. **Above 4.5 V output (450 kHz) nothing was measured.** The operating rule (lower the gain above 400 kHz) keeps the chain inside the measured region.

The defence against 1–3 is a cross-check, not a tighter tolerance. Across any gain change or restart, MonP/MonC (or MonP/DBPM with the beam aligned) must stay continuous (`normalization_proposal.md` (a)).

## 5. What is not known
- **Where the chamber's +21.5 Hz offset comes from.** It is gain-independent and survives blanking, so it enters after the input stage, probably a ground or shield offset through the BNC (chamber body, HV return). Not tested.
  - The dark columns of `data/calibration/monc_sr570_ranges.csv` describe MonC with its chamber cabled; without it, each is ~21 Hz lower.
  - It cancels in any dark subtraction made in the same state, and is negligible at normal rates.
  - With HV off, or with a capped cable instead of the open end, it might differ. The user chose to leave the cable as it is.
- **MonP's electronics.** Its SR570, V2F channel, dark and range factors are unmeasured. Everything above is transferred from MonC by assumption, and MonC's data already show that the two units differ (at MonP's UNCAL setting MonC's unit would clip, yet MonP reads ~200 cps without beam, if that reading was beam-off).
- The absolute accuracy of the SR570's CAL offset current, which all of §1's "absolute" figures depend on. A traceable current source, or the pixel-detector + foil calibration, would settle the whole chain at once.
- Temperature dependence beyond the 0.1 °C seen overnight.
- Gains outside 500 nA/V–20 µA/V in the grids (only darks at 200 nA/V; set 3 covered 1–500 nA/V at 0.02–0.2 % once).
- The ~1 Hz, minute-scale wander of the 5 µA/V dark and blanked readings. It sits in the later stages or the V2F, and the hutch sensors don't explain it. It is negligible above 10 kHz.

## 6. Recommendations (each needs the user's decision)
1. ~~Keep `RESULT.md`'s electronics term at ±0.5 %, or widen it to ±0.7 %.~~ **Done 2026-11-13: widened to ±0.7 %, with the V2F scale and loading included** (user: "Yes, widen it").
   - This is a type-B bound, and no coverage check is possible without an absolute reference.
   - Treated as 1σ it is conservative if MonP's unit is like MonC's (worst range +0.6 %). It is optimistic if MonP's unit is worse.
2. If MonP's accuracy matters below the ±3 % level, run one grid on MonP's SR570 in a maintenance window. It is 10 min, like `make_night_plan.py`'s grid, and it writes MonP, so it needs the user's explicit OK.
3. Use the measured MonC range factors when splicing across MonC gain changes. Re-measure them after any SR570 swap or repair.
4. Measure the dark after the last gain change, or use a stable offset (the interim CAL +2 nA) and measure it once per selection.
5. Run `A3init`/`A2init` after any SR570 power cycle, with the user's OK. Make MonP/MonC continuity a health-check item.

## Figures
These are made by the figure session. They are on main since 2026-11-13 (merge 929a5bb of `claude/figures-c4aacd` at 3e20aac; user: "merge the figures elec1-5"). Files: `analysis/figures/out/`; regenerate with `make_figures.py --only electronics`; code `analysis/figures/fig_electronics.py`.
- `elec1_linearity.png`: joint-fit residuals against output voltage, with and without 20 µA/V;
- `elec2_range_scale.png`: range factors, grids 1–4;
- `elec3_cal_levels.png`: CAL level factors, grids 1–4;
- `elec4_dark_scatter.png`: overnight darks per range, within-step against pass-to-pass scatter;
- `elec5_dark_error.png`: dark error as a fraction of the rate, for the cases in §3.

Each figure says it is MonC only. The figure session's review file `data/sweeps/review_by_figure_man.md` has findings F9 and F10, which corrected §1 and §3 of this file on 2026-11-13. Both were checked here: the per-count data, and a refit without 20 µA/V giving a V term of +0.005 … +0.007 %/V.
