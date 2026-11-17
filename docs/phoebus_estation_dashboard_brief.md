# Brief: build the Phoebus flux dashboard (three ion-chamber lanes)

For the agent that builds it. Updated 2026-11-17 by the agent that built and installed the lanes. **The design is decided and approved: read `docs/superpowers/specs/2026-11-17-flux-dashboard-design.md` first; it binds.** This brief is the PV map, the facts about the live lanes, and the checklist. Nothing is built yet.

## Rules that bind you (CLAUDE.md and the user)
- **Read-only on the IOC.** Indicators only: no write to any slot, TetrAMM, mono or beamline PV; no restart.
- **Only utilioc PV names** (`15IDC:util:`) in tracked files. The TetrAMM, mono and temperature source names are private; the lane republishes everything you need (see the E-station table).
- **The number is always shown**; warnings sit beside it (user rule).
- Phoebus **4.7.4** `.bob`; follow the `phoebus` skill (macro `P` with no default, a separate Phoebus instance next to the user's, live screenshots). Generated screens in `15IDC HA` are generated: follow `ioc/utilioc/screens/README.md`, do not hand-edit generated files.
- Commit as you go; **the ship to f99 is the user's step** (blocked by permissions as a production deploy: hand over the exact command). Never push.
- Python is the bluesky venv: `%USERPROFILE%\.venvs\bluesky\Scripts\python.exe -X utf8` (plain `python` is a broken stub). Live reads: `EPICS_CA_ADDR_LIST=<the subnet broadcast address, see the local F99_ACCESS.md>`, `EPICS_CA_AUTO_ADDR_LIST=NO`.

## The three lanes: PV map (all `15IDC:util:`, SCAN 1 second, EGU and PREC set)
### E-station (IC-500-50 on the TetrAMM; installed 2026-11-16)
Flux `userTran9`, bounds `userTran10`, flags `userTran11`, status `userCalcOut9`.
| What | PV | Unit |
|---|---|---|
| RESULT (best, corrected) | `userTran10.L` | ph/s |
| low / high | `userTran10.K` / `.M` | ph/s |
| up % / down % | `userTran10.N` / `.O` | % |
| formula (uncorrected) | `userTran9.P` | ph/s |
| wall-loss fraction | `userTran10.C` | fraction |
| recombination loss central / low-aspect / high-aspect | `userTran10.E` / `.F` / `.G` | fraction |
| plates constant (1 = horizontal) | `userTran10.P` | |
| channel 3 / channel 4 current | `userTran9.A` / `.B` | nA |
| net current | `userTran9.G` | A |
| dark subtracted (hand-set, default 0) | `userTran9.F` | nA |
| energy (side-bounce mono) | `userTran9.C` | keV |
| hutch air temperature | `userTran9.D` (deg F), `.H` (deg C) | |
| N2 pressure / density | `userTran9.E` / `.I` | kPa / g/cm3 |
| flags: bits 1, 2, 4, 8, 16, 32 and code | `userTran11.F .G .H .I .J .K` and `.L` | 0/1, code |
| status code with severity | `userCalcOut9.VAL` (+ `.SEVR`) | code |
Flag meanings (E-station): 1 energy above 12.5 keV (wall-loss band in use; informational on the dashboard, details only); 2 central recombination above 5 %; 4 pressure not updated for 2 h; 8 net current below 50 nA (low current: bounds understate); 16 energy outside 4.9 to 30.5 keV or NaN (alarm); 32 raw current fault: sum below -5 nA, a channel at or above 99 % of the 120 uA full scale, or NaN (alarm).

### MonP (CMC chamber, SR570 plus V2F plus scaler; installed 2026-11-12)
Flux `userTran1`, background `userTran2`, bounds `userTran3`, flags `userTran7`, status `userCalcOut1`, dark feed `userCalcOut2`.
| What | PV | Unit |
|---|---|---|
| RESULT / low / high | `userTran3.L` / `.D` / `.E` | ph/s |
| up % / down % | `userTran3.F` / `.G` | % |
| formula (uncorrected) | `userTran1.P` | ph/s |
| wall-loss fraction | `userTran3.C` | fraction |
| plates constant (0 = vertical) | `userTran3.M` | |
| scaler counts / count time | `userTran1.A` / `.B` | counts / s |
| SR570 gain index (number, unit) | `userTran1.C` / `.D` | enum indices |
| SR570 sensitivity | `userTran1.I` | A/V |
| energy (DCM) | `userTran1.E` | keV |
| hutch temperature | `userTran1.F` | deg C |
| N2 pressure / density | `userTran1.G` / `.K` | kPa / g/cm3 |
| pressure age (shared updater) | `userTran3.H` | s |
| background used / net rate | `userTran1.H` / `.J` | Hz |
| background estimate / stale flag | `userTran2.L` / `.N` | Hz / 0,1 |
| flags: bits and code | `userTran7.F .G .H .I .J .K` and `.L` | |
| status code with severity | `userCalcOut1.VAL` | code |
### MonC (same design, plates horizontal; chamber DETACHED since 2026-11-13, so its flux is not a beam measurement)
Flux `userTran4`, background `userTran5`, bounds `userTran6`, flags `userTran8`, status `userCalcOut4`, dark feed `userCalcOut5`: same letters as MonP in the corresponding slots (RESULT `userTran6.L`, low `.D`, high `.E`, plates `userTran6.M` = 1; pressure and its age come from the MonP lane: `userTran1.G`, `userTran3.H`; MonC's own bounds-slot age letter `.H` mirrors it).
**C-station flag meanings** (same bit numbers as the E-station, different meanings for 2 and 8): 1 energy above 12.5 keV (informational); 2 background stale (other gain or none); 4 pressure not updated for 2 h; 8 no beam (bounds not meaningful); 16 energy outside 4.9 to 30.5 keV (alarm); 32 scaler not counting (alarm).

## Live facts to design for (measured 2026-11-16/17)
- **The TetrAMM is currently FROZEN** (verified 2026-11-17): its IOC is connected and reports Acquiring, but the channel readings have stopped changing and all its PVs carry one last-update timestamp. The E-station lane keeps publishing the last value (about 0.70 nA on channel 3 and 0.12 nA on channel 4) with no alarm: the lane detects dead links, not frozen inputs. Do not draw conclusions from the E-station numbers until the user has the TetrAMM fixed; a freeze detector is proposed in `TODO.md`.
- RESULT and the formula go INVALID (STAT LINK) when an input link dies (for example the TetrAMM IOC down); the flags and status code do not. Colour RESULT by its own severity.
- The EPICS status shows MINOR whenever bit 1 is set (always at 30 keV): that is why the dashboard treats bit 1 as informational. The record itself is unchanged.
- With no beam RESULT is a small noise-driven number (E-station: net current under 1 nA; MonC detached: net 0.4 Hz) with the no-beam bit set.
- At 30 keV the wall-loss correction is large (MonP 42 %, MonC 26 %, E-station 29 %) and the stated bounds are about +20 % and -17 %: expected.
- A disabled lane keeps its last values with NO_ALARM: the screen cannot tell from values alone; the Slots tab shows each slot's run lamp.
- Live state at hand-off: MonP on beam at 30.0016 keV (RESULT about 6.2e12 ph/s); E-station and MonC no beam; TetrAMM connected and reading dark.

## What you must build (summary of the spec; the spec is the authority)
Top row: three cards (name, beam and mono, RESULT with unit and bounds, state chip; no sparkline in version 1). Details panel tabs: Inputs, Corrections, Flags (bit 1 only here), **Uncertainty budget**, **Model parameters** (every parameter, with its tag and source; the assumed and provisional ones drawn distinctly; plus the live `.CLC*` expression strings); the Trends tab is deferred. A model export from this repo plus a live currency check keep the displayed numbers true to what runs on the IOC.
- **Model export**: write `tools/export_dashboard_model.py` in the xray_fluxor repo (per lane: parameters with tags and sources, budget terms, factors, flag legend, slot map) and copy its JSON, stamped with the xray_fluxor commit, into the 15IDC HA repo; the generator there reads the copy. Sources: E-station `fluxor/parameters.toml` through `fluxor.params` and `calc/estation_lane.py` constants; C-station `calc/monp_transform.py` and `calc/quality_slots.py` constants.
- **Budget numbers** to reproduce (and check against the live factors): E-station symmetric terms mu_en/rho tables 3.0 %, W 0.6 %, density 0.2 %, gas stand-in P and T 1.2 %, collection length 3.0 %, TetrAMM gain 1.0 % (placeholder), energy readback 0.4 % (assumed): total 4.59 % (factors 0.954 and 1.046). C-station: tables 3.0 %, W 0.6 %, electronics 0.7 %, density 0.2 %, cross-section fit 0.9 %, guarded collection length 1.4 %, energy readback 0.4 %: total 3.58 % (0.964 and 1.036). (Energy readback added 2026-11-17; the totals were 4.57 % and 3.56 %, the factors are unchanged.)
- **Currency check** (`check_screens --live`, read-only): the budget and constants in the export reproduce the live `.CLC*` strings; a mismatch fails and names the term.

## Not in order yet (say so in your report; the user is aware)
1. **Trends are deferred.** The lane PVs are now archived (29 PVs, 2026-11-17: SCAN 10 s for the 21 fast ones, MONITOR for the 8 slow ones; the calcouts are stored without `.VAL`; the list is in the spec's Trends section), but the user has descoped Phoebus retrieval to a long-term goal and the site's Data Browser archive URL is not located. Version 1 has no sparklines and no Trends tab (leave room for them). This change was reported through the Experimenter session: say in your report that you built to it.
2. **No beam-on check of the E-station lane yet** (`TODO.md`): its RESULT, bounds and recombination terms have been verified in logic and on dark inputs only.
3. **The E-station Slots-tab and root-card changes (commit `b609297` in 15IDC HA) are not shipped**; the user ships.
4. **The numbers carry placeholders** (beam aspect and width, TetrAMM 1 % gain, gas stand-ins): they are what the Model parameters tab must make visible (`fluxor/PARAMETERS.md` is the registry's generated list).
5. **Per-channel photons/s is not live** (the lane publishes the sum): show the two currents, do not label a per-channel flux.

## Definition of done
Screens build with the generator; `check_screens.py --static` gives 0 failures; `--live` currency check passes against the real IOC (read-only); every PV in the maps is read-only on the screen; screenshots of the live state and of the simulated states (normal beam, no beam, low current, NO DATA, ALARM bit 16 and bit 32, each WARNING, bit 1 only, MonC detached) from a loopback soft IOC with the same PV names (the `cmc-epics-ioc` and `phoebus` skills); no private PV names or IPs in tracked files; the repos' docs updated in the same commits (README and HANDOFF tables in 15IDC HA; `docs/` in xray_fluxor); progress logged (append-only `PROGRESS.md`); the exact ship command handed to the user.


## Status 2026-11-17 (implementer): version 1 built
Built in `15IDC HA` (commits 438927e to 386a26e) and `tools/export_dashboard_model.py` here. Not shipped (the user's step). Trends not built, as descoped. See `calc/HANDOFF.md`, "Flux dashboard", and `PROGRESS.md`.
