# fluxor: operator guide

For the people who use it. What it does, how to call it, what each flag means. Internals are in `HANDOFF.md`.

## What it does
Turns a current-meter reading from an ion chamber into **photons per second** at a stated reference plane, with a low and a high bound and a list of warnings. It runs offline: you hand it the reading and the photon energy (and, if you have them, the gas pressure and temperature). It reads no PVs and writes nothing.

Chambers: the **IC-500-50** (E-station), and **MonP** / **MonC** as built (for checking against the live calc).
Electronics: **TetrAMM**, **FX4**, and the **SR570 + V2F** chain MonP and MonC use.

**Status (2026-11-14):** built and tested offline; it has not been compared with an independent absolute flux, and several inputs are assumed numbers (the generated list is `PARAMETERS.md`). Every result carries an `assumed:<name>` flag for each assumed number it used.

## How to use it
Run the worked example, then copy it:
```bash
%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -I -X utf8 fluxor/example.py
```
In Python:
```python
from fluxor.chains.tetramm import TetraMM
from fluxor.chambers.ic500_50 import Ic500_50
from fluxor.core import evaluate

chain = TetraMM(("Current3", "Current4"), darks={"Current3": 0.2, "Current4": -0.1}, dark_age_h=2)
r = evaluate(Ic500_50(), chain, {"channels": {"Current3": 2400.0, "Current4": 1600.0}}, energy_kev=10.0)
r.flux_best, r.flux_low, r.flux_high, r.flags, r.per_channel
```
- Leave `rng=` out and the range comes from the registry (row `tetramm.range`, provisional), so the result carries `assumed:tetramm.range`. Passing `rng=0` yourself drops that flag: do it only when you know the range.
- Leave `p_kpa=` and `t_c=` out and the registry's stand-ins are used (rows `gas.p_kpa`, `gas.t_c`): their flags appear and a "gas stand-in P,T" term (1 kPa, 2 C) enters the budget. Pass `p_kpa=` and `t_c=` once you have real values (no flag, no stand-in term).
- Readings are per-channel values in the TetrAMM's unit (nA at the E-station); for the FX4, amperes.
- The **dark** is the reading with the beam off and the bias on, per channel, in the same unit. Measure it the same day.
- **Spectrum:** by default the beam is taken as pure fundamental (the user's choice, no flag). To include harmonics pass `spectrum=[(1, 0.9), (3, 0.1)]` to `evaluate()`: pairs of (multiple of the energy, photon fraction), fractions summing to 1.
- **Sum, or each plate:** `current` is the sum of the channels you name as signal channels. `per_channel` gives each channel's share of the flux.

## What the result means
- `flux_best`: photons/s at the exit of the collection region (before the exit Kapton), with the wall-loss correction and the **central** recombination correction applied (see "Recombination" below).
- `flux_low`, `flux_high`: stated bounds. They always bracket the best estimate (low <= best <= high); you always get a number. For a negative current (flag `negative_current`) the best estimate is negative and the bounds are the mirror image of the bounds for the same positive current.
- The recombination loss that goes into the result is capped at 0.5 (50 %); the `recomb_low`, `recomb_central` and `recomb_high` numbers in `detail['chamber']` are the uncapped formula values, so they can exceed 0.5 when the formula no longer applies.
- `sigma_rel` and `budget`: the combined relative uncertainty and each term. `sigma_rel` is the uncertainty of the **absolute** flux. For normalising, most of its terms cancel; `UNCERTAINTY.md` §4 and §5 say which do not (above all the recombination change with current).

## Recombination: what the best estimate and the bounds mean
In the IC-500-50 some of the ion pairs recombine before they are collected, so the current reads low. The size of the loss depends on the current and on the beam's height divided by its width, and nobody has measured that ratio.
- **Best estimate:** corrected for the loss at the **central** ratio, 0.1 (a beam ten times wider than tall; undulator beams usually are). The size of that loss is 0.4 to 1.4 % at the currents of the November beam-on periods.
- **Bounds:** span the **range** of ratios, 0.03 to 1.0. The low bound uses the smallest loss (0.03), the high bound the largest (1.0, a round beam, the conservative case). At those currents the range is 0.1 to 14 %, so recombination can widen both bounds, the high bound much more.
- **Beam width:** 1.0 mm, taken from the upstream white-beam slits. The slits sit outside the beam's hot zone, so this is an **upper bound** on the width.
- The ratio and the width are assumed numbers (flags `assumed:beam.aspect_central`, `assumed:beam.aspect_low`, `assumed:beam.aspect_high`, `assumed:beam.width_mm`). A real height and width, from a screen or a knife-edge scan, replaces them (next section). Entering a measured beam aspect ratio means setting **all three** rows (`beam.aspect_low`, `beam.aspect_central`, `beam.aspect_high`) so that low <= central <= high; otherwise the flag `beam_aspect_rows_not_ordered` appears.
- The default for the correction can be switched off (row `recomb.apply_to_best` in `parameters.toml`); then the best estimate carries no recombination correction. The low bound then carries none either, and the high bound keeps the largest-ratio loss.

## How to replace an assumed number
Worked example for the gas pressure (the call leaves `p_kpa` out, so the stand-in row is used):
```text
1. Find the row in fluxor/PARAMETERS.md (the flag says which: assumed:gas.p_kpa).
2. Edit that row in fluxor/parameters.toml: new value, tag = "MEASURED", source = "what you measured it with", date.
3. Run: python -I -X utf8 fluxor/make_parameters_md.py   then   python -I -X utf8 -m unittest discover -s tests -t .
4. Calls that leave p_kpa out now use your number: the flag assumed:gas.p_kpa no longer appears, and the flux changes accordingly.
   A call that passes p_kpa itself never used the row, so editing the row does not change it.
```
Use the bluesky venv's `python` (`%USERPROFILE%\.venvs\bluesky\Scripts\python.exe`; plain `python` on this PC is a stub). Each row of `PARAMETERS.md` says in its "closes with" column what would replace it.

## Flags: what each one means and what to do
| Flag | Meaning | What to do |
|---|---|---|
| `assumed:<name>` | the result used a number nobody measured (an ASSUMED or PROVISIONAL row of the registry), for example `assumed:tetramm.gain_rel` (gain accuracy, a 1 % placeholder) | look it up in `PARAMETERS.md`; it says what would replace it (see "How to replace an assumed number") |
| `dark_not_given_<ch>` | no dark was supplied for that channel | measure one |
| `dark_stale_or_age_unknown` | the dark is more than 24 h old or its age was not given | take a new dark; the E-station dark moves by about 1 nA from week to week |
| `overrange_<ch>` | that channel is within 1 % of full scale or beyond: the reading is clipped | change range (that is a hardware setting: ask the owner of the unit) |
| `current_within_3_sigma_of_zero` | the signal is lost in noise; the flux is then bounded by the noise | longer averaging or more beam |
| `negative_current` | the net current is below zero by more than 3 sigma (a wrong dark, or reversed polarity): the best estimate is negative | check the dark and the polarity; the bounds are mirrored so low <= best <= high still holds |
| `beam_aspect_rows_not_ordered` | the three beam aspect rows are not in the order low <= central <= high | set all three rows together |
| `per_channel_flux_depends_on_beam_position` | the split between plates moves with the beam | use the sum |
| `beam_taller_than_30_percent_of_gap_formula_weak` | the central beam height is more than 30 % of the 10 mm gap, so the first-order recombination formula is weak | give a smaller beam size or treat the recombination correction as indicative |
| `recombination_over_1_percent` | the recombination loss at the largest ratio (1.0) exceeds 1 % at this current; it widens the high bound (and the low bound at its smaller ratio) | give the beam height and width; the high bound is the safe side |
| `recombination_formula_not_valid` | the loss at the largest ratio exceeds 10 %: the formula no longer applies there | do not trust the high bound; reduce the flux or raise the HV |
| `energy_outside_cross_section_range` | outside 4.9–30.5 keV (the live calc's limits) | the number is an extrapolation |
| `noise_from_resolution_only` (FX4) | the noise figure is only the ADC's resolution, a lower bound | measure the FX4's real dark noise |
| `range_full_scale_provisional` (FX4) | range 7 only: its full scale is taken as the standard 3 mA (the manual's picture shows a 10 mA unit; 10 mA is a special order) | check the unit's range table; ranges 0-6 are confirmed |
| `temperature_outside_15_25C` (FX4) | the unit is outside its recommended temperature | expect a larger offset |

## Never
Do not use it to change a range, bias or offset on the TetrAMM or FX4: it does not talk to them. Changing instrument settings is the owner's call.
