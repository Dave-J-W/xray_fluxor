# METHOD review: checks and corrections (handoff to Architect)

*Written 2026-11-13 by the METHOD.md session. It reviews the photons/s calculation as written up in `METHOD.md`.*
- **Round 1 (M1–M9)** was against HEAD 971a71c; the line references in §2 are to that commit.
- Architect then worked the M-series (commits 1f7b838 and 2d9fcc2).
- **Round 2** (§1b and §3, against HEAD 2d9fcc2) re-checks each closure independently and adds findings N1–N5.
- **Round 3** (§1c and §4, against **HEAD 9fff096**, the measured guarded chamber) re-derives every worked number, checks the status of M2 and N1–N5, and adds findings Q1–Q5.
- **Round 4** (§1d and §5, against **HEAD fea6dae**, which carries Architect's Q1–Q4 work in a84c2ca) runs the closing checks of Q1–Q5, re-checks N1 and N2, and adds findings R1–R4.
- **Consolidation audit** (§6, against **HEAD 1a06b94**, re-checked at 59bcea2) is the user's request of 2026-11-13: "make sure there is one place where all that knowledge lives and that no stale numbers live elsewhere". §6 inventories where each MonP/MonC fact lives, and findings C1–C10 list the stale copies. As reviewer, this session fixes none of them.
- **Round 5** (§7, against **HEAD 961c2e4**) runs the closing checks of Q2, Q5, R1–R4, N1, N2 and C1–C10, all worked by Architect (1a06b94, 59bcea2, 929a5bb, 961c2e4), and adds findings S1–S3. **Round 6** (e7a6d69) closes S1–S3; every finding in this file is now closed or accepted.

This session fixes nothing in Architect's files. Since 2026-11-13 it is the reviewer (user: "For now you are a reviewer, since that's simpler to collaborate with."): it writes only this file, and METHOD.md is Architect's.

**How to use this.**
- Each finding gives the defect, a failure scenario, the severity, a proposed fix and the closing check (CLAUDE.md format). A finding is closed when someone has run its closing check and logged the result.
- Anything that changes a live slot needs the user's OK and an installer run. Accepting a bias or a risk instead of fixing it is the user's call, recorded as a plan-change row.
- **Effect on METHOD.md:** METHOD.md quotes the live constants and the worked numbers built from them. After a constant changes, METHOD.md §6, §7 and §9 need the new numbers. Tell this session or the user, or update them in the same commit. As of 9fff096 they are current: round 3 recomputed them all from the live strings. As of fea6dae they are current except for the items in R1 and R2.
- The figures in `figures/` import upstream constants. They follow any change, but must be regenerated.

---

## 1. Checks run (read-only, bluesky venv, `-I -X utf8`)

| Check | Round 1 (971a71c) | Round 2 (2d9fcc2) |
|---|---|---|
| `calc/monp_transform.py` | **PASS**. Every expression ≤ 39 characters. Calc vs full NIST: worst 0.554 % at 5–20 keV, 0.890 % at 5–30 keV (at 25 keV); the gates are 1 % / 2 % | **PASS**, the same figures (the physics is unchanged) |
| `calc/quality_slots.py` | **PASS**: 8 flag cases. Bounds +3.0 / −14.0 % at 10 keV and +18.6 / −29.7 % at 30 keV (Λ = 0.505 at ρ₀) | **PASS**: +3.4 / −14.0 % at 10 keV and +24.5 / −29.5 % at 30 keV (Λ_s = 0.469 at ρ₀). Symmetric terms 3.35 %, so HIGH_FACTOR 1.034; LOW_FACTOR 0.86 allows δ ≤ +15.7 %; bit 1 at 12.6 keV, "never" clear while the band is widened |
| `calc/lanes.py` | **PASS**: no string too long, both lanes | **PASS** |
| `calc/background_transform.py` | **PASS**: converges to 59.9 Hz, then to 25.3 Hz after the gain change | **PASS**, the same |
| `data/queries/crosscheck_calculators.py` | Run on a scratch copy, because it rewrites two tracked CSVs. Both outputs were **byte-identical** to the committed files | Not re-run: its inputs and `data/queries/` are unchanged since round 1 |
| `analysis/wall_loss_fit.py` | n/a | Not run: it rewrites the tracked `analysis/out/wall_loss_fit.txt`. Its claims were re-derived independently instead (§1b) |
| Independent recomputation | A scratch script reproduced every worked number in METHOD.md | A new scratch script evaluates the **live expression strings themselves** with its own calc evaluator, rather than the Python mirror. It agrees with `quality_slots.bounds()` to 1e-12 and reproduces every worked number in METHOD.md (below) |

**Reference numbers** for re-checking after any further change (500 nA/V, 200 Hz dark, 98.99 kPa, 24.9 °C):

| | A: 10 keV, 224.0 kHz | B: 30 keV, round 1 (971a71c) | B: 30 keV, round 2 (2d9fcc2, live) |
|---|---|---|---|
| Formula Φ_F (live fits) | 1.009e12 | 3.695e12 | 3.695e12 |
| E_eff / Λ_s / Λ_lo / Λ_hi | 10.02 / 0 / 0 / 0 | 30.05 / 0.506 / 0.396 / 0.571 | 30.05 / 0.470 / 0.353 / 0.560 |
| Best estimate | 1.009e12 | 7.48e12 | **6.97e12** |
| Low – high | 0.868 – 1.043e12 (+3.4 / −14.0 %); it was 1.039e12, +3.0 %, in round 1 | 5.26 – 8.87e12 (+18.6 / −29.7 %) | **4.91 – 8.69e12 (+24.6 / −29.6 %)** |

## 1b. Round 2: is each closure real? (HEAD 2d9fcc2)

"Verified" means this session re-ran the closing check by an independent path and got the same answer. Nothing live was checked: this session has no live access, so the installs and `--compare` results in PROGRESS.md are taken from the log.

| Finding | Architect's status | Round 2 verdict | Evidence |
|---|---|---|---|
| M1 | closed | **Verified** | Own f_pe from the `xraydb_N.csv` columns, interpolated **linearly** (the fit script uses log-log). The live CLCC vs f_pe × MC: max \|err\| 0.0088, the same as the fit's 0.0088. `bounds(1, 30)` gives 1.883 at ρ₀ and 1.887 at the site density. The plan-change row quotes the user's approval. Live install: not verified here |
| M2 | open | Open, correctly | It waits on the wall distances and plate thickness. LOW_FACTOR 0.86 now allows δ ≤ +15.7 % (it was 13 %), which covers somewhat more of the Laplace range |
| M3 | closed | **Verified** | `RESULT.md:42` and `physics_note.md:343` use "0 to −13.6 %, δ up to +15.7 %" with flux = formula/(1 + δ). No "0.87" or "0 to −13" is left in the docs grepped. Recomputed: √(0.14² − 0.03348²) = 0.1359, and δ_max = 0.1573 |
| M4 | band closed; plate material open | **Verified, with N1** | Own coverage check over all 11 variant files at 14–30 keV: every single variant and both two-change corners are inside the band. The one exception is the reach +10 % / σ −20 % corner at one energy, 0.0019 above the upper edge, which is inside the 2 s.e. tolerance. The three-change corner misses 5 of 10 points, by up to +0.039 at 17 keV. Declaring that a stress case accepts a risk, and no user row does so (N1) |
| M5 | closed | **Verified** | SYMMETRIC_TERMS sum to 0.03348; HIGH_FACTOR = ceil(1.03348, 3 dp) = 1.034; the test asserts the match. No "max 0.6 %" is left in `RESULT.md` or `calc/HANDOFF.md` |
| M6 | closed | **Verified** | Numerical derivative of the live strings at 30 keV: wall-loss part −0.933, total −1.935. f_pe-scaled MC ±3 % runs: −1.093. This matches `calc/PRESSURE.md:62`. The density scaling now captures 85 % of the MC change (it was 89 % before the refit); METHOD.md §6 has been updated to match |
| M7 | closed | **Verified, with N2** | Own scan, 12–14 keV in 5 eV steps at 0.94–1.05 ρ₀: no gap at ≥ 0.95 ρ₀. 0.95 is recomputed as 98.99/99.26 × (1 − 0.0343) × 298.05/302.15 = 0.9500. There is no margin below that (N2) |
| M8 | closed | **Verified** | Fixed-string grep for every quoted stale text finds no hits in `calc/`, `RESULT.md`, `physics_note.md` or `analysis/*.py`. The only "caution flag" left (`calc/HANDOFF.md:73`) is deliberate history. There are no "cm"-named variant files, and the headers state the density |
| M9 | closed | **Verified** | `physics_note.md:121` has the line, with the right numbers |

## 1c. Round 3 (HEAD 9fff096): the measured guarded chamber

**Checks run** (read-only, bluesky venv, `-I -X utf8`; the working tree was clean apart from METHOD.md):

| Check | Result |
|---|---|
| `calc/monp_transform.py` | **PASS**. Calc vs full NIST: worst 0.556 % at 5–20 keV, 0.890 % at 5–30 keV. "L_CM 6.19 cm vs modelled l_eff 61.925 mm: −0.040 %" |
| `calc/quality_slots.py` | **PASS**. ±3.6 % at 10 keV. Symmetric terms 3.56 % → HIGH_FACTOR 1.036, LOW_FACTOR 0.964. Collection term 1.36 % (1.4 % carried). Bit 1 "never" clear while the band is widened. 30 keV best/formula: MonP ×1.749, MonC ×1.365 |
| `calc/lanes.py`, `calc/background_transform.py` | **PASS**, both lanes |
| `analysis/wall_loss_fit.py`, `wall_loss_families.py`, `collection_length_cmc.py` | Not run: they rewrite tracked outputs. Their outputs were re-derived from the committed CSVs instead (below) |
| Independent recomputation | A new scratch script takes the expression strings that `lanes.build()` installs **per lane**, evaluates them with its own calc evaluator, and uses its own linearly interpolated f_pe. It agrees with `quality_slots.bounds(…, lane)` and `monp_transform.evaluate()` to 1e-12, and with Architect's self-test figures |

**Closures and open items, re-checked:**

| Item | Round 3 verdict | Evidence |
|---|---|---|
| M2 | **Closed, verified** | The collection term recomputed from `analysis/out/collection_length_cmc.csv` (largest \|Δl_eff\| per tolerance group: 0.81, 0.73, 0.57, 0.24, 0.16 and 0 %, plus 0.5 % for the model) = 1.354 %. σ_s = √(3² + 0.6² + 0.7² + 0.2² + 0.9² + 1.4²) = 3.558 % → 1.036 / 0.964, as live. L_CM = 6.19 cm is in CLCO and CLCP on both lanes. See Q4 for the missing gap tolerance |
| Per-lane wall loss | **Verified** | The installed CLCC differs per lane: MonP (18.7, 20.1, 1.01), MonC (18.6, 28.4, 1.28). At the MC energies, the fit vs f_pe × central MC has max \|err\| 0.0107 (MonP) and 0.0038 (MonC), both at 18 keV. Both match `wall_loss_fit_<lane>.txt`. Every gated variant is covered at 14–30 keV, 10 of 10 per file, strictly. Between the MC energies, see Q1 |
| N1 (stress corner) | **Still open** | On MonP it misses 5 of 10 points strictly and 2 within 2 s.e., worst +0.031 at 18 keV. On MonC the worst is +0.003 at 18 keV. No PLAN.md row accepts it |
| N2 (bit 1 margin) | **Still open**, unchanged | Own scan at 0.93–1.05 ρ₀, both lanes: a gap only at ≤ 0.945 ρ₀ (from 12.48 keV at 0.93 ρ₀). None at ≥ 0.95 ρ₀ |
| N3 | Informational, still true | ±0.002 or less at 30 keV, ±3 % density (METHOD.md 6e) |
| N4 | **Superseded** | RESULT.md is being rewritten for 9fff096. The figures it should now carry for the first live reading (MonP, own 22.2 °C, site-mean P, no dark): formula 3.56e12, best 6.19e12, range 4.99–7.60e12 |
| N5 | **Closed, verified** | `grep -n "section 10" analysis/wall_loss_fit.py` returns nothing |

**Reference numbers, round 3** (500 nA/V, 200 Hz dark, 98.99 kPa, 24.9 °C; l = 6.19 cm):

| | A: 10 keV, 224.0 kHz (both lanes) | B: 30 keV, 75.2 kHz, MonP | B: 30 keV, 75.2 kHz, MonC |
|---|---|---|---|
| Formula Φ_F: NIST / live fits | 0.9754e12 / 0.9776e12 | 3.560e12 / 3.582e12 | the same |
| E_eff / Λ_s / Λ_lo / Λ_hi | 10.02 / 0 / 0 / 0 | 30.05 / 0.4295 / 0.3166 / 0.5195 | 30.05 / 0.2684 / 0.1716 / 0.3584 |
| Best estimate | 0.978e12 | **6.28e12** (×1.753) | **4.90e12** (×1.367) |
| Low – high | 0.942 – 1.013e12 (±3.60 %) | **5.05 – 7.72e12 (+23.0 / −19.5 %)** | 4.17 – 5.78e12 (+18.1 / −14.9 %) |
| d ln/d ln ρ at 30 keV: wall part (fit / MC ±3 %), total | | −0.85 / −0.81, −1.85 | −0.60 / −0.60, −1.60 |

## 1d. Round 4 (HEAD fea6dae): closing checks for Q1–Q5

**Checks run** (read-only, bluesky venv, `-I -X utf8`; the working tree was clean; fea6dae changes only a geometry comment and the log, so the numbers are a84c2ca's):

| Check | Result |
|---|---|
| `calc/monp_transform.py` | **PASS**. Unchanged: worst 0.556 % at 5–20 keV, 0.890 % at 5–30 keV; L_CM vs l_eff −0.040 % |
| `calc/quality_slots.py` | **PASS**. ±3.6 % at 10 keV; σ_s 3.56 % → 1.036 / 0.964; collection 1.36 % (1.4 % carried); bit 1 "never" clear while widened; 30 keV best/formula MonP ×1.760, MonC ×1.370 (at ρ₀) |
| `calc/lanes.py` | **PASS**, both lanes |
| Fit and coverage scripts | Not run (they rewrite tracked outputs). Re-derived from the committed CSVs |
| `install_lane --compare` | Not run (installer, live IOC). Architect's "0 differences" is Architect's evidence, not this session's |
| Independent recomputation | The round-3 scratch script, pointed at HEAD and given the new gap group. The per-lane strings from `lanes.build()` are `B>17.9?1-1/EXP(((B-17.9)/19.7)^1.17):0` (MonP) and `B>18.1?1-1/EXP(((B-18.1)/27)^1.41):0` (MonC); CLCD, CLCE, CLCO and CLCP are unchanged and the same on both lanes. Agrees with `quality_slots.bounds()` and `monp_transform.evaluate()` to 1e-12 |
| This file, as Architect left it | `git show --stat a84c2ca -- METHOD_REVIEW.md`: 9 insertions, 0 deletions. These are only the Status (Architect) lines under Q1–Q5; no text of rounds 1–3 was changed |
| Fine-grid coverage (new) | Each variant's f_pe × MC interpolated linearly between the MC energies, 14–30 keV in 0.05 keV steps (321 points per file), against the live band |

**Results:**

| Item | Round 4 result |
|---|---|
| Fit vs f_pe × central MC, at the MC energies | MonP max 0.0087 at 21 keV; MonC 0.0039 at 22 keV. Both match `wall_loss_fit_<lane>.txt` |
| The same between MC energies | MonP ≤ 0.0098 at 17.9 keV with linear interpolation, which overstates a convex onset; log interpolation gives ≈ 0.009. MonC ≤ 0.0044 at 18.2 keV. The 0.9 % fit term holds |
| Gated coverage at the MC energies, within 2 s.e. | 14/14 for every gated file on both lanes (140/140 per lane), as Architect reports |
| Gated coverage, fine grid, within 2 s.e. | 321/321 for every gated file on both lanes |
| Strict coverage (no s.e. allowance) | All gated files strict except MonP `combo_range+10_sigma0.8`: 13/14 at the MC energies, 289/321 on the fine grid, worst +0.0041 above the high edge at 25 keV (R3) |
| Collection term | Groups now include the plate gap (gap_+0.2: 0.000 %, gap_−0.2: +0.081 %, one 0.05 mm grid cell). Parts 0.57, 0.73, 0.81, 0.24, 0.16, 0, 0.08 % + 0.5 % = 1.357 % ≤ 1.4 % carried |
| Density check, 30 keV, site density | Wall part, fit / MC ±3 %: MonP −0.934 / −0.828, MonC −0.638 / −0.537; totals −1.935 and −1.640. Matches PRESSURE.md §3 and METHOD.md §6 and §7(d) |
| Where the fit is 0 (E_eff 13 keV to E0) | Largest gated variant: 0.017 on MonP (offset +1 mm, 17 keV) and 0.026 on MonC (offset +1 mm, 18 keV), under the 0.05 floor. Matches METHOD.md §7(f) |
| Bit 1 | Unchanged: widened while the bit is clear only at ≤ 0.945 ρ₀ (from 12.48 keV at 0.93 ρ₀), both lanes |

**Reference numbers, round 4** (the same inputs as round 3):

| | A: 10 keV (both lanes) | B: 30 keV, MonP | B: 30 keV, MonC |
|---|---|---|---|
| Formula Φ_F (live fits) | 0.9776e12 | 3.5816e12 | the same |
| E_eff / Λ_s / Λ_lo / Λ_hi | 10.02 / 0 / 0 / 0 | 30.05 / 0.4333 / 0.3200 / 0.5233 | 30.05 / 0.2715 / 0.1743 / 0.3615 |
| Best estimate | 0.978e12 | **6.320e12** (×1.7646) | **4.916e12** (×1.3726) |
| Low – high | 0.942 – 1.013e12 (±3.60 %) | **5.077 – 7.784e12 (+23.16 / −19.67 %)** | 4.182 – 5.811e12 (+18.20 / −14.94 %) |
| First live reading (22.2 °C, site P, no dark) | | formula 3.559e12, best **6.227e12**, 5.013 – 7.656e12 | best 4.857e12, 4.136 – 5.736e12 |

Per-Hz correction factors at the site density (500 nA/V): MonP ×1.0769 (20 keV), ×1.3566 (25), ×1.7646 (30); MonC ×1.0246, ×1.1586, ×1.3726.

---

## 2. Findings, most severe first

### M1. The wall-loss correction is applied to the whole signal, but the MC loss is per photoelectric absorption
- **Status: CLOSED 2026-11-13** (user: "Yes, fix M1 and M8"). The refit and band check are in `analysis/wall_loss_fit.py`: PASS, 80 of 80 f_pe-scaled points covered. `bounds(1, 30)["L"]` = 1.883. Installed live on both lanes; `--compare` gives 0 differences. Details in PROGRESS.md, 2026-11-13.
- **Severity:** medium. It biases the best estimate; the band still contains the corrected value.
- **Where:**
  - `analysis/wall_loss_mc.py:221` normalises the loss per photoabsorbed photon.
  - `calc/quality_slots.py:67` (CLCC) and `:72` (CLCL) divide the whole formula flux by 1 − Λ.
- **Defect.** The formula's signal comes from μ_en, which is the photoelectric part plus the Compton-electron part. Compton electrons carry ≤ 3.2 keV at 30 keV and travel ≲ 0.3 mm, so they never reach a plate. The true signal loss is f_pe·Λ, where f_pe is the photoelectric share of μ_en.
- **Scenario.**
  - At 30 keV, f_pe = 0.9245 (xraydb Elam split, `data/queries/out/xraydb_N.csv`: photo 0.1010, Compton-electron 0.0082 cm²/g). The true loss is then 0.468, not 0.506.
  - So the best estimate is **7.2 % high** at 30 keV: example B is 6.95e12, not 7.48e12.
  - It is 1.7 % high at 25 keV (f_pe = 0.9636) and 0.2 % at 20 keV (f_pe = 0.9857).
- **Proposed fix.** Refit the same functional form to Λ_tot(E) = f_pe(E)·Λ_MC(E), and keep CLCC's structure so it stays ≤ 39 characters. Take f_pe from xraydb on the MC energy grid. Re-derive the band edges against f_pe × each MC variant.
- **Closing check.** After the refit, `bounds(1, 30)["L"]` ≈ 1.87 (now 2.02). Every f_pe-scaled MC variant must lie inside [Λ_lo, Λ_hi] at 15–30 keV.

### M2. The collection-length bound is narrower than the new Laplace model's range
- **Status: OPEN.** It waits on the CMC-custom plate-to-wall distances and plate thickness. LOW_FACTOR stays 0.86 until then (2026-11-13).
- **Round 3: closed by 9fff096, verified (§1c).** The chamber turned out to be guarded, so the unguarded fringe-field range no longer applies. The collection length is a symmetric ±1.4 % term, with LOW_FACTOR 0.964 = 1 − σ_s.
- **Severity:** medium. It is already open in `physics_note.md:159`; it needs the user's dimensions.
- **Scenario.**
  - With end walls ≥ 2 cm from the plate ends, δ reaches +26 %. The flux is then ×0.79, below the live low factor of 0.86.
  - With end walls ≤ 0.5 cm, δ = −2.3 %, and the true flux is 2.4 % **above** the formula. That breaks the one-sided assumption. HIGH_FACTOR = 1.03 carries only the symmetric terms, so it does not cover this.
- **Proposed fix.**
  - Get the plate-to-end-wall and plate-to-side-wall distances and the plate thickness from the user, then run `analysis/fringe_field.py` for that geometry.
  - Set LOW_FACTOR = 1 − √(d_max² + σ_s²), with d_max = 1 − 1/(1 + δ_max) (see M3).
  - If δ_min < 0, set HIGH_FACTOR = 1 + √(σ_s² + d_min²). For example, d_min = 0.024 gives 1.040.
- **Closing check.** Run `fringe_field.py` for the measured geometry, log δ, and confirm that `bounds()` brackets Φ_F/(1 + δ) at both ends of the δ range.

### M3. Two conventions for turning δ into a flux factor
- **Status: CLOSED 2026-11-13.** The convention is 1/(1 + δ) throughout. LOW_FACTOR is kept at 0.86, the alternative this finding offers, because M2 may need a wider low side, not a narrower one. With σ_s = 3.35 % (M5) it allows a flux deficit of 13.6 %, δ ≤ +15.7 % (`quality_slots.COLLECTION_FLUX_DEFICIT`, `DELTA_MAX`). The closing grep is in PROGRESS.md.
- **Severity:** low.
- **Where:** `physics_note.md:136` and `RESULT.md` take δ = 13 % as "−13 %" on the flux (×0.87). `physics_note.md:159` takes δ = 26 % as ×0.79, which is 1/(1 + δ); by that rule δ = 13 % gives ×0.885.
- **Scenario.** The low bound is 1.5 points more conservative than the δ it says it covers. That is harmless, but the stated δ and the factor disagree.
- **Proposed fix.** Use 1/(1 + δ) throughout. With δ_max = 0.13: d_max = 0.115, and LOW_FACTOR = 1 − √(0.115² + 0.032²) = 0.881. Alternatively, keep 0.86 and state that it corresponds to δ_max ≈ 0.16.
- **Closing check.** grep `physics_note.md`, `RESULT.md`, `calc/OPERATOR.md` and `calc/quality_slots.py:116–118` for "13 %" and "0.87"; every hit must use one convention.

### M4. The wall-loss band covers each MC variant singly, not in combination
- **Status: band part CLOSED 2026-11-13; plate material OPEN.** Both combined runs were made. Reach +10 % with σ −20 % exceeded the upper edge at 20–28 keV, and reach −10 % with σ +20 % fell below the lower edge at 22 keV. The band was widened (cap 0.065 → 0.09, lower offset 0.06 → 0.07): `analysis/wall_loss_fit.py` covers 100/100 gated points. A three-change corner (adding a 1 mm offset) is reported as a stress case; it lies outside. The plate material is still to come from the user.
- **Severity:** low.
- **Scenario.** At 25 keV the upper edge (0.384 at ρ₀) clears the reach +10 % variant (0.3805) by 0.3 points, about 1.4 σ of MC statistics. A combined variant, reach +10 % with elastic σ −20 %, would very likely exceed it.
- **Related.** The backscatter allowance in Λ_lo (0.06 + 0.1Λ below Λ) is not tied to a plate material, which is unknown. At 30 keV it sits 5.4 points below the lowest variant.
- **Proposed fix.**
  - Run `wall_loss_mc.py --range-scale 1.1 --sigma-scale 0.8` and `--range-scale 0.9 --sigma-scale 1.2`, and widen the band edges if either combination falls outside.
  - Ask the user for the plate material, and size the backscatter allowance from its energy-backscatter coefficient.
- **Closing check.** Both combined runs lie inside [Λ_lo, Λ_hi] at 20/25/30 keV, and the plate material is logged.

### M5. The symmetric budget leaves out the cross-section fit error
- **Status: CLOSED 2026-11-13.** `quality_slots.SYMMETRIC_TERMS` lists μ_en 3, W 0.6, electronics 1 (placeholder), density 0.2 and fit 0.9 %. They sum in quadrature to 3.35 %, so HIGH_FACTOR is 1.034. The test asserts HIGH_FACTOR − 1 = σ_s to 0.1 %. The budget tables (RESULT.md, physics_note §3.7) list the fit, and "max 0.6 %" is reworded.
- **Severity:** low.
- **Where:** `RESULT.md:59` and `calc/HANDOFF.md:25` say the fit is "max 0.6 %". That is against the fit's own target. Against log-log NIST, the `monp_transform.py` self-test shows 0.89 % at 25 keV.
- **Defect.** The fit error is in no budget. W's ±0.6 % is the full spread of five sources, used as if it were 1σ.
- **Scenario.** μ_en 3 ⊕ W 0.6 ⊕ electronics 1 ⊕ density 0.2 ⊕ fit 0.6 gives σ_s = 3.3 %, but HIGH_FACTOR = 1.03 encodes 3.0 %. The high bound is about 0.3 points narrow.
- **Proposed fix.** Add a fit line (±0.6 %, 0.9 % at 25 keV) to `physics_note.md` §3.7 and to `RESULT.md`, or state that it is counted inside μ_en's ±3 %. Set HIGH_FACTOR = 1 + σ_s from the listed terms. Reword "max 0.6 %" to "0.6 % vs its NIST-anchored target; 0.9 % vs log-log NIST".
- **Closing check.** The budget table lists the fit, and HIGH_FACTOR − 1 equals the quadrature sum of the listed terms to 0.1 %.

### M6. The 30 keV pressure sensitivity is under-stated
- **Status: CLOSED 2026-11-13** (with M1). After the photoelectric-share refit, the numerical closing check gives −0.93 at 30 keV, and the MC ±3 % runs give −1.09. `calc/PRESSURE.md` now shows both, with a total of ≈ −1.9 %/%.
- **Severity:** low. Documentation only; the live calc is unaffected.
- **Where:** `calc/PRESSURE.md:50` gives −1.01 for the wall-loss term at 30 keV, and `:63` says "≈ −2 %/%" in total.
- **Scenario.** The live formula gives −1.14 (analytic, at the site density), and the MC ±3 % runs give −1.27, so the total is −2.15 to −2.3 %/%. The 20 and 25 keV rows agree (−0.54, −0.85).
- **Proposed fix.** Set the 30 keV row to −1.14 (as applied live) with a note "MC: −1.27", and set the total to ≈ −2.15 %/%.
- **Closing check.** Numerically, (ln(1−Λ(E_eff(ρ(1−h)))) − ln(1−Λ(E_eff(ρ(1+h)))))/(2h) at 30 keV, from `quality_slots.e_eff` and `wall_loss_band`, gives −1.14.

### M7. Status bit 1 and the band's 13 keV switch use different energies
- **Status: CLOSED 2026-11-13.** Bit 1 is now `A>12.6`: 13 × (0.95)^0.568, where 0.95 is the lowest density seen at the site relative to ρ0. So the bit is set wherever the band is widened, at any observed density. The test checks this at 12–14 keV and densities 0.95–1.03 ρ0: "never" clear while widened.
- **Severity:** low.
- **Where:** bit 1 is set at raw E > 13.5 keV (`calc/quality_slots.py:88`). The high bound's +0.04 term switches at E_eff > 13 keV (`:69`).
- **Scenario.** At E = 13.2 keV the high bound is +7.3 % while the status reads 0 (OK).
- **Proposed fix.** Set bit 1 to `A>13`. At hutch densities E_eff and E differ by only ~0.2 %, and the string fits. Alternatively, document the 13–13.5 keV gap in `calc/OPERATOR.md`.
- **Closing check.** `flags(13.2, …)` gives bit 1 = 1 wherever `bounds(…, 13.2)` gives F > 3.0.

### M8. Stale or misleading text
- **Status: CLOSED 2026-11-13.** Every row was fixed, and the live CMTC was re-installed on both lanes. The MC variants were re-run with the same seed: the data are byte-identical, the headers state the real density, and the files now carry mm names. The closing grep is logged in PROGRESS.md, 2026-11-13.
- **Severity:** low. One item reaches the live screens.

| Location (HEAD 971a71c) | Says | Should say |
|---|---|---|
| `calc/lanes.py:137`, CMTC, written to the live IOC | "wall-loss upper bound fraction" | the central MC wall-loss fraction, e.g. "wall-loss fraction (MC fit)" as in `quality_slots.py:78`. Needs a lane re-install to reach the IOC |
| `calc/lanes.py:6`, `:129` | the bounds slot's "caution flag" (K) | removed; drop the words |
| `calc/quality_slots.py:8–13`, `:36–38` | the STATUS docstring and INPB/INPC describe the old 0/1/2 code | the flags code; `lanes.py` overrides these inputs |
| `calc/HANDOFF.md:41–42` | G, H "by hand" | G is the live pressure; H is the background via the dark feed |
| `calc/HANDOFF.md:127` | the old status expression | the flags code (`userTran7/8.L`) |
| `calc/HANDOFF.md:130` | "B = E" | B = E_eff (CLCB) |
| `calc/HANDOFF.md:141` | "Scheduling: NOT yet installed" | installed by the user on 2026-11-12 (`calc/PRESSURE.md` §2) |
| `calc/monp_transform.py:48`, `:53` | INPE None; G 99.26 | as built by `lanes.py`: energy linked, G 98.99 |
| `RESULT.md:47` | "Dark offset (~50–100 Hz, not subtracted)" | subtracted since 2026-11-12; MonP's archived no-beam rate at 500 nA/V was 182–227 Hz |
| `physics_note.md:200` | MC "at the site mean density" | at 99.26 kPa / 24.9 °C (ρ₀ = 1.1221e-3), the mean before the 228 m correction; E_eff accounts for it |
| `physics_note.md:208` | dose peak "0.39 vs 0.34" | 0.39 at 10 and 20 keV, 0.49 at 30 keV (`analysis/out/wall_loss_mc_validation.csv`) |
| `analysis/wall_loss_mc.py:230`, and the variant file names | every header says 99.26 kPa, including the ±3 % density runs; older names say "cm" for a gap in mm | write the actual density into the header; the names are cosmetic |

- **Closing check.** grep for each quoted string; no hits outside the append-only `PROGRESS.md`.

### M9. The absorbed-fraction form is not stated
- **Status: CLOSED 2026-11-13.** The line is in `physics_note.md` §2.2.
- **Severity:** low, informational.
- **Defect.** The formula uses 1 − exp(−μ_en ρ l). The local-deposition form is (μ_en/μ)(1 − exp(−μ ρ l)); the formula's version is 0.11 % larger at 10 keV, 0.2 % at 5 keV and 0.07 % at 30 keV.
- **Scenario.** The flux is low by that much. That is negligible against ±3 %, but no document says so.
- **Proposed fix.** One line in `physics_note.md` §2.2. No code change.
- **Closing check.** The line is present.

---

## 3. Round 2 findings (HEAD 2d9fcc2), most severe first

### N1. The three-change MC corner is outside the band, and no user row accepts that
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** PLAN.md 2026-11-13 row quotes the user ("Yes, both") and names the corner and its round-4 size; METHOD.md §7(f) and CHAMBER_FACTS F10.4 say it is accepted.
- **Status, round 3 (9fff096): OPEN.** It now applies per lane. MonP's stress corner misses at 18 keV (0.081 against 0.050, about 3.4 % on the high bound) and marginally at 20 keV (0.156 against 0.151). MonC's misses at 18 keV by 0.003. Between 18 and 20 keV the MonP miss is larger still (Q1). No PLAN.md row accepts it.
- **Status, round 4 (fea6dae): OPEN.** After the refit, MonP's stress corner misses at 18 keV (0.081 against 0.056, about 2.7 % on the high bound) and at 25 keV (0.361 against 0.351, about 1.5 %); on the fine grid the worst is +0.028 at 17.9 keV (about 3 %). MonC's misses at 18 and 18.5 keV by 0.003. Still no PLAN.md row accepts it, and METHOD.md §7(f) still quotes the round-3 numbers (R1).
- **Status (Architect, 2026-11-13): risk accepted by the user** in a PLAN.md plan-change row that quotes the user ("Yes, both") and names the corner and its size from round 4. METHOD.md §7(f) says so. No band change.
- **Severity:** low. This is a process gap: CLAUDE.md requires accepted risks to be closed with a plan-change row.
- **Where:** `analysis/out/wall_loss_fit.txt` lists `gap9.09mm_sig0.80_off1.0mm` as MISSES "[stress case, not gated]". `METHOD_REVIEW.md` M4 and METHOD.md §7(f) describe it the same way. The 2026-11-13 rows in `PLAN.md` say only that the band covers "the combined MC corners".
- **Scenario.** With electron reach +10 %, elastic σ −20 % and the beam 1 mm off centre, the f_pe-scaled loss exceeds the upper edge at 16, 17, 18, 22 and 25 keV, by up to +0.039 at 17 keV (0.079 against 0.040). At 17 keV the true flux would then be about 4 % above the stated high bound.
- **Proposed fix.** Either the user accepts it in a plan-change row, quoting them and naming the corner and its size, or the band is widened. At 16–18 keV the term that binds is 2Λ_s + 0.04; at 22–25 keV it is the 0.09 cap.
- **Closing check.** A PLAN.md row exists that quotes the user on this corner, or `wall_loss_fit.py` reports it covered.

### N2. Status bit 1 has no margin below the 2025 density extreme
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** CLCF is `A>12.5` in `lanes.build()` on both lanes. A 1 eV scan at 0.900–0.960 ρ₀ finds the band widened with bit 1 clear only at ≤ 0.933 ρ₀; it is clear from 0.934 ρ₀, 1.7 % below the lowest density seen (0.95).
- **Status, round 3: OPEN,** unchanged (§1c).
- **Status, round 4: OPEN,** unchanged (§1d).
- **Status (Architect, 2026-11-13): fixed, live on both lanes** (user: "Yes, both"). `quality_slots.py` RHO_FLAG1_OVER_RHO0 = 0.934 → FLAG1_E_KEV 12.5; CLCF `A>12.5`. Its M7 scan now runs at 0.934, 0.95, 0.97, 1.0 and 1.03 ρ₀ (12–14 keV in 5 eV steps): "never". A 1 eV scan clears at 0.934 ρ₀ and opens at 0.932 (from 12.491 keV). `install_lane --compare` showed 2 differences per lane (CLCF, CMTF); after the install, 6 × VERIFIED, LANE OK and 0 differences on both lanes.
- **Severity:** low.
- **Where:** `calc/quality_slots.py` RHO_MIN_OVER_RHO0 = 0.95 and FLAG1_E_KEV = 12.6.
- **Scenario.**
  - 0.95 is the 2025 minimum pressure (−3.43 %) combined with the hutch's maximum temperature (29.0 °C). Those did not happen at the same time, which is conservative, but it rests on one year of pressure data.
  - At 0.94 ρ₀ the gap reopens: from 12.555 keV the band is widened while the status is still OK.
  - The effect is tiny: +4 % on the high bound over ≤ 0.05 keV with status 0.
- **Proposed fix.** Floor to 12.5 keV, which covers ρ ≥ 0.934 ρ₀ (13 × 0.934^0.568 = 12.5), or record the margin as accepted.
- **Closing check.** The `quality_slots.py` M7 scan, extended to 0.934 ρ₀, reports "never".

### N3. The photoelectric share is effectively evaluated at E_eff, not E
- **Severity:** low, informational.
- **Where:** CLCC evaluates the fit Λ_s(E) = f_pe(E)·Λ_MC(E) at E_eff. The density scaling is meant for the electron transport. f_pe is photon physics and does not depend on density, but it moves with E_eff too.
- **Scenario.** At 30 keV and ±3 % density, E_eff moves by ∓0.5 keV and f_pe by about ±0.4 %. Λ_s then shifts by about ±0.002, below the MC statistics (0.0023).
- **Proposed fix.** None needed. Record it as an assumption: it is now METHOD.md 6e. If the fit is ever split into f_pe(E) × Λ_MC(E_eff), the calc's 39-character limit is the constraint.
- **Closing check.** The statement is in METHOD.md §6 (done in this round).

### N4. The first-live-reading figures in RESULT.md use the site-mean density for E_eff
- **Status, round 3: superseded** by the 9fff096 constants. The closing check now applies to the new figures (§1c): formula 3.56e12, best 6.19e12, range 4.99–7.60e12 at P = 98.99 kPa, 22.2 °C, MonP, `rho` = P·M/(R·T).
- **Severity:** low, rounding level.
- **Where:** `RESULT.md:64` says "6.9 × 10¹² ph/s, range 4.9–8.6 × 10¹²".
- **Scenario.** Those figures follow from the logged 3.66e12 formula flux with E_eff at the site density. At the reading's own 22.2 °C, the gas is denser, E_eff is lower and Λ_s smaller, which gives 6.87e12, range 4.85–8.54e12, i.e. "4.9–8.5". This session's estimate assumes P = 98.99 kPa; the actual pressure at 13:50 is not on file here.
- **Proposed fix.** Recompute with the reading's own T and the logged P, or say "at site-mean density".
- **Closing check.** `quality_slots.bounds(3.66e12, 30, rho(P_log, 22.2 °C))` matches the RESULT.md text.

### N5. A stale cross-reference in the new fit script
- **Status: CLOSED, verified in round 3:** the closing grep returns nothing.
- **Severity:** low.
- **Where:** `analysis/wall_loss_fit.py:4` says "finding M1, METHOD.md section 10". METHOD.md no longer has a §10; the findings are in this file.
- **Proposed fix.** "finding M1, METHOD_REVIEW.md".
- **Closing check.** `grep -n "section 10" analysis/wall_loss_fit.py` returns nothing.

---

## 4. Round 3 findings (HEAD 9fff096), most severe first

### Q1. The band is gated only at the MC energies, and MonP's fit starts inside the 18–20 keV gap
- **Status (Architect, 2026-11-13): fixed; closing check run.**
  - MC energies 18.5, 19, 19.5 and 21 keV were added to `analysis/wall_loss_mc.py`, and the families re-run (22/22 rc = 0). The runner now exits 1 on any failed run: a first attempt crashed on a print format and had silently left the old CSVs in place.
  - Refit, MonP: (17.9, 19.7, 1.17), max error 0.0087 at 21 keV; the old fit was off by 0.019 on the new points. MonC: (18.1, 27.0, 1.41), 0.0039.
  - `wall_loss_fit.py` → 140/140 gated points per lane, PASS.
  - Installed on both lanes; `--compare` 0 differences.
- **Status, round 4 (reviewer): CLOSED, verified.** At the MC energies every gated file is 14/14 within 2 s.e. on both lanes (140/140), and on a 0.05 keV interpolated grid 321/321. The reported max fit error (0.0087 MonP, 0.0039 MonC) includes the new energies. The one strict-only shortfall is R3.
- **Severity:** low to medium. The stated high bound can be 1–2 % too low over a narrow energy range near 18.7 keV on MonP.
- **Where:** `analysis/wall_loss_fit.py` checks coverage and fit error only at the MC energies (…, 16, 17, 18, 20, 22, … keV). MonP's CLCC is 0 up to E_eff = 18.7 keV. The high edge there is 0 + min(0.09, 0.05) = 0.050.
- **Scenario.**
  - MonP, E_eff ≈ 18.7 keV. The gated reach +10 % / σ −20 % corner is 0.043 at 18 keV and 0.132 at 20 keV (f_pe-scaled).
  - Interpolated to 18.7 keV it is 0.063 (log-linear) to 0.074 (linear), against a high edge of 0.050 + 2 s.e. = 0.053. So it is outside by 0.010–0.022, i.e. 1.1–2.4 % on the high bound.
  - The central case there is about 0.020 against a fit of 0, so the best estimate is about 2 % low. That is twice the reported max fit error of 0.0107.
  - The stress corner (N1) is about 0.10 at 18.7 keV, against 0.050.
  - MonC is fine: every gated variant interpolates inside its band, because its fit starts at 18.6 keV and its losses are smaller.
- **Proposed fix.** Add MC energies at 18.5, 19 and 19.5 keV to both families (or a 0.5 keV grid from 16 to 22 keV), and gate the fit and the band on them. If the gated corner still exceeds the edge, raise the floor (0.05 → ~0.07), or let the 2·C term start below E0.
- **Closing check.** `wall_loss_fit.py` on the denser grid reports 100 % of gated points covered per lane, and the max \|fit − target\| it reports includes the new energies.

### Q2. Stale numbers and wording left in code and data after 9fff096
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** The `quality_slots.py:69–70` comments now say 0.0356 and 1.036; the round-3 fixed-string greps return nothing. The `install_lane --compare` part was not run by this session.
- **Status (Architect, 2026-11-13): fixed.** lanes.py docstring and CMTO ("fraction absorbed in 6.19 cm (l_eff)", installed live), monp_transform.py docstring, quality_slots.py docstring and comments, collection_length_cmc.py docstring, and the CSV header ("/ 61.90 mm").
- **Status, round 4 (reviewer): OPEN, one row left.** Fixed-string greps in `calc/` and `analysis/` find none of the quoted texts except the `quality_slots.py` comments, now at lines 69–70: `OTHER_TERMS = …  # 0.0335` and `HIGH_FACTOR = …  # 1.033 (CLCE)`. The values are 0.0356 and 1.036. The `install_lane --compare` part was not run by this session.
- **Status (Architect, 2026-11-13, round 4): fixed.** `quality_slots.py` comments now say 0.0356 and 1.036 (CLCE). Comments only: no slot changes, no install.
- **Severity:** low. One item, the PV comment, reaches the live IOC.

| Location (9fff096) | Says | Should say |
|---|---|---|
| `calc/lanes.py:118`, the flux slot's comment for O (installed as a CMT field) | "fraction absorbed in 6 cm" | "in 6.19 cm", or "in l_eff". Needs a lane re-install to reach the IOC |
| `calc/monp_transform.py:15` | "O absorbed fraction in 6 cm" | 6.19 cm (L_CM) |
| `calc/lanes.py:18–20` | MonC assumed of "MonP's geometry (6 cm vertical plates, 1 cm gap, no guards)" | the guarded chamber as measured, MonC horizontal and MonP vertical; MonP's build assumed equal |
| `calc/quality_slots.py:16–30`, the BOUNDS docstring | fit 17.5/19.1/1.08, max 0.009; LOW_FACTOR 0.86 "the collection length… 13.6 %"; symmetric 3.27 %; HIGH_FACTOR 1.033 | per-lane WALL_FITS, LOW_FACTOR 0.964 = 1 − σ_s, σ_s 3.56 %, HIGH_FACTOR 1.036 |
| `calc/quality_slots.py:68–69` | `# 0.0335`, `# 1.033 (CLCE)` | 0.0356, 1.036 |
| `calc/quality_slots.py:40` (WALL_FITS comment) | "Both: the measured 11.2 mm gap" | 10.85 mm (the families use a 5.425 mm half gap; the BAND comment already says 10.85) |
| `analysis/collection_length_cmc.py:14` | "The calc uses l = 6.0 cm" | 6.19 cm |
| `analysis/out/collection_length_cmc.csv:1` | "delta = l_eff / 62 mm - 1" | 61.90 mm (the values are relative to 61.9; the code now writes `{L:.2f}`, so the CSV predates that format change). Regenerate, or edit the header |

- **Closing check.** A fixed-string grep for each quoted text in `calc/` and `analysis/` returns no hits, and `install_lane --compare` shows the new comment on both lanes.

### Q3. calc/PRESSURE.md §3 still has the old single-chamber density check
- **Status (Architect, 2026-11-13): fixed.** PRESSURE.md §3 now has per-lane rows. At 30 keV, after the Q1 refit: MonP fit −0.93 / MC −0.83, MonC −0.64 / −0.54. METHOD.md §6 and §7d carry the same values.
- **Status, round 4 (reviewer): CLOSED, verified.** A central difference of the live CLCB/CLCC strings at 30 keV and site density gives −0.934 (MonP) and −0.638 (MonC); the ±3 % MC files give −0.828 and −0.537. These match PRESSURE.md §3 as rounded.
- **Severity:** low. Documentation only.
- **Where:** `calc/PRESSURE.md:55–63`: MC 52.19 / 48.40 %, "−0.93 against the MC's −1.09: about 85 %", and "−0.55 %/% at 20 keV and −0.93 %/% at 30 keV; total ≈ −1.9 (MC −2.1)".
- **Scenario.** These are from the 10 mm vertical-plate MC and the old fit. With the per-lane fits, at 30 keV and the site density:
  - MonP: the wall part is −0.85 from the fit and −0.81 from its ±3 % MC runs, so the fit captures 105 %. The total is −1.85.
  - MonC: −0.60 from the fit and −0.60 from the MC; the total is −1.60.
- **Proposed fix.** Per-lane rows from `analysis/out/wall_loss/<lane>/density_0.97.csv` and `density_1.03.csv`.
- **Closing check.** PRESSURE.md quotes per-lane values that match a numerical derivative of the live CLCB/CLCC strings.

### Q4. The collection-length term has no plate-gap tolerance
- **Status (Architect, 2026-11-13): fixed.** Cases gap_±0.2 were added to `collection_length_cmc.py` (the HV plate moved ±0.2 mm, the user's tolerance at the beam track), and the group was added to COLLECTION_GROUPS. The largest |Δ| is 0.08 %, so the term stays 1.36 % → 1.4 %.
- **Status, round 4 (reviewer): CLOSED, verified.** The CSV has gap_+0.2 and gap_−0.2, and `collection_term()` recomputed with them is 1.357 %, under the 1.4 % carried. ±0.2 mm at the beam track is the right tolerance for this 2-D model (the ±0.5 mm across the width is not on the beam line). The effect is at the model's 0.05 mm grid resolution, so read it as "≤ 0.1 %".
- **Severity:** low.
- **Where:** `calc/quality_slots.py` COLLECTION_GROUPS has no gap case. The gap is 10.85 mm, ±0.2 mm at the beam track and ±0.5 mm across the width (`cmc_chamber_geometry.py`).
- **Scenario.** The fringe field at the guard gaps scales with the plate gap, and so does the field behind the guards' 0.51 mm set-back. A ±0.5 mm gap change is not in the 1.35 %. It probably adds a few tenths of a percent at most, but that is not shown.
- **Proposed fix.** Add `plate_gap_±0.5` cases to `collection_length_cmc.py`, and a group for them if they change l_eff by more than ~0.3 %.
- **Closing check.** The CSV has the gap cases, and `collection_term()` with them still fits under the carried 1.4 %, or the term is raised.

### Q5. The reach variants rescale the gap but not the beam offset or width
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** `wall_loss_mc.py:8–11` has the line.
- **Status (Architect, 2026-11-13): noted (informational), no change.**
- **Status, round 4 (reviewer): OPEN (informational).** Its closing check, one docstring line, is not met: `wall_loss_mc.py` has no such line. Closing it needs either the line, or a user decision to drop it.
- **Status (Architect, 2026-11-13, round 4): fixed.** `wall_loss_mc.py` docstring states that --range-scale rescales the half gap only, and what that means for MonC and a centred beam. The docstring and the `wall_loss()` banner also now say that the lane runs take their geometry from `wall_loss_families.py` (the banner prints the run's actual gap, orientation, FWHM and offset), which covers the note carried to the consolidation audit.
- **Severity:** low, informational.
- **Where:** `analysis/wall_loss_mc.py` sets HALF_GAP = BASE_HALF_GAP / range_scale, but leaves OFFSET_X and the beam FWHM as they are.
- **Scenario.** A ±10 % electron reach is equivalent to shrinking or growing **every** length by that factor. For MonC (offset 0.525 mm), reach +10 % then behaves like an offset of 0.578 mm in the true geometry: slightly conservative, and negligible. For MonP (centred) it makes no difference.
- **Proposed fix.** None needed. One line in the `wall_loss_fit.py` or `wall_loss_mc.py` docstring.
- **Closing check.** The line is present.

---

## 5. Round 4 findings (HEAD fea6dae), most severe first

### R1. METHOD.md still has round-3 numbers in four places the refit moved
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** The closing grep returns nothing; §7(f) and the consistency check carry the round-4 numbers.
- **Status (Architect, 2026-11-13): fixed.** METHOD.md:72 and the bit 1 row → 17.9 / 18.1 keV; §7(f) → 140 of 140, the new MC energies, and the round-4 stress-corner numbers; the consistency check → a84c2ca, 6.23 × 10¹², 5.01–7.66 × 10¹². The closing grep returns nothing.
- **Severity:** low. Documentation only, but METHOD.md is the document the numbers are checked against.
- **Where, and what it should say:**

| Location | Says | Should say |
|---|---|---|
| `METHOD.md:72` | the correction "is exactly 1 for E_eff up to 18.7 keV (MonP) or 18.6 keV (MonC)" | 17.9 keV (MonP), 18.1 keV (MonC) |
| `METHOD.md:503` (bit 1 row) | "MC-corrected above E_eff = 18.7 keV (MonP) or 18.6 keV (MonC)" | 17.9 / 18.1 keV |
| `METHOD.md:433`, §7(f) | "100 of 100 points per lane … The check is made at the MC energies only" | 140 of 140; the MC energies now include 18.5–21 keV |
| `METHOD.md:434–436`, §7(f) stress corner | MonP above at 18 keV "(0.081 against 0.050), about 3.4 %", "marginally at 20 keV (0.156 against 0.151)"; MonC at 18 keV only | MonP 0.081 against 0.056 at 18 keV (about 2.7 %) and 0.361 against 0.351 at 25 keV (about 1.5 %); MonC at 18 and 18.5 keV, by 0.003 |
| `METHOD.md:561`, consistency check | "as of 9fff096 … best estimate 6.19 × 10¹², range 4.99–7.60 × 10¹²" | as of a84c2ca: formula 3.56 × 10¹², best **6.23 × 10¹²**, range 5.01–7.66 × 10¹² |

- **Scenario.** A reader at E = 18.3 keV on MonP takes METHOD.md:72 at its word and expects best = formula. The live slot applies ×1.011 there (Λ_s = 0.0104), so the numbers differ from the text by 1 %, and a check of the slot against METHOD.md reports a fault that is not there.
- **Proposed fix.** Change the five places as in the table. The rest of §6, §7 and §9 already carries the refit numbers.
- **Closing check.** `git grep -nE "18\.7 keV|18\.6 keV|100 of 100|0\.156 against|6\.19 × 10¹², range" METHOD.md` returns nothing, and the §7(f) and consistency-check numbers match §1d of this file.

### R2. The MonP 30 keV factor is quoted as ×1.77, but it is ×1.76; MonC's 20 keV factor is ×1.02, not ×1.03
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** The `×1.77` grep returns nothing; RESULT.md has ×1.76, ×1.02 and 8.43e7; METHOD.md has 7.78 × 10¹² (7.784 unrounded).
- **Status (Architect, 2026-11-13): fixed.** ×1.76 in METHOD.md (§9 table and the text), RESULT.md and physics_note.md (three places); MonC ×1.02 at 20 keV; 8.43e7 per Hz; Φ_hi ≈ 7.78 × 10¹² (7.784 unrounded) in §7 and §9. The closing grep returns nothing.
- **Severity:** low. Rounding, 0.3 % and 0.5 %, well inside the stated bounds. But these factors are the headline numbers operators read.
- **Where.**
  - MonP ×1.77 at 30 keV: `METHOD.md:532` (§9 table) and `:551`; `RESULT.md:18`; `physics_note.md:245`, `:248` and `:358`.
  - MonC ×1.03 at 20 keV: `RESULT.md:20` and `physics_note.md:245`.
  - `RESULT.md`, the MonP best-estimate row at 30 keV: 8.44e7 per Hz; 4.7755e7 × 1.7646 = 8.43e7.
  - `METHOD.md` §7 worked example B: Φ_hi = 7.79 × 10¹². Computed from the rounded steps (3.582 × 1.036 × 2.098) that is 7.786; from the unrounded slot it is 7.784, i.e. 7.78. (u = +23.2 % is right either way.)
- **Scenario.** At the site density, 1/(1 − Λ_s) = 1/(1 − 0.43331) = 1.7646 on MonP at 30 keV, and 1.0246 on MonC at 20 keV (§1d). ×1.77 comes from rounding 1.765, already a rounded value, a second time. An operator multiplying a formula reading by 1.77 is 0.3 % high against the live best estimate, and a check of RESULT.md against the slot fails at three significant figures.
- **Proposed fix.** ×1.76 for MonP at 30 keV, ×1.02 for MonC at 20 keV, 8.43e7 per Hz, and 7.78 × 10¹² (or quote the rounded-step arithmetic as approximate). §9's "dominant: ×1.77" becomes ×1.76.
- **Closing check.** `git grep -nE "×1\.77|x1\.77" -- METHOD.md RESULT.md physics_note.md` returns nothing, and every 20–30 keV factor in RESULT.md matches the per-Hz line in §1d to the digits quoted.

### R3. One MonP gated variant is now covered only within the 2 s.e. allowance
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7), with a nit.** METHOD.md:434 states it. Its "about 0.8 % on the high bound at 25 keV" is 0.64 % (S3a).
- **Status (Architect, 2026-11-13): stated, no band change.** METHOD.md §7(f) now says that the reach +10 % / σ −20 % corner on MonP is covered only within 2 MC s.e. at 23–27 keV (up to 0.004 above Λ_hi, about 0.8 % on the high bound at 25 keV).
- **Severity:** low, informational.
- **Where.** `analysis/out/wall_loss/MonP/combo_range+10_sigma0.8.csv` against the live band. At 25 keV the f_pe-scaled loss is 0.0041 above Λ_hi; on the 0.05 keV interpolated grid, 32 of 321 points (around 23–27 keV) are above it by up to that amount. The f_pe-scaled MC standard error there is 0.0021, so the 2 s.e. allowance is 0.0042: it covers the 0.0041 with 0.0001 to spare. At 9fff096 this file was covered strictly.
- **Scenario.** A rerun of the families with more electrons (smaller s.e.), or any small change in the MonP fit near 25 keV, turns this into a gate failure without any change in the physics. Separately, METHOD.md §7(f) says the band "covers" the corner, which a reader takes as strict.
- **Proposed fix.** Either keep it and say in METHOD.md §7(f) that the reach +10 % / σ −20 % corner on MonP is covered only within 2 MC s.e. at 23–27 keV, or widen the band there (the 0.09 cap binds at 25 keV).
- **Closing check.** METHOD.md §7(f) states it, or a strict check (no s.e. allowance) of that file passes.

### R4. `wall_loss_fit.py`'s report table prints 18.5 and 19.5 keV as "18" and "20"
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** Both fit reports show 18.5 and 19.5 keV rows.
- **Status (Architect, 2026-11-13): fixed.** Table row format `{e:5g}`; both .txt files regenerated, and the diff is the two energy labels per file only.
- **Severity:** cosmetic.
- **Where.** `analysis/out/wall_loss_fit_MonP.txt` and `_MonC.txt`: the per-energy table shows two rows labelled 18 and two labelled 20. Architect changed the MISSES line to `{e:g}` in a84c2ca, but not the table's format.
- **Scenario.** A reader of the fit report sees two different targets for "18 keV" and thinks the MC is inconsistent.
- **Proposed fix.** `{e:g}` (or `{e:4.1f}`) in the table row too, then regenerate the two .txt files.
- **Closing check.** The two .txt files show 18.5 and 19.5 keV rows.

**Carried to the consolidation audit (not a finding here).** `analysis/wall_loss_mc.py`'s docstring and its defaults (`HALF_GAP = BASE_HALF_GAP = 0.5` cm, the `wall_loss()` banner "vertical plates ±5 mm … 1 mm FWHM") still describe the 10 mm vertical-plate chamber. The lane geometry comes only from `wall_loss_families.py`'s arguments. That is the question of where the chamber dimensions live, which the user asked for separately.

---

## 6. Consolidation audit (HEAD 1a06b94 and 59bcea2): where each fact lives, and the stale copies

**Scope and method.**
- Tracked files at 1a06b94, read-only. The append-only log (PROGRESS.md), the plan-change rows (PLAN.md, which are dated history) and this file are excluded. Raw data under `data/queries/` and `references/` are excluded too.
- Each fact was located with fixed-string and regex `git grep`, and the copies were compared with the source named in the "Lives in" column.
- Also checked: the two worktrees under `.claude/worktrees/` and this session's own memory notes, outside the repo.
- Architect committed 59bcea2 (N1 accepted, N2: bit 1 at 12.5 keV) during the audit. It changes only the bit-1 lines in METHOD.md and calc/OPERATOR.md (row 12), so the findings below hold at 59bcea2. The line numbers are the same at both commits.
- Not audited: the untracked `FLUX_NOTE_REPLY.md` / `.docx`.

### 6.1 Inventory

"Lives in" is where the value is defined today. Where that is code or a generated table, the code is the truth for the live calc.

| # | Fact group | Lives in (one place today?) | Other copies | Copies current? |
|---|---|---|---|---|
| 1 | Chamber dimensions, electrodes, mounting (collector 60.5 mm, HV plate 75.5 mm, guards 1 mm away, set back 0.51 mm, gap 10.85 ± 0.2 / ± 0.5 mm, plates 60 mm wide, shell, slots; MonP vertical, MonC horizontal) | **`analysis/cmc_chamber_geometry.py`**, one place: every value is tagged MEASURED / INTERPRETED / ASSUMED, and `collection_length_cmc.py`, `wall_loss_families.py`, the figures and the `lanes.py` plate check all import it | METHOD.md chamber paragraph and §6; physics_note.md §3.1 "Measured 2026-11-13"; RESULT.md (gap only) | Those are current. **Stale:** physics_note.md §1 and §3.6 (C2), calc/OPERATOR.md and calc/PRESSURE.md (C6), TODO.md and normalization_proposal.md (C7) |
| 2 | Beam position and size (MonC 4.90 mm from the collector, 5.95 mm from HV, offset 0.525 mm; vertical size 20–40 µm, 0.03 mm taken; horizontal ~1 mm; MonP centred, ASSUMED) | **Split.** The MonC position is in the geometry module (derived from the Kapton scar). The beam widths, and MonP's offset of 0, are constants in `analysis/wall_loss_families.py` (C8) | METHOD.md §0 and §6; physics_note.md §1 and §3.1 | Consistent |
| 3 | HV, 2.7 kV (supply readout, not verified) | **No source file.** Prose only | METHOD.md §0 and 2a; physics_note.md §1 and §3.6; `data/sweeps/monc_sweep1_results.md` | Same value everywhere; physics_note.md §3.6 has it "across 1 cm" (C2) |
| 4 | Collection length: l_eff = 61.925 mm, L_CM = 6.19 cm, ± 1.4 % | `analysis/out/collection_length_cmc.csv` → `calc/monp_transform.py` L_CM, with a self-test tying the two together | METHOD.md 3g and §7(a); RESULT.md; physics_note.md §3.1 and §3.7; calc/HANDOFF.md; calc/OPERATOR.md | Current, except calc/PRESSURE.md:27 (C6) and RESULT.md's tolerance list, which omits the plate gap (C9) |
| 5 | **MonC per-gain uncertainty**: factor, u, dark, dark sd per gain | **`data/calibration/monc_sr570_ranges.csv`**, one place. Generated by `analysis/make_monc_calibration.py` from a hashed step log, so it is reproducible. Not used live: `calc/monc_gain_cal.py` is a draft, so the live calc carries 0.7 % at every gain | ELECTRONICS_CONCLUSIONS.md §1 and §3; tools/OPERATOR.md; TODO.md | ELECTRONICS_CONCLUSIONS.md matches the table (range factors re-referenced to 5 µA/V agree to 0.01 %). **tools/OPERATOR.md's dark sd values are stale** (C4) |
| 6 | **Leakage current at 2.7 kV**, −2.6 ± 12.8 pA (zero), and the +21.5 ± 1.3 Hz output-side offset from the cabled chamber | ELECTRONICS_CONCLUSIONS.md §1 and §5, with the evidence in `monc_sweep1_results.md` "Leakage run" and `analysis/monc_leak.py`. The calibration table's header repeats both | tools/OPERATOR.md (−3 ± 13 pA, ~21 Hz) | The leakage value is consistent. **The no-beam breakdown "8.4 + ~10 Hz SR570 + 40 Hz" survives in three places** (C4) |
| 7 | **MonC operating state** (gain, offset, cabled or not) | **Nowhere current.** tools/OPERATOR.md "Current MonC setting" plus this session's memory notes | PLAN.md leakage row | Unknown whether the chamber was reconnected after 12:26 on 2026-11-13 (C5) |
| 8 | MonC/MonP electronics conclusions (linearity, noise, floors 8.4 Hz and 1 count, drift, temperature, settling, state errors) | ELECTRONICS_CONCLUSIONS.md, with the evidence in `monc_sweep1_results.md` | tools/OPERATOR.md; TODO.md; physics_note.md §3.5 | Consistent, except ELECTRONICS_CONCLUSIONS.md's own §2 (C3) |
| 9 | Symmetric budget (μ_en 3, W 0.6, electronics 0.7, density 0.2, fit 0.9, collection 1.4 → σ_s 3.56 %, 1.036 / 0.964) | **`calc/quality_slots.py` SYMMETRIC_TERMS** (live) | RESULT.md; physics_note.md §3.7; METHOD.md §7; calc/OPERATOR.md | Current there. **Stale:** ELECTRONICS_CONCLUSIONS.md §2 (C3); physics_note.md §3.1 and §3.3 (C2) |
| 10 | Wall-loss fits and band (MonP 17.9 / 19.7 / 1.17, MonC 18.1 / 27.0 / 1.41) | `calc/quality_slots.py` WALL_FITS and BAND, gated by `analysis/wall_loss_fit.py` | METHOD.md (7 places); physics_note.md; calc/HANDOFF.md | Current (round 4) |
| 11 | Gas references: ρ₀ = 1.1221e-3 at 99.26 kPa and 24.9 °C (MC reference); site mean 98.99 kPa and 24.9 °C at 228 m | `calc/monp_transform.py` and `calc/quality_slots.py`; climatology in `analysis/out/` | METHOD.md; RESULT.md; physics_note.md; calc/PRESSURE.md; calc/OPERATOR.md; `wall_loss_mc.py` | Consistent: each copy says which of the two it is |
| 12 | Status bit 1 threshold, 12.5 keV since 59bcea2 (was 12.6) | `calc/quality_slots.py` FLAG1_E_KEV | METHOD.md:504; calc/OPERATOR.md:47 and :55 | Current: 59bcea2 changed all three with the code |
| 13 | MonP dark (no-beam rate at 500 nA/V) | calc/OPERATOR.md, the archived table (227 ± 33, 182, 192 Hz) | METHOD.md §4 and RESULT.md (182–227 Hz); ELECTRONICS_CONCLUSIONS.md §2 (190–284 cps, the same interval in 1 s counts) | Consistent with each other, but ELECTRONICS_CONCLUSIONS.md says "`RESULT.md` assumes 50–100 Hz", which is no longer true (C3) |

**Summary.** The numbers have good homes, but there are **five** of them: the geometry module, the calibration table, `quality_slots.py`, ELECTRONICS_CONCLUSIONS.md and METHOD.md. Nothing indexes them, and the prose documents restate the values instead of pointing to the source. That restating is how every stale copy below arose. Each one is a sentence written before a measurement landed and not revisited when it did.

### 6.2 Findings

#### C1. There is no single place where the MonP/MonC facts live, and nothing indexes the five that exist
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7), with S1.** CHAMBER_FACTS.md covers the 13 groups (57 rows). The checker gives PASS on HEAD, and FAIL on 9 of 12 planted errors; the 3 it misses are S1.
- **Status (Architect, 2026-11-13): fixed, option (a)** (user: "One register (a)"). `CHAMBER_FACTS.md` holds 57 facts in the 13 groups of §6.1, each with value, ±, tag, date and source, and the file that defines it. `analysis/check_chamber_facts.py` evaluates the 49 coded rows against their sources: PASS, and a planted-error test (gap 10.86, MonP p 1.18, bit 1 12.6) gives 3 × DIFFERS and FAIL. 8 rows (MonC state, floors, the N1 acceptance, MonP dark) have the register as their home. Groups 5 and 8 point to the calibration table and ELECTRONICS_CONCLUSIONS.md and quote only the values cited elsewhere.
- **Severity:** medium. This is the user's request, and the structural cause of C2–C9.
- **Where.** See §6.1. CLAUDE.md also asks for a `README.md` indexing the subprojects; there is none (nor `RUNBOOK.md` or `HEALTH_CHECK.md`, which are outside this audit).
- **Scenario.** The next measurement, for example MonP's own SR570 grid or MonP's beam position, lands in one file. Every prose copy of the old value then goes stale silently, as the 6 cm, 1 cm and unguarded description did in physics_note.md §1 (C2).
- **Options for the user** (the decision is the user's):
  - **(a) One register.** A tracked `CHAMBER_FACTS.md` (or similar): one row per fact, with value, unit, tag (MEASURED, ASSUMED, …), date, source and the file that defines it. Prose documents link to its rows instead of restating them; METHOD.md and RESULT.md keep only the worked numbers. A small check script compares the register with the geometry module, the calibration table and `quality_slots.py`, so the register cannot drift from the code.
  - **(b) Designated homes plus an index.** Keep the five sources and add `README.md` with a "where each fact lives" table (§6.1 is a draft). Each prose copy gets a pointer to its source.
  - This session's recommendation is **(a)**. One file is what the user asked for, and a register checked against code is the only form that stays true without someone remembering to update it.
- **Closing check.** The chosen home exists, and each of the 13 groups in §6.1 is either in it or pointed to from it. A re-run of this audit's greps finds no restated value that disagrees with its source.

#### C2. physics_note.md still opens with the unguarded 6 cm / 1 cm chamber
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7), with S2.** The closing grep matches only lines marked as history (139, 164, 419). §5 item 5 at :406 still says "Already known: no guards" (S2).
- **Status (Architect, 2026-11-13): fixed.** §1 describes the guarded chamber with F-IDs; l = l_eff = 6.19 cm (F4.2); the LOW_FACTOR paragraph, the fringe-field heading and the §6 "no guard electrodes" answer are marked as history; ±3.56 %; 2.7 kV across 10.85 mm; and the §3.1 beam distances (4.9 mm). The closing grep matches only lines marked as history (139, 164, 419).
- **Severity:** medium. §1 is the first description of the chamber a reader meets, and it contradicts everything after 2026-11-13.

| Location | Says | Should say |
|---|---|---|
| `physics_note.md:22–23` | "Collection plates are 6 cm long with a 1 cm gap [PROVISIONAL, user]"; "The plates are vertical … **no guard electrodes** [user, 2026-11-12]" | guarded CMC-custom design, collector 60.5 mm, gap 10.85 mm, MonP vertical, MonC horizontal; pointer to the geometry module |
| `physics_note.md:46` | "**l = 6 cm.** The plate length stands in for the effective collection length; this is the dominant uncertainty (§3.1)" | l = l_eff = 6.19 cm, ± 1.4 %; μ_en (± 3 %) is now dominant |
| `physics_note.md:162` | "The **present** low bound, LOW_FACTOR 0.86 … ±3.27 % symmetric terms" | past tense; it is inside the section marked as superseded |
| `physics_note.md:287` | "(Since 2026-11-13 the total carries … ±3.27 %.)" | ±3.56 %, with collection 1.4 % |
| `physics_note.md:352` (§3.6) | "2.7 kV across 1 cm" | across 10.85 mm |

- **Scenario.** A maintainer reads §1, takes the chamber as unguarded with l = 6 cm, and "corrects" the 6.19 cm in the calc back to 6.0 cm. That is a 3.1 % shift in every published flux.
- **Closing check.** `git grep -nE "6 cm long|no guard electrodes|l = 6 cm\.|present low bound|±3\.27|across 1 cm" physics_note.md` returns only lines explicitly marked as history.

#### C3. ELECTRONICS_CONCLUSIONS.md §2 carries the budget from before the chamber was measured
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** The closing grep returns nothing; the figure pointer names main (929a5bb).
- **Status (Architect, 2026-11-13): fixed.** §2 gives ±3.56 % and ×1.036 / ×0.964 (F9.5, F9.6); the MonP dark row says that RESULT.md now gives 182–227 Hz (F13.1) and that the dark is subtracted live; there is no one-sided term; the figures are on main (merge 929a5bb, C10). The closing grep returns nothing.
- **Severity:** medium. It is the electronics source document, and it states a wrong total.

| Location | Says | Should say |
|---|---|---|
| `ELECTRONICS_CONCLUSIONS.md:46` | "RESULT.md gives MonP's total as ±3.2 % without the collection-length term"; "its total is ±3.27 % and the live high bound is ×1.033" | ±3.56 % with collection 1.4 %; ×1.036 / ×0.964 |
| `ELECTRONICS_CONCLUSIONS.md:54` | "`RESULT.md` assumes 50–100 Hz" (MonP dark) | RESULT.md now gives 182–227 Hz and subtracts the dark live |
| `ELECTRONICS_CONCLUSIONS.md:56` | "The total stays ±3.2–3.3 %, plus the one-sided collection-length term (0 to −13 %)" | ±3.56 %, symmetric; no one-sided term |
| `ELECTRONICS_CONCLUSIONS.md:128–135` | the electronics figures live "on branch `claude/figures-c4aacd` (commit ca2c812, not merged here)" | that branch is now at 3e20aac and still unmerged (C10) |

- **Scenario.** Someone weighing whether a MonP SR570 grid is worth a maintenance window reads §2 and compares the electronics term with a 13 % collection term that no longer exists. The value of the grid is then misjudged by a factor of several.
- **Closing check.** `git grep -nE "3\.2–3\.3|0 to −13|×1\.033|assumes 50–100" ELECTRONICS_CONCLUSIONS.md` returns nothing, and the figure pointer names a merged path, or says why it isn't merged.

#### C4. The MonC no-beam breakdown and dark scatter are stale in the operator guide and two other places
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** tools/OPERATOR.md:47 has the CSV dark sd; :51 has the breakdown with +21.5 Hz and about −10 Hz (8.4 + 21.5 + 40 − 10 ≈ 60; detached 8.4 + 40 − 10 ≈ 38.5); results-file lines 262 and 267 are struck through with a correction.
- **Status (Architect, 2026-11-13): fixed.** tools/OPERATOR.md: the breakdown includes the +21.5 Hz connection (F6.2) and about −10 Hz SR570 output offset, the detached and cabled rates (F7.3, F7.4), and the dark sd from the calibration CSV (F5.2). monc_sweep1_results.md: both lines struck through with a correction, in the file's own style. TODO.md: the dark includes F6.2 when cabled.
- **Severity:** medium, because tools/OPERATOR.md is what someone at the beamline reads.

| Location | Says | Measured since |
|---|---|---|
| `tools/OPERATOR.md:50` | interim ≈59 Hz = "8.4 Hz V2F zero + ~10 Hz SR570 output offset + a calibrated 40 Hz" | the chamber connection adds +21.5 Hz, and the unplugged reading is ≈38.5 Hz. So the SR570's own output share at 5 µA/V is about −10 Hz, not +10 Hz (38.5 − 8.4 − 40) |
| `data/sweeps/monc_sweep1_results.md:262` and `:267` | "Every dark … is V2F zero + SR570 output offset"; "58.8 Hz is 8.4 + ~10 Hz SR570 + 40 Hz" | the same. The file already strikes through its other superseded "~1 nA" reading, but not these lines |
| `TODO.md:29` | "Every quoted MonC dark includes [the 8.4 Hz]" | and the +21.5 Hz from the chamber when cabled |
| `tools/OPERATOR.md:47` | dark sd per reselection "7 Hz at 500 nA/V, 3.5 … 1 µA/V, 2.5, 1, 0.6 and 16 Hz at 20 µA/V" | the calibration table: 7.8, 3.8, 2.5, 1.0, 0.6, **18.9** Hz (and 21.6 at 200 nA/V) |

- **Scenario.** An operator sees 38.5 Hz with no beam and reads it, from the breakdown, as the SR570 output offset having fallen by 20 Hz. They raise a fault, or ask for an `A3init`, which writes the SR570, when the chamber is simply unplugged.
- **Closing check.** tools/OPERATOR.md quotes the breakdown with the chamber term, and quotes its dark sd values from `data/calibration/monc_sr570_ranges.csv` (or points to it). The two results-file lines are struck through with a pointer, as for "~1 nA".

#### C5. Nothing records whether MonC's chamber is cabled now
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** tools/OPERATOR.md:50 and CHAMBER_FACTS F7.2: detached, user-confirmed ~16:55 on 2026-11-13. The read-only S4 check was not run by this session.
- **Status (Architect, 2026-11-13): fixed.** User, 2026-11-13 ~16:55: "monc is not cabled up, it's still detached". CHAMBER_FACTS F7.2 (detached, since 10:13); tools/OPERATOR.md "Current MonC setting" leads with it; calc/OPERATOR.md says the MonC lane's flux is not a beam measurement while detached. The read-only S4 check was not run (it needs a no-beam window).
- **Severity:** medium. The MonC lane's background, and the "20–120 Hz" sanity band in tools/OPERATOR.md, both depend on it.
- **Where.** `tools/OPERATOR.md:57` says "With the chamber unplugged (since 2026-11-13 10:13) it reads ≈38.5 Hz … Expect ~60 Hz again once the chamber is reconnected". The leakage run (12:09–12:26) ran unplugged, and no later tracked line says it was reconnected. This session's memory note also still gives ≈59 Hz as current.
- **Scenario.** With the chamber still unplugged, MonC sees no beam signal at all. The MonC lane then publishes a flux near zero, which is a number, not an error by design (calc/OPERATOR.md). Anyone using MonC in the meantime normalises by nothing.
- **Proposed fix.** The user says what the state is. tools/OPERATOR.md "Current MonC setting" then gets it, with the date and time and who observed it. A read-only S4 check (about 38 Hz versus 60 Hz with no beam) can confirm it from outside.
- **Closing check.** tools/OPERATOR.md states the cabling state with a date after 12:26 on 2026-11-13.

#### C6. Two calc documents still describe the old chamber
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** The closing grep returns nothing.
- **Status (Architect, 2026-11-13): fixed.** calc/OPERATOR.md: the same design, mounted with the plates horizontal, own fit (F1.3, F10.2); calc/PRESSURE.md: `1 − exp(−6.19·M·K)` and `exp(−6.19·N·K)` over l_eff (F4.2). The closing grep returns nothing.
- **Severity:** low.

| Location | Says | Should say |
|---|---|---|
| `calc/OPERATOR.md:38` | "It assumes MonC is a CMC-custom chamber of MonP's geometry. Not yet confirmed." | the same design, confirmed by the user on 2026-11-13; mounted with the plates horizontal, so it has its own wall-loss fit |
| `calc/PRESSURE.md:27` | "O = 1 − exp(−6·M·K) fraction absorbed in the 6 cm plates" | `1-EXP(-6.19*M*K)`, over l_eff = 6.19 cm |

- **Scenario.** An operator who reads "not yet confirmed" discounts MonC's flux, which now rests on a measured chamber.
- **Closing check.** `git grep -nE "Not yet confirmed|exp\(−6·M·K\)|6 cm plates" calc/` returns nothing.

#### C7. TODO.md and normalization_proposal.md ask for chamber facts that have been delivered, or state the opposite of them
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** TODO.md:19 ticked; the reminder is gone; :24 and :41 rewritten to what is open; normalization_proposal.md:32 and :76 answered with pointers.
- **Status (Architect, 2026-11-13): fixed.** TODO: fringe-field item ticked as superseded; geometry reminder ticked; the MonC addendum is rewritten to what is open; "MonP specifics" lists the beam position (F2.5), l_gap and HV at the chamber (F3.1). normalization_proposal.md: K_C sentence and the question answered with a pointer.
- **Severity:** low.
- **Where.**
  - `TODO.md:19`: the unguarded fringe-field item; "Needed from the user: the plate-end-to-end-wall gap …". Delivered 2026-11-13, and the chamber is guarded.
  - `TODO.md:35`: "REMINDER FOR THE USER: provide CMC-custom ion chamber geometry details". Delivered.
  - `TODO.md:41`: "MonP geometry. Known: no guards, vertical plates." Wrong on guards. Still open: MonP's beam position, and l_gap.
  - `TODO.md:24`: MonC "addendum: different plate geometry, HV and electronics". Same design; the electronics are measured.
  - `normalization_proposal.md:32` and `:76`: "Is MonC also a CMC-custom chamber with the same geometry as MonP?" Answered: yes, mounted differently.
- **Scenario.** The user is asked again for measurements already taken, or a new session plans work on a "different MonC geometry".
- **Closing check.** Those TODO items are ticked or rewritten to what is still open (MonP beam position, l_gap, HV readout), and the proposal's question is answered with a pointer to the geometry module.

#### C8. Beam size and HV feed the models but are not in the geometry source
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** The four PARAMS exist with tags; `wall_loss_families.families()` reads them; the 22 commands built by the old (961c2e4^) and new modules have identical arguments.
- **Status (Architect, 2026-11-13): fixed.** PARAMS gains beam_fwhm_vertical (0.03, MEASURED, 0.02–0.04), beam_fwhm_horizontal (1.0), monp_beam_offset (0.0, ASSUMED) and hv (2.7 kV). `wall_loss_families.families()` reads them; MONC_VERTICAL_FWHM_MM is removed. The 22 generated MC commands are byte-identical before and after (diff). The closing grep finds only the docstring's "0.03 taken".
- **Severity:** low.
- **Where.**
  - `analysis/wall_loss_families.py:27` `MONC_VERTICAL_FWHM_MM = 0.03`, and `:34` MonP `"offset_mm": 0.0, "fwhm_mm": 1.0`. These are constants in an MC driver, not tagged values in `cmc_chamber_geometry.py`.
  - The 2.7 kV HV exists only in prose.
- **Scenario.** MonP's beam position is measured (it is ASSUMED centred now) and entered in the geometry module, as the module's docstring asks. The MC families still run centred, and nothing fails.
- **Proposed fix.** Add `beam_fwhm_vertical` (0.02–0.04 mm, user), `beam_fwhm_horizontal` (~1 mm, user), `monp_beam_offset` (0, ASSUMED) and `hv` (2.7 kV, supply readout, unverified) to PARAMS, and have `wall_loss_families.py` read them.
- **Closing check.** `git grep -n "0.03\|fwhm_mm\": 1.0\|offset_mm\": 0.0" analysis/wall_loss_families.py` shows only reads from `cmc_chamber_geometry`, and PARAMS has the four entries with tags.

#### C9. RESULT.md: the first-live-reading line and the tolerance list predate the refit
- **Status, round 5 (reviewer, 2026-11-13): CLOSED, verified (§7).** RESULT.md:75 has 3.56 × 10¹², 6.2 × 10¹², 5.0–7.7 × 10¹²; :48 names the plate gap.
- **Status (Architect, 2026-11-13): fixed.** 3.56 × 10¹², 6.2 × 10¹², 5.0–7.7 × 10¹²; the tolerance list names the plate gap at the beam track.
- **Severity:** low.
- **Where.**
  - `RESULT.md`, first live reading: "formula flux of 3.55 × 10¹² and a best estimate of 6.2 × 10¹² ph/s, range 5.0–7.6 × 10¹²". Round 4 recomputed it: 3.559 → **3.56**, 6.227 → 6.2, 5.013 – 7.656 → 5.0 – **7.7** × 10¹². This was missed by R1, which covered only METHOD.md.
  - `RESULT.md:46`, the collection-length tolerance list (guard gap, guard recess, collector length, beam height, HV plate): it now also includes the plate gap (Q4).
- **Closing check.** The RESULT.md line matches the §1d first-reading row of this file, and the tolerance list names the plate gap.

#### C10. Two worktrees hold old copies of every document, and one holds knowledge that is cited from main
- **Status, round 5b (reviewer, 2026-11-13): CLOSED.** User: "Yes, remove it" (the merged `monc-dark` worktree). `git worktree remove .claude/worktrees/monc-dark` (no --force; the worktree was clean and `monc-dark` is an ancestor of main) unregistered it and deleted its files; the branch `monc-dark` is kept. Windows left the empty folder in place ("resource busy": some process has it as its working folder) and it can be deleted once that process closes. `git worktree list` now shows main and `figures-c4aacd`, which belongs to the Figure man session and is kept.
- **Status, round 5 (reviewer, 2026-11-13): PARTLY CLOSED (§7).** The figures are merged (929a5bb); elec1–elec5 and `review_by_figure_man.md` are on main. The closing check is not met: both worktrees are still listed. Removing the merged `monc-dark` worktree is the user's call; nothing in the record says the user decided it.
- **Status (Architect, 2026-11-13): figures merged** (user: "merge the figures elec1-5"): `claude/figures-c4aacd` (3e20aac) merged as 929a5bb. PROGRESS.md kept both sides (append only), and monc_sweep1_results.md kept main's newer superset. `make_figures.py --only electronics` builds elec1–elec5 on main. The merged `monc-dark` and `figures-c4aacd` worktrees are left in place for the user to remove.
- **Severity:** low. The decision is the user's.
- **Where.** `git worktree list`:
  - `.claude/worktrees/monc-dark` at 9bb7cbf (merged into main);
  - `.claude/worktrees/figures-c4aacd` at 3e20aac, on `claude/figures-c4aacd`, **not merged**. It holds the electronics figures elec1–elec5 and `data/sweeps/review_by_figure_man.md` (findings F9, F10), which ELECTRONICS_CONCLUSIONS.md cites.
- **Scenario.** A plain search of the project folder, which is what this audit's first grep did, finds old chamber and budget numbers in both worktrees. Meanwhile the electronics figures cited from main exist only on an unmerged branch.
- **Proposed fix (user's call).** Merge the figures branch, or record in ELECTRONICS_CONCLUSIONS.md that its figures and F9/F10 live there. Remove the merged `monc-dark` worktree once nobody is using it.
- **Closing check.** `git worktree list` shows only worktrees in use, and every file ELECTRONICS_CONCLUSIONS.md cites exists on main or is labelled as on its branch.

---

## 7. Round 5 (HEAD 961c2e4): closing checks for everything open

**Checks run** (read-only, bluesky venv, `-I -X utf8`; the working tree was clean):

| Check | Result |
|---|---|
| Architect's edits to this file | 1a06b94: 6 insertions; 961c2e4: 10 insertions; 0 deletions in either. Status lines only |
| Self-tests | `monp_transform.py`, `quality_slots.py`, `lanes.py`, `background_transform.py`: **PASS** |
| Independent recompute (round-4 script, unchanged) | The live CLCC/CLCD/CLCE/CLCO/CLCP strings are as in round 4, and CLCF is `A>12.5` on both lanes. Every gated wall-loss file is covered within 2 s.e. on both lanes, at the MC energies and on the 0.05 keV grid (40 of 40 file × grid checks). Collection term 1.357 %. 30 keV and first-live-reading numbers identical to §1d |
| Bit 1 (N2) | 1 eV scan, 12–14 keV, at 0.900–0.960 ρ₀ in 0.001 steps: the band is widened with bit 1 clear only at ≤ 0.933 ρ₀ (from 12.245 keV at 0.90 ρ₀); never from 0.934 ρ₀ up |
| Closing greps | R1, R2, Q2, C3, C6: no hits. C2: only lines marked as history. A broad re-sweep for the old values (11.2 mm, 1 cm gap, no guards, ±3.27, ×1.033, LOW_FACTOR 0.86, ~10 Hz SR570, 12.6 keV, 18.7 keV, ×1.77, 3.2–3.3) finds only history lines, the superseded `wall_loss_bound.py` and its output, the MC script's documented defaults, the fringe-field figure's labelled old scan, and physics_note.md:406 (S2) |
| C8: MC commands | The 22 commands built by `wall_loss_families.command()` before (961c2e4^, loaded from git) and after have identical arguments |
| `analysis/check_chamber_facts.py` | Read-only. HEAD: "57 facts, 49 checked against code or tables, 8 defined in the register itself", **PASS** |
| Planted errors, own set (12 cases on scratch copies of the register) | **FAIL, as it should**, for: gap 10.85 → 10.95; 60.5 → 60.6 (one unit in the last digit); vertical → horizontal; one value of the MonP fit changed; a fit value missing; a duplicate ID; a misspelt tag; the leakage sign flipped. PASS for 60.5 → 60.50 (within rounding, correct). **PASS, but should fail:** a row given an extra `|` with a wrong value; a row missing a cell with a wrong value; a coded row's check cell changed to "register" with a wrong value (S1) |
| Privacy | No IP addresses, e-mail addresses or account or host names in the files new to main (`analysis/figures/`, `review_by_figure_man.md`, `site.env.template`, `.gitignore`, CHAMBER_FACTS.md, the checker, FLUX_NOTE_REPLY.md). The .docx was not scanned |
| Not run | `install_lane --compare` (installer, live IOC); the read-only S4 check of MonC's detached rate |

### S1. The facts checker passes when a register row is malformed
- **Status, round 6 (reviewer, 2026-11-13): CLOSED, verified.** On e7a6d69 the checker gives PASS (60 facts, 52 checked). My 12 planted cases plus three new ones (F7.2 deleted, F5.6 +0.62 → +0.72, an F5.4 factor changed) all give FAIL, except the within-rounding case, which correctly passes.
- **Status (Architect, 2026-11-13): fixed.** `check_chamber_facts.py`: every line starting `| F<n>.<n> |` is read, and one without 9 cells fails (MALFORMED). REGISTER_ONLY lists the 8 IDs that may say "register" (F7.1–F7.4, F8.1, F8.2, F10.4, F13.1): any other "register" row fails (NOT ALLOWED), a listed row that gains a check fails, and a listed row that is deleted fails (MISSING). Counts are printed but not pinned. Planted, each gives FAIL: F1.4 with a '|' in the Fact cell and 61.5 mm (10 cells); F1.7 with a cell missing (8); F1.5's check replaced by "register"; F7.2 deleted. HEAD gives PASS.
  - **Found while doing this:** `tolerance()` didn't accept a leading '+', so '+0.62' got a tolerance of 0.5 and passed a planted +0.72. It now takes [+-] and an exponent sign, and any form it can't parse gets no tolerance (strict). Re-planted: F5.6 +0.72 and F5.5 0.040 → 2 × DIFFERS, FAIL. No row before this change used a '+' value, so no earlier PASS depended on it.
- **Severity:** low to medium. The checker is what keeps the single register true (C1), and this is its blind spot.
- **Where.** `analysis/check_chamber_facts.py` `rows()` keeps only lines with exactly 9 cells, and skips any other `| F…` line without a word. A row whose check cell reads "register" is never compared with anything, and the script doesn't know which rows are allowed to be register-only.
- **Scenario.** Someone edits F1.4 and writes "Collector | upper plate" in the Fact cell, and with it a wrong length. That row now has 10 cells, so it drops out: the script reports "56 facts" and **PASS**. The same happens with a missing cell, or when a coded row's check is replaced by "register". Each of these was planted here and passed.
- **Proposed fix.** Fail on any line that starts with `| F<n>.<n> |` and doesn't have 9 cells. Fail when a row in a section that has a code source (§1–§6, §9–§12) has check = "register", unless its ID is on a short list in the script. Optionally, print the counts and pin them in the test.
- **Closing check.** The three planted cases above each give FAIL. The other nine still give FAIL, and HEAD gives PASS.

### S2. physics_note.md §5 still lists the chamber geometry as a measurement to make, with "no guards"
- **Status, round 6 (reviewer, 2026-11-13): CLOSED, verified.** `git grep -n "Already known: no guards" physics_note.md` returns nothing.
- **Status (Architect, 2026-11-13): fixed.** §5 item 5 now reads "Done 2026-11-13 … guarded (CHAMBER_FACTS §1)" and keeps only l_gap, MonP's beam position (F2.5) and the HV at the chamber (F3.1) open. The closing grep returns nothing.
- **Severity:** low.
- **Where.** `physics_note.md:406`, §5 item 5: "**Geometry.** Plate length, gap, thickness and width; which plate collects; plate-to-body and plate-to-window distances, including l_gap. (Already known: no guards; vertical plates.)"
- **Scenario.** A reader planning hutch time asks the user again for plate dimensions taken on 2026-11-13, and reads that the chamber has no guards.
- **Proposed fix.** Mark the item done on 2026-11-13 (CHAMBER_FACTS §1), and leave only what is open: l_gap, MonP's beam position (F2.5) and the HV at the chamber (F3.1).
- **Closing check.** `git grep -n "Already known: no guards" physics_note.md` returns nothing.

### S3. Small inaccuracies in the new text
- **Status, round 6 (reviewer, 2026-11-13): CLOSED, verified.** (a) METHOD.md:434 says about 0.6 %; (b) F7.4 says ≈ 60.0 with the 0.9 Hz difference; (c) F3.1 OBSERVED, F10.4 DECISION; (d) F5.4–F5.6 are checked against the calibration CSV and cited from ELECTRONICS_CONCLUSIONS.md.
- **Status (Architect, 2026-11-13): fixed, all four.** (a) METHOD.md:434 → about 0.6 %. (b) F7.4 now says ≈ F7.3 + F6.2 = 60.0, and that the windows differ by 0.9 Hz, inside ±1.3. (c) F3.1 tagged OBSERVED, in the register and in `cmc_chamber_geometry.py` (OBSERVED added to its tag list); F10.4 tagged DECISION (added to the register's tags and the checker's). (d) New rows F5.4 (gain factor per gain), F5.5 (its u) and F5.6 (range-to-range relative to 5 µA/V: +0.08, +0.24, −0.12, +0.15, +0.62 %), checked against the CSV; ELECTRONICS_CONCLUSIONS.md §1 and §3 cite F5.6. Register: 60 facts, 52 checked, PASS.
- **Severity:** low (nits).
- **(a)** `METHOD.md:434` says the MonP corner's 0.004 excess is "about 0.8 % on the high bound at 25 keV". At 25 keV Λ_hi = 0.3514 and the variant is 0.3555, so the shortfall is (1 − 0.3514)/(1 − 0.3555) − 1 = **0.64 %**: about 0.6 %.
- **(b)** CHAMBER_FACTS F7.4 gives 59.1 Hz "(= F7.3 + F6.2)". 38.5 + 21.5 = 60.0. The two measured windows differ by 0.9 Hz, inside F6.2's ±1.3. Write "≈", or give both numbers.
- **(c)** Tags. F3.1, the HV, is tagged MEASURED but is a supply readout not verified at the chamber; the register's own OBSERVED fits it better. F10.4, a risk the user accepted, is tagged LIVE.
- **(d)** The user named "uncertainty per gain" as one of the facts to consolidate. The register has rows for MonC's dark and dark scatter per gain, but none for the per-gain factor and its u (the CSV's `factor` and `u_factor_rel` columns). ELECTRONICS_CONCLUSIONS.md §1 and §3 still quote the range factors (+0.24 %, +0.62 %, …) without a row ID. They agree with the CSV (§6.1, row 5).
- **Closing check.** Each item is fixed, or explicitly declined in its status line.

---

**Out of scope:** the SR570 interrogation and the MonC sweep work (branch `monc-dark`) were not reviewed as experiments. §6 checks only where their numbers are copied.
