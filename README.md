# xray_fluxor

Absolute and relative x-ray incident flux from ion-chamber currents, for the ChemMatCARS (15-ID) ion chambers:
- **MonP** and **MonC**, the C-station chambers (SR570 → V2F → scaler);
- the **IC-500-50** at the E-station (TetrAMM).

It provides three things:
- the method (counts or current to photons/s, with its uncertainty);
- the live calculation that runs in the utilioc IOC's slots, one **lane** per chamber;
- the operator display of those lanes.

**Public repository:** https://github.com/Dave-J-W/xray_fluxor. Procedures for installing, updating, publishing and
recovering are in [RUNBOOK.md](RUNBOOK.md).

## Where to start
| You want | Read |
|---|---|
| **Convert monitor counts or current to photons/s yourself (an agent's handoff)** | [docs/handoff_counts_to_photons.md](docs/handoff_counts_to_photons.md) |
| The number and how far to trust it | [RESULT.md](RESULT.md), [UNCERTAINTY.md](UNCERTAINTY.md) |
| The method, step by step, with worked examples | [METHOD.md](METHOD.md), with the evidence in [physics_note.md](physics_note.md) |
| The chamber and electronics facts (one register, checked against code) | [CHAMBER_FACTS.md](CHAMBER_FACTS.md) (`analysis/check_chamber_facts.py`) |
| The electronics measurements | [ELECTRONICS_CONCLUSIONS.md](ELECTRONICS_CONCLUSIONS.md) |
| The live lanes: what the PVs mean (operators) | [calc/OPERATOR.md](calc/OPERATOR.md) |
| The live lanes: design, install, traps (maintainers) | [calc/HANDOFF.md](calc/HANDOFF.md), [calc/PRESSURE.md](calc/PRESSURE.md) |
| The offline package (any chamber and electronics chain) | [fluxor/OPERATOR.md](fluxor/OPERATOR.md), [fluxor/HANDOFF.md](fluxor/HANDOFF.md), [fluxor/PARAMETERS.md](fluxor/PARAMETERS.md) |
| The Phoebus dashboard | [op/README.md](op/README.md) |
| Plan, decisions, history | [PLAN.md](PLAN.md) (with its plan-changes table), [PROGRESS.md](PROGRESS.md) (append-only), [TODO.md](TODO.md), [METHOD_REVIEW.md](METHOD_REVIEW.md) |

## Inventory: what lives where

### In this repository (tracked, published)
| Path | What | Documents |
|---|---|---|
| `calc/` | The lanes: the slot expressions of each lane (`lanes.py` for MonP and MonC, `estation_lane.py` for the E-station), the constants they come from (`monp_transform.py`, `quality_slots.py`, `background_transform.py`), the installer (`install_lane.py`), the pressure updater's design | `calc/OPERATOR.md`, `calc/HANDOFF.md`, `calc/PRESSURE.md` |
| `fluxor/` | The offline package: chamber and chain plugins, and the tagged parameter registry (`parameters.toml`, which generates `PARAMETERS.md`) that the E-station lane is generated from | `fluxor/OPERATOR.md`, `fluxor/HANDOFF.md` |
| `op/` | The flux dashboard (Phoebus 4.7.4): generator, the generated `.bob`, static and live checks, a loopback simulator, screenshots | `op/README.md` |
| `tools/` | Bench and helper tools: the pressure updater `asos_pressure.py`, the dashboard model export `export_dashboard_model.py`, MonC bench tools | `tools/OPERATOR.md`, `tools/HANDOFF.md` |
| `docs/` | `dashboard_model.json` (the model the dashboard draws: parameters, budget, flags, slot map, expected `.CLC*` strings), specs, plans, briefs | |
| `analysis/` | Models and their outputs: wall-loss Monte Carlo and fits, collection length, the facts checker, uncertainty studies, figures (`analysis/figures/`) | headers of each script |
| `data/` | Small inputs: cross-section queries, calibration tables, sweep summaries | |
| `references/` | Datasheets and the xraydb two-carrier evidence file | |
| `tests/` | `python -I -X utf8 -m unittest discover -s tests -t .` (covers fluxor, the registry, the lanes and the dashboard) | |

### Kept out of this repository, on purpose
| What | Where | Why |
|---|---|---|
| Host names, account names, site addresses | gitignored `F99_ACCESS.md`, `site.env`, `secrets.env` (a tracked `site.env.template` shows the keys) | CLAUDE.md privacy rule |
| The E-station lane's source PV names (TetrAMM, energy, temperature) | gitignored `calc/estation_pvs.local.json` (tracked template `calc/estation_pvs.template.json`) | the same rule. Anyone installing the lane takes them from the running IOC or from the user (RUNBOOK §2) |
| Raw logger data and archiver pulls | a data folder next to this checkout, not under git | size; regenerable |
| Regenerated figures | `analysis/figures/out/` (gitignored) | rerun `analysis/figures/make_figures.py` |
| The publishing gate: the private-names list, the name scan, the publishing skill | outside every repository, in the user's Claude configuration | a list of private names inside a repository would publish them (RUNBOOK §4) |
| This checkout's full git history | this PC only | old commits hold private names, so only squashed snapshots are published (RUNBOOK §4) |

### In the site repository (15IDC HA, local, no remote)
| What | Path there |
|---|---|
| The utilioc IOC that runs the lanes: records, startup, autosave, deployment | `ioc/utilioc/` |
| utilioc's own screens, and the copied calc/std screens | `ioc/utilioc/screens/utilioc.bob`, `screens/upstream/` |
| **A vendored copy of the flux dashboard** | `ioc/utilioc/screens/flux_dashboard.bob`, with the source commit and sha256 in `flux_dashboard.SOURCES.txt`, copied by `ioc/utilioc/tools/vendor_dashboard.py` |

### Running at the beamline (on the current production host)
| What | Where |
|---|---|
| MonP lane | `15IDC:util:` `userTran1`–`3` (flux, background, bounds), `userTran7` (flags), `userCalcOut1`–`2` (status, dark feed) |
| MonC lane | `userTran4`–`6`, `userTran8`, `userCalcOut4`–`5`. It reads the live pressure from the MonP lane. **The MonC chamber is detached since 2026-11-13 (CHAMBER_FACTS F7.2)** |
| E-station lane | `userTran9`–`11`, `userCalcOut9` (`userTran12` reserved) |
| Live pressure | `tools/asos_pressure.py`, run from cron under the service account, writes `userTran1.G` (`calc/PRESSURE.md`) |
| Lane configuration across restarts | utilioc's autosave (in the site repository) |

## Why the dashboard lives here, and not with the IOC
Decided by the user on 2026-11-17 ("Yes, move them"; PLAN.md, plan changes). Before that, it was generated in the site
repository.
- **A display belongs with the code that defines its PVs.** synApps modules keep their displays in `xxxApp/op/`, next to
  the databases they draw, and a site takes them from the module. In the same way, the lanes' expressions, budget and
  flags are defined here, and the dashboard draws them. Keeping the two together means one change and one review.
- **One source, no hand-kept copy.** The generator reads `docs/dashboard_model.json` directly. `tests/test_dashboard.py`
  fails if the screen falls behind it.
- **The site repository needs no copy of this code.** An agent there clones this public repository, vendors the
  generated `.bob`, and installs the lanes from the same clone (RUNBOOK §2–3). The user asked for exactly this: "As long as an agent working 15IDC HA can pull what they need from github to update the IOC and phoebus I'll be happy".
- **The site keeps a vendored copy rather than a link.** The host's screens folder must hold the `.bob` beside
  `utilioc.bob`, which opens it by a relative name. A byte-for-byte copy with its commit and sha256 is how the site
  repository already carries calc's and std's screens.
