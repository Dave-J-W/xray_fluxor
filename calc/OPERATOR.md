# MonP photons/s on utilioc: operator guide

**The rule:** the flux is **always** published. When it is less trustworthy, the record raises an EPICS warning (MINOR or MAJOR) and the stated bounds widen. The number does not disappear.

*How far to trust the number for absolute flux, and for normalising a scan: `UNCERTAINTY.md`.*

## What to read
| PV | Meaning |
|---|---|
| `15IDC:util:userTran3.L` | **MonP exit flux, BEST ESTIMATE, photons/s** (after the collection region, before the Kapton exit window), wall-loss corrected. Its alarm severity tells you how far to trust it |
| `15IDC:util:userTran3.D` / `.E` | **stated low / high bounds** around it, photons/s |
| `15IDC:util:userTran1.P` | the standard ion-chamber **formula** only, *not* wall-loss corrected. **Not the result:** it is outside the result's bounds above ~17 keV, by design. Equal to the result below ~17 keV; 0.57 of it at 30 keV on MonP, 0.73 on MonC |
| `15IDC:util:userTran3.C` / `userTran6.C` | fraction of the signal lost to the plates (Monte Carlo of each chamber as mounted). MonP: 0 below ~18 keV, 0.07 at 20, 0.26 at 25, 0.43 at 30 keV. MonC (plates along the E-vector, so less loss): 0.02 at 20, 0.14 at 25, 0.27 at 30 keV |
| `15IDC:util:userTran3.F` / `.G` | the same as **+% / −%** |
| `15IDC:util:userCalcOut1.VAL` | **status code**: the sum of the status bits (0 OK; any bit MINOR; 16 or 32 MAJOR). See "Status code" below |
| `15IDC:util:userTran3.M` / `userTran6.M` | **plate orientation** of MonP / MonC as mounted: 0 = plates vertical (MonP), 1 = plates horizontal (MonC). A fixed value; it changes only if a chamber is remounted |
| `15IDC:util:userTran2.L` | MonP background (no-beam) estimate, Hz. It is subtracted from the flux |
| `userTran1.J` | MonP net rate, Hz (counts / count time − background) |
| `userTran1.I` | MonP SR570 sensitivity, A/V (5e-07 = 500 nA/V) |
| `userTran1.E` | mono energy, keV |
| `userTran1.F` | hutch temperature, °C |

All four slots update once per second. Each has its own screen with every value and a comment: utilioc screen → Slots tab → userTran1, userTran2, userTran3, userCalcOut1, userCalcOut2.

## MonC: the same, in its own lane
MonC has an identical set of slots. Read it exactly as MonP, with these slot numbers:

| | MonP | MonC |
|---|---|---|
| best-estimate exit flux ph/s | `userTran3.L` | `userTran6.L` |
| standard formula (uncorrected) | `userTran1.P` | `userTran4.P` |
| low / high bound | `userTran3.D` / `.E` | `userTran6.D` / `.E` |
| status code | `userCalcOut1.VAL` | `userCalcOut4.VAL` |
| status bits | `userTran7.F`–`.K` | `userTran8.F`–`.K` |
| background Hz | `userTran2.L` | `userTran5.L` |
| scaler / SR570 | scaler1.S3 / 15IDC:A2 | scaler1.S4 / 15IDC:A3 |

Notes on MonC:
- MonC uses MonP's live pressure and the same energy and temperature.
- MonC is the same CMC-custom design as MonP (user, 2026-11-13), mounted with its plates horizontal, so it has its own wall-loss fit (CHAMBER_FACTS F1.3, F10.2).
- **MonC's chamber is detached at present (CHAMBER_FACTS F7.2).** MonC then sees no beam, and its lane's flux is not a beam measurement until the chamber is reconnected.
- Its background includes the interim CAL +2 nA offset: ≈59 Hz at the standard 5 µA/V with the chamber cabled, ≈38.5 Hz detached (F7.4, F7.3). At 20 µA/V the no-beam rate (~610 Hz) is above the 400 Hz threshold (`userTran5.F`), so the background stops updating there unless `.F` is raised.
- With no beam at MonC, the net rate and flux sit around zero and can be slightly negative. That is a number, not an error; the bounds are then meaningless.

## Status code: what it means
The status code is a **sum of bits**, one per condition. Each bit is also its own 0/1 PV, so a screen can show every condition by name. Any bit set gives MINOR; 16 or 32 give MAJOR.

| Bit | MonP PV | MonC PV | Meaning when 1 | Effect on the number |
|---|---|---|---|---|
| 1 | `userTran7.F` | `userTran8.F` | energy above 12.5 keV | photoelectrons can reach the plates. Above ~17 keV the RESULT is Monte-Carlo corrected, and from ~13 keV its bounds widen (MonP: +15/−11 % at 20 keV, +23/−20 % at 30 keV; MonC: +14/−6 %, +18/−15 %) |
| 2 | `userTran7.G` | `userTran8.G` | **this monitor's** background estimate is stale: taken at another SR570 gain, or none yet (MonP: `userTran2`, MonC: `userTran5`) | the last background is still subtracted; ≤0.3 % at normal rates |
| 4 | `userTran7.H` | `userTran8.H` | the live pressure has not updated for 2 h (shared by both monitors) | the last pressure is used; weather drift ~0.4 %/day |
| 8 | `userTran7.I` | `userTran8.I` | no beam: this monitor's rate has been below its no-beam threshold for longer than the settle time | the flux is ~0 and the bounds are not meaningful |
| 16 | `userTran7.J` | `userTran8.J` | energy outside 4.9–30.5 keV (MAJOR) | the cross-section fit is extrapolated |
| 32 | `userTran7.K` | `userTran8.K` | the scaler is not counting (MAJOR) | no rate |
| **code** | `userTran7.L` = `userCalcOut1.VAL` | `userTran8.L` = `userCalcOut4.VAL` | sum of the bits above | |

Example: code 3 = 1 + 2 (above 12.5 keV, and the background is stale). Code 9 = 1 + 8 (above 12.5 keV, no beam).

Below 13 keV the bounds are the flux × 0.964 and × 1.036: ±3.6 %, the symmetric terms in quadrature (μ_en tables 3 %, W 0.6 %, electronics 0.7 %, density 0.2 %, cross-section fit 0.9 %, collection length 1.4 %, energy readback 0.4 %; RESULT.md). The chamber is guarded and was measured on 2026-11-13, so the collection length is now a small symmetric term rather than a one-sided −14 %. Above 13 keV the wall-loss model's own uncertainty is added on both sides.

## When the number is wrong, and what to do
| You see | Why | Do |
|---|---|---|
| P jumps by ×2, ×2.5 or ×10 with no beam change | the SR570 gain was changed on the **front panel**. EPICS only knows gains sent from EPICS (listen-only RS-232) | change gains only from EPICS; or set the front panel back |
| Status 1 right after a gain change | the background estimate was taken at the old gain | close the shutter for ~20 s once; the background re-measures itself |
| P is 0 | no beam, or the scaler is not counting (then status 2) | start the scaler (AutoCount) |
| Slot magenta (INVALID, LINK) | an input PV is not answering | check the scaler, the SR570 IOC (15IDC:A2), the mono, Sensor2 |

## Background estimate (userTran2)
- It updates by itself whenever MonP's raw rate stays **below 400 Hz** (`.F`) for **more than 10 s** (`.G`): a closed shutter or a beam dump. The shutter PV is not used.
- It is a running mean of up to 60 samples (`.I`), then an average over about the last minute. With beam on, it holds its last value.
- `.N` = 1 means stale: it was taken at another SR570 gain, or none has been taken yet. It is still subtracted, and the flux shows MINOR.
- `.O` is the seconds since its last update.
- If the dark ever drifts above 400 Hz, it stops updating; raise `.F`.
- Archived today (2026-11-12), `15IDC:scaler1.S3` below 400 Hz:

  | Time (local) | Mean rate |
  |---|---|
  | 12:42–13:24 | 227 ± 33 Hz |
  | 13:29–13:32 | 182 Hz |
  | 13:32–13:34 | 192 Hz |

## Live pressure
*(The full data flow, sensitivities and failure behaviour are in `calc/PRESSURE.md`.)*
- `userTran1.G` is the N2 pressure, kPa. It is written by `tools/asos_pressure.py` on the production host, from the newest LOT airport observation (14 km away; stations agree to 0.05 %).
- `userTran3.H` counts the seconds since the last update. After **2 h** without an update the status goes to **MINOR** (the flux keeps using the last pressure).
- If the updater stops, the last value stays. Worst case it drifts from the truth by about 1–3 % over a day of weather. In an emergency you can set `userTran1.G` by hand (site mean at the hutch, 228 m: 98.99 kPa).

## Hand-set values (kept across restarts by autosave)
- `userTran2.F` / `.G` / `.I`: background threshold 400 Hz, settle 10 s, averaging 60 samples.

## Turning it off
Set the slot's Enable to 0 (`15IDC:util:userTran1Enable`, and so on). Nothing outside `15IDC:util:` is ever written by these slots.

## E-station flux (IC-500-50, TetrAMM): offline definition, not installed yet
When installed it will give the E-station beam flux in photons/s on slots `userTran9` (formula), `userTran10` (RESULT and bounds), `userTran11` (flags) and `userCalcOut9` (status code). Read it like MonP: the number is always published, and the alarm and the bounds say how far to trust it. It is a **relative normalising number first**: the chamber, beam size and gas conditions are placeholders (the registry's ASSUMED rows), so the absolute scale is uncertain.

| PV | Meaning |
|---|---|
| `15IDC:util:userTran10.L` | **RESULT**, photons/s at the exit of the collection region, with the wall-loss and recombination corrections |
| `15IDC:util:userTran10.K` / `.M` | stated **low / high** bounds, photons/s |
| `15IDC:util:userTran10.N` / `.O` | the bounds as +% / −% of RESULT |
| `15IDC:util:userTran9.P` | the plain formula (no wall-loss or recombination correction): **not the result** |
| `15IDC:util:userTran9.F` | **dark current, nA, hand-set** (default 0): enter the TetrAMM dark if known; it is subtracted from the sum of the two channels |
| `15IDC:util:userCalcOut9.VAL` | status code (0 OK; any bit MINOR; 16 or 32 MAJOR) |

Status bits (each is also its own 0/1 value, `userTran11.F`–`.K`; the code is `userTran11.L`):

| Bit | Meaning when 1 | What to do |
|---|---|---|
| 1 | energy above 12.5 keV: the wall-loss band is in use | nothing; the bounds are wider |
| 2 | recombination loss above 5 % (a very high chamber current, roughly above 14 µA total) | nothing; the RESULT already corrects it and the bounds carry its range; consider a lower beam current or attenuation |
| 4 | the live pressure has not updated for 2 h | check the pressure updater (same as MonP); the last pressure is used |
| 8 | low current: net current below 50 nA (no beam, or a very weak signal) | the flux is small or 0 and the stated bounds understate the uncertainty (the noise is a large fraction of the signal); do not use the number for normalising |
| 16 | energy outside 4.9–30.5 keV, or the readback is NaN (MAJOR) | check the mono readback; the cross-section fits are extrapolated. At E = 0 the flux and bounds read inf; above about 60 keV HIGH can fall below RESULT |
| 32 | raw current sum below −5 nA, a channel at/above 99 % of the TetrAMM full scale, or a NaN reading (MAJOR) | negative: check the TetrAMM offset and the dark. Full scale: reduce the beam or change the TetrAMM range. NaN: check the TetrAMM |

A dead or disconnected TetrAMM can make RESULT go INVALID (its severity) while the status code stays 0, so check RESULT's own severity as well as the status. A slot shown magenta (INVALID) means an input is not answering: the TetrAMM, the mono readback, the hutch temperature or the MonP pressure. To turn the lane off, set the Enable of each of the four slots to 0.

### Installing, checking and removing the E-station lane (maintainer, bluesky venv, `EPICS_CA_ADDR_LIST` set)
Needs `calc/estation_pvs.local.json` (the source PV names; see the template). Always list first:
```
python -X utf8 calc/install_lane.py --lane EStn --dry-run     # read-only: checks the four slots, lists every write, writes nothing
python -X utf8 calc/install_lane.py --lane EStn               # install and verify
python -X utf8 calc/install_lane.py --lane EStn --compare     # read-only: expect "0 field(s) differ"
python -X utf8 calc/install_lane.py --lane EStn --remove --dry-run   # list what removing would write
python -X utf8 calc/install_lane.py --lane EStn --remove      # give the four slots back
```
- A slot counts as free only if its description is exactly the factory default (`user Transform N`; a calcout shows its record name) and it has no links or expressions. Anything else, including a changed description with nothing else set, is treated as someone else's and every mode refuses (exit 1) and writes nothing.
- The dry-run, the install and error messages print the real source PV names (the TetrAMM, energy and temperature links). Do not paste that output into a file that is tracked in git.
- A first install brings the lane up on two test currents (2400 and 1600 nA) with the TetrAMM links empty, checks the formula, and only then connects the TetrAMM. During that time (a few to ten seconds) `userTran9.P` shows a test flux that is not real; nothing else consumes it yet. A **re-run** of a lane that is already installed first switches all four slots off, so everything reading them (`userTran10.L` and so on) holds its last real value, frozen and without a new alarm, for roughly 10 to 20 seconds, then each slot comes back as it verifies. It never shows a test flux. Do not run an install or re-install during a measurement. A hand-entered dark (`userTran9.F`) is kept on a re-install unless you add `--reset-values`.
- **"WARNING ... TetrAMM link(s) ... not connected from this PC"** with `LANE OK (with 1 WARNING)`: the lane is installed, but the TetrAMM IOC is not answering. The flux is INVALID (and 0) until it comes back. Start the TetrAMM IOC, then run `--compare`.
- **"WARNING: the utilioc does not see the TetrAMM"** with `LANE OK (with 1 WARNING)`: this PC can read the TetrAMM but the utilioc cannot (network route or broadcast setting). The lane is installed but the flux is INVALID and 0; the formula was not checked on live currents. Fix the route, then run `--compare`. Only the line `verified on live currents` means the formula was checked on real currents. It is also withheld, with a WARNING, when the beam is off (this PC reads less than 5 nA in total: "beam off or currents below 5 nA") or when the slot's alarm is INVALID (a link is not answering; the TetrAMM inputs, energy, temperature or pressure): then run `--compare` and re-check with beam on.
- `LANE FAILED` (with or without a `MISMATCH` line): the install stopped. Every slot it had touched has been switched OFF (Enable 0) and the test currents were zeroed first, so the lane is not being updated any more. **A switched-off lane's PVs are not cleared: they keep their last values, with no alarm (SEVR NO_ALARM) and no sign that they are stale.** The installer zeroes the flux and bounds first so the last values are 0, not a test flux, but nothing downstream may rely on a disabled lane: check `Enable` (and `--compare`) before trusting any E-station number. To recover, fix the cause and run the install again, or run `--lane EStn --remove` to give the four slots back. If the last line says `cleanup is INCOMPLETE`, set the PVs it lists (an Enable, or A/B of `userTran9`) to 0 yourself. Send the output to the maintainer; do not use the flux.
- `--remove` returns the four slots to the factory defaults (descriptions, comments, empty expressions, Enable on but doing nothing); it never touches a slot that is not ours. If it prints `REMOVE FAILED`, the removal is partly done (slots before the failing one are restored, the failing one is partly restored, the rest are switched off but not restored); fix the cause and run it again.
- `--compare` prints `utilioc not reachable` and exits 2 if the utilioc does not answer.


## Flux dashboard (2026-11-17)

A read-only Phoebus display of the three lanes (E-station IC-500-50, MonP, MonC), opened from the **Flux dashboard** button in utilioc's header. It is generated in this repository (`op/`, see `op/README.md`) and copied to utilioc's screens by the site repository. Each card shows RESULT in photons/s, the low and high bounds, up and down %, and a chip: **ALARM** (flag 16 or 32), **NO DATA** (RESULT is INVALID: an input link is dead), **NO BEAM** or **LOW CURRENT** (flag 8; the number stays), **WARNING** (flag 2 or 4), **NO CONTACT** (utilioc not answering). Flag 1 (energy above 12.5 keV) never shows on a card; it is on the Flags tab as information. Tabs: Inputs, Corrections, Flags, Uncertainty budget, Model parameters (ASSUMED and PROVISIONAL rows are tinted; the last page shows the expressions running on the IOC). The Trends tab (this chamber, and all three RESULTs on a log axis; 10 minutes, 1 hour, 24 hours) is live history only: it starts empty when the display opens and nothing is read from the archiver. Card rows, top to bottom: high, up %, RESULT, down %, low.

**The E-station card is not a trusted measurement while the TetrAMM is frozen.** The lane detects a dead input link, not readings that have stopped changing, so it keeps publishing the last value with no alarm (found 2026-11-17). The card says so. A freeze detector is proposed in `TODO.md`; it is not built.
