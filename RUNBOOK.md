# Runbook: install, update, publish, recover

The procedures for this repository and for the parts of the site repository (15IDC HA) that come from it. What lives
where, and why, is in [README.md](README.md) ("Inventory"). Rules that apply throughout (CLAUDE.md):
- **Anything that writes to the IOC needs the user's OK for that action.** That covers installing a lane, a `caput`, and
  freeing a slot. One OK doesn't cover the next.
- **Changing an SR570 gain or offset always needs the user. MonP is never touched.**
- **Pushing to GitHub needs the user's go for that push.**

Python on the beamline PC: the bluesky venv (`%USERPROFILE%\.venvs\bluesky\Scripts\python.exe`, run with `-I -X utf8`).
Channel Access: set `EPICS_CA_ADDR_LIST` to the subnet broadcast address and `EPICS_CA_AUTO_ADDR_LIST=NO`.

---

## 1. Get a working checkout
```bash
git clone https://github.com/Dave-J-W/xray_fluxor.git
```
```bash
python -I -X utf8 -m unittest discover -s tests -t .
```
```bash
python -X utf8 analysis/check_chamber_facts.py
```
- The tests must report OK (one test skips without the local PV file) and the facts checker must report PASS.
- Local files a clone doesn't have:
  - `calc/estation_pvs.local.json`, needed only to install the E-station lane (§2);
  - `site.env` (from `site.env.template`), needed only by the archiver analysis scripts.
- **Why a clone is enough:** everything the lanes and the dashboard need is published. Only private values are left
  out, and each has a template (README, "Kept out").

## 2. Install, reinstall or check a lane on utilioc
Always start read-only:
```bash
python -X utf8 calc/install_lane.py --lane MonP --compare
```
```bash
python -X utf8 calc/install_lane.py --lane MonP --dry-run
```
- `--compare` diffs every generated field against the live IOC and writes nothing. 0 differences means the IOC runs
  this checkout's lane.
- `--dry-run` lists the writes an install would make.
- **Install** (with the user's OK): `python -X utf8 calc/install_lane.py --lane MonP`. It refuses a slot owned by
  someone else, writes with readback, and ends with "LANE OK".
  - Hand-set values (the live pressure, background thresholds) are written only to a fresh slot, or with `--reset-values`.
  - So a re-run never overwrites the live pressure.
- Lanes: `MonP`, `MonC`, `EStn`.
  - MonC reads the pressure from the MonP lane, so install MonP first on a fresh IOC.
  - **EStn needs `calc/estation_pvs.local.json`**: copy `calc/estation_pvs.template.json`. Fill it in from the running
    IOC (the installed `userTran9` input links, read with `caget`) or from the user.
  - EStn's TetrAMM links go in last, and `--remove` returns its four slots to their free defaults.
- **After any install:** `python -I -X utf8 op/tests/check_dashboard.py --live`, which only reads. It must report every
  expected `.CLC*` string equal to `docs/dashboard_model.json`, so the IOC runs what the dashboard describes.
- More checks: `calc/HANDOFF.md`, "Verify / reinstall" (including `calc/soak_check.py`, live against the full physics).
  Freeing a slot by hand is under "To free the slot" there.
- **Why it is built like this:**
  - The installer is the only writer, and it is guarded. A slot that belongs to another project is never overwritten.
  - `--compare` makes "is the IOC current?" a read-only question.

## 3. Change something and carry it through
One chain, in order. Skip the steps that your change doesn't touch.

| Step | Command | Why |
|---|---|---|
| 1. Change the source | a constant in `calc/*.py`, a row in `fluxor/parameters.toml`, a fact's source | each number has one home (CHAMBER_FACTS.md, PARAMETERS.md) |
| 2. Regenerate what derives from it | `fluxor/make_parameters_md.py` (registry rows); `calc/quality_slots.py`, `calc/estation_lane.py`, `calc/monp_transform.py` self-tests | generated files never drift from their source |
| 3. Check the register | `analysis/check_chamber_facts.py` → PASS; update the CHAMBER_FACTS row (old value kept as "was …") and grep the docs for its ID | no stale copy of a number |
| 4. Export the dashboard model | `tools/export_dashboard_model.py` → `docs/dashboard_model.json` | the dashboard's tables and its live check read it |
| 5. Regenerate the dashboard | `op/tools/gen_dashboard.py op/bob/flux_dashboard.bob`, then `op/tests/check_dashboard.py --static` | the `.bob` is never edited by hand |
| 6. Test | `python -I -X utf8 -m unittest discover -s tests -t .` | includes `tests/test_dashboard.py`, which fails on a stale screen |
| 7. Docs and log | the OPERATOR.md and HANDOFF.md the change affects, in the same commit; a PROGRESS.md entry; a PLAN.md plan-changes row if the user approved a change of method | CLAUDE.md: a change isn't done until its docs are |
| 8. Commit | explicit paths, never `git add -A` | other sessions share this checkout |
| 9. Publish | §4, with the user's go | the site repository takes what it needs from GitHub |
| 10. Vendor into the site repository | §5 | the host's screens come from there |
| 11. Ship to the host | the user's step | |
| 12. Reinstall the lane, if its expressions changed | §2, with the user's OK, then `check_dashboard.py --live` | a lane changes only by an install |

A change that leaves the slot expressions unchanged (for example a new budget term that doesn't move the rounded bound
factors) stops at step 10. Compare the generated expressions before and after to know which case you're in. The
2026-11-17 energy-readback term is an example (calc/HANDOFF.md, dated decisions).

## 4. Publish to GitHub
The public repository gets **one squashed commit per publish**, on top of the previous one. It never gets this
checkout's history.

**Why:**
- Some early commits contain an account name, so the history can't be published as it is.
- Building the commit from the tree (`git commit-tree`) lets a gate check exactly what goes out.
- Nothing local is rewritten, so other sessions aren't disturbed.

The procedure is the publishing skill's (outside this repository; see README, "Kept out"):
1. `git fetch origin`, and check that `origin/main` is still the last published commit.
2. Build the tree from HEAD with a temporary index. PROGRESS.md gets one substitution: a cron line that names the
   service account's home and a site address. The local file stays as it is, because PROGRESS.md is append-only.
3. `git commit-tree <tree> -p origin/main` with a message and the attribution line.
4. **Gate, in the same script, before the push:**
   - the name scan exits 0. It reads every file of the tree, and unpacks zip members (docx/xlsx), PDF streams and PNG
     text chunks;
   - no site address or home path is in the tree;
   - the tree differs from HEAD only in PROGRESS.md.
5. `git push origin <commit>:refs/heads/main`. **Never** run `git branch -f main origin/main` here: local main has
   unrelated history and would lose it.
6. Check on GitHub (`gh api repos/Dave-J-W/xray_fluxor/commits`), and fetch any changed binary to scan it again.

**Before committing a document** (docx, xlsx, PDF): clear its author and "last modified by" metadata. In docx these
are `docProps/core.xml` creator and lastModifiedBy. **Why:** on 2026-11-17 a docx carried the user's name in its
metadata into three public commits. A raw-byte scan can't see inside the zip, and a name list can't catch a name it
doesn't list (a third person's name in `creator`). The history was replaced twice by a force-push (PROGRESS.md,
2026-11-17).

**If something private was published:** fix it locally, then rebuild the public history without it. That is a
force-push, so it needs the user's explicit go. Tell the user what remains:
- GitHub serves old commits by SHA for a while;
- the push shows in the activity feed;
- GitHub Support can purge cached views.

## 5. Refresh the dashboard in the site repository (15IDC HA)
From a clone of the public repository (§1), not from this working checkout:
```bash
python3 ioc/utilioc/tools/vendor_dashboard.py <clone> ioc/utilioc/screens
```
```bash
python3 ioc/utilioc/tools/vendor_dashboard.py <clone> ioc/utilioc/screens --check
```
- It copies `op/bob/flux_dashboard.bob` byte for byte from the clone's last commit of that file, and writes
  `flux_dashboard.SOURCES.txt` (commit and sha256). `--check` says whether the copy is current.
- Commit that in the site repository. Shipping to the host is the user's step.
- **Why a clone of the public repository:** the SOURCES file then names a commit that anyone can fetch. This checkout's
  local commit IDs never appear on GitHub.
- **Why the committed blob (`git show`), not the working file:** a Windows checkout has CRLF line endings, and the copy
  must be the same bytes on every system.

## 6. Recovery
| Problem | Do |
|---|---|
| The checkout is lost | §1. The clone has every file but not the local history: that exists only on this PC (open item below) |
| A lane is wrong or missing on the IOC (for example after a utilioc reinstall without its autosave) | `install_lane.py --compare` (§2), then reinstall with the user's OK; then `check_dashboard.py --live` |
| The live pressure stopped updating (status bit 4) | `calc/PRESSURE.md`, "When things go wrong": the cron line, schedule and manual override |
| The dashboard on the host is older than the lanes | §5, then ship (the user) |
| The dashboard's live check fails | its message names the slot, field and term. Either the IOC needs a reinstall (§2), or the export or screen is stale (§3, steps 4–6) |
| Something private was published | §4, last paragraph |

## Open items
- **This checkout's history is on one PC only.** The public repository holds squashed snapshots, not the history, and
  there is no private remote. A private backup remote is the user's call.
- The E-station lane's source PV names are not published (by design). A new installer takes them from the running IOC
  or from the user.
- MonC's chamber is detached (CHAMBER_FACTS F7.2). Its lane runs, but it isn't a beam measurement.
