# Design: IC-500-50 chamber plus TetrAMM and FX4 electronics chains (offline package)

Date: 2026-11-13. Status: built offline on the night of 2026-11-13 (steps 1-5, see "Build status"); the parameter framework (tagged registry `fluxor/parameters.toml`, spectrum input, recombination range) was built on 2026-11-14 under `docs/superpowers/plans/2026-11-14-fluxor-parameter-framework.md`; awaiting the user's review. Approach A, chosen by the user on 2026-11-13.

## Purpose
Extend xray_fluxor from the SR570 → V2F → scaler chain on the MonP and MonC chambers to:
1. a new chamber model, the AVS IC-500-50 (second ID line, E-station), and
2. two new electronics chains that read current directly, the CAEN TetrAMM (reading this chamber now) and the Pyramid FX4 (will read it later).

Deliverable now: an **offline** Python package with tests and docs. No new live PVs. Live lanes are a later step the user approves separately.

## Given configuration (user, 2026-11-13)
| Item | Value | Status |
|---|---|---|
| Chamber | AVS IC-500-50, 50 mm electrode, gold-plated Cu with guard rings, not gridded | given |
| Gap | 10 mm | given |
| Gas | nitrogen, flowing | given; pressure source open |
| Windows | factory 25 µm Kapton | given |
| HV | 1.7 kV | given |
| Collector | split (saw-tooth) plate, two BNC outputs | model both channels separately, with a sum option. Experimenter, 2026-11-13: the signal is on TetrAMM channels 3 and 4 only (about 60.5 / 39.5 %), channels 1 and 2 carry nothing |
| Beam | second ID line, independent of MonP and MonC; beam size deferred | position assumed centred |
| Electronics now | TetrAMM | ordering code and range unknown |
| Electronics later | FX4 | model suffix and range unknown |

## Structure
```
fluxor/
  core.py          evaluate(chamber, chain, reading, conditions) -> Result
  chambers/        base.py, ic500_50.py, cmc_guarded.py (wraps today's MonP/MonC chamber)
  chains/          base.py, sr570_v2f.py (reference), tetramm.py, fx4.py
tests/
```
- **Chain plugin:** raw reading plus settings (range, sample rate or averaging, channel, offset in use, bias) → signed current in A, with named uncertainty terms (size, type A or B) and status flags. It knows nothing about photons.
- **Chamber plugin:** current, energy, gas conditions → photons/s at the reference plane, with per-plate and summed outputs. It holds geometry, absorption, W, collection length, wall loss and the recombination bound.
- **`evaluate()`** returns flux, low and high bounds, the uncertainty budget as a table, and flags. It never withholds a number: an imperfect value always comes with a warning and an uncertainty (the standing rule).
- **Conditions (P, T, E)** are caller inputs. Offline there are no PV reads.
- Constants and cross sections stay in `data/queries/` and `physics_note.md`. The wall-loss MC is reused through a chamber-specific run.
- `calc/` and the live MonP and MonC calc are **not touched**. A later step may generate slot expressions from the same plugin definitions (the live 39-character expression limit then applies to that generator, not to this package).

## Chain plugins
Both return a signed current directly. There is no V2F count, no gain enum, no 1e5 Hz/V constant, no ~8.4 Hz floor or clipping at zero. "Dark" is a current offset.

| | TetrAMM | FX4 |
|---|---|---|
| Inputs | 4 channels, 24-bit, internal 100 kHz sampling averaged down; RNG command picks the range | 4 channels, 8 input ranges (one range for all channels), conversion 1e5 Hz, sample frequency by averaging |
| Offset | user offset calibration, `I = I_raw − offset` | per-channel zero offset in non-volatile memory, plus scale factors |
| Terms (from manual) | range gain accuracy, residual offset after zeroing, equivalent input noise by range and averaging, full-scale clip | range gain accuracy, offset drift with air temperature (manual fig. 32), noise vs sample rate, full-scale clip |

Common:
- Status flags: overrange (within about 1 % of full scale), lost in noise (below a few times the noise), stale dark.
- Dark term: the offset measured with beam off and HV on, stored as a recorded value with its date.
- HV is not the chain's job. The 1.7 kV is an input to the chamber plugin.
- Channel mapping is configuration: plate 1 and plate 2 map to channel numbers; sum is the default and separate readout is selectable.
- The accuracy figures depend on the exact order code and the manuals' text has none. **Changed during the build (A10):** the plugin emits a 1 % placeholder gain term with a `gain_accuracy_placeholder` flag, instead of refusing, because the standing rule is that a flagged number beats none.

## IC-500-50 chamber plugin
Reused: absorption and W as for MonP and MonC, with N₂ density from P and T; reference plane = exit of the collection region, before the exit Kapton (the Kapton and air path stay out of scope); the photoelectron-track MC rerun for this geometry (10 mm gap, plate orientation, beam position), giving a fitted signal-loss curve with a band like the per-lane fits; `l_eff` from the fringe-field analysis redone for the guard rings.

New:
- **Recombination at 1.7 kV:** a Boag volume-recombination estimate at the highest expected flux, carried as a one-sided bound, not a model. Expected collection efficiency is near 1; the check confirms it.
- **Split plate:** per-plate flux and their sum. The sum is the headline, because the position-dependent split cancels in it. A single plate depends on beam position (unknown), so it carries a wide uncertainty and a warning flag.
- **Flowing N₂:** P and T are caller inputs with a stated source.

Assumptions until confirmed:
- Plates horizontal, like MonC.
- Beam centred in the gap.
- `l_eff` = the 50 mm electrode length with a wide stated uncertainty, because the brochure gives no guard or electrode-width dimensions.

## Testing and gates
1. **Regression:** SR570 + V2F chain with the MonP chamber through the new `evaluate()` reproduces RESULT.md's 4.37e6 ph/s per Hz at 10 keV (±3.6 %).
2. **Chain tests:** known current → expected reading per range, from the manuals; synthetic offset and noise tests for the flags.
3. **Chamber tests:** hand formula vs `evaluate()` within about 2 % at 5–20 keV; recombination bound vs a hand Boag calculation.
4. **Real-data check:** deferred until the user finds archived PVs. Until then the checks are synthetic, and every output says so.

## Documentation
New subproject `fluxor/` with `OPERATOR.md` and `HANDOFF.md`, updated in the same commit as each change; a section per plugin in HANDOFF.md. Append-only `PROGRESS.md` entry per session. A `PLAN.md` addendum with plan-changes rows quoting the user. No host names, IPs, account names or PV prefixes in tracked files.

## Scope guard (drift: stop and ask)
- Any write to EPICS PVs, to TetrAMM or FX4 settings, to HV, or to utilioc slots.
- Touching `calc/` or the live MonP and MonC calc.
- The Kapton windows and the air path.
- Beam-size effects and a split-plate position model.
- Buying hardware or recommending a different chamber.

## Steps and gates
| # | Step | Gate (evidence) |
|---|---|---|
| 1 | Package skeleton and interfaces; SR570 chain and CMC chamber wrapped | the 4.37e6 regression passes |
| 2 | TetrAMM chain plugin | chain tests pass; terms trace to manual pages |
| 3 | FX4 chain plugin | the same |
| 4 | IC-500-50 chamber plugin, MC rerun, recombination bound | hand-formula cross-check; MC output saved in `analysis/out/` |
| 5 | Docs and a worked 10 keV example per chain | OPERATOR.md and HANDOFF.md exist; the example runs |
| 6 | Real-data comparison | waits on archived PVs; may be a later addendum |

## Open items (the user's input needed)
1. TetrAMM ordering code, ranges and settings in use; FX4 model suffix and ranges.
2. Vendor drawing of the IC-500-50 electrode and guard geometry (for `l_eff` and the MC).
3. Pressure and temperature source for the flowing N₂ at the E-station.
4. Split-plate wiring: **answered by the Experimenter's data (2026-11-13)**: the chamber signal is on TetrAMM channels 3 and 4, not on one channel and not summed in hardware; channels 1 and 2 carry nothing; the all-channel sum PV is a software sum of the four (so it includes the unused channels' dark). The detailed note is local (it names PVs). Still open: whether channels 3 and 4 are the two halves of the split plate, whether the TetrAMM bias is used, and which plate is HV.
5. Plate orientation, and the highest expected flux (for the recombination bound).
6. Archived PVs for the TetrAMM chain, for step 6.

## Build status (2026-11-13 night)
| Step | Result |
|---|---|
| 1 skeleton, SR570 chain and MonP/MonC chamber wrapped | done; regression reproduces RESULT.md's 4.37e6 ph/s per Hz at 10 keV within 1 % and the live calc's formula within 2 % at 5-30 keV |
| 2 TetrAMM chain | done; noise table, ranges, flags tested; gain accuracy is a flagged placeholder (A10) |
| 3 FX4 chain | done; ranges 4, 6, 7 provisional (A12), noise a lower bound (A13) |
| 4 IC-500-50 chamber | done; wall-loss MC rerun and fitted, band covers 140 of 140 points; recombination bound checked against a numerical solution; l_eff and beam size are assumptions (A3, A6) |
| 5 docs and worked example | `fluxor/OPERATOR.md`, `fluxor/HANDOFF.md`, `fluxor/ASSUMPTIONS.md`, `fluxor/example.py` |
| 7 parameter framework | done (2026-11-14): every non-code number is a tagged row of `fluxor/parameters.toml` read through `fluxor/params.py`, with an `assumed:<name>` flag on results that use an ASSUMED or PROVISIONAL row; `fluxor/PARAMETERS.md` is generated and supersedes `fluxor/ASSUMPTIONS.md`; photon-spectrum input (default pure fundamental); recombination as a central value plus a beam aspect-ratio range, the best estimate carrying the central correction. Plan: `docs/superpowers/plans/2026-11-14-fluxor-parameter-framework.md` |
| 6 real-data comparison | first part done (2026-11-14, rerun on the parameter registry): the package runs on 7 archived clean beam-on periods at the E-station mono energies (8-20 keV; the first run at 30.001 keV used the wrong mono and is void); flux 9.7e11 to 1.41e13 ph/s (best estimate now includes the central recombination correction), wall loss 0-3.5 %, recombination 0.4-1.4 % at the central height/width 0.1 and 0.11-14.2 % over the full range 0.03 to 1.0 (bounds span that range), total sigma 4.4 %. No independent absolute flux reference exists, so the absolute accuracy is NOT confirmed; gas P and T are stand-ins and harmonic content is unknown (A7, A23, A25, A27-A29) |
Every assumed number is a row of `fluxor/PARAMETERS.md` (generated; supersedes `fluxor/ASSUMPTIONS.md`).
