# Proposal: normalizing with MonP and MonC together

*Architect, 2026-11-12. A proposal for the user's decision, not yet adopted.* Both chambers are CMC-custom ion chambers on the same N2 supply.

## Where things stand
- The experiment signal is divided by **raw MonC counts**.
- MonP (upstream, after the DBPM) is recorded but not used.
- **DBPM summed signal: `15IDGen:0:userTran6.E`** (user, 2026-11-13). DESC "ID1 DBPM Calc", field comment "tot". It read −9.72 with no beam on 2026-11-13.
  - **Archived since 2026-11-13** (SCAN, 5 s, the same as the MonP/MonC counts; submitted at the user's request: "Yes, archive it"). Before that the archiver returned 404 for it. Experimenter's request list used `15IDC:userTran10.E`, which is configured but has 0 events.
  - User: "MonP is usually more robust to beam misalignment than the DBPM, but when the beam is aligned their ratio could be interesting." So MonP/DBPM is a meaningful comparison **only with the beam aligned**. A misalignment shows up mainly in the DBPM sum, not in MonP.
- MonC sits after the last excitation slits and before the attenuators. Its SR570 gain changes often, with focusing and the S1 configuration.

**Weaknesses of raw-MonC normalization:**
1. **Gain changes.** Every MonC sensitivity change is a step in the normalizer. It has to be bookkept, and it is only as good as the SR570's ±0.5 % range-to-range accuracy, which has not been verified here. (Since measured on MonC: up to +0.62 % at the nominal ratio, CHAMBER_FACTS F5.6; MonP is still unmeasured.) Because the SR570's RS-232 is listen-only, a front-panel change never reaches EPICS, and that error is silent.
2. **Weather.** MonC's photons-per-count follows the gas density. From day to day that is 0.4 % median and up to 3 % (pressure), plus ~0.2 % (hutch temperature). Normalized data compared across days carries that error. (`physics_note.md` §3.3)
3. **Offsets.** The dark offset (manually set near 50–100 Hz) sits inside the normalizer. That is negligible at >100 kHz, but not at low MonC rates.
4. **No cross-check.** A MonC fault, a bad cable or a wrong gain in EPICS looks exactly like a flux change.
5. **No absolute scale.** Raw counts are not photons.

A ratio of the two chambers is free of weather, because both share the N2. **Dividing the sample signal by one chamber is not.** The second chamber does not remove weather from the normalization. What it buys is the following.

## Proposed scheme

**Per data point, convert both chambers to photons/s** with the physics-note conversion:
```
Φ_X = K_X(E, ρ) · (N_X − D_X) · S_X            X = P (MonP), C (MonC)
ρ   = P_ASOS(t) · M / (R · T_Sensor2(t))       one shared density for both chambers
```
- **N_X** is the scaler rate.
- **D_X** is the most recent dark rate measured at the same sensitivity and offset.
- **S_X** is the SR570 sensitivity from EPICS.
- **K_X** is the physics-note conversion for that chamber's geometry and V2F range. MonC's chamber is the same design as MonP's (CHAMBER_FACTS §1), so K_C differs only in mounting and its own reference plane.
- **P_ASOS** is the hourly LOT station pressure; **T_Sensor2** is `15ID:Sensor2:Temperature`.

**1. Normalize the experiment to Φ_C** (photons/s after the slits), not to raw MonC counts.
- MonC is still the right chamber: it sees what passed the slits.
- The density term in K_C removes the weather. Cross-day comparisons improve from ~1–4 % to ~0.2–0.4 %.
- The unit becomes detector counts per incident photon. That makes it absolute to the extent K_C is (§5 anchor), and comparable across beamtimes.

**2. Track the transfer ratio r(t) = Φ_C / Φ_P.** It is the slit and optics transmission between the chambers, times the air/window path between them. To first order it is independent of weather and of the source.
- **(a) Gain-change splicing and in-situ SR570 calibration.** Across a MonC (or MonP) sensitivity change, r must be continuous, because nothing physical changed. The jump in r at the change *is* the error in the SR570's range-to-range ratio. Logged over time, these jumps build a measured table of the true range ratios, replacing the ±0.5 % spec. A front-panel change that EPICS never heard about shows up as an unexplained step in r: the silent error becomes visible.
  - This is not hypothetical. In MonC sweep 1 (Experimenter, 2026-11-12), the MonC scaler channel did not respond to any EPICS SR570 command, while EPICS showed every write as accepted. A scheme that trusts EPICS gain values without a cross-check would have normalized silently wrong. r would flag it at the first gain change.
- **(b) Diagnosis.** A change in Φ_P (and the DBPM sum) means source, monochromator or upstream. A change in r with Φ_P steady means slits, focusing, or beam position at the slits. Today both look the same in raw MonC.
- **(c) Fallback.** When MonC is invalid, use Φ_C ≈ r̄ · Φ_P, with r̄ taken from the neighbouring valid points, and flag those points. MonC is invalid when it is:
  - above 400 kHz or overloaded;
  - mid gain change;
  - having its offset re-tweaked;
  - too close to its dark.
- **(d) Optional low-noise variant, not the default:** Φ_C,smooth = Φ_P · LowPass(r). It uses MonP's larger signal for fast fluctuations and MonC only for the slow transmission. This is valid **only if** the fast fluctuations are common to both chambers, i.e. from upstream. Beam jitter *at the slits* is exactly what MonC sees and MonP does not, and the low-pass would wrongly remove it. Test first with the MonP–MonC coherence spectrum, using 1 s logger data. Adopt it only where coherence is high.

**3. Keep raw data, so the normalization can be recomputed.** Store per point:
- N_P, N_C
- S_P, S_C, and both offset settings
- D_P, D_C (with time of measurement)
- E
- the DBPM sum and its gain
- P and T (or the time, for a later ASOS lookup)

Never store only the normalized value: every constant above will improve, and old data should get the better constants.

**4. Malfunction monitor (the TODO item).** Watch both ratios:
- **MonP/DBPM** for upstream faults, judged only while the beam is aligned: MonP tolerates misalignment better than the DBPM (user). It carries the weather (only MonP depends on gas density), so use the density-corrected Φ_P.
- **r** for faults between the chambers.

What counts as an error state is still to be scoped with the user.

## How to test it before adopting it (all from existing data, read-only)
1. **The density correction itself.** In archiver history with the beam on **and aligned**, the ratio MonP-counts/DBPM-sum should track pressure/temperature with **slope +1** (efficiency ∝ ρ). `15IDGen:0:userTran6.E` is archived from 2026-11-13, so the test needs a few days of data from then. A regression against ASOS P and Sensor2 T tests §3.3 directly, with no new hardware. **First run 2026-11-17 (`analysis/density_slope_test.py`): all archived data are at 30 keV, so it tests the direct + wall-loss correction (expected slope 1.8–1.9); b = 2.14 ± 0.58 in the headline fit, not robust to the analysis choice (variants 2.1–4.0). Compatible, not confirmed; repeat below 15 keV (`calc/PRESSURE.md` §8).**
2. **SR570 range ratios.** Find MonC and MonP sensitivity changes in the history, measure the jump in r at each, and see whether they are within ±0.5 % and repeatable.
3. **Stability of r** at fixed slit, focus and energy over hours. Its scatter sets how good the fallback (c) is.
4. **Coherence** of MonP and MonC at 1 s (Experimenter's logger) decides whether variant (d) is worth anything.

Tests 1 and 2 overlap with Experimenter's dark-drift archiver work (same PVs). Coordinate, rather than pulling twice.

## Needed from the user
- ~~Is MonC also a CMC-custom chamber with the same geometry as MonP?~~ Answered 2026-11-13: yes, the same design, mounted with its plates horizontal (CHAMBER_FACTS F1.1–F1.3). Each lane has its own wall-loss fit, so r is energy-independent apart from the air path only below the wall-loss onset (~18 keV).
- Agreement that normalization moves from raw MonC to Φ_C (and r for checks), once the tests pass.
