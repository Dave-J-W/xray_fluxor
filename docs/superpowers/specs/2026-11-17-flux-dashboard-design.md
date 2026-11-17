# Design: Phoebus flux dashboard for the three ion-chamber lanes

Date: 2026-11-17. Status: scoped with the user on 2026-11-17; waiting for the user's review of this written spec. Nothing is built. Another agent will execute it (handoff brief: `docs/phoebus_estation_dashboard_brief.md`, to be updated to point here).

## Decisions made with the user (2026-11-17)
| Topic | Decision (user's words in quotes) |
|---|---|
| Scope | All three chambers on one dashboard: the E-station IC-500-50, MonP and MonC ("All three chambers") |
| Audience | "Both on one screen": a big-number summary for operators on top, an expert panel below |
| Trends | The user chose "Archived history" (hours to days back, per chamber). **Changed 2026-11-17, reported by the Experimenter session from the user: Phoebus retrieval of archived data is descoped to a long-term goal.** The lane PVs ARE now archived (see Trends), so the data exists, but version 1 builds no archive-backed plot: no Trends tab and no sparklines. To be confirmed with the user |
| Home | The `15IDC HA` repo, generated and checked like the existing utilioc screens; shipped to the host by the user. **Superseded 2026-11-17 (user: "Yes, move them"): the generator, screen and checks live in xray_fluxor `op/`; `15IDC HA` vendors the `.bob` (`vendor_dashboard.py`) from a clone of the public repo; PLAN.md** |
| MonC (chamber detached since 2026-11-13) | Show it like the others and rely on its own flags; no hand-edited DETACHED banner |
| Flag bit 1 (energy above 12.5 keV, wall-loss band in use) | "informational note, no warning. The error bounds are warning enough." Then: "downgrade the 'wall-loss band on' warning away from the MonP headline label and small card into the details area." So bit 1 appears only in the details Flags tab |
| Model parameters | "as long as all the modeling parameters are in the dashboard somewhere, make sure" |
| Uncertainty | "Add an uncertainty contributions/budget tab" |

## Rules that bind the build (CLAUDE.md, standing user rules)
- Read-only: indicators only; no widget writes; no write to any slot or beamline PV; no restart.
- Only utilioc PV names (`15IDC:util:`) in tracked files. The TetrAMM, mono and temperature source names stay private; the lane republishes everything the dashboard needs.
- The number is always shown ("an imperfect number with a warning beats no number"); warnings sit beside it, never replace it.
- Phoebus 4.7.4 `.bob`; follow the `phoebus` skill; macro `P` has no default.
- The ship to f99 is the user's step (production deploy); hand over the exact command. Never push.

## Layout
**Top row: one card per chamber** (E-station, MonP, MonC). Each card shows: the chamber name and the beam it sees with its energy and the mono it comes from (E-station: the side-bounce mono; MonP and MonC: the DCM; the two lines are different beams and the card says which); the RESULT in photons/s (big, with unit), the low to high bounds and the up/down percentages; a state chip; (version 1 has no sparkline: archive-backed plots are deferred, see Trends). Clicking a card selects the chamber for the details panel below.

**State chip** (derived on the screen from the lane's own PVs; bit 1 is never used here):
| State | When | Look |
|---|---|---|
| ALARM | flag bit 16 (energy outside 4.9 to 30.5 keV or NaN) or bit 32 (E-station: raw current fault; C-station: scaler not counting) | red |
| NO DATA | RESULT's severity is INVALID (an input link dead; the flags do not show this) | magenta border (Phoebus convention) |
| NO BEAM / LOW CURRENT | E-station bit 8 (net current below 50 nA); C-station bit 8 (no beam) | muted, the number stays visible |
| WARNING | E-station bit 2 (recombination above 5 %) or bit 4 (pressure not updated for 2 h); C-station bit 2 (background stale) or bit 4 | yellow |
| (none) | otherwise | no chip |
The legend text comes from the lane, not from the bit number: the same bit numbers mean different things on the two kinds of lane (bit 2 and bit 8).

**Details panel** for the selected chamber, tabs:
1. **Inputs**: raw readings and what the lane read: E-station: channel 3 and 4 currents (nA, `userTran9.A/.B`), net current, dark subtracted, energy, hutch temperature (deg F and deg C), pressure, density; C-station: count rate, count time, SR570 gain, background Hz, net rate, energy, temperature, pressure, density.
2. **Corrections**: the formula (uncorrected) flux, wall-loss fraction, recombination (E-station: central, low, high loss; C-station: not applicable), RESULT, low, high, up %, down %.
3. **Flags**: every bit with its lamp, text and class (info or warning or alarm). **Bit 1 lives here only** ("wall-loss band in use", informational), plus the code and the status record's severity.
4. **Uncertainty budget** (new): see below.
5. **Model parameters** (new): see below.
6. **Trends** (deferred, long-term goal; not in version 1): archived RESULT with its low and high, the net current or rate, and the energy; time ranges 1 h, 24 h, 7 d; one plot for the selected chamber and the three RESULTs on a comparison plot. Build the layout so the tab can be added without rework.

## Uncertainty budget tab
For each lane, a table and a stacked bar of the symmetric contributions in quadrature, the asymmetric terms listed beside them, and the live totals.
- **Symmetric terms** (relative, 1 sigma, kind A or B, quadrature). E-station (from the `fluxor` registry, `fluxor/PARAMETERS.md`): mu_en/rho tables 3.0 %, W 0.6 %, density 0.2 %, gas stand-in P and T 1.2 % (sigma 1.0 kPa and 2.0 C on the stand-in rows), collection length 3.0 %, TetrAMM range gain 1.0 % (placeholder), energy readback 0.4 % (assumed, added 2026-11-17), total 4.59 % (the slot's factors 0.954 and 1.046). C-station (from `calc/quality_slots.SYMMETRIC_TERMS`): mu_en/rho tables 3.0 %, W 0.6 %, electronics 0.7 %, density 0.2 %, cross-section fit 0.9 %, guarded collection length 1.4 %, energy readback 0.4 % (added 2026-11-17), total 3.58 % (0.964 and 1.036). Before 2026-11-17 the totals were 4.57 % and 3.56 %; the factors did not change.
- **Asymmetric, energy-dependent terms** (live): the wall-loss fraction (and its band around it: the live flux bounds carry it), and, E-station only, the recombination range between the low and high beam aspect ratios. Show the live wall loss and recombination PVs beside the static numbers, and state that these widen the live up/down percentages beyond the quadrature total.
- **Live totals**: up % and down % of RESULT (E-station `userTran10.N/.O`; C-station `userTran3.F/.G`, `userTran6.F/.G`), and the quadrature total from the table, so the reader sees how much of the stated uncertainty is the symmetric budget and how much the energy-dependent corrections add.
- **Not in the live budget** (stated on the tab): the TetrAMM noise term (the lane does not carry it; the low-current flag covers it), and any per-channel split.
- Each term carries its status (the registry tag: given, derived, choice, assumed, provisional) so assumed placeholders are visible as such.

## Model parameters tab
Every parameter the lane uses, not only those with a PV: generated tables per lane with name, value, unit, tag (given, measured, derived, choice, provisional, assumed), source and "closes with" for the placeholders; the assumed and provisional rows are drawn distinctly. Sources:
- E-station: every row of `fluxor/parameters.toml` that the lane consumes (gap, voltage, l_eff and its allowance, electrode width, split band, wall-loss fit constants, beam width and aspect rows, recombination constants, gas stand-in values and sigmas, TetrAMM range, gain placeholder, dark sigma, unit, spectrum, the symmetric terms), plus the lane's derived constants and thresholds (W/(e*1e3), the flag thresholds in `calc/estation_lane.py`: 12.5 keV, 5 %, 7200 s, 50 nA, 4.9 to 30.5 keV, -5 nA, 99 % of 120 uA).
- C-station: the constants of `calc/monp_transform.py` and `calc/quality_slots.py` (W 34.8 eV, collection length 6.19 cm, the per-lane wall-loss fit E0, s, p, the band constants, the symmetric terms, the density reference and range exponent, the cross-section fit coefficients, V2F scale 1e5 Hz/V, the background rule: threshold 400 Hz, settle 10 s, averaging 60 samples).
- **As installed** (live, read-only): for each slot the expression strings (`.CLCA` to `.CLCP`, string PVs) and the slot DESC, in a collapsible area, so the numbers actually running on the IOC are visible next to the tables.

## Keeping the displayed parameters and budget true
The tables are static text generated at build time; the constants live inside slot expressions on the IOC, so a drift is possible. Design:
- A **model export** in this repo (`tools/export_dashboard_model.py`, to be written) emits one JSON file per build from the registry and the calc modules: per lane the parameters (with tags and sources), the budget terms, the factors, the flag legend, the slot map. The 15IDC HA generator reads a committed copy of that JSON (with the xray_fluxor commit it came from) so the two repos stay decoupled.
- A **currency check** (`check_screens --live`, read-only) reads each slot's live `.CLC*` strings and the DESCs and verifies that (a) the sigma terms in the export reproduce the live factors (the quadrature total gives the HF and LF constants found in the live bounds expression), (b) the wall-loss fit constants and the other constants in the export appear in the live strings, (c) the slot map matches. A mismatch fails the check and names the term. Static checks verify the generated screen against the JSON.
- The tables carry the xray_fluxor commit and the date of the export in a footer.

## Trends and the archiver (updated 2026-11-17)
- **Archived (the user's go-ahead, "Yes, archive them", 2026-11-17; checked by the Experimenter session):** 29 lane PVs, all "Being archived" and connected, prefix `15IDC:util:`. **SCAN 10 s (21):** `userTran10.L .K .M`, `userTran9.P .C .A .B .G`, `userTran1.P .J .E`, `userTran3.L .D .E .H`, `userTran4.P .J`, `userTran6.L .D .E`, `userTran5.L`. **MONITOR (8):** `userTran11.L`, `userCalcOut9`, `userTran7.L`, `userCalcOut1`, `userTran8.L`, `userCalcOut4`, `userTran2.L`, `userTran1.G`. The rule used: SCAN 10 s for PVs updating at 0.09 Hz or faster, MONITOR for slower than 0.1 Hz (measured over 120 s). **The archiver stores the calcouts without `.VAL`** (`userCalcOut9`, `userCalcOut1`, `userCalcOut4`): a plot must use those names. Not archived (not requested): the per-bit flags, `userTran6.F/.G`, `userTran10.N/.O` and the recombination PVs.
- **Phoebus retrieval is a long-term goal (the user).** The Data Browser archive URL setting for the site has not been located; the Experimenter found a candidate (an unverified pbraw URL on the archiver host, port 17668) and the management UI on port 17665, which the user uses. Do not build archive-backed widgets in version 1; when retrieval is taken up, locate the site's Data Browser setting first.
- **The E-station rows are not trustworthy until the TetrAMM is fixed** (see Open item 0): the readings are frozen.

## Technical approach
One generated display in the `15IDC HA` repo, built by a small generator in the same style as `gen_screens.py` and `gen_root.py`, with a chamber **panel template** used three times; each use gets its slot numbers and labels as macros (E-station: userTran9, 10, 11 and userCalcOut9; MonP: userTran1, 2, 3, 7 and userCalcOut1; MonC: userTran4, 5, 6, 8 and userCalcOut4) and its flag legend. A checker (`check_screens.py --static` and `--live`) covers structure, PV names (utilioc only, none private), read-only widgets, the macro expansion for all three, and the currency check above. The existing root card links to the dashboard.

## Test and verification
No writes to the real slots. Build a local soft IOC with the same PV names (see the `cmc-epics-ioc` skill; loopback only) and Phoebus screenshots (the `phoebus` skill) of: normal beam, no beam, low current, NO DATA (INVALID), ALARM (bit 16, bit 32), WARNING (pressure stale, E-station recombination, C-station stale background), bit 1 only (no chip on the card, lamp on the Flags tab), MonC detached (no beam); plus the live state at the time of the build. The dashboard is also checked live, read-only, against the real IOC with the currency check.

## Out of scope
Per-channel photons/s (the live lane publishes the sum; the dashboard shows the two currents but does not label a per-channel flux); a dark-estimator slot (userTran12 is reserved); any change to the slots or the IOC; the beam-on verification of the E-station lane (still a to-do in `TODO.md`); shipping the screens to the host; alarm-handler configuration.

## Open items
0. **Input freshness (found 2026-11-17).** The E-station lane detects dead links (RESULT goes INVALID) but not FROZEN inputs: on 2026-11-17 the TetrAMM IOC stayed connected but stopped updating (channel readings constant over many seconds, all its PVs sharing one last-update timestamp), and the lane kept publishing a flat RESULT with no alarm. The dashboard cannot tell either. A follow-up change to the lane (a freeze detector, with a flag or MAJOR severity) is proposed in `TODO.md`; it needs the user's approval because it changes the installed slots.
1. The archiver request (waits on the survey).
2. The beam-on check of the E-station lane has not happened; until it does, the E-station RESULT and bounds are verified in logic and on dark inputs only.
3. The user's review of this spec was given on 2026-11-17; the handoff brief is updated; the other agent builds it.
