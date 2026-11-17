# fluxor: handoff

For the next maintainer. Design, files, rules, pinned versions, dated decisions, traps and open items. The spec is `docs/superpowers/specs/2026-11-13-ic500-chains-design.md`; every assumed number is a row of `PARAMETERS.md` (generated from `parameters.toml`; its `legacy` column keeps the old A-ids of the superseded `ASSUMPTIONS.md`).

## What it is
An offline Python package: **chain plugins** (raw reading → signed current, with uncertainty terms and flags) and **chamber plugins** (current, energy, gas → photons/s at the reference plane with bounds), joined by `core.evaluate()`. It does not touch PVs, hardware or the live calc.

## Files
| File | Role |
|---|---|
| `fluxor/parameters.toml`, `fluxor/params.py`, `fluxor/make_parameters_md.py` → `fluxor/PARAMETERS.md` | every non-code number, tagged and sourced; the registry flags `assumed:<name>` on results that use an ASSUMED or PROVISIONAL row. `PARAMETERS.md` is generated and supersedes `ASSUMPTIONS.md`. Any task that edits `parameters.toml` must rerun `make_parameters_md.py` and commit `PARAMETERS.md` |
| `fluxor/core.py` | `Term`, `ChainResult`, `ChamberResult`, `Result`, `evaluate()`. Combines relative terms in quadrature, the absolute current noise as a relative term, and the wall-loss band and the recombination loss at the low, central and high beam aspect ratio (the best estimate carries the central recombination correction while `recomb.apply_to_best` is true; the bounds use the low and high ratios; with the switch false the low bound carries no recombination and the high bound keeps `recomb_high`). Bounds are built on abs(I) and mirrored for a negative current (flag `negative_current`). `recomb_*` in `ChamberResult` are capped at 0.5; the `recomb_*` fields in `detail['chamber']` are uncapped |
| `fluxor/constants.py` | W, e, N₂ density, NIST μ and μ_en (log-log interpolation of `data/queries/nist_hubbell_seltzer/z07_nitrogen.html`, as `calc/monp_transform.full_physics`) |
| `fluxor/chambers/base.py` | `IonChamber(reg)`: the standard formula over a photon spectrum (`flux(current, e, p_kpa=None, t_c=None, spectrum=None)`; a None P or T reads the flagged stand-in rows `gas.p_kpa` / `gas.t_c` and adds a "gas stand-in P,T" term from their sigma; fractions must be non-negative and sum to 1; list of (multiple of E, photon fraction); default the registry row `spectrum.fractions`, pure fundamental), the share-weighted wall-loss band (the live calc's `BAND`), and the recombination hook |
| `fluxor/chambers/ic500_50.py` | the AVS IC-500-50: reads l_eff, gap, HV, `ic500.wall_fit`, beam width and aspect ratios from the registry; recombination loss at the low, central and high beam aspect ratio (`beam.aspect_low/central/high`, width `beam.width_mm`, height capped at the gap) returned as `recomb_low/best/high` |
| `fluxor/chambers/cmc_guarded.py` | MonP and MonC as built, from `calc/quality_slots.py` and `calc/monp_transform.py` (imported, read only) |
| `fluxor/chains/tetramm.py`, `fx4.py`, `sr570_v2f.py` | the three chains; the SR570 one is the regression reference |
| `analysis/wall_loss_ic500.py` | runs the wall-loss MC for the IC-500-50 (same MC and variants as MonP and MonC) → `analysis/out/wall_loss/IC500/` |
| `analysis/wall_loss_fit_ic500.py` | fits the signal loss, checks `ic500_50.WALL_FIT` equals the rounded fit, and tests that the band covers every variant (140 of 140) → `analysis/out/wall_loss_fit_IC500.txt` |
| `analysis/estation_step6.py` | step 6, first part: runs the package on the archived E-station beam-on periods (`data/estation/beam_on_periods_2026-11.csv`, numbers only) → `analysis/out/estation_step6.csv/.txt` |
| `tests/test_fluxor.py`, `tests/test_params.py` | tests in all: regression, chains, chambers, evaluate, spectrum, recombination, the low <= best <= high grid, gas stand-ins, the example script; registry, `replaced()` validation, flags, a reader for every ASSUMED/PROVISIONAL row, `PARAMETERS.md` order and content |
| `fluxor/example.py` | the worked example |

## Run
```bash
%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 -m unittest discover -s tests -t .
%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 analysis/wall_loss_ic500.py      # MC (a few seconds with 4 jobs)
%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 analysis/wall_loss_fit_ic500.py  # must print PASS
```
`python -I` ignores the working directory, so scripts insert the repo root on `sys.path` themselves. Environment: the bluesky venv (Python 3.12.4, xraydb 4.6.1 for the cross-section tables, numpy and scipy for the wall-loss fit). No new dependencies.

## Rules the code follows
- A flagged number beats none (standing user rule 2026-11-12): nothing returns None or raises on doubt; doubt is a flag and a bound.
- Best estimate carries modelled corrections: the wall loss and, while `recomb.apply_to_best` is true, the recombination loss at the central beam aspect ratio. The bounds use the low and high aspect ratios, so recombination widens both.
- Every non-code number is a row of `parameters.toml` read through the registry (`reg.value(name)`); an ASSUMED or PROVISIONAL row raises `assumed:<name>` in every result that read it. Nothing in code holds a copy.
- Constants and their provenance: `physics_note.md`, `data/queries/`, `ELECTRONICS_CONCLUSIONS.md`. The package does not restate a MonP/MonC fact that `CHAMBER_FACTS.md` holds; it imports it from `calc/`.
- No PV names in tracked files. The E-station TetrAMM PV names live in the Experimenter's local note and in local memory.

## Dated decisions
- 2026-11-13, user: offline model first; approach A (offline package with chamber and chain plugins, live calc untouched). Quoted in `PLAN.md`.
- 2026-11-13, user: "proceed and see what you can get built tonight; keep a list of your assumptions". The list is `ASSUMPTIONS.md`.
- 2026-11-13, Experimenter: the E-station signal is on TetrAMM channels 3 and 4 only (about 60.5 / 39.5 %), channels 1 and 2 carry nothing, and the software sum PV adds all four channels. So the chain takes named signal channels and does not use the sum PV.
- 2026-11-13, implementer: the spec's "refuse to emit a gain term" became "emit a 1 % placeholder with a flag" (A10); it is now the row `tetramm.gain_rel` / `fx4.gain_rel`, flagged `assumed:<name>`.
- 2026-11-14, user: "make a plan to implement with assumptions chosen wisely and recorded. we need a framework that works that we can add better numbers to later." Built as the registry (plan `docs/superpowers/plans/2026-11-14-fluxor-parameter-framework.md`). Choices made under it: the pure fundamental is the default spectrum (user: monochromators are fairly good at monochromating; a CHOICE row, no flag); recombination is a central value plus a range over beam height/width (0.03 to 1.0, central 0.1), and `recomb.apply_to_best` (default true) makes the best estimate carry the central correction. This reverses the earlier choice A19 (best estimate carries modelled corrections only, recombination to the high bound). Confirmed by the user on 2026-11-16 ("Yes, keep it") after the step-6 numbers were shown.

## Known traps
- **The E-station energy is the side-bounce mono, not the DCM.** The first step-6 run used the C-station DCM readback (30.001 keV) and was void; the E-station beam-on periods are at 8-20 keV. The E-station energy PV is not archived; its hardware axis is (local note). Check the energy source before trusting any E-station flux.
- **Recombination loss scales as beam height / width**, and the slits say nothing about the ratio (A29).
- **A recombination loss of about 1 % at a few µA is plausible at the central aspect ratio (0.1), and up to 14 % at a round beam (1.0).** The best estimate carries the CENTRAL correction (`beam.aspect_central`, `recomb.apply_to_best` true); the bounds span `beam.aspect_low` to `beam.aspect_high`. Set `recomb.apply_to_best` to false to drop the correction from the best estimate. Both bounds move with the range, not only the high one.
- **The recombination hook sees only the fundamental energy**, not the spectrum's harmonics. Harmless: recombination depends on the current, not on the photon energy.
- **`params.default()` is a shared mutable singleton** whose use-tracking (`Registry.used`) accumulates until `reset_use()`. Every chamber `flux()` and chain `current()` call resets it first, but code that reads values from the registry directly, then reads `flags()`, should call `reset_use()` first.
- **`Registry.replaced()` validates like `load()`**: a tag outside `params.TAGS`, or an ASSUMED/PROVISIONAL row without `closes_with`, raises ValueError (pass `closes_with=` when re-tagging a row that had none).
- **A row's `value` in `parameters.toml` is the only copy; do not re-introduce a constant in code.** Module constants such as `ic500_50.WALL_FIT` are read-only mirrors of the default registry for scripts and tests; the chambers read the registry at `flux()` time.
- **What-if runs:** `Registry.replaced(name, value, ...)` returns a new registry with one row overridden; pass it as `Ic500_50(reg)` / `TetraMM(..., reg=reg)` to see the effect without editing the TOML.
- **Every ASSUMED or PROVISIONAL row needs a code reader** (a test greps for the row name in `fluxor/` and `analysis/`); an unread assumed row never flags.
- **SumAll includes the unused channels' dark** (about 0.5 nA on channel 1). Always name the signal channels.
- **Compare PVs only with identical IOC timestamps** when checking channel sums from the archive (Experimenter, 10 s scan, 0.1 s means).
- **Range, bias and offsets are not archived** at the E-station, so a dark from the archive cannot be matched to a range or offset state.
- **The package's MonP bounds are not the live bounds**: no 0.9 % cross-section-fit term (A18).
- `ic500_50.WALL_FIT` is a rounded fit of an MC with assumed geometry; change the geometry and the fit script will fail until the constant is updated.
- `python -I`: scripts and tests add the repo root to `sys.path`; a new entry point must do the same.

## Live E-station lane
The utilioc slots for the E-station (`calc/estation_lane.py`; design in `docs/superpowers/specs/2026-11-16-estation-live-lane-design.md`; section "E-station lane" in `calc/HANDOFF.md`) are generated from this registry. Editing a `parameters.toml` row changes the lane only after the lane is regenerated (rerun `calc/estation_lane.py`, whose self-test compares it with `fluxor.core.evaluate`) and reinstalled. Rows the lane consumes: `ic500.l_eff_cm` (and its sigma), `ic500.wall_fit`, `ic500.plate_orientation`, `ic500.gap_mm`, `ic500.volts`, `recomb.alpha_cm3_s`, `recomb.mobility_cm2_vs`, `beam.width_mm`, `beam.aspect_low/central/high`, `terms.mu_en_tables_rel`, `terms.w_rel`, `terms.density_rel`, `terms.energy_readback_rel` (added 2026-11-17; it changed σ_s from 4.57 to 4.59 % but not the rounded factors, so the installed lane is unchanged), `tetramm.gain_rel`, `tetramm.range`, `tetramm.unit_a`, `gas.p_kpa` and `gas.t_c` (with their sigmas, for the stand-in term). The flag thresholds are constants in `estation_lane.py`, not rows.

## Open items
See `PARAMETERS.md`: every ASSUMED and PROVISIONAL row (the `closes with` column says how) needs your inputs: the beam's real height and width, gas P and T, instrument order codes, FX4 range table, one trusted flux number. The old A20 (real-data comparison) still needs an independent flux reference. A live lane (utilioc slots for the E-station) is a separate step that needs your approval; the 39-character slot limit will apply to that generator.

## Glossary

- beam-on period (was "window", renamed 2026-11-14): a stretch of the archive in which the E-station chamber saw beam, with constant energy and slits and a dark measurement on both sides; the Experimenter's script keeps the old name estation_windows.py
