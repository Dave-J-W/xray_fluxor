# CHAMBER_FACTS.md: the register of MonP and MonC facts

This is the one place the facts about the two ion chambers and their electronics are listed (user, 2026-11-13: one register, METHOD_REVIEW C1 option (a)). Other documents cite a row by its ID, for example "gap 10.85 mm (CHAMBER_FACTS F1.5)". They don't restate a value without its ID.

**How it stays true.**
- **Defined in** names the file that holds the value. Where that is code or a generated table, the code is what the live calc uses, and the **Check** cell is an expression that `analysis/check_chamber_facts.py` evaluates there. Run the script after any change to a fact or to its source:
  ```
  <bluesky venv>\Scripts\python.exe -X utf8 analysis/check_chamber_facts.py
  ```
  It must report PASS. A row that differs from its source fails it.
- Check = **register** means no file defines the value: this register is its home (operating state, observations, prose-only numbers). Only the IDs listed in the script's REGISTER_ONLY may say so; the script fails on any other, and on any row that doesn't have 9 cells. Change it here first, then any document that cites it.
- When a fact changes:
  1. change its source;
  2. change the row here, keeping the old value in the Source cell ("was …");
  3. run the check;
  4. grep the docs for the row ID and fix any sentence that uses it.
- **Tags:**
  - MEASURED: the user's reading or a recorded measurement.
  - OBSERVED: a state or a rate seen at a given time.
  - ASSUMED: not measured; a placeholder that something depends on.
  - INTERPRETED: our reading of the user's words.
  - DERIVED: computed from other rows.
  - MODEL: the output of a model run.
  - LIVE: a constant of the live calc.
  - DECISION: a decision of the user's, quoted in PLAN.md.
- MonC was measured by hand. MonP is the same design (user), mounted with its plates turned 90°. Values seen only on MonC are marked "(MonC)".

Columns: ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check

## 1. Chamber: dimensions, electrodes, mounting
The full parameter list, with every value tagged, is in `analysis/cmc_chamber_geometry.py` (PARAMS, `derived()`, `slot_fit()`). The figures, the collection-length model, the MC families and the `lanes.py` plate check all import it. These rows are the facts other documents quote.

| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F1.1 | Design: CMC-custom, guarded. Collector = upper plate (BNC centre pin); HV = lower plate; Al guard blocks beside the collector, grounded to the shell | upper | | | MEASURED | 2026-11-13, user, meter checks (MonC) | `cmc_chamber_geometry.py` signal_plate | `cg.v("signal_plate")` |
| F1.2 | MonP mounting: plates vertical, E-vector toward the plates | vertical | | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` monp_plates | `cg.v("monp_plates")` |
| F1.3 | MonC mounting: plates horizontal, E-vector along the plates | horizontal | | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` monc_plates | `cg.v("monc_plates")` |
| F1.4 | Collector (upper plate) length along the beam | 60.5 | mm | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` | `cg.v("upper_plate_length")` |
| F1.5 | Plate gap, inner face to inner face, at the beam track | 10.85 | mm | 0.2 at the track; 0.5 across the width | MEASURED | 2026-11-13, user (11.45 mm lower plate to guard face, less ~0.6 mm); was "about 1 cm" | `cmc_chamber_geometry.py` plate_gap | `cg.v("plate_gap")` |
| F1.6 | HV (lower) plate length along the beam | 75.5 | mm | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` | `cg.v("lower_plate_length")` |
| F1.7 | Plate width, across the beam | 60.0 | mm | | MEASURED | 2026-11-13, user ("about 6 cm") | `cmc_chamber_geometry.py` | `cg.v("plate_width")` |
| F1.8 | Plate thickness (aluminium) | 1.0 | mm | | MEASURED | 2026-11-13, user (revised from 1/16") | `cmc_chamber_geometry.py` | `cg.v("plate_thickness")` |
| F1.9 | Collector-to-guard gap, at each end | 1.0 | mm | | MEASURED | 2026-11-13, user ("about 1 mm") | `cmc_chamber_geometry.py` block_gap | `cg.v("block_gap")` |
| F1.10 | Guard set-back from the collector plane, away from the gap | 0.51 | mm | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` block_recess | `cg.v("block_recess")` |
| F1.11 | Guard block thickness (they sit directly on the shell) | 12.7 | mm | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` | `cg.v("block_thickness")` |
| F1.12 | Upper plate face inside the aperture's top ledge (its 1 mm thickness straddles the ledge) | 0.6 | mm | | MEASURED | 2026-11-13, user (straddle confirmed) | `cmc_chamber_geometry.py` | `cg.v("upper_plate_inset_from_aperture_top")` |
| F1.13 | Window aperture: machined slot, height | 12.8 | mm | | MEASURED | 2026-11-13, user, calipers; ends semicircles of radius 6.4 mm | `cmc_chamber_geometry.py` | `cg.v("window_aperture_h")` |
| F1.14 | Window slot length, reconciled (exterior width held fixed) | 64.48 | mm | | DERIVED | from the user's four slot readings, least squares | `cmc_chamber_geometry.py` slot_fit() | `cg.slot_fit()["W"]` |
| F1.15 | Shell exterior: along the beam × width × height | 95.16 × 101.4 × 44.5 | mm | 0.2, 0.25, 0.25 | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` | `(cg.v("exterior_length"), cg.v("exterior_width"), cg.v("exterior_height"))` |

## 2. Beam position and size
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F2.1 | Beam below the aperture top, from the Kapton scar (MonC) | 5.5 | mm | | MEASURED | 2026-11-13, user | `cmc_chamber_geometry.py` | `cg.v("beam_below_aperture_top")` |
| F2.2 | Beam to the collector's face (MonC) | 4.90 | mm | | DERIVED | F1.5, F1.12, F2.1 | `cmc_chamber_geometry.py` derived() | `d["beam_to_upper_inner_face"]` |
| F2.3 | Beam to the HV plate's face (MonC) | 5.95 | mm | | DERIVED | F1.5, F1.12, F2.1 | `cmc_chamber_geometry.py` derived() | `d["beam_to_lower_inner_face"]` |
| F2.4 | Beam offset from mid-gap, toward the collector (MonC; used by the MonC MC) | 0.525 | mm | | DERIVED | F2.2, F2.3 | `cmc_chamber_geometry.py` derived() | `fam["MonC"]["offset_mm"]` |
| F2.5 | MonP beam offset from mid-gap | 0.0 | mm | | ASSUMED | not measured on MonP; the MonC scar does not apply | `cmc_chamber_geometry.py` monp_beam_offset | `fam["MonP"]["offset_mm"]` |
| F2.6 | Beam inboard of the plate width centre | 2.0 | mm | | MEASURED | 2026-11-13, user (MonC) | `cmc_chamber_geometry.py` | `cg.v("beam_inboard_of_plate_centre")` |
| F2.7 | Vertical beam size, FWHM (across MonC's gap; mid value of 0.02–0.04) | 0.03 | mm | 0.01 | MEASURED | user | `cmc_chamber_geometry.py` beam_fwhm_vertical | `fam["MonC"]["fwhm_mm"]` |
| F2.8 | Horizontal beam size, FWHM (across MonP's gap) | 1.0 | mm | | MEASURED | user ("~1 mm") | `cmc_chamber_geometry.py` beam_fwhm_horizontal | `fam["MonP"]["fwhm_mm"]` |
| F2.9 | Polarization: E-vector horizontal | horizontal | | | MEASURED | user | `cmc_chamber_geometry.py` | `cg.v("polarization")` |

## 3. High voltage
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F3.1 | Chamber HV (both chambers), from the supply readout; not verified at the chamber | 2.7 | kV | | OBSERVED | user | `cmc_chamber_geometry.py` hv | `cg.v("hv")` |

## 4. Collection length
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F4.1 | Effective collection length l_eff of the guarded collector, 2-D Laplace + field lines at 0.05 mm grid | 61.925 | mm | | MODEL | `analysis/collection_length_cmc.py`, 2026-11-13 | `analysis/out/collection_length_cmc.csv` nominal | `leff` |
| F4.2 | Length used in the live flux formula (L in CLCO/CLCP) | 6.19 | cm | | LIVE | from F4.1; self-test within 0.1 % | `calc/monp_transform.py` L_CM | `mt.L_CM` |
| F4.3 | Collection-length uncertainty: model spread over the dimension tolerances plus 0.5 % for the 2-D model | 1.36 | % | | DERIVED | COLLECTION_GROUPS, incl. the ±0.2 mm gap | `calc/quality_slots.py` collection_term() | `100 * qs.collection_term()` |
| F4.4 | Collection-length term carried in the live budget | 1.4 | % | | LIVE | ≥ F4.3 | `calc/quality_slots.py` SYMMETRIC_TERMS | `100 * qs.SYMMETRIC_TERMS["collection length (guarded)"]` |
| F4.5 | Change in the flux reading when the beam moves 1 mm across the gap, toward the collector and toward the HV plate (through l_eff; at every energy, on top of any wall-loss change; MonC: a vertical move, MonP: horizontal) | +0.28, −0.20 | % | | MODEL | 2-D model, 2026-11-13; used in UNCERTAINTY.md §4.1 and `unc10_summary` (2026-11-17) | `analysis/out/collection_length_cmc.csv` beam_z_±1 | `[lcase("beam_z_+1", "flux_deficit_pct"), lcase("beam_z_-1", "flux_deficit_pct")]` |

## 5. MonC SR570 per-gain calibration
Lives in `data/calibration/monc_sr570_ranges.csv`: factor, u, dark and dark sd per gain. It is generated by `analysis/make_monc_calibration.py` from a hashed step log, measured on MonC's SR570 unit as installed 2026-11-12 with the chamber cabled. The live calc doesn't use it yet: `calc/monc_gain_cal.py` is a draft, and the live budget carries F5.3 at every gain. MonP's SR570 has not been measured. The rows below are the values other documents quote.

| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F5.1 | Offset-off dark, chamber cabled, at 200 nA/V, 500 nA/V, 1, 2, 5, 10, 20 µA/V (includes F6.2 and the 8.4 Hz V2F zero) | 538.6, 217.3, 111.6, 94.6, 20.0, 13.6, 604.7 | Hz | | MEASURED | 92 overnight passes, 2026-11-12/13 | calibration CSV dark_Hz | `[cal[s]["dark_Hz"] for s in ("200 nA/V", "500 nA/V", "1 uA/V", "2 uA/V", "5 uA/V", "10 uA/V", "20 uA/V")]` |
| F5.2 | Dark scatter per gain selection (pass-to-pass sd), same gains as F5.1 | 21.6, 7.8, 3.8, 2.5, 1.0, 0.6, 18.9 | Hz | | MEASURED | 92 overnight passes | calibration CSV dark_sd_reselect_Hz | `[cal[s]["dark_sd_reselect_Hz"] for s in ("200 nA/V", "500 nA/V", "1 uA/V", "2 uA/V", "5 uA/V", "10 uA/V", "20 uA/V")]` |
| F5.3 | Electronics term in the live budget (SR570 gain × V2F scale, incl. V2F input loading; type B) | 0.7 | % | | LIVE | user 2026-11-13, "Merge, use 0.7 %" | `calc/quality_slots.py` SYMMETRIC_TERMS | `100 * qs.SYMMETRIC_TERMS["electronics"]` |
| F5.4 | Gain factor per gain, relative to the mean SR570 CAL level, at 500 nA/V, 1, 2, 5, 10, 20 µA/V (unmeasured gains: 1, with u 0.7 %) | 1.00060, 1.00216, 0.99859, 0.99976, 1.00124, 1.00599 | | | MEASURED | overnight grids g2–g4, `monc_grid.py` | calibration CSV factor | `[cal[s]["factor"] for s in ("500 nA/V", "1 uA/V", "2 uA/V", "5 uA/V", "10 uA/V", "20 uA/V")]` |
| F5.5 | Statistical uncertainty of F5.4, same gains (the absolute CAL scale is in F5.3) | 0.010, 0.009, 0.020, 0.013, 0.015, 0.030 | % | | MEASURED | the same | calibration CSV u_factor_rel | `[100 * cal[s]["u_factor_rel"] for s in ("500 nA/V", "1 uA/V", "2 uA/V", "5 uA/V", "10 uA/V", "20 uA/V")]` |
| F5.6 | Range-to-range gain relative to 5 µA/V, at 500 nA/V, 1, 2, 10, 20 µA/V (the step a scan sees across a gain change if the nominal ratio is used) | +0.08, +0.24, −0.12, +0.15, +0.62 | % | | DERIVED | F5.4 | calibration CSV factor | `[100 * (cal[s]["factor"] / cal["5 uA/V"]["factor"] - 1) for s in ("500 nA/V", "1 uA/V", "2 uA/V", "10 uA/V", "20 uA/V")]` |

## 6. Leakage and the chamber connection offset (MonC, 2.7 kV)
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F6.1 | Chamber leakage current (zero within error) | -2.6 | pA | 12.8 | MEASURED | leakage run 2026-11-13 12:09–12:26, `analysis/monc_leak.py`; ELECTRONICS_CONCLUSIONS.md §1, §5 | calibration CSV header | `hdr(r"leakage current (-?[\d.]+) \+-")` |
| F6.2 | Output-side offset from the cabled chamber, the same at every gain and when blanked (not a current) | 21.5 | Hz | 1.3 | MEASURED | the same run | calibration CSV header | `hdr(r"include \+([\d.]+) \+- [\d.]+ Hz")` |

## 7. MonC operating state
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F7.1 | MonC SR570 setting: interim operation, 5 µA/V, offset CAL +2 nA ON | 5 µA/V CAL +2 nA | | | OBSERVED | re-set 2026-11-13 08:10 after the overnight grids (first set 2026-11-12 15:20:44); `tools/monc_hold.py interim_5uA_cal2nA` | register | register |
| F7.2 | **MonC chamber cabling: DETACHED.** The chamber is unplugged, with the BNC cable end open, so MonC sees no beam signal and the MonC lane's flux is not a beam measurement | detached | | | OBSERVED | unplugged 2026-11-13 10:13; the user confirmed it was still detached on 2026-11-13 at ~16:55 | register | register |
| F7.3 | MonC no-beam rate at F7.1, chamber detached | 38.5 | Hz | 0.1 | MEASURED | 2026-11-13 10:16–12:09, 5-min means; figure elec5 | register | register |
| F7.4 | MonC no-beam rate at F7.1, chamber cabled (≈ F7.3 + F6.2 = 60.0; the two windows differ by 0.9 Hz, inside F6.2's ±1.3) | 59.1 | Hz | 0.1 | MEASURED | 2026-11-13 08:11–10:13; overnight 60.2 ± 0.6 over 91 holds | register | register |

## 8. Electronics conclusions (MonC, and MonP by assumption)
These live in `ELECTRONICS_CONCLUSIONS.md`, with the evidence in `data/sweeps/monc_sweep1_results.md` and figures elec1–elec5 (`analysis/figures/`): linearity, noise, drift, temperature, settling, the floors and the state errors. Only the floors are quoted elsewhere:

| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F8.1 | V2F rate at zero input (SR570 off) | 8.4 | Hz | | MEASURED | 47 min SR570-off record, 2026-11-12 | register | register |
| F8.2 | Count rate for a negative SR570 output (clipped) | 1 | count | | MEASURED | the same | register | register |

## 9. Symmetric uncertainty budget (live)
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F9.1 | μ_en/ρ tables (spread of NIST vs Chantler/Elam) | 3.0 | % | | LIVE | `data/queries/` | `calc/quality_slots.py` SYMMETRIC_TERMS | `100 * qs.SYMMETRIC_TERMS["mu_en/rho tables"]` |
| F9.2 | W(N₂) (full spread of five sources, as 1 σ) | 0.6 | % | | LIVE | physics_note.md §2.1 | the same | `100 * qs.SYMMETRIC_TERMS["W"]` |
| F9.3 | Gas density, live P and T | 0.2 | % | | LIVE | calc/PRESSURE.md | the same | `100 * qs.SYMMETRIC_TERMS["density (live P, T)"]` |
| F9.4 | Cross-section fit in the calc vs log-log NIST (worst at 25 keV) | 0.9 | % | | LIVE | monp_transform self-test | the same | `100 * qs.SYMMETRIC_TERMS["cross-section fit"]` |
| F9.5 | Quadrature total σ_s, with F4.4, F5.3 and F9.7 | 3.58 | % | | DERIVED | was 3.56 before F9.7 (2026-11-17) | `calc/quality_slots.py` OTHER_TERMS | `100 * qs.OTHER_TERMS` |
| F9.6 | Live bound factors, high and low (CLCE, CLCD) | 1.036, 0.964 | | | LIVE | 1 ± σ_s, rounded outward | `calc/quality_slots.py` | `(qs.HIGH_FACTOR, qs.LOW_FACTOR)` |
| F9.7 | Mono energy readback: an assumed 0.1 % energy error × the largest d ln Φ / d ln E over 5–30 keV (3.7, MonP best estimate at 29.5 keV; 2.2 below 15 keV), rounded up | 0.4 | % | | ASSUMED | user 2026-11-17, "Add the term"; no edge scan yet; UNCERTAINTY.md | `calc/quality_slots.py` SYMMETRIC_TERMS | `100 * qs.SYMMETRIC_TERMS["energy readback"]` |

## 10. Wall loss (photoelectrons reaching the plates)
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F10.1 | MonP wall-loss fit (E0 keV, s keV, p) of f_pe × MC, 10.85 mm gap, plates vertical | 17.9, 19.7, 1.17 | | | LIVE | refit 2026-11-13 (METHOD_REVIEW Q1), 140/140 gated | `calc/quality_slots.py` WALL_FITS | `qs.WALL_FITS["MonP"]` |
| F10.2 | MonC wall-loss fit, plates horizontal, beam F2.4 | 18.1, 27.0, 1.41 | | | LIVE | the same | `calc/quality_slots.py` WALL_FITS | `qs.WALL_FITS["MonC"]` |
| F10.3 | Band constants a, b, cap, k, floor, e_widen (keV) | 0.9, 0.07, 0.09, 2, 0.05, 13 | | | LIVE | METHOD.md §7(f) | `calc/quality_slots.py` BAND | `tuple(qs.BAND.values())` |
| F10.4 | Three-change MC stress corner outside the band: accepted risk | accepted | | | DECISION | user 2026-11-13, "Yes, both" (PLAN.md; METHOD_REVIEW N1) | register | register |

## 11. Gas references
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F11.1 | MC reference density ρ₀ (N₂ at 99.26 kPa, 24.9 °C) | 1.1221e-3 | g/cm³ | | LIVE | CLCB | `calc/quality_slots.py` RHO0 | `qs.RHO0` |
| F11.2 | Site-mean pressure at 228 m (fresh-install value of the pressure input) | 98.99 | kPa | | MEASURED | `analysis/out/pressure_climatology.txt` | `calc/monp_transform.py` SLOT | `mt.SLOT["values"]["G"]` |
| F11.3 | W(N₂) used in the formula | 34.8 | eV | | LIVE | physics_note.md §2.1 | `calc/monp_transform.py` W_EV | `mt.W_EV` |
| F11.4 | Lowest gas density seen at the site, relative to ρ₀ | 0.95 | | | DERIVED | 2025 minimum pressure × hutch maximum temperature | `calc/quality_slots.py` RHO_MIN_OVER_RHO0 | `qs.RHO_MIN_OVER_RHO0` |

## 12. Status bit 1 (wall-loss band in use)
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F12.1 | Bit 1 threshold on the raw energy (CLCF), both lanes | 12.5 | keV | | LIVE | 2026-11-13 (METHOD_REVIEW N2; was 12.6, and 13.5 before that) | `calc/quality_slots.py` FLAG1_E_KEV | `qs.FLAG1_E_KEV` |
| F12.2 | Density the bit 1 threshold is designed for, relative to ρ₀ | 0.934 | | | LIVE | 1.6 % below F11.4 | `calc/quality_slots.py` RHO_FLAG1_OVER_RHO0 | `qs.RHO_FLAG1_OVER_RHO0` |

## 13. MonP dark
| ID | Fact | Value | Unit | ± | Tag | Date, source | Defined in | Check |
|---|---|---|---|---|---|---|---|---|
| F13.1 | MonP no-beam rate at 500 nA/V (archived, 2026-11-12 12:42–13:34: 227 ± 33, 182, 192 Hz). The live calc subtracts the measured dark | 182–227 | Hz | | OBSERVED | archiver; the table in calc/OPERATOR.md | register | register |

## Not known yet
- MonP's beam position in its gap (F2.5 is ASSUMED centred). The 1 mm offset variant of the wall-loss band covers up to 1 mm off centre, but the N1 stress corner (F10.4) is the case where that matters.
- The HV at the chamber (F3.1 is the supply readout).
- Plate-material backscatter (the MC ignores it; the band's lower edge allows for it; METHOD_REVIEW M4).
- MonP's SR570 grid (section 5 is MonC only).
- The monochromator's energy readback error (F9.7 assumes 0.1 %). An edge scan (a foil K edge) at the working energy would measure it.
