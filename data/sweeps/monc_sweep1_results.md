# MonC SR570 sweep 1: results (2026-11-12)

> Summary and uncertainty assessment of everything below: `ELECTRONICS_CONCLUSIONS.md` (repo root, 2026-11-13).

The user approved the sweep 2026-11-12 ("Yes, run it"), with these conditions:
- after the sweep, the 1 Hz logger keeps running;
- MonC sees no stray beam;
- at the user's request ("change to offset takes less than 2 seconds… 5 seconds of counting is enough"), the run was split: steps after V6 use 2 s settle + 5 s count.

Only six `15IDC:A3` fields were written. MonP (`15IDC:A2`) was not written.

## Files
- Plans: `monc_sweep1_plan.csv` (B0–V6 as run), `monc_sweep1b_plan.csv` (V7–R).
- Step means: `monc_sweep_steps_20261112_130916.csv` (B0–V6, 60 s counts) and `monc_sweep_steps_20261112_131942.csv` (V7–R, 5–6 counts).
- The 1 s record of every count and setting change is outside git: `xray_fluxor-data/ca_logger/20261112_130858_monc_sweep1_then_dark.csv`. It keeps running for dark drift.

## Result: S4 (MonC) does not respond to any SR570 setting
| Block | Settings | Expected (nominal) | S4 mean, counts per 1 s count |
|---|---|---|---|
| B0 baseline | 50 nA/V, 20 nA +, UNCAL, u=+6 | 240 Hz or 0 | 8.41 (n=111) |
| V vernier | u = 0, +25, +50, +100, −25, −50, −100 | up to 4 kHz for one sign | 8.41, 8.46, 8.57, 8.53, 8.46, 8.41, 8.0 |
| S sign | −/+50, −/−50, +/+50 | 2 kHz or 0 | 8.17, 8.33, 8.17 |
| L level | 10, 5, 50, 20 nA | 1–5 kHz | 8.4, 8.33, 8.5, 8.5 |
| G gain, offset ≈1 nA | 1, 5, 20, 100, 200, 500, 50 nA/V | 100 kHz … 200 Hz | 8.5, 8.6, 8.5, 8.2, 8.17, 8.17, 8.17 |
| Z offset off | 50, 500, 20, 5, 1, 50 nA/V | dark × 1/S | 8.17, 8.0, 8.17, 8.2, 8.5, 8.33 |
| C CAL 1 nA | +, then − | 2 kHz or 0 | 8.4, 8.33 |
| R restore | baseline | = B0 | 8.24 (n=29) |

- Over the whole run (882 counts in the logger), S4 was only ever 8 or 9 (531 × 8, 351 × 9). The spread is ±1-count quantization of a constant ~8.4 Hz.
- At G1 the gain went ×50 (to 1 nA/V) with ~1 nA offset on, which should have read ~100 kHz; it read 8.5.
- The IOC processed every write: each change appears in the logger with a fresh IOC timestamp, and readbacks matched. So the EPICS side changed, but nothing downstream of it did.
- Over the same period MonP's S3 (read-only) varied 190–284, so scaler1 itself is counting.

## What this means
S4's ~8.4 Hz does not come from the MonC SR570 as EPICS sees it. One of these is true (to check by hand):
1. The commands don't reach the SR570: RS-232 cable, port or baud, or the unit's remote setting. The SR570 is listen-only, so EPICS can't tell.
2. The SR570 output isn't reaching the V2F → scaler1 channel 4 (unplugged, or a different patch).
3. The SR570 or its V2F is powered off; ~8 Hz would then be the V2F's zero-input rate.

In every case the dark-drift study can't use MonC until this is resolved. The V2F input-impedance test (via the SR570 offset as a source) is blocked too.

Also seen: after `offset_cal` or `offset_sign` writes, `off_u_put` got extra updates (−50, +50) before the final 6. The IOC database seems to rewrite the vernier when the sign or mode changes. The restored value is 6, as checked by readback.

## Remote diagnosis (2026-11-12, read-only)
The user confirmed in Phoebus that offset on/off, CAL/UNCAL and other changes give no response: "So it does appear that we have a communication issue." The user also reports that MonC was recently powered off.

IOC side, all healthy:
- MonC records write through asyn port `serial3`. The asyn record `15IDC:asyn_3` is Connect, Enable, autoConnect, NO_ALARM, 9600 8N2, no flow control. This matches the manual's "Listen only, 9600 Baud DCE, 8 bit, no parity, 2 stop bits".
- MonP uses `serial2` (`15IDC:asyn_2`) with identical settings.
- Last commands sent decode correctly: `A3sens_put` 14 = SENS14 = 50 nA/V; `A3offset_put` 13 = IOLV13 = 20 nA. `IOON` and `IOUC` go through `A3offset_on_put` / `A3offset_cal_put`. No write errors.
- `A3init` / `A3init1` (the seq that re-sends all settings) are INVALID/UDF: they have never run since IOC boot. Same for `A2init`.
- Output terminator `OEOS=\r`, but the manual says "Commands must end with a carriage return and linefeed <CR><LF>". MonP's port is the same, so this is a weak suspect, unless MonP has never been commanded remotely either.

Downstream:
- S4 has been 8 or 9 every count since 13:08:58 (1214 counts to 13:29). That is ≈80 µV equivalent at 1e5 Hz/V, consistent with a V2F at zero input.
- Manual, POWER-UP: "the unit will return the settings that were in effect when the power was last turned off. If an error is detected or if the backup battery is exhausted, the default settings will be used" (1 µA/V calibrated, offset +1 pA cal off, bias off). At 1 µA/V a pA-level dark gives µV, so it would also read as zero.
- So the remote data can't separate:
  - (a) SR570 off (line power or internal batteries dead);
  - (b) on, but serial commands not arriving (cable or port mapping);
  - (c) output not reaching the V2F.
  
  It can rule out a fault in the IOC configuration.

## Checklist for the next hutch visit
1. SR570 display lit? Which sensitivity/offset does it show (expect 50 nA/V, 20 nA UNCAL + if commands arrive)? Is the line cord in?
2. While someone watches the display, change `A3sens_num` in Phoebus: does the display follow? If not, check the RS-232 cable from the SR570 to the port behind `serial3`.
3. SR570 OUTPUT BNC → V2F input → V2F output → scaler1 channel 4.
4. Once it responds, re-send all settings (`A3init`, needs the user's OK), because the unit will have its own or default settings, not EPICS's.

## MonC SR570 switched on (2026-11-12, user in hutch)
The user: "I went in and basically turned [MonC's] SR570 'on'" (corrected from "monp" to "monc"; "monc wasn't really live, it should be now").

Logger timeline (IOC timestamps, CST):
- 13:26:13–13:26:56: A3 changes from Phoebus (the user's tests: vernier, on/off, CAL, sign, units, gain). These were made before power-on, so the unit didn't receive them. EPICS was left at 50 nA/V, 50 nA, sign −, UNCAL, vernier −4.
- 13:29:56: S4 = 5945, then 1, then 18 at 13:30:04. That is the SR570 power-on transient. Since then S4 has been rising: 27–36 (13:31), 34–46 (13:33), 49 (13:36). This is warm-up, or the unit's own stored settings; it is not yet the EPICS state.
- MonP (read-only, not touched): S3 ≈3.5–5 k from 13:24:26 to 13:29:06, back to ≈180, then ramping to 75 k by 13:36. That looks like beam in the C station, from other activity. MonC doesn't follow it, so MonC is not seeing beam.

Sweep 1 (13:09–13:23) therefore ran with the MonC SR570 switched off. Its S4 ≈8.4 Hz is the V2F reading with the SR570 off.

# Sweep 2 (unit live), 2026-11-12 13:37–13:41
- Approved by the user: "Yes, run it", for: A3init to push all EPICS settings, restore the baseline, re-run the sweep with 2 s settle + 5 s counts.
- `A3init` processed at 13:37:15 (NO_ALARM). Plan `monc_sweep2_plan.csv`. Step means in `monc_sweep_steps_20261112_133745.csv`. The 1 s record is in the logger file above.
- Baseline restored and read back. The logger keeps running.

S4 means (counts per 1 s count; quantization ±1; 5–6 counts per step except R0/B0/R):

| Step | Setting | S4 |
|---|---|---|
| R0 / B0 / R | baseline: 50 nA/V, 20 nA, +, UNCAL, u=+6 | 14.9 / 14.1 / 15.7 |
| V1 | u = 0 | 1.0 (clipped) |
| V2 / V3 / V4 | u = +25 / +50 / +100 | 766.0 / 1789.0 / 3806.7 |
| V5 / V6 / V7 | u = −25 / −50 / −100 | 1.0 / 1.0 / 1.0 (clipped) |
| S1 / S2 / S3 | sign −, u=+50 / sign −, u=−50 / sign +, u=+50 | 1763.0 / 1.0 / 1789.0 |
| L1 / L2 / L3 / L4 | level 10 / 5 / 50 / 20 nA (u=+50) | 1788.8 / 255.0 / 1789.3 / 1789.8 |
| G1…G7 | 1 / 5 / 20 / 100 / 200 / 500 / 50 nA/V (u=+50, 20 nA) | 82282.5 / 19680.2 / 4390.7 / 900.2 / 705.6 / 289.5 / 1789.8 |
| Z1…Z6 | offset OFF: 50 / 500 / 20 / 5 / 1 / 50 nA/V | 54.5 / 117.0 / 58.6 / 55.3 / 475.0 / 54.3 |
| Z7 | offset ON, 1 nA level, UNCAL u=+50 | 255.2 |
| C1 / C2 | CAL 1 nA, sign + / sign − | 2056.0 / 1.0 (clipped) |

First reading (to be checked properly, e.g. with fits and figures):
- **The CAL offset is accurate.** 1 nA at 50 nA/V → 2056 Hz. Nominal 20 mV → 2000 Hz, plus the offset-OFF dark of 54.5 Hz, makes 2054.5: agreement to ~0.1 %. In CAL mode the IOC label "+" gives positive output and "−" clips. So the IOC's "+" label is right in its effect, whatever IOSN index it sends.
- **The UNCAL vernier is linear, but only one sign counts.** V2–V4: 40.5 Hz per unit (fit over three points). The line crosses zero at u ≈ +6. The baseline u=+6 sits only ~15 Hz above the clip: **at baseline, MonC's dark is barely above the unipolar V2F's floor, so any downward drift would be hidden by clipping.** This is a trap for the dark-drift study.
- **In UNCAL the sign setting is ignored** (S1 ≈ S3, S2 clipped): the vernier's own sign decides. *(Corrected 2026-11-12, see set 3 section E: the IOC maps a sign write onto the vernier's sign and back, so the S steps did not hold sign − at all. The small S1/S3 difference is a command-path effect.)*
- **The UNCAL scale depends on the level's range group, not the level.** 10, 20 and 50 nA all give 1789 Hz; 1 and 5 nA both give 255 Hz.
- **Offset ON at u=0 is not the same as offset OFF.** u=0 clips, while OFF gives +54.5 Hz. The UNCAL generator at 0 adds ≈ −(240+55) Hz-equivalent at 50 nA/V.
- **The offset-OFF dark is not a pure input current.** It is flat at ~55 Hz for 5–50 nA/V, 117 Hz at 500 nA/V and 475 Hz at 1 nA/V. These are range-dependent output offsets, not a single current over S.
- **The gain series is not a clean 1/S law.** G5 (200 nA/V) = 705.6 against ~450 expected. Range-dependent offsets again.
- **Warm-up drift:** baseline 14.9 → 14.1 → 15.7 Hz over ~4 min, ~1 h after power-on. S4 rose 18 → 53 Hz in the first ~7 min after power-on (13:30–13:37) before A3init changed the settings.

# Experiment set 3 (2026-11-12 13:49–13:58)
- On the user's authority: "propose a new set of experiments on monc and execute them". PLAN.md has the row.
- Plan `monc_set3_plan.csv` (68 steps, 2 s settle + 5 s counts). Step log `monc_sweep_steps_20261112_134949.csv`.
- Analysis: `python -I analysis/monc_set3.py data/sweeps/monc_sweep_steps_20261112_134949.csv`.
- Per-count view: `analysis/step_counts.py`.
- Baseline restored and read back. Baseline repeats F0/F1/F2/R: 15.5 / 16.6 / 15.6 / 16.4 Hz.

## A. CAL offset linearity at 50 nA/V (sign +; offset-off dark 54.0 / 56.0 Hz before / after, mean 55.0)
| CAL level | f − dark (Hz) | nominal 1e5·I/S | ratio |
|---|---|---|---|
| 1 nA | 2001.0 | 2000 | 1.0005 |
| 2 nA | 4007.6 | 4000 | 1.0019 |
| 5 nA | 10006.0 | 10000 | 1.0006 |
| **10 nA** | **19768.6** | 20000 | **0.9884** |
| 20 nA | 40118.5 | 40000 | 1.0030 |
| 50 nA | 100145.3 | 100000 | 1.0015 |

- The offset × gain × V2F chain is good to ±0.3 % at every level except **10 nA, which reads 1.16 % low**.
- The same deficit shows at 50 nA/V in block B (19822.8 Hz at 10 nA): it belongs to that offset level.
- The V2F is linear to 100 kHz within these errors.

## B. Per range: offset-off dark, and CAL points at ~0.2 V and ~1 V
| S (nA/V) | dark, offset off (Hz) | (f_hi − dark)/nominal at ~1 V |
|---|---|---|
| 1 | 464.6 | 0.9998 |
| 2 | clipped (≤1) | ≈0.9994 (dark unknown) |
| 5 | clipped | ≈1.0014 (dark unknown) |
| 10 | 9.5 (true ≈12, slow recovery from clip, see per-count) | 1.0015 |
| 20 | 59.0 | 1.0017 |
| 50 | 54.8 | 1.0015 |
| 100 | 31.2 | 1.0018 |
| 200 | 359.5 | 1.0010 |
| 500 | 151.6 | 1.0007 |

- Gain × offset accuracy is 0.02–0.2 % on every range: well inside the SR570's ±0.5 % spec.
- **The offset-off dark is an output-referred offset that depends on the range: −?…+4.6 mV, with both signs.** It is not an input current; a current would scale as 1/S, giving 465, 232, 93, … Hz from the 1 nA/V value. All are within the spec's 10 mV term (= 1 kHz).
- Two-point intercepts are unreliable where the lo or hi level is 10 nA (e.g. S = 50 nA/V), because of the A finding.

## C. UNCAL vernier transfer (50 nA/V, 20 nA level)
- Linear fit over u = 8–200 (8 points): **40.38 Hz/unit = 20.19 pA/unit**, intercept −229.3 Hz, zero crossing at **u = +5.68**. Residuals ≤ 11 Hz.
- Linear to full scale: u = 500 → ratio 1.0000, u = 1000 → 1.0007. So the vernier full scale for this level group is ±20.2 nA.
- **UNCAL at u = 0 is −284 Hz relative to offset OFF** (−229 vs +55). That is −2.8 mV, i.e. −142 pA input-equivalent: the UNCAL generator's zero error.
- **The near-clip behaviour depends on history.** u = 6 gave 1 Hz when stepped up from u = 4, against 15–17 Hz at the same settings reached from above (F steps). u = 8 recovered from 29 to 98 Hz over ~1.5 s.

## D. UNCAL scale per level group (50 nA/V)
| Level | u=50 (Hz) | u=100 (Hz) | slope |
|---|---|---|---|
| 2 nA (with 1, 5 nA from sweep 2) | 256.2 | 1062.0 | 16.1 Hz/unit = 8.06 pA/unit |
| 20 nA (10, 50 the same) | 1765.2 | 3782.8 | 40.35 Hz/unit = 20.18 pA/unit |
| 100 / 200 nA | 19713.2 / 19712.8 | 39747.7 (200) | 400.7 Hz/unit = 200.4 pA/unit |
| 500 nA | 9554.8 | – | (a different group) |

- The UNCAL full scale is set by a level group, not by the level itself, and the groups are not simply decades.
- The zero error differs by group (intercepts ≈ −550 Hz for the 1–5 nA group, −229 for 10–50, −322 for 100–200).
- **Implication for MonP** (same kind of setting: UNCAL, 200 nA, u = −6, 500 nA/V): on a unit like MonC's this would be a negative offset, clipping. MonP reads ~200 cps dark, so MonP's unit or chamber behaves differently. Don't reason about MonP's offset from MonC's numbers.

## E. UNCAL sign, A/B/A/B at u = +100, 20 nA
- Readings: 3756.7 ("−" sequence), 3809.0 ("+"), 3755.3 ("−"), 3808.6 ("+"). The "−" sequence reads 1.39 % lower, reproducibly.
- **Corrected 2026-11-12, finding F1 by the figure session (`review_by_figure_man.md`):** the original text said "Sign − is 1.39 % lower… the sign bit… change[s] the scale". That was wrong. In UNCAL **the IOC couples `offset_sign` and `off_u_put`**:
  - writing sign − made the IOC set u = −100 (13:58:07);
  - the runner's next write u = +100 flipped the sign back to + (13:58:08).
  
  So every E counting window had the **same EPICS state (sign +, u = +100)**, and the 1.39 % is a **path dependence**: the hardware state left by the command sequence (sign − … u +100) differs from the "+" sequence's, and EPICS can't show it.
- The runner's per-write readback missed this, because it checks each field right after writing it, not at the end of the step. Fixed: the runner now re-reads every written field at the end of each step and flags any change.
- The same applies to sweep 2's S block (S1 = 1763 vs S3 = 1789).

# Sweep-1 re-run: offset-off dark per range, and near-clip recovery (2026-11-12 14:01–14:07)
- The user asked to "re-run the useful portions of your first sweep". Plan `monc_sweep1_rerun_plan.csv`, step log `monc_sweep_steps_20261112_140106.csv`. Baseline restored and read back.
- Only the Z (dark) block was re-run, because set 3 superseded the rest (vernier → C, sign → E, level → D, gain → B, CAL → A). The near-clip test (H) was added because of the set 3 C6 anomaly.

## Offset-off dark (Hz) by range, in order of measurement (unit powered on 13:29:56)
| S (nA/V) | sweep 2 (13:40) | set 3 (13:53) | re-run up (14:02) | re-run down (14:04) |
|---|---|---|---|---|
| 1 | 475.0 | 464.6 | 453.9 | 447.6 |
| 2 | – | clip | clip | clip |
| 5 | 55.3 | clip | clip | ≈4–5 (recovering) |
| 10 | – | ≈12 (recovering) | clip | ≈5–6 (recovering) |
| 20 | 58.6 | 59.0 | 56.5 | 57.0 |
| 50 | 54.5 / 54.3 | 54.8 (55.0 in A) | 55.2 / 53.5 | 53.9 |
| 100 | – | 31.2 | 30.9 | 30.6 |
| 200 | – | 359.5 | 433.7 | 412.6 |
| 500 | 117.0 | 151.6 | 176.6 (180→171 within the step) | – |

- **20, 50 and 100 nA/V are stable to about ±2 Hz over 25 min.**
- **1, 200 and 500 nA/V drift by tens of Hz** over the same time. This is likely warm-up after the 13:29:56 power-on; it needs a longer record.
- 2 nA/V is negative (clipped); 5 and 10 nA/V are only a few Hz positive. These read slowly (see below) and depend on the previous state.
- The 1 nA/V dark falls ~2 Hz/min (475 → 448 over 25 min). If it were an input current, that would be 4.5 pA drifting −0.02 pA/min. Other ranges don't scale with it, so it is output-referred.

## Near-clip recovery (per-count data, `analysis/step_counts.py`)
- **Recovery after a clipped (negative-output) state takes ~10 s near zero.** u = +6 approached from below (u = 0 or −10) gives 1, 1, 1 … for 9–10 s, then 16–17 Hz (H3, H7, twice).
- From above (u = 20 → 6) it reads 16.7 Hz at once (H1, H5).
- Large outputs recover in 1–2 s (e.g. 29 → 98 Hz at u = 8 in set 3).
- So the C6 = 1 Hz in set 3 and the 5 and 10 nA/V dark readings were recovery artefacts, not a second stable state.
- **Rule: after anything that drove MonC negative, discard ≥ 12 s before reading a near-zero level.**
- The cause (SR570 output stage, or V2F integrator recovery) can't be told apart from here.

## Baseline (50 nA/V, 20 nA, UNCAL, u = +6)
- 14.1–15.7 Hz (13:38–13:41), 15.5–16.6 (13:50–13:58), 16.3–17.4 (14:01–14:07).
- It is rising ~+0.1 Hz/min, about 1 h after power-on, and stays only ~17 Hz above the clip.

# Sets 4 and 5: MonC operating points (2026-11-12 15:05–15:20)
- The user: "gather more data around our operating points" and "cover 1-20uA/V range". MonC's standard gain is 5 µA/V (spec files: 6,711 scans; `spec master` handoff 2026-11-12-monitors). MonP's gain ≤ MonC's, with flux within ~4× (user).
- Plans `monc_set4_plan.csv` and `monc_set5_plan.csv`; step logs `monc_sweep_steps_20261112_150515.csv` (set 4) and `…_151415.csv` (set 5); analysis `python -I analysis/monc_ladders.py <set4> <set5>`. Baseline restored and read back after each set.

## Offset-off dark by range (Hz)
| Range | dark | notes |
|---|---|---|
| 200 nA/V | 522–545 | drifts within a step (sd 9) |
| 500 nA/V | 216–222 | |
| 1 µA/V | 113–120 | |
| 2 µA/V | 88–92 | |
| **5 µA/V** | **16.3–19.3** | 7 readings over 15 min, rising ~3 Hz then steady ~18 |
| 10 µA/V | 12.5–13.0 | |
| 20 µA/V | 578–606 | |

- At 5 µA/V the old UNCAL setting (20 nA, u = +6) gives 18.5 Hz and u = 0 gives 16.0 Hz. **The UNCAL offset is negligible at the standard gain**, as expected: ~20 pA/unit is 0.4 Hz/unit at 5 µA/V.
- ~~Anomaly: set 4's first step (50 nA/V…) read 630 Hz… another command-path state invisible to EPICS.~~ **Corrected 2026-11-12, finding F8 by the figure session:** there was no anomaly.
  - The logger shows MonC was set outside my runs (by the user, presumably via Phoebus): offset OFF at 15:01:29, then 20 µA/V at 15:04:49–51.
  - Set 4's P0 (15:05:15) didn't write the gain, so it read **20 µA/V offset-off dark ≈ 630 Hz**. That is consistent with the 578–606 Hz measured at 20 µA/V later.
  - Lesson: a plan's first step must write the gain and every setting it assumes. Plans from set 6 on start with a full state write.

## Ladders: (f − dark) / nominal, output 0.02–4 V (2–400 kHz)
| Range | ratios (output V) |
|---|---|
| 1 µA/V | 1.0071 (0.02), 1.0038 (0.2), 1.0022 (0.5), 1.0021 (1), 1.0052 (2) |
| 2 µA/V | 1.0007 (0.025), 0.9986 (0.25), 0.9986 (0.5), 1.0016 (1), 0.9997 (2.5) |
| 5 µA/V | 1.0011 (0.02), 0.9997 (0.2), 1.0028 (0.4), 1.0009 (1), 0.9995 (2), **0.9953 (4)** |
| 10 µA/V | 1.0031 (0.02), 1.0042 (0.2), 1.0023 (0.5), 1.0009 (1), 0.9968 (2) |
| 20 µA/V | 1.0053 (0.025), 1.0072 (0.25), 1.0057 (0.5), 1.0015 (1), 1.0051 (2.5) |

- **1–20 µA/V, 0.2–4 V: every point within 0.995–1.007.** That matches the SR570's ±0.5 % gain spec plus CAL-level errors of a few tenths of a percent (cf. the 10 nA level at −1.2 %).
- Range gain and level error are mixed in each point. The overlaps (e.g. the 2 µA level on 1, 2, 5 and 10 µA/V) would allow a joint fit separating them, but only relative to one overall scale. Open item.
- The 4 V point (398 kHz) reads −0.47 %, the only clear high-output deficit. It may be the V2F near 40 % of full scale, or the 20 µA level, which is also low at 10 µA/V (0.9968): unresolved.

## Interim configuration (set 15:20:44)
- The user: "set MonC to 5uA/V and set the offset such that counts are less than 120 Hz". The old software runs MonC with no background subtraction.
- Set: 5 µA/V, CAL +2 nA, ON (`tools/monc_hold.py interim_5uA_cal2nA`).
- Measured: **58.8 Hz** (20 counts 58–60). That is the ~18 Hz dark plus a calibrated 40 Hz, leaving ~60 Hz margin to the 120 Hz limit and ~59 Hz to the clip.
- The +40 Hz is 0.02 % of a typical 2×10⁵ cps MonC rate.

# V2F zero-input rate and the two "floors" (2026-11-12; prompted by the user: "the V2F's floor is ~8 Hz, right? We have lots of data on that from our failed sweep")
Source: the MonC SR570 was switched OFF until 13:29:56. Its output then carries no amplifier signal, so S4 is the V2F's own zero-input rate.
- Logger, 13:08:57–13:29:54 (21.0 min): 1,258 one-second counts, {8: 749, 9: 509}. **Mean 8.405 Hz, sem 0.014.** Drift −0.005 Hz/min; thirds 8.47 / 8.35 / 8.40. (`python -I analysis/v2f_zero.py <logger.csv>`)
- Archiver 5 s record, 12:42:33–13:08:57: 317 samples, {8: 172, 9: 145}, mean 8.457 Hz.
- **V2F zero-input rate on MonC's channel ≈ 8.4 Hz** (≈ 84 µV equivalent input at 1e5 Hz/V), steady over 47 min.
- Caveat: an unpowered SR570's output is not guaranteed to be exactly 0 V, so this is the zero with the SR570 off.

**Two different floors. My earlier text conflated them:**
1. **Zero SR570 output → ≈ 8.4 Hz** (the V2F zero offset).
2. **Negative SR570 output → exactly 1 count per 1 s gate** (every clipped step, sd 0). Below about −84 µV the V2F stops; the 1 count is a gate or V2F artefact.

Consequences:
- ~~**Every "dark" in this document is V2F zero (≈8.4 Hz) + SR570 output offset.**~~ **Corrected 2026-11-13 by the leakage run:** with the chamber cabled, every dark also includes the +21.5 Hz chamber-connection offset (CHAMBER_FACTS F6.2). The SR570's own share is then (f − 8.4 − 21.5 Hz)/1e5 Hz/V. The examples below are as first computed, without that term. Examples, offset off:
  - 5 µA/V: 18 Hz → ~9.6 Hz ≈ 96 µV;
  - 10 µA/V: 13 Hz → ~4.6 Hz ≈ 46 µV;
  - 50 nA/V: 54 Hz → ~46 Hz ≈ 0.46 mV.
- "Margin to the clip" means the distance to the 1-count floor: (f − 1 Hz), not (f − 8.4 Hz).
- ~~The interim setting (5 µA/V, CAL +2 nA, 58.8 Hz) is 8.4 Hz V2F zero + ~10 Hz SR570 + 40 Hz offset.~~ **Corrected 2026-11-13:** cabled, it is 8.4 Hz V2F zero + 21.5 Hz chamber connection + 40 Hz CAL offset + about −10 Hz SR570 output offset. Detached, it reads 38.5 Hz (CHAMBER_FACTS F6.2, F7.3, F7.4). That is ~50 Hz above the V2F zero and ~58 Hz above the 1-count floor.
- The vernier fit (set 3 C: f = 40.38·u − 229.3) reaches the V2F zero (8.4 Hz) at u = 5.89, consistent with u = 6 reading 15–17 Hz.

# Overnight program (under the user's 17 h grant), started 2026-11-12 15:40:45
- Plan `monc_night_plan.csv` (`analysis/make_night_plan.py`). The runner has `--deadline=2026-11-13T08:15 --restore=interim_5uA_cal2nA` and runs detached (launcher PID 34260). Output goes to `xray_fluxor-data/sweeps/night_20261112.out`; step log `…/monc_sweep_steps_20261112_154045.csv`.
- A grid every 24 passes (≈4 h). A dark pass every ~10 min, with the interim setting held in between.

## Grid 1 (15:41–15:51): `python -I analysis/monc_grid.py <steplog> g1`
Darks and blanked readings (Hz):

| Range | dark | blanked | dark − blanked (input stage) | blanked − 8.4 (later stages) |
|---|---|---|---|---|
| 500 nA/V | 217.4 | 1336.8 | −1119 | +1328 |
| 1 µA/V | 116.9 | 674.2 | −557 | +666 |
| 2 µA/V | 94.1 | 473.6 | −380 | +465 |
| 5 µA/V | 19.4 | 171.9 | −153 | +164 |
| 10 µA/V | 13.2 | 89.9 | −77 | +82 |
| 20 µA/V | 613.7 | 3458.0 | −2844 | +3450 |

- **Blanking (BLNK: "grounds the amplifier signal path after the front end") raises the reading 5–9×.** The later stages carry a large positive output offset; the input stage cancels most of it with a negative one.
- **The small operating dark (≈11 Hz SR570 share at 5 µA/V) is the difference of two ≈160 Hz terms**, so its drift may be larger than its size suggests. The overnight passes track both.

Joint fit of 29 ladder points: ln(ratio) = range + level + c·V_out. **rms residual 0.013 %**, so the model is adequate.
- **V2F / output-voltage term: +0.014 % per volt** (grid 1 only; grids 2–4 give +0.003 to +0.004 %/V, see "Overnight results" below). The V2F is linear to 400 kHz within ~0.06 %. **The 4 V deficit seen in set 4 is the 20 µA CAL level, not the V2F.**
- CAL levels relative to their mean: 200 nA 1.0021, 500 nA 1.0003, 1 µA 1.0002, 2 µA 1.0032, 5 µA 1.0011, 10 µA 0.9995, **20 µA 0.9952**, 50 µA 0.9984.
- Range scale (gain × mean level × V2F): 500 nA/V 1.0002, 1 µA/V 1.0018, 2 µA/V 0.9983, **5 µA/V 0.9996**, 10 µA/V 1.0011, **20 µA/V 1.0064**.
- Gain and mean level remain degenerate in absolute terms: only their product is fixed, so ranges are relative to the mean CAL level. Grids 2–5 test repeatability.

# Overnight results (2026-11-12 15:40 to 2026-11-13 ~08:10)
- The run stopped before `p92_hold`, which would have run past the 08:15 deadline. It printed `restored:` and exited 0.
  - 92 dark passes and 4 grids ran; grid 5 was due after pass 96. No step ended in a state other than the one written (step-log column `changed` empty in all 1,224 steps).
- Readback at 08:10, after the run: 5 µA/V, CAL, nA 2, +, ON, blank OFF. S4 was 58–59 Hz over 15 counts, mean 58.6.
- Step log: `xray_fluxor-data/sweeps/monc_sweep_steps_20261112_154045.csv`. Per-pass table: `data/sweeps/monc_night_passes_20261112.csv`.

## Grids 1–4 (15:41, 20:00, 00:20, 04:40): `python -I analysis/monc_grid.py <steplog> g<N>`
| | g1 | g2 | g3 | g4 |
|---|---|---|---|---|
| rms residual | 0.013 % | 0.005 % | 0.005 % | 0.007 % |
| output-voltage term | +0.014 %/V | +0.004 %/V | +0.003 %/V | +0.003 %/V |
| range 500 nA/V | 1.00017 | 1.00057 | 1.00060 | 1.00064 |
| range 1 µA/V | 1.00182 | 1.00215 | 1.00220 | 1.00215 |
| range 2 µA/V | 0.99828 | 0.99853 | 0.99859 | 0.99867 |
| range 5 µA/V | 0.99957 | 0.99975 | 0.99975 | 0.99979 |
| range 10 µA/V | 1.00114 | 1.00124 | 1.00124 | 1.00124 |
| range 20 µA/V | 1.00639 | 1.00608 | 1.00594 | 1.00594 |

- **Grids 2–4 repeat to ≤0.015 % in every range scale and ≤0.025 % in every CAL level, over 8.7 h.**
- Grid 1 differs by up to 0.04 %, and its fit is 2–3× worse. It ran ~2.5 h after the unit was powered on, so this is probably warm-up (not tested).
- ~~**The V2F term is +0.003 %/V, not grid 1's +0.014 %/V.** Over 0–4.5 V the V2F is linear to ~0.015 %.~~ **Corrected 2026-11-13, finding F9 by the figure session:**
  - the 20 µA/V dark jumps by 20–30 Hz inside a step (per-count: g3_20u_d 593 → 615 Hz at +9 s; g4_20u_off 616 → 584 Hz), and its points pull the fit;
  - without 20 µA/V (`monc_grid.py <steplog> g<N> 20u`), g2/g3/g4 give rms 0.001/0.002/0.006 % and **V term +0.006/+0.007/+0.005 %/V**, i.e. **≈0.03 % at 4.5 V**;
  - the range factors barely change (≤0.015 %).
- CAL levels relative to their mean, g2–g4: 200 nA 1.0017, 500 nA 1.0000, 1 µA 0.9999, **2 µA 1.0030**, 5 µA 1.0010, 10 µA 0.9997, **20 µA 0.9955**, 50 µA 0.9991.
- Blanked readings across the four grids, in Hz:
  - 500 nA/V 1337–1340, 1 µA/V 674.1–674.2, 10 µA/V 89.9–90.6, 20 µA/V 3458–3465: within 0.8 %;
  - 5 µA/V 171.9–173.4: 0.9 %;
  - 2 µA/V 473.6 → 479.1: +1.2 %, rising each grid.

## Dark passes (92, every ~10.7 min): `python -I analysis/monc_passes.py <steplog> [out.csv]`
Offset-off darks, Hz, per-step means (~11 counts each):

| Range | mean | sd across passes | min–max | slope (Hz/h) | sd of 1 s counts within a step (median) |
|---|---|---|---|---|---|
| 200 nA/V | 538.6 | 21.6 | 489–585 | −0.78 | 8.2 |
| 500 nA/V | 217.3 | 7.8 | 192–236 | −0.65 | 0.9 |
| 1 µA/V | 111.6 | 3.8 | 102–120 | −0.34 | 0.7 |
| 2 µA/V | 94.6 | 2.5 | 88–101 | −0.04 | 0.7 |
| 5 µA/V | 20.0 | 1.0 | 17.5–22.3 | −0.03 | 0.5 |
| 10 µA/V | 13.6 | 0.6 | 12.1–14.9 | −0.03 | 0.5 |
| 20 µA/V | 604.7 | 18.9 | 569–655 | −2.02 | 1.8 |
| 5 µA/V blanked | 173.0 | 0.9 | 170.0–174.8 | +0.01 | 0.5 |
| **interim hold (5 µA/V CAL +2 nA), 480 s** | **60.2** | **0.6** | **58.9–61.3** | **−0.03** | 0.8 |

- **No overnight drift that matters, but the slopes are not zero** (figure session, with standard errors): 500 nA/V −0.66 ± 0.16, 1 µA/V −0.35 ± 0.08, 20 µA/V −1.9 ± 0.4 Hz/h. The largest, −2 Hz/h at 20 µA/V, is 0.3 %/h of that dark. At 5 µA/V and in the interim hold it is −0.03 Hz/h.
- **The pass-to-pass scatter is not drift.** Detrended, lag-1 correlation between successive passes is −0.04 to +0.22 for every series. The sd from successive differences matches the plain sd.
  - The scatter is set when the range is selected. Each selection of 500 nA/V, 1 µA/V or 20 µA/V lands on a dark that differs by 7, 3.5 or 16 Hz sd. Within one step it holds to <1–2 Hz, **except 20 µA/V, which jumps by 20–30 Hz inside a step** (F9; 95th-percentile in-step max−min 26 Hz).
  - So **a dark must be measured after the last range change**. A dark from an earlier selection of the same range carries that scatter.
- At 5 µA/V the scatter is ~0.9 Hz across passes against 0.15 Hz expected from counting. The two 5 µA/V darks in one pass, ~70 s apart with a range change between them, correlate at r 0.61. The dark before and after a blank (no range change) correlates at r 0.79. So part of the ~1 Hz is a common component lasting minutes. It is equivalent to ~10 pA at 5 µA/V.
- The blanked 5 µA/V reading scatters by the same 0.9 Hz, so this component is in the later stages or the V2F, not the input stage.
- **The interim setting reads 60.2 ± 0.6 Hz all night** (each 480 s hold mean, sd across passes). It stays within the user's <120 Hz limit by 59 Hz, and 59 Hz above the clip.
- Hutch temperature: see the next section.

## Dark passes vs hutch temperature (2026-11-13): `python -I analysis/monc_passes_temp.py <steplog> <passes.csv> <T RAW csv>…`
- Data: raw 60 s SCAN archiver pulls of `15ID:Sensor1/2/5:Temperature`, made by the figure session (`archiver-pulls/xray_fluxor/…_2026-11-12T1900_2026-11-13T1429.csv`, outside git). Sensor2 is the C-hutch sensor; Sensors 3 and 4 read 0 °C (no sensor).
- **The temperature hardly moved: Sensor2 22.12–22.24 °C over the run, Sensor1 0.08 °C, Sensor5 0.14 °C.** So the night tests only small temperature changes.
- With Sensor2 (C hutch), at lag 0, 30 min, and after removing a straight line in time from both:
  - |r| ≤ 0.28 for every series. The largest are 200 nA/V −0.28, 500 nA/V −0.23 and the interim hold +0.23.
  - With 11 series × 3 tests, one or two |r| > 0.21 (p < 0.05) are expected by chance. Signs do not agree between sensors.
  - Sensor5's larger r (20 µA/V +0.49, hold +0.33) mostly disappears when the time trends are removed (+0.19). It is a shared slow trend, not a tracked fluctuation.
- **No temperature dependence is resolved.** The slopes give upper bounds (Sensor2, ±1σ):
  - interim hold: +5.6 ± 2.5 Hz/°C;
  - 5 µA/V dark: +1.7 ± 4.6 Hz/°C;
  - 10 µA/V dark: +0.2 ± 2.7 Hz/°C.
  - Over the user's stated 0.5 °C hutch stability, that is ≲4 Hz on the interim setting.
- Limits:
  - 0.1 °C of leverage is small.
  - No sensor is known to be at the SR570 or V2F.
  - The ~1 Hz minute-scale component at 5 µA/V is not explained by these sensors.

# Chamber unplugged, 2026-11-13 ~10:13 (read-only analysis of the logger)
- The user (via the figure session): "Up until i started measuring the monc chamber in my office it was fully connected, but no beam going through. Right now nothing is at the end of the monc BNC cable that connects to the SR570, because the chamber is in my office."
  - So the overnight data had the chamber cabled with no beam. HV on is likely, but 2.7 kV isn't verified.
- `python -I analysis/monc_interim_watch.py <logger.csv>`: no `15IDC:A3` setting event since 08:12. Handling noise from **10:13:15 to 10:14:39 CST** (counts 27–79 Hz), then a new steady level.

| Interim setting, 5 µA/V CAL +2 nA | mean | sd of 1 s counts | sd of 5-min means | slope |
|---|---|---|---|---|
| 08:12–10:13, chamber cabled | 59.09 Hz | 0.90 | 0.47 | +0.17 Hz/h |
| 10:15–11:55, open BNC cable | **38.48 Hz** | 0.97 | 0.55 | +0.34 Hz/h |

- **Unplugging the chamber removed 20.6 Hz** at the interim setting. The noise didn't change.
- ~~At 5 µA/V that is 1.03 nA of input current. The overnight offset-off darks fit the same current (f = a + 1e5·I/S, I = 1.043 nA, a = 12.2 Hz), so most of the "dark" was ~1 nA from the chamber.~~ **Wrong. Overturned the same day by the leakage run below:** the drop is the same ~21 Hz at every gain, and in the blanked reading too. The 1/S fit was fooled because the SR570's own range offsets also fall roughly as 1/S.
  - This corrects my earlier reading that the dark "doesn't scale as 1/S" (sweep-1 re-run section). That was right for the first hour after power-on (e.g. 54 Hz at 50 nA/V, where 1 nA would give 2000 Hz), but not overnight. Something changed between 14:07 and 15:05 on 2026-11-12: HV switched on, or the current charging up. Not known.
- Not affected:
  - the CAL ladder factors (each subtracts a dark from the same selection);
  - F9, the 20 µA/V jumps of 20–30 Hz, which are far more than 1 nA can give there (5 Hz).
- **The confirming test needs MonC writes, so it needs the user's OK** *(run 12:09 with the user's OK; the predicted drops failed, see "Leakage run")*:
  - one dark pass now, with the open cable (preferably capped);
  - expected drops vs overnight: 500 nA/V −208, 1 µA/V −104, 2 µA/V −52, 5 µA/V −21, 10 µA/V −10, 20 µA/V −5 Hz;
  - the blanked readings should not change, because the blank grounds the path after the input.

# Leakage run: chamber unplugged, BNC cable end open (2026-11-13 12:09–12:26)
- The user: "run monc experiment, I like having a solid number for the leakage current. I'm leaving the BNC cable unmodified however". PLAN.md row 2026-11-13.
- Plan `monc_leak_plan.csv` (`analysis/make_night_plan.py <out> 5 --passes-only --hold=60`): 5 passes, the same steps and order as the overnight passes, with 60 s interim holds. Step log `monc_sweep_steps_20261113_120911.csv` (in git). Exit 0, `restored:`, 0 state mismatches. Interim setting back: hold p5 38.7 Hz.
- Analysis: `python -I analysis/monc_leak.py <overnight steplog> <leak steplog> [n_last]`. It compares the last 10 overnight passes (chamber cabled) with the 5 passes now.

| Offset-off dark | with chamber (Hz) | without (Hz) | difference (Hz) |
|---|---|---|---|
| 200 nA/V | 538.8 ± 21.7 | 516.8 ± 16.6 | 22.0 |
| 500 nA/V | 214.4 ± 5.5 | 193.5 ± 2.6 | 21.0 |
| 1 µA/V | 110.0 ± 3.2 | 89.0 ± 2.8 | 21.0 |
| 2 µA/V | 93.0 ± 2.4 | 71.4 ± 1.4 | 21.5 |
| 5 µA/V | 19.4 ± 0.9 | **1.0 (clipped)** | ≥ 18.4 |
| 10 µA/V | 13.3 ± 0.6 | **1.0 (clipped)** | ≥ 12.3 |
| 20 µA/V | 591.5 ± 12.3 | 565.5 ± 15.8 | 26.0 |
| 5 µA/V blanked | 172.9 ± 1.0 | 151.5 ± 1.2 | 21.4 |
| interim hold | 59.5 ± 0.6 | 38.6 ± 2.0 | 21.0 |

(± is the pass-to-pass sd.)

- **The leakage current is zero within the errors.** Fitting difference = c + 1e5·I/S over the unclipped gains 200 nA/V–2 µA/V:
  - **I = −2.6 ± 12.8 pA** (last 10 passes); I = +1.9 ± 9.0 pA (all 92). So **|I| < ~25 pA (2σ)**.
  - c = 21.5 ± 1.3 Hz; reduced χ² 0.04.
  - For scale: 25 pA is 0.5 Hz at 5 µA/V, 0.00025 % of the 10 µA behind 2×10⁵ cps.
- **What the chamber connection does add is a gain-independent output offset, +21.5 ± 1.3 Hz ≈ +0.21 mV at the V2F input.**
  - It is present when blanked. BLNK grounds the path after the front end, so this enters after the input stage: most likely a ground or shield offset (chamber body, HV supply return) carried in on the BNC shield. Not tested.
  - It is in every dark and hold measured with the chamber cabled. It cancels in a dark subtraction at the same state.
- **Without the chamber, the SR570's own offset-off output at 5 and 10 µA/V is negative (clipped).** So the "≈11 Hz SR570 share at 5 µA/V" was ~21 Hz from the chamber connection on top of a negative SR570 offset.
  - The interim +2 nA CAL offset keeps MonC positive either way: 38.6 Hz without the chamber, ~60 Hz with it.
- Caveats:
  - "With minus without" is chamber cabled overnight (HV state not verified) against the open, uncapped cable. Any pickup on the open end is in it. The noise didn't change (sd of 1 s counts 0.90 → 0.97 at the interim setting).
  - The with-chamber data are 4–20 h older. Over the night the drifts were ≤ 2 Hz/h, and the result is the same with 10 or 92 passes.
