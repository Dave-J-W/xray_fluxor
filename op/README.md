# op: the flux dashboard (Phoebus)

The operator display for the three flux lanes defined in this repository (`calc/`, `fluxor/`). It lives here, next
to the code that defines its PVs, in the way synApps modules keep their displays in `op/`. The utilioc IOC that runs
the lanes is in the site repository (15IDC HA), which vendors the generated `.bob` byte for byte (its
`ioc/utilioc/tools/vendor_dashboard.py`, with the commit and sha256 in `screens/flux_dashboard.SOURCES.txt`). Moved
here from 15IDC HA on 2026-11-17 (user: "Yes, move them"; PLAN.md).

## What it shows
A read-only Phoebus 4.7.4 display, opened with macro `P` = `15IDC:util:` (from the **Flux dashboard** button in utilioc's
header, or on its own). It shows the photon flux of this repository's three lanes: the E-station IC-500-50, MonP and
MonC. Top: one card per chamber (RESULT in photons/s, low and high, up and down %, a state chip). The **Details**
button of a card picks the chamber for the tabs below (a local selection, `loc://flux_sel`; nothing is written to the
IOC). Tabs: Inputs, Corrections, Flags (bit 1 is shown here only, as informational), Uncertainty budget (the symmetric
terms with their tags, a stacked bar of their variance shares, the live wall-loss and recombination terms, the live
up and down), Model parameters (every parameter with value, unit, tag, source and what closes it; ASSUMED and
PROVISIONAL rows drawn tinted; the last page shows the live `.CLC*` strings and DESC of each slot), Trends (user,
2026-11-17: strip charts of this chamber's RESULT with low and high, net current or rate, and energy, and of the three
RESULTs together on a log axis, each over 10 minutes, 1 hour and 24 hours). **The trends are live history only**: they plot
what the display received since it was opened and start empty; nothing is read from the archiver (retrieval stays a
long-term goal). Card rows, top to bottom: high, up %, RESULT (very large), down %, low. SR570 sensitivity is shown in
µA/V (a read-only formula PV scaling the record's A/V by 1e6).

State chip: ALARM (flag 16 or 32), NO DATA (RESULT INVALID: an input link is dead), NO BEAM or LOW CURRENT (flag 8; the
number stays), WARNING (flag 2 or 4), none otherwise; NO CONTACT while utilioc's heartbeat is not there. Flag 1 never
shows on a card. **The E-station card carries a standing note: the lane does not detect a frozen TetrAMM** (the readings
stop changing with no alarm; a freeze detector is proposed in `TODO.md`, not built).

## How to open it
- At the beamline: the **Flux dashboard** button in utilioc's header (the site's vendored copy).
- From a checkout: open `op/bob/flux_dashboard.bob` in Phoebus with macro `P=15IDC:util:` (see the phoebus skill for a
  separate instance next to your own). It only reads.

## How to change it
1. Change the lanes or the budget here (`calc/`, `fluxor/parameters.toml`), then `tools/export_dashboard_model.py`
   (writes `docs/dashboard_model.json`).
2. Change the layout in `op/tools/gen_dashboard.py` if needed. Never edit the `.bob` by hand.
3. `python -I -X utf8 op/tools/gen_dashboard.py op/bob/flux_dashboard.bob`, then
   `python -I -X utf8 op/tests/check_dashboard.py --static` (also run by `tests/test_dashboard.py`).
4. Commit and publish to GitHub. Then refresh 15IDC HA's copy from a clone of the public repo (next section).
5. After the lanes are reinstalled: `op/tests/check_dashboard.py --live` (CA gets only, `EPICS_CA_ADDR_LIST` set,
   `EPICS_CA_AUTO_ADDR_LIST=NO`) must report every `.CLC*` string equal to the export.

## For an agent working in 15IDC HA
The full procedures are in `RUNBOOK.md` (§2 lanes, §3 the change chain, §5 vendoring); this is the short form.
Everything the site repository needs is in the public repository https://github.com/Dave-J-W/xray_fluxor:
```bash
git clone https://github.com/Dave-J-W/xray_fluxor.git      # or: git -C xray_fluxor pull
```
- **Phoebus:** `python3 ioc/utilioc/tools/vendor_dashboard.py <clone> ioc/utilioc/screens` copies `op/bob/flux_dashboard.bob`
  and writes `flux_dashboard.SOURCES.txt` (the public commit and the sha256); `--check` says whether the copy is current.
  Commit that in 15IDC HA; shipping to the host is the user's step.
- **The IOC (the lanes in utilioc's slots):** the slot expressions are defined in `calc/` (`calc/lanes.py`,
  `calc/estation_lane.py`) and installed over Channel Access by `calc/install_lane.py --lane MonP|MonC|EStn`
  (`--dry-run` and `--compare` first; see `calc/HANDOFF.md`, "Verify / reinstall"). Installing writes to the IOC, so it
  needs the user's OK each time. The E-station lane's source PV names (TetrAMM, energy, temperature) are not published:
  copy `calc/estation_pvs.template.json` to the gitignored `calc/estation_pvs.local.json` and fill it in from the running
  IOC (the installed `userTran9` input links, read with `caget`) or from the user. The MonP and MonC lanes need no local file. After an install, `op/tests/check_dashboard.py --live` checks that the IOC runs what the
  screen describes.
- Python: the scripts use the standard library, except `calc/` (numpy) and `op/tests/dashboard_sim.py` (caproto) and
  `--live` (pyepics).

## Files
| Path | What |
|---|---|
| `bob/flux_dashboard.bob` | generated by `tools/gen_dashboard.py`; do not edit by hand |
| `tools/gen_dashboard.py` | the generator: lane PV maps, layout; reads `../docs/dashboard_model.json` (parameters, budget terms, flag legend, slot map, expected `.CLC*` strings) |
| `tools/bob_widgets.py` | Phoebus widget helpers (colours, fonts, label, rect, textupdate, led, state_label), copied unchanged from 15IDC HA's `gen_screens.py` so the generator needs nothing outside this repository |
| `tests/check_dashboard.py` | `--static`: the `.bob` matches its generator, read-only widgets, only `$(P)` and `loc://flux_sel` names, no IP, the model adds up. `--live`: the currency check, every expected `.CLC*` string read from the IOC (CA gets only) must equal the export; a mismatch names slot, field and term |
| `tests/dashboard_sim.py` | loopback caproto simulator of the lane PVs (127.0.0.1:5076, never the network) for the state screenshots |
| `img/` | screenshots |

Screenshots: live on 2026-11-17 ([live](img/flux_dashboard_live_2026-11-17.png)); simulated, from the loopback simulator
(values made up, PV names real): [normal](img/flux_dashboard_sim_normal.png) ([Flags tab](img/flux_dashboard_sim_normal_flags.png)),
[no beam / low current](img/flux_dashboard_sim_nobeam.png) ([MonC flags](img/flux_dashboard_sim_nobeam_flags.png)), [NO DATA
(E-station), ALARM bit 16 (MonP), ALARM bit 32 (MonC)](img/flux_dashboard_sim_nodata_alarms.png), WARNING
([E bit 2, MonP bit 4, MonC bit 2](img/flux_dashboard_sim_warn_a.png); [E bit 4, MonP bit 2, MonC bit 4](img/flux_dashboard_sim_warn_b.png)),
[ALARM bit 32 on the E-station, bit 1 only on MonP (no chip)](img/flux_dashboard_sim_bit1_alarm32.png) with
[its Flags tab](img/flux_dashboard_sim_bit1_alarm32_flags.png), [IOC down](img/flux_dashboard_sim_ioc_down.png), live trends ([picture](img/flux_dashboard_live_trends_2026-11-17.png)).
MonC "detached" is just its no-beam state: the card has no hand-written DETACHED banner (user, 2026-11-17).
