# Design: live E-station lane on the utilioc (IC-500-50 read by the TetrAMM)

Date: 2026-11-16. Status: approved by the user to build and install ("yep, go ahead", 2026-11-16, after being offered "Live E-station lane on the utilioc"). Builds on the offline package `fluxor/` (parameter registry, `fluxor/PARAMETERS.md`).

## Goal
A relative normalising number in photons/second for the E-station beam, live, on the same utilioc as MonP and MonC, with an EPICS alarm and stated low/high bounds. The user (2026-11-16): the goal is a good RELATIVE normalising number in photons/s; absolute uncertainty is not a blocker.

## What the lane computes (same physics as `fluxor/`, same conventions as the MonP/MonC lanes)
Inputs, all read-only links (`NPP NMS`, as the existing lanes): TetrAMM channel 3 and channel 4 mean currents (nA), the E-station mono energy readback (keV), the E-hutch air temperature (deg F, converted in the slot), and the live pressure the MonP lane already maintains (`userTran1.G`, kPa, with its age counter `userTran3.H`). **Gas follows the MonP/MonC convention: ambient barometric pressure from the existing updater and a hutch temperature PV; no new gauge or sensor** (user, 2026-11-16: "why do you insist on doing everything different from the example in this same repo").

Slots (a "lane", like `calc/lanes.py`; slot numbers come from the read-only discovery of free slots, lowest free first):
| role | kind | content |
|---|---|---|
| flux | transform | net current A = MAX(A+B-dark,0)·1e-9; T degC; density; ln E; mu_en/rho and mu/rho (the same cubic fits as MonP, `calc/coefficients.json`); absorbed fraction over l_eff = 5.0 cm (registry `ic500.l_eff_cm`); P = I·W/(e·E)/f_abs·exp(−mu·rho·l): the formula, not wall-loss corrected |
| bounds | transform | E_eff; wall-loss fraction from the IC-500-50 fit (registry `ic500.wall_fit`, MC `analysis/wall_loss_ic500.py`); recombination central/low/high from the current (loss ∝ I, registry rows `beam.aspect_*`, `beam.width_mm`, `recomb.*`); RESULT = P/(1−Lw)/(1−r_central); low and high with the symmetric σ factors and the wall-loss band, as `fluxor.core.evaluate` |
| flags | transform | one 0/1 per condition and their sum (status code) |
| status | calcout | the code with alarm severity (>0.5 MINOR, >15.5 MAJOR) |

Constants in the slot expressions are generated from the `fluxor` registry (single source of truth); a test checks the slot mirror against `fluxor.core.evaluate` within 2 % over 5–30 keV, several currents and gas conditions. Every expression string is at most 39 characters (autosave limit; existing rule).

Flag bits (same code layout as the existing lanes so one screen design serves all; thresholds revised 2026-11-16 after the offline review, named constants in `calc/estation_lane.py`): 1 E>12.5 keV (wall-loss band in use), 2 central recombination loss above 5 % (about 14 uA total), 4 pressure not updated for 2 h, 8 net current below 50 nA (low current: the stated bounds understate the uncertainty), 16 E outside 4.9-30.5 keV or NaN (MAJOR), 32 raw current sum below -5 nA, or a channel at/above 99 % of the 120 uA full scale, or NaN (MAJOR). The flux is always published; flags only add severity (user rule: an imperfect number with a warning beats none).

## Scope guard (stop and ask)
- Writes only to the free utilioc slots chosen by the discovery, through the guarded installer (`calc/slotlib.install`: refuses a slot owned by someone else, Enable off → write → read back → Enable on → verify). No write to any TetrAMM, FX4, mono, slit, HV or beamline PV, and no restart of any IOC.
- No PV names outside the utilioc slot names in tracked code: the E-station source PV names live in a gitignored local file with a committed `.template` (CLAUDE.md privacy rule).
- Screens: per the repo procedure (`utilioc-slot-screens`), the cmc-services screens get updated, but shipping them is the user's step.
- No dark estimator slot in this first version: the dark is a hand-set value in the flux slot (default 0 nA); the TetrAMM dark is about 0.5 nA against 1–4 µA signals. A rate-gated estimator like MonP's is a later addendum.

## Assumptions (all carried from `fluxor/parameters.toml`; the lane inherits their flags as a warning that the numbers are placeholders)
Plate orientation, beam aspect and width, l_eff = 5.0 cm ±3 %, TetrAMM gain accuracy 1 % placeholder, gas stand-in σ (1.0 kPa, 2.0 C), recombination correction on the best estimate (user confirmed 2026-11-16). The beam size will come later (user: not a blocker).

## Verification gates
1. Offline: expressions ≤ 39 characters, mirror vs `fluxor.core.evaluate`, no NaN (unary-minus trap: `calc/HANDOFF.md`).
2. `--dry-run` lists every write and every slot is free.
3. Install: every field read back, flux verified against the mirror on live inputs, no NaN, SEVR as expected.
4. `--compare` reports 0 differences afterwards; MonP and MonC `--compare` still 0 differences.
5. Soak: live RESULT against `fluxor` at the live inputs within 2 % (energy within 5–30 keV).

## Docs
`calc/HANDOFF.md` and `calc/OPERATOR.md` (new lane section, how to read the flags, how to remove the lane), `fluxor/HANDOFF.md` (the lane is generated from the registry), `TODO.md` (dark estimator; later beam size).
