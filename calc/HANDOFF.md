# MonP photons/s on utilioc: handoff

## What and where
- **Slot:** `15IDC:util:userTran1` (transform record) on utilioc, the current production host (f99). Installed 2026-11-12 by `calc/install_monp_slot.py` from this repo.
- **Source of truth:** `calc/monp_transform.py` `SLOT`. It holds every link, expression, comment and hand-set value.
- **The physics:** `physics_note.md`. The finished number and its provenance: `RESULT.md`.

## Lanes (2026-11-12): one identical slot set per monitor
- `calc/lanes.py` builds every field of every slot for a lane: flags, status, dark, flux, bkg, bounds. The expressions come from `monp_transform.py`, `background_transform.py` and `quality_slots.py`, so they are identical in every lane. Only the links, DESC, comments and slot numbers differ.

  | Lane | flux / bkg / bounds | status / dark | Scaler | SR570 |
  |---|---|---|---|---|
  | MonP | userTran1 / 2 / 3, flags userTran7 | userCalcOut1 / 2 | scaler1.S3 | 15IDC:A2 |
  | MonC | userTran4 / 5 / 6, flags userTran8 | userCalcOut4 / 5 | scaler1.S4 | 15IDC:A3 |

- MonC reads the live pressure (`userTran1.G`) and its age (`userTran3.H`) from the MonP lane, so one updater serves both.
- `calc/install_lane.py --lane MonP|MonC` installs a lane, `--dry-run` lists the writes, and `--compare` diffs the generated lane against the live IOC (read-only). The `--compare` for MonP gave **0 differences** on 2026-11-12, after one comment (userTran1.CMTG) was updated, so the generator reproduces the installed MonP setup.
- It replaces `install_monp_slot.py`, `install_background_slot.py` and `install_quality_slots.py` (removed 2026-11-12; they are in git history before that date).
- **MonC installed 2026-11-12** on userTran4-6 / userCalcOut4-5, after utilioc was raised to 20 slots (Implementer Z, restart 15:34). MonP `--compare` after the restart: 0 differences.

## Files
| File | Purpose |
|---|---|
| `calc/monp_transform.py` | slot definition; `evaluate()` mirrors the expression strings; `full_physics()` is the independent NIST conversion; `main()` is the self-test (expression lengths ≤39, calc vs full within 1 % at 5–20 keV and 2 % to 30 keV) |
| `calc/fit_coefficients.py` → `calc/coefficients.json` | minimax cubic fits of ln(μ_en/ρ) and ln(μ/ρ) for N, 5–30 keV, NIST-anchored: within 0.6 % of the target, 0.9 % of log-log NIST (25 keV); in the budget as ±0.9 % |
| `calc/install_monp_slot.py` (removed; see Lanes) | refuses an occupied slot; Enable off → write → read back → Enable on → verify P against `evaluate()` on live inputs. Re-run safe. `--dry-run` lists every write |
| `calc/soak_check.py` | read-only: live P vs `full_physics()` on the slot's own inputs |
| `CHAMBER_FACTS.md` + `analysis/check_chamber_facts.py` | the register of MonP/MonC facts (dimensions, beam, HV, collection length, calibration, leakage, MonC state, budget, wall-loss fits, gas references, bit 1, MonP dark), each with the file that defines it; the script checks every coded row against its source and must PASS after any change to a constant here (2026-11-13, METHOD_REVIEW C1) |

## Design
- Transform values are evaluated A→P, so each expression may use earlier letters only.
- **Inputs:**

  | Letter | Source |
  |---|---|
  | A | `15IDC:scaler1.S3` (counts) |
  | B | `15IDC:scaler1.T` (s) |
  | C | `15IDC:A2sens_num` (enum index: 1, 2, 5, … 500) |
  | D | `15IDC:A2sens_unit` (index: pA, nA, µA, mA /V) |
  | E | `ID15A1:DCMM:XTAL:E.RBV` (keV) |
  | F | `15ID:Sensor2:Temperature` (°C) |
  | G | pressure kPa, live: written every 15 min by `tools/asos_pressure.py` (MonC: linked to `userTran1.G`) |
  | H | background Hz: `userCalcOut2.VAL` (the dark feed, from the userTran2 estimate), through **MS** |

  All links are read-only (`NPP NMS`), except H, which is `NPP MS` so that the flux carries the status severity.
- **Computed:**

  | Letter | Expression | Meaning |
  |---|---|---|
  | I | `(1+(C%3)^2)*10^(FLOOR(C/3)+3*D-12)` | sensitivity A/V; idx%3 → 1, 2, 5 |
  | J | `B>0?MAX(A/B-H,0):0` | net rate, clamped at 0 |
  | K | `G*3.369272E-3/(F+273.15)` | ρ = P·M/(R·T) |
  | L | `LN(E)` | |
  | M | μ_en/ρ fit | |
  | N | μ/ρ fit | |
  | O | `1-EXP(-6.19*M*K)` | absorbed fraction over l = L_CM = 6.19 cm, the guarded collector's modelled l_eff (was 6 cm, the plate length, before 2026-11-13) |
  | P | `J*I*2.17205E12/E/O*EXP(-6.19*N*K)` | 2.17205e12 = W / (e · 1e3) / (1e5 Hz/V), with W = 34.8 eV and the V2F on x1 / 0–10 V |

- Every string is ≤39 characters: autosave stores links in 40 bytes, and CA string puts are 40 bytes.
- utilioc autosaves A–P, CLCx, INPx, CMTx, DESC, SCAN, PREC, COPT and EGU (calc `transform_settings.req` + `utilSlotExtras_transform_settings.req`).

## Dated decisions
- 2026-11-12, user: read-only input links to the five beamline PVs approved ("Yes, set them"). The mono energy PV was given as `ID15A1:DCMM:XTAL:E`; the slot reads its `.RBV`.
- 2026-11-12, user: dark stays 0 for now (superseded the same day by the next line).
- 2026-11-12, user: "subtract it, but in general an imperfect number with a epics warning and/or stated uncertainty is better than no number (this is always true!)". The background from userTran2 is subtracted through userCalcOut2, with status severity and the bounds slot userTran3.
- The links are NMS rather than MS, as approved. MS would put input alarms onto the slot; it is an open option.
- 2026-11-17, user: "Add the term" (the mono energy readback). `SYMMETRIC_TERMS["energy readback"]` = 0.004 (an ASSUMED 0.1 % energy error × d ln Φ / d ln E ≤ 3.7; CHAMBER_FACTS F9.7). σ_s went from 3.56 to 3.58 %; HIGH_FACTOR 1.036 and LOW_FACTOR 0.964 did not change, so the slot expressions of both lanes are identical and nothing was reinstalled. A larger term (a measured readback error above ~0.15 %, i.e. a term above 0.55 %) would change the factors and need a reinstall.

## Status flags (2026-11-12)
- Each lane has a flags transform (MonP userTran7, MonC userTran8). Its inputs:
  - E and count time from the flux slot;
  - the stale flag N, the no-beam seconds H and the settle time G from the background slot;
  - the pressure age from userTran3.H.
- It computes six 0/1 bits, F–K = 1, 2, 4, 8, 16, 32, and the code L = their sum. The status calcout copies L, with HIGH 0.5 MINOR and HIHI 15.5 MAJOR.
- The bounds slot no longer carries J/K (the old caution flag).
- DESCs since 2026-11-12:
  - "<lane> flux formula ph/s" (userTran1/4; .P is the formula, NOT the result);
  - "<lane> flux RESULT ph/s" (userTran3/6; .L is the result);
  - "<lane> status flags" and "<lane> flux status code".
- The installer adopts any slot whose DESC ends in "(xray_fluxor)", and writes hand values only to slots without that suffix.
- The net rate (flux .J) is clamped at 0 (`B>0?MAX(A/B-H,0):0`). With no beam, dark noise can no longer make the flux negative, so low ≤ result ≤ high always holds. The background slot still sees raw counts.

## Known traps
- **EPICS calc precedence:** unary minus binds tighter than `^`. `EXP(-(x)^p)` is `EXP((-x)^p)`, which is NaN. Use `1/EXP(x^p)`. The Python mirrors cannot catch this, so `slotlib.install` now fails any non-finite value: NaN once passed the float comparisons.
- **The MonP background is tagged by gain only, not by offset state.** userTran2 has no free letters. A hand re-tweak of the SR570 offset at the same gain therefore leaves the old estimate unflagged until the next no-beam period. Experimenter's MonC data show the dark depends on offset state too. A future setup (soft IOC) should tag by gain + offset (on, CAL, level, sign) and sanity-check each dark against an expected band per gain.
- **The SR570 RS-232 is listen-only.** `.I` is the last gain sent from EPICS, not the front panel. Experimenter's MonC sweep 1 showed an SR570 whose EPICS state did not match the hardware at all.
- **The V2F range is baked into the constant (1e5 Hz/V).** If the N101VTF is switched to 0–5 V, the 2.17205E12 must be halved, and the self-test must be updated too.
- **The energy fit is valid only for 5–30 keV.** Above ~14 keV P is a lower bound (wall loss, physics_note §3.1).
- A first draft of the constant left out the 1e5 Hz/V; the self-test caught it (×1e5). Keep running `monp_transform.py` after any edit.

## Verify / reinstall
```bash
python -I -X utf8 calc/monp_transform.py                       # offline self-test: PASS
python -X utf8 calc/install_lane.py --lane MonP --compare       # live vs generated, read-only: expect 0 differences
python -X utf8 calc/install_lane.py --lane MonP --dry-run       # what would be written
python -X utf8 calc/install_lane.py --lane MonP                 # install + verify ("LANE OK")
python -X utf8 calc/soak_check.py --n 6                        # live vs full physics (~0.6 % at 30 keV)
```
Use the bluesky venv, with `EPICS_CA_ADDR_LIST` set to the subnet broadcast and `EPICS_CA_AUTO_ADDR_LIST=NO`.

To free the slot:
1. `userTran1Enable` 0.
2. Clear INPA–INPF and CLCI–CLCP.
3. Set DESC back to "user Transform 1".

## Background estimate slot: `15IDC:util:userTran2` (installed 2026-11-12)
- Definition, Python mirror (`step()`) and simulated-day test: `calc/background_transform.py`. Run it: PASS.
- Installer: `calc/install_lane.py` (was `install_background_slot.py`), via the shared guarded installer `calc/slotlib.py`.
  - A re-run keeps the running estimate and the hand-set values; `--reset-values` restores F/G/I.
- Inputs come from `userTran1.A-D` (counts, time, gain indices), so there are no links outside utilioc.
- State lives in the transform values themselves. A letter used before it is computed in the A→P order holds its previous value:

  | Letter | Holds |
  |---|---|
  | H | seconds below threshold |
  | K | samples in the estimate |
  | L | the estimate |
  | M | the estimate's gain code (C + 10·D) |
  | O | age |

  utilioc autosaves A–P, so the estimate survives a restart. The H counter also survives, but it resets on the first sample with beam.
- **Design choice:** the rule is the rate (below 400 Hz for more than 10 s), not the shutter PV. The user called the shutter PV unreliable, and a rate rule also catches beam dumps. If a weak beam (heavily detuned mono) ever sits below 400 Hz, it would be taken as background; MonP is upstream of the attenuators, so this is rare.

## Warnings and bounds (installed 2026-11-12): `calc/quality_slots.py`, installed by `calc/install_lane.py`
**Rule from the user:** "an imperfect number with a epics warning and/or stated uncertainty is better than no number (this is always true!)". No slot blocks, zeroes or freezes the flux. Doubt is carried as alarm severity and as bounds.

| Slot | Role |
|---|---|
| `userTran7` | status flags: one 0/1 bit per condition (F–K, `quality_slots.FLAG_BITS`) and their sum, the status code, in L (`F+2*G+4*H+8*I+16*J+32*K`). MonC: userTran8 |
| `userCalcOut1` | status code: CALC `A`, with A = userTran7.L. HIGH 0.5/MINOR, HIHI 15.5/MAJOR, so bits 16 (E outside 4.9–30.5 keV) and 32 (scaler not counting) are MAJOR. The limits are autosaved via utilSlotExtras_calc_settings.req |
| `userCalcOut2` | VAL = userTran2.L. It reads userCalcOut1.VAL through **MS**, so it carries the status severity |
| `userTran1.INPH` | `15IDC:util:userCalcOut2.VAL NPP MS`: the flux subtracts the background *and* inherits the status severity |
| `userTran3` (MonP) / `userTran6` (MonC) | bounds and best estimate. A = the lane's flux .P (**MS**). B arrives as E and is replaced by E_eff = `B*(1.1221E-3/I)^.568` (CLCB, I = the density). C = Lw, the **signal** wall loss, from EACH LANE'S OWN fit (`quality_slots.WALL_FITS`, `clcc(lane)`): MonP `B>17.9?1-1/EXP(((B-17.9)/19.7)^1.17):0`, MonC `B>18.1?1-1/EXP(((B-18.1)/27)^1.41):0`. They are fitted to the MC of each chamber as mounted (MonP plates vertical, E toward them; MonC plates horizontal, E along them; 10.85 mm gap), times the photoelectric share f_pe (`analysis/wall_loss_families.py` → `analysis/wall_loss_fit.py`; max |err| 0.009 / 0.004, including MC points at 18.5–21 keV where the fits switch on). **L = A/(1−C), the best estimate.** D = low `A*.964/(1-MAX(.9*C-.07,0))`. E = high `A*1.036/(1-C-MIN(.09,2*C+.05*(B>13)))`. F / G = +% / −% relative to L. The constants are named in `quality_slots.py`: LOW_FACTOR = 1 − σ_s and HIGH_FACTOR = 1 + σ_s from SYMMETRIC_TERMS, which since 2026-11-13 include the guarded collection length ±1.4 %; plus BAND. The strings are built from them. Per lane, the band covers every f_pe-scaled MC variant and both two-change corners, 140 of 140 points (`analysis/out/wall_loss_fit_<lane>.txt`); the three-change corner is reported but not gated |

Severities only flow downstream, so there is no loop: userCalcOut1 reads userTran1 through NMS.

Check everything at once: `calc/status_check.py`. It checks that the status severity reaches the dark feed, the flux and the bounds.

## Live pressure (2026-11-12): `tools/asos_pressure.py`
**The full record is in `calc/PRESSURE.md`:** data flow, physics, sensitivities, accuracy, failure modes, and what is and is not live. The cron line is now installed by the user (see PROGRESS).
- Runs on the production host from `~/xray_fluxor/` (shipped with `git archive`; the commit is in `.deployed-commit`), with the utility venv (pyepics). It logs to `~/xray_fluxor/logs/pressure.log`.
- Sources: the IEM current-obs JSON (primary) and the NOAA AWC METAR (fallback). Guards: 95–104 kPa, observation ≤2 h old. On failure it writes nothing.
- Writes `15IDC:util:userTran1.G` (kPa) and `userTran3.H` = 0. userTran3 counts H up by 1 s per scan, and the flags slots (userTran7/8) turn `H > 7200` into status bit 4.
- **Scheduling:** the service account's crontab, `7,22,37,52 * * * *` (installed by the user on 2026-11-12; `tools/asos_pressure.py` CRON_SCHEDULE records it). The full line, with the CA address kept out of the repo:
  `7,22,37,52 * * * * cd ~/xray_fluxor && EPICS_CA_ADDR_LIST=<CA broadcast address> EPICS_CA_AUTO_ADDR_LIST=NO ~/venvs/utility/bin/python tools/asos_pressure.py >> logs/pressure.log 2>&1`
- **Shipping trap:** `git archive` on the Windows PC writes CRLF (`core.autocrlf=true`). Python runs the file either way, but strip `\r` before comparing hashes with `git show`.
- Assumptions: physics_note §3.3 A1–A7. A1 is confirmed (open outlet).

## E-station lane (defined offline 2026-11-16): IC-500-50 read by the TetrAMM
**Installed live on 2026-11-16** on the C-station utilioc (userTran9, userTran10, userTran11, userCalcOut9), verified on test currents, and on live TetrAMM dark inputs after the TetrAMM IOC came back (lane formula within 0.6 % of `fluxor`; not yet checked with beam on). This section is the definition (`calc/estation_lane.py`, evaluator `calc/calc_eval.py`, tests `tests/test_estation_lane.py`); the installer is `install_lane.py --lane EStn` (below). Design and approval: `docs/superpowers/specs/2026-11-16-estation-live-lane-design.md`.

- **Slots** (free on the C-station utilioc at the 2026-11-16 discovery; transform 12 is reserved for a later dark estimator; calcouts 3, 6, 7, 8 are not ours): flux `userTran9`, bounds `userTran10`, flags `userTran11`, status `userCalcOut9`. Install order: flags, status, flux, bounds. All inputs are read-only links (`NPP NMS`; a link that would exceed 39 characters with its modifiers is written bare, which means the same, because NPP and NMS are the defaults).
- **Source of truth for the numbers:** the fluxor registry. `estation_lane._generate()` reads `fluxor/parameters.toml` through `fluxor.params.default()` and the fluxor chamber and chain code: `ic500.l_eff_cm` (the 5 in the absorbed fraction and the transmission), `ic500.wall_fit` (the CLCC string), the band constants (`quality_slots.BAND`, asserted equal to the chamber's), W and e (`fluxor.constants`; 2.17205E17 = W/(e·1e3), asserted), the density constant M/(R·1000) (3.369238E-3; MonP types 3.369272E-3, 1e-5 apart), the recombination coefficient per ampere (`Ic500_50.extra_flags_and_high` at 1 µA, rows `beam.*` and `recomb.*`; the loss is linear in the current and capped at 0.5 in the slot, as in fluxor), the symmetric factors LOW 0.954 / HIGH 1.046 (quadrature of the chamber terms, `tetramm.gain_rel` and the gas stand-in term at the stand-in P and T; floor/ceil to 3 decimals as in `quality_slots`), and the TetrAMM full scale (flag 32). The flag thresholds are named constants at the top of `estation_lane.py` (`RAW_NEG_MARGIN_NA` 5 nA, `RECOMB_FLAG_FRACTION` 0.05, `LOW_CURRENT_NA` 50 nA, `FULL_SCALE_FRACTION` 0.99); the expressions, comments, `FLAG_BITS` and the tests all read them, so a change is one edit. To change a number, edit its registry row, run the self-test, and reinstall; do not edit a string.
- **The slot cannot know whether P is a stand-in.** The live pressure is the MonP updater's ambient number, so the gas stand-in term stays in the factors. The cross-section fit term (0.9 %) of the C-station lanes is not carried: fluxor uses the NIST tables, and the fits are within 0.6 % of them (inside the 2 % gate).
- **Source PV names** live only in `calc/estation_pvs.local.json` (gitignored via `calc/*.local.json`; keys `current3`, `current4`, `energy`, `hutch_temp_f`; committed template `calc/estation_pvs.template.json`). `build()` raises a `FileNotFoundError` naming the template if the local file is missing. The hutch temperature is in degrees Fahrenheit and posts only on change; the slot converts `(D-32)/1.8`. `input_links()` returns the two TetrAMM links (INPA, INPB) separately and `build()` omits them, so the installer sets them last, after commissioning. Until then, in a fresh commissioning, the flux slot shows the TEST-CURRENT flux (2400 + 1600 nA) for a few seconds before the links are written; a re-run of a commissioned lane shows frozen last values instead (the slots are disabled).
- **Letter map.** Rule: a computed letter may use only input letters and earlier letters (`check_letter_order()`; no state letters in this lane).

  | Slot | Inputs | Computed |
  |---|---|---|
  | flux 9 | A ch3 nA, B ch4 nA, C E keV, D hutch °F, E pressure kPa (`userTran1.G`), F dark nA (hand value 0) | G net current A `MAX(A+B-F,0)*1E-9`; H T °C; I density; J ln E; K μ_en/ρ; L μ/ρ (the MonP cubics with the log letter J); M absorbed fraction `1-EXP(-5*K*I)`; O raw-current fault 0/1, NaN-safe `A+B>=-5&&A<118800&&B<118800?0:1`; **P formula flux** `G*2.17205E17/C/M*EXP(-5*L*I)`; N unused |
  | bounds 10 | A flux.P, B flux.C (then E_eff), D flux.G, I flux.I, P plates (1 = horizontal) | C wall-loss fraction; E/F/G recombination loss at central/low/high aspect; H, J low/high denominators; K LOW; **L RESULT** `A/(1-C)/(1-E)`; M HIGH; N up %; O down % |
  | flags 11 | A energy, B raw fault (flux.O), C pressure age (`userTran3.H`), D net current A, E central recombination (bounds.E) | F bit 1, G bit 2, H bit 4, I bit 8, J bit 16, K bit 32, **L code** |

  Bounds follow `fluxor.core.evaluate`: low = A·LF/((1−max(.9C−.07,0))(1−r_low)), high = A·HF/((1−C−min(.09, 2C+.05[E_eff>13]))(1−r_high)), RESULT = A/(1−C)/(1−r_central). The registry says the recombination correction is on the best estimate (user, 2026-11-16).
- **Flag bits** (same code layout as the C-station lanes, so one screen design serves all): 1 E above 12.5 keV; 2 central recombination above 5 % (about 14 µA of total current on the present assumed beam aspect, so ordinary E-station currents do not set it); 4 pressure age above 7200 s; 8 net current below 50 nA (low current: the stated bounds understate the uncertainty, MINOR; the TetrAMM noise plus the 1 nA dark sigma is about 3 % of the current at 50 nA; the lane agrees with `fluxor.core.evaluate` within 1 % on low/high from 49 nA up and within 2 % from about 32 nA); 16 E outside 4.9–30.5 keV or NaN (MAJOR, `A>=4.9&&A<=30.5?0:1`); 32 raw sum below −5 nA, a channel at/above 99 % of full scale, or NaN (MAJOR). Bits 16 and 32 are written so a NaN input sets them. The status calcout is `A` with HIGH 0.5 MINOR and HIHI 15.5 MAJOR.
- **Known behaviour.** (1) Bit 32 tests the raw sum A+B against −5 nA (not 0), so zero-beam noise does not flicker MAJOR. (2) The two TetrAMM channels are summed; fluxor's per-channel split is not in the slot. (3) At zero or negative net current RESULT and both bounds are 0 (fluxor widens the high bound by the absolute noise there; the slot does not; bit 8 covers the region below 50 nA). (4) At E = 0 the flux and bounds are published as inf (LN(0) is −inf) and bit 16 is MAJOR; at E above about 60 keV HIGH can fall below RESULT (also MAJOR by bit 16). (5) A NaN input (a dead TetrAMM) makes the flux NaN (the calc MAX/MIN propagate NaN, as in EPICS) and sets bits 16 or 32: MAJOR.
- **Mirror and test:** `evaluate_lane(inputs)` runs the installed strings through `calc/calc_eval.py` (an EPICS-calc evaluator: unary minus binds tighter than `^`, so `EXP(-(x)^p)` is NaN, the trap above). `calc_eval` is proven against the MonP expressions (`monp_transform.SLOT`, `quality_slots.BOUNDS`, `FLAG_BITS`). `python -I -X utf8 calc/estation_lane.py` is the self-test: lengths ≤ 39, no NaN/inf on a grid, and the lane against `fluxor.core.evaluate` (formula within 1 % at 5–20 keV and 2 % to 30 keV, RESULT/low/high within 2 %) at 0.5/3/4/100 µA, 8/10/20/30 keV, three gas states, two darks. Measured worst: formula 0.22 % (5–20 keV) and 0.60 % (30 keV), RESULT 0.60 %, low 0.40 %, high 0.79 %.
- **Installer (`calc/install_lane.py --lane EStn`; offline-tested in `tests/test_install_estation.py` against a fake `epics` module and an in-memory IOC that evaluates the slot strings with `calc/calc_eval.py`).** Modes: `--dry-run` (read-only occupancy check, then every write in order, then nothing written), default install, `--compare` (read-only), `--remove` (with `--dry-run` to list). MonP/MonC are unchanged: `--compare` is the old loop (now `_compare_entries`) and the install loop is the old one; `estation_lane` (and so fluxor) is imported lazily, only for EStn.
  - **Preflight (all modes).** Reads `HEARTBEAT`, then each of the four slots and classifies it. **ours**: DESC ends `(xray_fluxor)`. **free**: DESC is exactly the real default (`user Transform N`; for a calcout the bare record name, e.g. `userCalcOut9`) AND no INPx, CLCx or OUTx is set (a calcout's CALC `0` and empty OUT count as unset; comments CMTx, values, PREC, COPT and EGU are not looked at: a free transform has CMTA-P = `a`..`p`). **foreign**: anything else, including a foreign DESC with nothing else set, an empty DESC, and the default DESC with a link or expression set. Any foreign slot: exit 1 before anything is written (install, dry-run and remove all refuse the same way). `slotlib.install()` repeats its own, weaker guard per slot; that guard is unchanged for MonP/MonC.
  - **Install order and commissioning (fresh lane).** flags, status, flux, bounds through `slotlib.install()` (Enable off, write and read back every field, hand values, Enable on, two scans, verify, NaN check). The flux slot differs from MonP: it is installed with INPA and INPB (the two TetrAMM links) **empty**, the hand values A=2400.0 and B=1600.0 nA (test currents), and F=0 (dark) only in a fresh slot or with `--reset-values` (a re-run keeps a hand-entered dark). The formula is verified on those test currents with live energy, temperature and pressure. Only after all four slots are verified are A and B zeroed, then INPA and INPB written (`estation_lane.input_links()`, bare, 36 characters) and read back (the string is reported). Why: the formula can then be checked against the mirror on known numbers, with no dependency on the TetrAMM, and no test current is left to look like a flux if the TetrAMM is down. While the test currents are on, `userTran9.P` (the formula) shows a test flux for about 3 to 10 s (a few scans per slot plus the verifications); the other three slots of a FRESH lane are not yet consuming it.
  - **Re-run of a commissioned lane** (flux slot ours AND both TetrAMM links already in place): all four slots are put to Enable 0 first (flux first), before anything is rewritten; each is re-enabled only as it verifies; the TetrAMM links are NOT cleared and no test currents are used (the slots are verified on the live currents, as MonP is). Consumers therefore see the last real values frozen (disabled records keep their values, no alarm update) for roughly 10 to 20 s, never a fake flux. A re-run whose links are not both in place (for example after a failed install) is a fresh commissioning. Do not re-run during a measurement.
  - **Failure cleanup order.** If test currents were put: A and B are zeroed while the flux slot is still enabled, one scan is waited (flux P and, through it, bounds L recompute to 0), then Enable 0 on flux, one scan, then bounds, flags, status. Every step is attempted even if another fails; the summary lists any write that failed (`cleanup is INCOMPLETE`) and says to set those PVs by hand. `--remove` zeroes the letters (including P and L) explicitly, so it leaves no stale values.
  - **Live-link verification.** `verified on live currents` is printed only if the slot's SEVR is not INVALID, this PC reads the two currents with a total above `LIVE_FLOOR_NA` (5 nA) and the slot's A and B agree with them. Beam off (total at or below the floor) or SEVR INVALID are warnings (exit 0) without that line.
  - **Failure handling (every failure path, including a caput that returns failure, a link that does not read back as written, a verifier mismatch, a final-check mismatch and any exception).** Every slot this run touched is put to Enable 0 (flux first; a failing disable does not stop the others), A and B of the flux slot are zeroed if the test currents were put there, then `LANE FAILED: ... fix the cause and re-run, or run --lane EStn --remove` is printed and the exit code is 1. The TetrAMM links are only ever written after all four slots verified.
  - **Link readback.** A bare DB link may read back with the default modifiers appended (`PV NPP NMS`, cut at 39 characters). `slotlib.strings_match(back, value, field)` treats a modifier-less written link as equal to that form (only the default modifiers, possibly cut), and ONLY for link fields (`INP*`, `OUT*`): every other comparison, in MonP/MonC and here, is exact. The post-write check compares the PV name (first token). The real string on the IOC is reported at install; confirm it at the supervised install (open item).
  - **TetrAMM IOC down, or invisible to the utilioc.** The final check reads the two source PVs from THIS PC. If either does not answer: `WARNING`, `LANE OK (with 1 WARNING)`, exit 0; the slot is enabled with its links set (Enable and link strings confirmed), the flux is INVALID and 0, and the formula was NOT verified on live currents. If both answer, the slot's A and B must agree with them (relative 1e-3 plus 0.5 nA, one re-read allowed for scan drift): if they do not (this PC reaches the TetrAMM but the utilioc does not: links INVALID or stale), `WARNING: the utilioc does not see the TetrAMM` and exit 0, again without claiming verification. Only when they agree is the formula verified on the live currents and `verified on live currents` printed; a mismatch there is `LANE FAILED` (slots disabled, exit 1). After a warning, start the TetrAMM IOC (or fix the route) and run `--compare`.
  - **Verifiers** (`v_estn_flux/bounds/flags/status`): flux: every computed letter against `estation_lane.evaluate_lane` on the slot's own A-F, relative 1e-3 with an absolute guard of 1e-30 for zeros; bounds: every computed letter of `EXPR["bounds"]` run on the slot's own A, D, I, P and the **raw energy read from `flux.C`** (B is E_eff in the slot), plus the plates constant P; flags: the six bits and the code exactly; status: VAL equals the code and SEVR equals `quality_slots.severity(code)`.
  - **`--compare`.** Field by field against `estation_lane.build()` plus the two TetrAMM links. The dark hand value F is compared only when the slot is not ours (a slot that is ours keeps the operator's value).
  - **`--remove`.** Only slots that are ours; free slots are skipped; a foreign slot refuses the whole run. All Enables go off first, then each slot is restored to the REAL free default read from the live IOC on 2026-11-16: transform SCAN Passive, PREC 3, COPT Conditional, EGU empty, INPx and CLCx empty, **CMTA-P the lower-case letters a-p**, letters A-P put to 0, DESC `user Transform N`, then Enable **1** (a free slot reads Enable 1, with empty expressions it does nothing). Calcout: INPA-L empty, CALC `0`, SCAN Passive, PREC 5, EGU empty, HIGH/HIHI/HYST 0, HSV/HHSV NO_ALARM, OOPT `Every Time`, DOPT `Use CALC`, OCAL `0`, OUT empty, A-L and VAL put to 0, DESC the bare record name, Enable 1. A put of a computed letter or VAL that the IOC refuses is reported and ignored; any other refused put stops the remove (`REMOVE FAILED`, the slots stay disabled; exit 1). The test compares the whole fake record to the default dict after install then remove.
  - **Writes are confined** to the four records (`userTran9/10/11`, `userCalcOut9`, and their `Enable`): `_guard_write()` refuses any other PV in every EStn write outside `slotlib.install()` (links, zeroing, cleanup, remove), `slotlib.install()` refuses any target outside `15IDC:util:`, and the tests assert it on the fake.
  - **Source PV validation.** `estation_lane.validate_pvs()` (called by `load_pvs`, `build`, `input_links`): each of the four source names must match `[A-Za-z0-9_:.-]+` (no whitespace, so no trailing ` PP`/` CPP`) and must not start with `15IDC:util:`; the error names the key, never the value.
  - **`--compare` and an unreachable IOC.** `--compare` reads `HEARTBEAT` first: if it does not answer it prints `utilioc not reachable` and exits 2 (not N differences).
  - **Transcripts contain the real source PV names.** The dry-run, the install and the error output print the TetrAMM, energy and temperature links (INPA-INPD) as written. Do not paste an installer transcript into a tracked file.
  - **Seen against the real IOC (2026-11-16):** a bare link reads back as the name plus ` NP` (cut at 39 characters; the link itself is whole and connected); a real TetrAMM-down install run gave `LANE OK (with 1 WARNING)` with the slot Enabled and INVALID; after the IOC came back the utilioc link recovered by itself within minutes (CA link search backoff). **Still not shown:** whether the IOC accepts a put of the computed letters and VAL in `--remove` (a refused put there is reported and ignored).
- **Privacy:** the tests check that the new and edited tracked files contain none of the real source PV names (nor the values in the local file).

## Open items
- If the background should *not* go stale on gain changes that the user re-zeroes by hand, consider storing it in amps (userTran2.P) and converting at the current gain.
- Collection length: done 2026-11-13 (M2 closed). l = l_eff = 6.19 cm is in the formula. The symmetric ±1.4 % term is tested against `quality_slots.collection_term()`. If the chamber is remeasured, re-run `analysis/collection_length_cmc.py --h 0.05` and re-set `monp_transform.L_CM`; the test flags a mismatch over 0.1 %.
- METHOD_REVIEW.md: M1–M9 are closed except M4's plate-material part (backscatter allowance; the plates are aluminium per the user). N1–N5 (second round) are open; see that file.
- Wall loss per chamber: done 2026-11-13. To redo it after a geometry change: `analysis/wall_loss_families.py` (22 MC runs, ~6 min with 4 jobs), then `analysis/wall_loss_fit.py`. It prints the rounded fit per lane; copy it into `quality_slots.WALL_FITS`, re-run until PASS, then install both lanes. MonP's beam position in its gap is ASSUMED centred (not measured).
- Plate orientation per lane: `lanes.LANES[lane]["plates"]`, published as the constant `userTran3.M` / `userTran6.M` (0 vertical, 1 horizontal) and re-asserted at every install. `lanes.py` checks it against `cmc_chamber_geometry.py`.
