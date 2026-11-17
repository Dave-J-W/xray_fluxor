# How good is the flux number? Absolute and relative uncertainty

*Written 2026-11-17. This is the reader's guide to the uncertainty of every flux number in this repository: MonP and MonC at C-station (the live utilioc lanes), and the IC-500-50 at E-station (the `fluxor` package and its live lane). It explains, sorts and points. The numbers themselves live in their sources. MonP and MonC numbers carry their `CHAMBER_FACTS.md` row ID (for example F9.5); E-station numbers carry their `fluxor/PARAMETERS.md` row name. When a source changes, the source wins: fix this file to match.*

Where the detail is:
- the formulas and the derivatives: `METHOD.md` §7;
- the physics evidence for each term: `physics_note.md` §3;
- the electronics measurements: `ELECTRONICS_CONCLUSIONS.md`;
- the finished numbers: `RESULT.md`.

---

## 1. Which number do you need?

An ion chamber is used for two different jobs, and each job has its own uncertainty.

| You want… | Example | The uncertainty that matters |
|---|---|---|
| **Absolute flux**: how many photons/s actually arrived | dose, sample damage, detector efficiency, comparing with another beamline | **absolute**: §3 |
| **Relative flux at one energy**: how the flux changed from one reading to the next | normalising a scan, a time series, or repeats across a beamtime | **relative, fixed energy**: §4 |
| **Relative flux across energies**: the ratio of the flux at two energies | normalising an energy scan, or comparing data taken at different energies | **relative, across energy**: §5 |

**The sorting rule.** An error that is the same for both readings cancels when you divide one by the other. So the question to ask of each source is: *does it change between the two readings I am comparing?*
- A constant of the chamber, such as W or the collection length, is the same in every reading. It sets the absolute scale and cancels in every ratio.
- A cross-section table is the same at one energy but not at two. It cancels in a fixed-energy series, but not in an energy scan.
- The weather, the dark and a gain change differ from one reading to the next. They never cancel, though most of them can be corrected.

Absolute and relative errors are therefore not two lists of different sources. They are the same sources, sorted by whether they cancel. Table 2 below sorts all of them.

### Headline numbers

| | Absolute | Relative, fixed energy, with the live corrections | Relative across energies |
|---|---|---|---|
| **MonP, ≤ 13 keV** | **±3.6 %** (F9.5, F9.6) | **~0.2 % or better** at full beam, same gain. Raw counts with no correction: 0.4 % per day (median), up to 4 % over 3 days, from the weather alone | up to **~5 %** between energies far apart (cross-section tables and fit); **~0** within ~1 keV |
| **MonP, 30 keV** | **+23 % / −20 %** (wall loss) | as above; a ~1 mm beam move changes it by up to ~3 % (worst near 20 keV, ~0.6 % at 30 keV) | wall loss dominates: **~+19 / −17 %** against an energy below 13 keV |
| **MonC** | as MonP; at 30 keV **+18 / −15 %** | as MonP; a gain change steps it by up to **+0.62 %** at the nominal ratio (F5.6), ~0.02 % with the measured factors (F5.5) | as MonP, smaller wall loss |
| **E-station IC-500-50, 10 keV, 4 µA** | **−5.5 % / +20 %**, mostly the unmeasured beam shape (recombination) | the change in recombination with current: **0.2–7 %** for a 2× change in current (§4.2) | as MonP, plus the assumed plate orientation above 13 keV |

Some of these numbers are bounds and some are estimates; §3 to §5 say which. **None of the absolute numbers has been checked against an independent flux measurement** (§7).

**MonC's chamber has been unplugged since 2026-11-13 10:13 (F7.2).** Until it is reconnected, the MonC lane's number is not a beam measurement.

---

## 2. Words used here

| Term | Meaning |
|---|---|
| **absolute error** | the error in the photons/s itself |
| **relative error** | the error in the ratio of two flux readings, which is what normalisation uses |
| **cancels** | the same in both readings of a ratio, so it drops out |
| **σ_s** | the **symmetric terms** combined in quadrature: each term is taken as one standard deviation, and they are added as independent errors (METHOD §7) |
| **wall-loss band** | the range of the wall-loss correction (photoelectrons that reach a plate before they stop), above 13 keV (METHOD §6, §7f) |
| **stated bounds** | the published low and high values. They are **not** a 68 % or 95 % confidence interval (§3.3) |
| **type A / type B** | type A is measured scatter; type B is a judgement, a specification or a spread between references |
| **state error** | the instrument not doing what EPICS says (for example a gain changed at the front panel). It is a gross error, not a percentage (§6) |
| **best estimate** | the published result, with the modelled corrections applied: `userTran3.L` (MonP), `userTran6.L` (MonC), `userTran10.L` (E-station); `flux_best` in `fluxor` |

---

## Table 2. Every source, sorted

**How to read it.** "0" means the source cancels for that use. **Bold** marks a source that is *not* in the published bounds. For the C-station lanes, a source inside σ_s is marked "in σ_s".

### 2a. C-station: MonP and MonC (live lanes)

| Source | Size, and where it is defined | Absolute | Relative, fixed energy | Relative across energy |
|---|---|---|---|---|
| μ_en/ρ tables (NIST, against Chantler/Elam) | ±3 %, type B (F9.1) | yes, in σ_s | 0 | **partly**: the only independent theory (Chantler) differs from NIST in μ/ρ by −6.1 % at 5 keV, −4.0 % at 10, −3.3 % at 15, −1.4 % at 20 and +1.4 % at 30 keV (`data/queries/out/compare_N.csv`). So the error is not one common scale: treat it as independent for energies far apart, and nearly common within a few keV |
| Collection length l_eff (guarded chamber, 2-D model) | ±1.4 % (F4.3, F4.4) | yes, in σ_s | 0, unless the beam moves: ±1 mm in height changes l_eff by 0.24 % (METHOD §7a) | 0 |
| Cross-section fit inside the 39-character slot | ≤ 0.9 %, worst at 25 keV (F9.4) | yes, in σ_s | 0 | **yes**: it differs from one energy to another, up to 0.9 % at each |
| Electronics: SR570 gain × V2F scale, absolute | ±0.7 %, type B (F5.3) | yes, in σ_s | 0 at a fixed gain; for a gain change, see below | 0 |
| W(N₂) | ±0.6 % (F9.2) | yes, in σ_s | 0 | 0 (W does not depend on the photon energy at these energies) |
| Gas density, live P and T | ±0.2 % (F9.3) | yes, in σ_s | **≤ 0.2 %**, and less over minutes to hours: part of it is a constant offset (the elevation, A4 in physics_note §3.3), which cancels. Not tested directly yet (§7) | as fixed energy. Above ~18 keV the density also enters through the wall loss, which doubles the sensitivity at 30 keV (METHOD §7d); the live calc corrects it |
| Weather, **if raw counts are used** (no density correction) | | — | **≤0.03–0.2 % within an hour; 0.4 % median and 1.6 % (95th percentile) over a day; up to 4 % over 3 days** (physics_note §3.3) | the same |
| Wall loss (photoelectrons reaching a plate) | 0 below 13 keV. Above, the band (F10.1–F10.3); at 30 keV, ×1.76 on MonP, band alone +18.9 % / −16.7 % | yes, the band multiplies the bounds | 0 at a fixed beam position. **A 1 mm beam move on MonP changes the signal by ~3 % at 20 keV, ~1.4 % at 25 keV and ~0.6 % at 30 keV** (old 10 mm MC sensitivity table, physics_note §3.1). Not in the bounds as a relative term | **yes, the largest term**: it switches on at 13–18 keV and reaches ×1.76 (MonP) / ×1.37 (MonC) at 30 keV, uncertain by the band |
| Wall-loss stress corner (three MC changes at once) | up to ~3 % on the high bound near 18 keV (F10.4) | **accepted risk, outside the bounds** | 0 | the same |
| **Dark (background) residual** | δD / N; per gain in F5.2. MonP no-beam rate 182–227 Hz (F13.1) | **not in σ_s**; flagged stale by status bit 2 | **≤ 0.1 % above 100 kHz; 1 % at 10 kHz; 10 % at 1 kHz** when D is ~100 Hz off. A fresh dark at the same gain: 0.0004 % at 100 kHz (5 µA/V). Table in ELECTRONICS_CONCLUSIONS §3 | the same |
| **Gain change** (SR570 range to range) | MonC measured: up to +0.62 % at the nominal ratio (F5.6); ~0.02 % with the measured factors (F5.4, F5.5). MonP not measured: assume ±0.7 % (F5.3) | inside F5.3 | **a step at every gain change**, of the size in the cell to the left | the same |
| **Electronics noise** | ≤ 0.003 % per 1 s count (MonC; ELECTRONICS_CONCLUSIONS §1) | negligible | negligible. **Do not use √N**: V2F counts are not Poisson, and √N is ~190× too large | the same |
| **Electronics linearity** | ≤ 0.03 % over 10–450 kHz; **below 10 kHz up to 0.7 %, not settled** (ELECTRONICS_CONCLUSIONS §1) | — | between rates that differ a lot, below 10 kHz | the same |
| **Warm-up after an SR570 power-on** | darks move by tens of Hz in the first hour; range factors by 0.04 % within ~2.5 h | — | in the first hours after power-on | the same |
| **Gas purity** | +0.34 % signal per 1 % residual air | — | **only in the first hour after the chamber is opened** (physics_note §3.4) | the same |
| Energy readback (mono) | ±0.4 % (F9.7), since 2026-11-17: an **ASSUMED** 0.1 % energy error (no edge scan yet) × d ln Φ / d ln E, which is 2.2 below 15 keV and at most 3.7 (MonP best estimate at 29.5 keV; 3.2 on MonC). Computed with `fluxor` | yes, in σ_s | 0 if the energy is steady | **yes**, if the calibration error changes with energy (an angle offset gives an error that grows with energy) |
| **Harmonics** | MonP is nearly blind to the third harmonic (wall loss and low μ_en; physics_note §3.1) | **not in the bounds** | if the harmonic content changes | **yes** |
| Recombination | ≈ 0 at 2.7 kV across 10.85 mm [PROVISIONAL] (physics_note §3.6) | not carried | 0 | 0 |

### 2b. E-station: IC-500-50 read by the TetrAMM (`fluxor`, live lane on `userTran9–11`)

Every row tagged ASSUMED or PROVISIONAL in `fluxor/PARAMETERS.md` puts an `assumed:<name>` flag on every result that uses it.

| Source | Size, and the registry row | Absolute | Relative, fixed energy | Relative across energy |
|---|---|---|---|---|
| μ_en/ρ tables | 3 % (`terms.mu_en_tables_rel`, reused from MonP) | yes, in σ_s | 0 | partly, as 2a |
| Collection length | 3 % allowance (`ic500.l_eff_cm`: 50 mm from the vendor figure; the allowance is for fringe field and guards, which the figure doesn't show) | yes, in σ_s | 0 | 0 |
| Gas stand-in P, T | 1.2 % at the stand-in values (1 kPa, 2 °C; `gas.p_kpa`, `gas.t_c`) | yes, in σ_s | **the chamber temperature is taken as the hutch air**, so a chamber that warms or cools on its own is not followed | as fixed energy |
| TetrAMM range gain | 1 %, a **placeholder** (`tetramm.gain_rel`, ASSUMED) | yes, in σ_s | 0 at a fixed range | 0 |
| W | 0.6 % (`terms.w_rel`) | yes, in σ_s | 0 | 0 |
| Density, live | 0.2 % (`terms.density_rel`) | yes, in σ_s | ≤ 0.2 % | as fixed energy |
| Current noise and residual dark | 1 nA per channel (`tetramm.dark_sigma_nA`: the dark moved ~1 nA from week to week), with the TetrAMM's noise; 0.035 % at 4 µA | yes, in quadrature with σ_s | **about 1.4 nA / I for the two-channel sum: 0.07 % at 2 µA, 2.8 % at 50 nA.** Below 50 nA status bit 8 is set and the number shouldn't be used | the same |
| **Recombination** (ion pairs that recombine before they are collected) | grows in proportion to the current and to beam height / width. **The beam shape has not been measured** (`beam.aspect_low/central/high` = 0.03 / 0.1 / 1.0, `beam.width_mm`). At 4 µA: 0.43 / 1.42 / 14.2 % | the best estimate carries the central loss; the bounds span low to high (the high bound widens most) | **yes, the largest relative term at E-station**: the loss changes with the current. Halving 4 µA lowers the central correction by 0.71 %, but the true change could lie anywhere from 0.21 % to 7.1 % | the same |
| Wall loss | above 13 keV, band around `ic500.wall_fit`. **The plate orientation is assumed** (`ic500.plate_orientation`, horizontal) | yes | 0 at a fixed position | yes, as 2a |
| Per-channel split | the share between the two halves moves with the beam (`ic500.split_band_mm`) | — | **use the sum of the two channels**, which doesn't depend on position | — |
| Energy readback | 0.4 % (`terms.energy_readback_rel`, ASSUMED: 0.1 % energy error × d ln Φ / d ln E ≤ 3.3 for this chamber, carried at the C-station value). The E-station energy is the side-bounce mono, and its readback isn't archived (fluxor/HANDOFF.md, Known traps) | yes, in σ_s | 0 if steady | yes |

---

## 3. Absolute uncertainty: how the bounds are built

### 3.1 The rule (both stations)
1. Each symmetric term is a one-sigma relative error on the flux, mostly type B.
2. They are added in quadrature: σ_s = √(Σ term²).
3. The **wall-loss band** (and at E-station the **recombination range**) then **multiplies** each edge. These are stacked linearly, not in quadrature, which is the cautious choice.
4. The factors are rounded outward to three decimals.

```
high = formula × (1 + σ_s) / ((1 − wall_hi) × (1 − recomb_high))
low  = formula × (1 − σ_s) / ((1 − wall_lo) × (1 − recomb_low))
best = formula / ((1 − wall_best) × (1 − recomb_central))
```
C-station has no recombination factor (it is taken as 1). The exact slot expressions are in METHOD §7, and the `fluxor` code is `core.evaluate()`.

### 3.2 The numbers

**C-station, MonP and MonC** (F9.1–F9.6):

| Term | % |
|---|---|
| μ_en/ρ tables | 3.0 |
| collection length | 1.4 |
| cross-section fit | 0.9 |
| electronics | 0.7 |
| W | 0.6 |
| density (live) | 0.2 |
| energy readback (assumed 0.1 % in E) | 0.4 |
| **σ_s** | **3.58** → bound factors ×0.964 / ×1.036 (3.56 before the energy term, 2026-11-17; the factors did not change) |

μ_en/ρ is 70 % of the variance. Every other term together is less than it.

Worked bounds (METHOD §7, MonP, 224 kHz at 10 keV / 75.2 kHz at 30 keV, 500 nA/V, site-mean gas):

| | best estimate | low – high | relative |
|---|---|---|---|
| 10 keV | 0.978 × 10¹² ph/s | 0.942 – 1.013 × 10¹² | ±3.6 % |
| 30 keV | 6.32 × 10¹² ph/s | 5.08 – 7.78 × 10¹² | +23.2 % / −19.7 %; the wall-loss band alone is +18.9 / −16.7 % |
| MonC, same 30 keV reading | 4.92 × 10¹² ph/s | 4.18 – 5.81 × 10¹² | +18.2 % / −14.9 % |

**E-station, IC-500-50** (`fluxor`, gas stand-ins, two-channel sum 4 µA, 10 keV, computed 2026-11-17):

| Term | % |
|---|---|
| μ_en/ρ tables | 3.0 |
| collection length (allowance) | 3.0 |
| gas stand-in P, T | 1.2 |
| TetrAMM range gain (placeholder) | 1.0 |
| W | 0.6 |
| energy readback (assumed) | 0.4 |
| density | 0.2 |
| current noise and residual dark | 0.04 |
| **σ_s** | **4.59** |

Recombination at 4 µA is 0.43 % (low), 1.42 % (central) and 14.2 % (high). The result is **4.35 × 10¹² ph/s, bounds −5.5 % / +20.2 %** (with the energy term). The high bound is mostly the round-beam recombination case. A measured beam height and width would remove most of it.

### 3.3 What the bounds are, and what they are not
- **They are stated bounds, not a confidence interval.** Each side is about one sigma of σ_s, times the full edge of the wall-loss band (and of the recombination range) on that side. The probability that the true flux lies inside has not been measured.
- **Most terms are type B** (references, specifications, model spreads). Only an independent absolute flux measurement can test them (§7).
- **Some things are left out of the bounds.** Each one has its own flag, or it appears in Table 2 in bold:
  - the dark residual (flag: status bit 2, background stale; E-station bit 8, low current);
  - a gain change made outside EPICS (no flag possible; see §6);
  - harmonics;
  - the accepted wall-loss stress corner (F10.4).
- **Below 13 keV the C-station bounds are symmetric (±3.6 %).** Above 13 keV they are asymmetric, because the wall-loss band is.

---

## 4. Relative uncertainty at one energy (normalising a scan or a series)

### 4.1 C-station
MonC at 10 keV, every term on one axis and against count rate: `figures/out/unc10_summary.png`, `unc10_vs_rate.png` (`analysis/figures/fig_unc10.py`).

At a fixed energy every chamber constant cancels: μ_en, W, l_eff, the fit, the absolute electronics scale and the wall-loss model. What is left is anything that changes between readings:

| What changed between the two readings | Size of the relative error | What removes it |
|---|---|---|
| nothing (same gain, full beam, minutes apart) | **≲ 0.01 %** (noise ≤ 0.003 %, dark negligible above 100 kHz) | — |
| nothing, same gain, **hours** apart (electronics only) | **~0.003 %** per reading (MonC, measured: grid repeats 4–9 h apart need a slow wander of 0.0032 % beyond noise and dark; `figures/out/unc10_check.png`. The CAL source's own drift is in it, so it is an upper bound) | — |
| hours to days, using the **live photons/s** | **≤ 0.2 %** (density residual; not yet tested directly, §7) | — |
| hours to days, using **raw counts** | 0.03–0.2 % per hour; **0.4 % median per day; up to 4 % over 3 days** | use the live photons/s (`userTran3.L` MonP, `userTran6.L` MonC), or a MonP/MonC ratio, which cancels the weather because both chambers share the N₂ |
| an SR570 gain change | MonC: up to **+0.62 %** at the nominal ratio (F5.6). MonP: **unknown, up to ~0.7 %** | MonC: the measured factors (F5.4, ~0.02 %; `calc/monc_gain_cal.py` is a draft, not installed). MonP: measure its ranges (ELECTRONICS_CONCLUSIONS §6, item 2) |
| a low count rate | **δD / N**: 1 % at 10 kHz and 10 % at 1 kHz if the dark is ~100 Hz off | measure the dark after the last gain change (status bit 2 clears) |
| beam moved by 1 mm across the gap, **any energy** | **+0.28 / −0.20 %** through the collection length (F4.5; MonC: a vertical move, MonP: a horizontal one) | keep the beam fixed in the chamber |
| beam moved by ~1 mm, at 18 keV and above (MonP) | **up to ~3 %** (at 20 keV) through the wall loss, on top of the row above | keep the energy below ~18 keV for precise normalisation, or keep the beam fixed |
| the SR570 was power-cycled | the dark moves by tens of Hz for ~1 h | wait an hour; run `A3init`/`A2init` (with the user's OK) |

### 4.2 E-station
| What changed | Size | What removes it |
|---|---|---|
| nothing (fixed range, steady current ≳ 1 µA) | ≲ 0.1 % | — |
| the **chamber current** (the beam got brighter or weaker) | **recombination**. The central correction is applied, but the beam shape is unknown, so the true change in loss can be **0.3× to 10×** the change that was corrected. Example: 4 → 2 µA corrects 0.71 %, while the truth lies between 0.21 % and 7.1 % (the top of that range is past the formula's 10 % validity at 4 µA, flag `recombination_formula_not_valid`) | measure the beam height and width (rows `beam.aspect_*`, `beam.width_mm`); or lower the current, which shrinks the loss in proportion |
| the dark (week to week) | **about 1.4 nA / I** (1 nA per channel, two channels): 0.07 % at 2 µA, 2.8 % at 50 nA | a dark measured the same day (`userTran9.F`) |
| the TetrAMM range | unknown (the 1 % gain placeholder) | the order code's accuracy table, or a calibration |
| chamber temperature against the hutch air | 0.34 % per K of difference | a sensor on the chamber body (TODO.md) |

---

## 5. Relative uncertainty across energies (energy scans)

Everything in §4 still applies. In addition, these no longer cancel:
1. **Wall loss**, above 13 keV (MonP from 17.9 keV, MonC from 18.1 keV, E-station from 17.7 keV in the fit). This is the largest term by far. Between 10 and 30 keV the MonP correction goes from 1 to ×1.76, uncertain by +18.9 / −16.7 %. **For precise energy scans, stay below ~17 keV, or use the best estimate and carry its bounds.**
2. **Cross-section tables.** The table error is not one common scale. Chantler differs from NIST in μ/ρ by −4.0 % at 10 keV and +1.4 % at 30 keV, a 5 % change in shape over that range (Table 2a). Below 20 keV the shape changes by about 1–2 % per 5 keV.
3. **The cross-section fit in the slot**: up to 0.9 % at any energy, with a different value at each.
4. **The energy readback**: a 0.1 % energy error gives 0.22 % (below 15 keV) to 0.37 % (MonP at 30 keV) on the flux. The absolute budget carries it as 0.4 % (F9.7), on an ASSUMED 0.1 %. In an energy scan it cancels only if the readback error is the same fraction at every energy, which an angle offset does not give.
5. **Harmonics**, if their share changes across the scan.

Below ~13 keV, then, an energy-scan normalisation is good to about 1–2 % from the cross-section shape and fit, plus §4. Above it, the wall-loss band dominates.

---

## 6. Errors no percentage covers

These are state errors. Each one gives a factor, not a percentage, and the only defence is a cross-check (ELECTRONICS_CONCLUSIONS §4):
- **EPICS shows what was sent, not what the SR570 holds.** The RS-232 link is listen-only. One whole sweep ran on an SR570 that was switched off.
- **Someone changes the gain at the front panel.** The number is then off by a factor of 2–10.
- **The MonC chamber is unplugged** (F7.2, since 2026-11-13).
- **The wrong energy source is used.** The first E-station run used the C-station monochromator and was void.

**Cross-check:** across any gain change or restart, the MonP/MonC ratio (or MonP/DBPM with the beam aligned) must stay continuous (`normalization_proposal.md`, point 2a).

---

## 7. What has been tested, and what hasn't

| Claim | Test | Status |
|---|---|---|
| Absolute flux, either station | an independent flux (pixel detector + foils, or a calibrated diode) | **not done**. Every absolute number here is untested physics |
| The arithmetic of the formula | other calculators (CHESS, xraydb with one carrier, Hephaestus, the C-station note) | agrees once the inputs are aligned (physics_note §4). This tests the code, not the constants |
| Live lane = offline model | `calc/soak_check.py` (MonP); `calc/estation_lane.py` self-test (E-station, within 0.6 % of `fluxor`) | passes; again code consistency only |
| Wall-loss band covers the MC variants | `analysis/wall_loss_fit.py`: 140 of 140 points per lane within 2 MC standard errors | passes, except the accepted stress corner (F10.4) |
| The density correction (relative) | `analysis/density_slope_test.py` (calc/PRESSURE.md §8): slope of MonP/DBPM against density, expected 1.83–1.93 at 30 keV | **inconclusive**: 2.14 ± 0.58, and 2.1–4.0 across analysis choices. Needs a run below 15 keV |
| MonC range factors (relative) | overnight grids g2–g4 | measured; repeat to ≤ 0.015 % over 8.7 h (F5.5) |
| MonP range factors | the same grid on MonP | **not done** (it writes MonP: needs the user's OK) |
| Gain-change continuity of MonP/MonC | find jumps in the ratio at archived gain changes (normalization_proposal test 2) | **not done** |

**An absolute anchor would test the whole absolute chain at once.** At one energy it would replace the μ_en, W, l_eff and electronics terms with its own uncertainty. A second anchor energy above 25 keV would test the wall-loss model.

---

## 8. How to quote the uncertainty of your data

1. **Absolute flux:** quote the best estimate with its low and high bounds (`userTran3.L`, `.D`, `.E` for MonP; `userTran6` for MonC; `userTran10.L`, `.K`, `.M` at E-station), and say they are stated bounds (§3.3). Check the status code first: bits 2 and 8 mean the bounds leave something out.
2. **A normalised series at one energy:** normalise to the live photons/s, not to raw counts, and stay at one SR570 gain if you can. Then the relative error is §4's table. For high precision, keep the rate above 10 kHz and take a fresh dark after any gain change.
3. **An energy scan:** add §5. Below 13 keV it is about 1–2 %. Above 13 keV, carry the bounds' wall-loss part as a correlated systematic: it moves smoothly with energy and has the same sign at every energy.
4. **Never use √N on V2F counts.**
