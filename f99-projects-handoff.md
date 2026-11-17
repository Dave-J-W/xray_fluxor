# Working on the current production host from another repo

For an agent (or person) on a project that lives in **its own repo** but needs things from the
current production host, "f99" in older text: reading and changing PVs, configuring utilioc's
calculators, running its own scripts, or adding a small soft IOC of its own. Written for the
physics-calculation project, kept general for any project of that scope.

**Where the concrete values are.** This file is committed, so it names no addresses or accounts.
It uses these placeholders; the real values are in `F99_ACCESS.md` (gitignored, same folder as the
repo root) which the user hands you with this file.

| Placeholder | Meaning |
|---|---|
| `$HOST` | the current production host (RHEL 9, 20 CPUs, 62 GB) |
| `$SVC` | the service account: runs every IOC, owns the repo checkout, no sudo |
| `$OPS` | the operator account: key login, passwordless sudo, for root-only steps |
| `$BCAST` | the subnet's broadcast address, the Channel Access search address |
| `$EB` | EPICS base tools, `~$SVC/epics/base-7.0.8.1/bin/linux-x86_64` (caget, caput, camonitor, cainfo, pvget, pvput) |

Companion documents (all in the cmc-services repo): [utilioc OPERATOR](../ioc/utilioc/OPERATOR.md)
(the calculators), [host HANDOFF](../host/HANDOFF.md) (accounts, boot, decisions),
[RUNBOOK](../RUNBOOK.md), [process placement](process-placement.md), [screens README](../screens/README.md)
(adding an IOC to the root screen), [HEALTH_CHECK](../HEALTH_CHECK.md).

## 0. The short version

1. **f99 is the current production host.** Nothing mission-critical runs on it until February 2027
   (user, 2026-11-12), so a short outage costs little, but treat everything on it as production:
   settings are kept across restarts and the beamline will rely on them.
2. **Reading is free; writing needs the right to write that PV** (section 2). When in doubt, read,
   and ask the user before the write.
3. **Use the broadcast address for Channel Access.** Several IOCs share the host, and a CA search
   sent to the host's own address reaches only one of them.
4. **Only your own prefix, plus the utilioc slots the user has given you.** Never write `15IDC:zb:`
   (real power switches), `15IDC:uepsilon:` (a running experiment), or anything on the beamline's
   other hosts.
5. **Other sessions share the host.** Before anything heavy, read the event log and look for running
   tests (section 8). A latency test may be running; it is easily spoiled.
6. **Everything an operator can set is autosaved, and a restart resumes operation.** So a value you
   write stays until someone changes it. Put things back, or say what you left.
7. **Never print or copy secrets.** Zigbee2MQTT's `configuration.yaml` holds the network key; the
   MQTT and Home Assistant passwords are in files you do not need.
8. **If a tool is denied by your permission mode, do not work around it.** Give the user the exact
   command and verify the result from outside.

## 1. What is on the host

| IOC | Prefix | procServ port | Owner | What it is |
|---|---|---|---|---|
| zbplugs | `15IDC:zb:` | 20125 | this repo | Zigbee smart plugs (real power switches) |
| utilioc | `15IDC:util:` | 20126 | this repo | synApps utility IOC: 3 each of EPID, userCalc, userTran, userCalcOut, userStringCalc, userArrayCalc, userStringSeq, userAve, plus iocStats |
| confocalDT | `15IDC:uepsilon:` | 20127 | its own session and repo | a distance sensor IOC recording an experiment |

Also running: Mosquitto, Zigbee2MQTT and Home Assistant (rootless containers). All IOCs run as `$SVC`
under procServ, started at boot by `start_ioc -b` from the service account's `@reboot` cron line,
reachable on Channel Access (5064/5065) and PV Access (5075/5076). **There is no firewall** on this
host or on the central host (user decision, 2026-11-04), and **none of the IOCs has access security**:
any client that can reach them can write any writable PV. The only guard is what you agree to do.

**Hosts, by name.** "Current production host" = this one. "Central host" = the beamline's central
EPICS server, a possible later home for these IOCs (RUNBOOK section 2). Never use "the production
host" alone: it is ambiguous. Never write to the central host from a project like yours.

## 2. What you may do, must ask, must never do

| | Examples |
|---|---|
| **Do freely** | Read any PV served by this host (`caget`, `camonitor`, `pvget`). Read logs and the files in this repo's deployed checkout. Run `scripts/util-links.sh`, `scripts/check-host.sh` (needs `$OPS`), `screens/check_screens.py`. Work in your own directory under `~$SVC`. Ship your own code to your own folder. |
| **Ask the user first** (every time, unless "Grants" at the end records a standing permission) | Write any utilioc slot PV (including `DESC`, links, expression, Enable). Restart any deployed IOC. Point any output outside your own prefix. Register a new IOC, prefix or port. Anything needing `sudo`. Install system packages. Run builds or other heavy work while a test is running. Reboot. Change anything under `host/`, the tuned profile, `site.env`. |
| **Never** | Write to the central host. Write `15IDC:zb:` PVs or publish to the MQTT broker (real plugs switch real loads). Write `15IDC:uepsilon:` PVs. Change the firewall, sshd, sudoers, accounts. Dump `configuration.yaml` of Zigbee2MQTT or print any secrets file. Edit the deployed checkout in place (ship from a commit). Run two copies of an IOC that serves the same prefix on the subnet. Put an SDIS/interlock you rely on for safety on an EPID blocking PV (it is not fail-safe). |

Why "ask" for slots: utilioc's links and outputs run on their own after you leave and after every
restart. A slot pointed at a beamline PV writes there repeatedly. The user decides, per slot, which
outputs are acceptable.

## 3. Reaching the host

Access is by SSH, key only, from the user's Windows PC (the key is restricted to that PC). Concrete
commands are in `F99_ACCESS.md`. In outline:

- As `$SVC`: `ssh -o BatchMode=yes -i <key> $SVC@$HOST '<command>'`. Everything IOC-related runs here.
- As `$OPS`, only when root is needed: `ssh ... $OPS@$HOST "sudo bash -c 'cd ~$SVC/cmc-services && <command>'"`.
  The service account's home is mode 700, so `$OPS` cannot read it without sudo.
- The SSH banner prints a post-quantum warning on every connection; filter it with
  `2>&1 | grep -v -i "post-quantum\|store now\|openssh.com"`.
- If SSH is refused, stop and tell the user. Access is the user's to grant; do not look for another way in.
- A long SSH pipeline can hang: run long jobs in the background on the host (`nohup`, `systemd-run --user`)
  and poll a log, rather than holding the session open.

From the PC you can also read and write PVs directly with pyepics or caproto, with the broadcast
address in section 5. The PC is on the same subnet.

## 4. Layout on the host (under `~$SVC`)

| Path | What |
|---|---|
| `cmc-services/` | this repo, shipped from a commit by `scripts/ship-to-host.sh`; `.deployed-commit` says which. Do not edit in place. |
| `confocalDT/`, `confocalDT_data/`, `confocalDT_tools/`, `replay/` | the confocalDT session's work: not yours |
| `epics/base-7.0.8.1/`, `epics/support/` | EPICS base 7.0.8.1 and synApps modules (asyn, autosave, busy, calc R3-7-5, iocStats, sequencer, sscan, std R3-6-4), built by `host/build-epics.sh` and pinned by commit. Do not rebuild. |
| `venvs/utility/` | Python 3.11 with numpy, scipy, pyepics, caproto, PyYAML. Free to use for analysis, no root needed. |
| `cmc-services/ioc/zbplugs/.venv` | Python 3.11 with pythonSoftIOC (`softioc` 4.7.2) and caproto: owned by zbplugs, do not modify it; make your own venv (`python3.11 -m venv`, pip reaches PyPI) for a soft IOC of yours |
| `ioclist.conf` | the IOC table: `NAME PORT ONBOOT COMMAND`, one line per IOC |
| `bin/start_ioc` | starts IOCs under procServ (`-l` lists, `-b` boot set, `-s` silent) |
| `ioc_logs/<name>.log` | each IOC's procServ console log (start_ioc deletes it at every start; each IOC copies it to its own `logs/console.log`) |
| `backups/` | daily backup archives (see section 8) |
| `cmc-data/` | Mosquitto, Zigbee2MQTT, Home Assistant data: not yours |

Python: the system `python3` is old (3.9). Use `python3.11` or a venv built from it.

Hardware: 20 logical CPUs. CPUs 10, 11, 22, 23 are reserved for future real-time IOCs: ordinary
processes, interrupts and kernel work are kept off them (the service account's processes run on 0-9
and 12-21). Do not pin anything to the reserved CPUs. Normal IOCs run at default priority
(`docs/process-placement.md`).

## 5. Seeing and changing PVs

### The environment
Channel Access finds IOCs by UDP broadcast. Set, in the shell or the script, before any client runs:

```bash
export EPICS_CA_ADDR_LIST=$BCAST        # the subnet's broadcast address
export EPICS_CA_AUTO_ADDR_LIST=NO
EB=~$SVC/epics/base-7.0.8.1/bin/linux-x86_64     # on the host (not on the PATH)
```

- **Do not** use the host's own IP, `127.0.0.1` or `localhost` in a CA address list: a unicast
  search reaches only one IOC on a host that runs several, and which one is not fixed.
- PV Access (`pvget`) works with the host's IP or the broadcast address, not with `127.0.0.1`.
- On the PC, set the same two variables before `import epics` (pyepics), and `PYTHONIOENCODING=utf-8`.

### Reading
```bash
$EB/caget -t 15IDC:util:HEARTBEAT                 # -t: terse, value only
$EB/caget 15IDC:util:userCalc1.CALC 15IDC:util:userCalc1.VAL
$EB/camonitor 15IDC:util:userCalc1.VAL            # Ctrl-C to stop
$EB/cainfo 15IDC:util:userCalc1.VAL               # host, access rights, type
```
A PV that does not answer within a second or two is not running, or your address list is wrong. If
`HEARTBEAT` counts, the IOC is up.

### Writing (after section 2 says you may)
```bash
$EB/caput 15IDC:util:userCalc1.DESC "my calc"
$EB/caput 15IDC:util:userCalcOut2.CALC "A*2"
$EB/caput 15IDC:util:userCalcOut2.INPA "15IDC:util:userTran1.A CP NMS"   # link text: quote it
$EB/caput 15IDC:util:userCalc1Enable 1            # enum PVs take 0/1 or the state name
$EB/caput -S 15IDC:util:userStringCalc1.CALC "A+B"                       # -S: write a long string into a char array
```
Then **always read back** (`caget`) and compare. `caput` says "Old/New" with the value it
accepted; a field can silently clamp or reject (a link that is too long, a limit).

### Rules that bite
- **Links are cut at 39 characters, including the modifiers** (` CP NMS`, ` PP NMS`). Autosave stores
  link text in 40 bytes: a longer link works until the next restart, then comes back truncated and can
  point at a different PV. `bash ~$SVC/cmc-services/scripts/util-links.sh` flags long ones. Use shorter
  intermediate PV names (a helper slot's `.VAL`) instead of long beamline PV names.
- Everything is autosaved every 30 s and restored at start. A change in the last 30 s before a crash can
  be lost; a change you forget stays.
- A slot runs only while its own Enable, its family's Enable and `userCalcGlobalEnable` are all 1.
  Writing to a `Disable...` record **enables** the family: write the `...Enable` record.
- `epidNStop`: write 0 (turn off). Writing 1 turns feedback ON.
- An EPID start is smooth only with `KI` not 0, `VAL` close to `CVAL`, and the present actuator value
  inside the drive limits (`epidN_limits.A` and `.B`, not `DRVL`/`DRVH`). Details: utilioc OPERATOR.
- Output links outside `15IDC:util:` make the slot write there every time its condition holds, and after
  every restart. Agree each with the user (and the PV's owner) before setting it.
- Stopping a slot or loop is done with its Enable or its blocking PV, never by restarting the IOC.

## 6. Designing a calculation for utilioc

There are **3 slots of each family**, and they are shared with everyone. A different count is a change to
utilioc itself (`ioc/utilioc/utilApp/Db`, the substitutions file, tests and an audit in this repo): ask
the user, do not edit it from your repo.

Suggested flow for a physics design project:

1. **Design and test offline** in your repo (numpy against recorded or synthetic data), and restate the
   result in the calc expression language (`ioc/utilioc/OPERATOR.md`, "What each family does"; the
   language is calc R3-7-5's: A-L inputs, `CALC` expression, 39-character link limit). An offline
   reference implementation of each expression is what proves the slot later.
2. **Choose the family.** `userCalc`/`userCalcOut` for a scalar from up to 12 inputs; `userTran` for
   16 related values; `userStringCalc`/`userArrayCalc` for strings and arrays (up to 2000 points);
   `userStringSeq` for ordered writes; `userAve` for averaging; EPID for feedback.
3. **Ask for slots.** Name the slots you want and every output PV you will point at. Check what is free:
   `bash ~$SVC/cmc-services/scripts/util-links.sh --all` (a slot with no links is unused).
4. **Install from a script in your repo**, not by hand: a list of `caput` lines (or a small Python
   with pyepics) that disables the slot, writes every field, reads each back and compares, then
   enables it. Keep the script in your repo and record in it which slot is used for what. A re-run must
   be safe.
5. **Soak with outputs pointed at utilioc's own PVs first** (`15IDC:util:...`), compare against the
   offline reference, and only then point the output outside, with the user's agreement.
6. **Record the result:** slot assignments, links, and the commit of your repo that installed them. Tell the
   user, so the utilioc OPERATOR or HANDOFF can list it.
7. **Leave nothing half-done:** unused slots cleared (`caput <slot>.OUT ""` and so on, `DESC` back to
   empty), Enables as they were.

A scratch copy of utilioc on loopback for testing before touching the deployed one has **not** been set
up or verified (open items); the repo's own tests (`static_check.sh`, `autosave_roundtrip.py`) need the
deployed IOC stopped first and need the user's OK.

## 7. When a small soft IOC is warranted, and how to add one

Use utilioc's calculators when the calculation is an expression of PVs. Write a soft IOC when it needs
state, loops, files, hardware or libraries (numpy, scipy, a device protocol), or when it must serve PVs
that did not exist. The existing ones are the patterns: **zbplugs** (pythonSoftIOC, code in this repo),
**confocalDT** (a compiled IOC in its own repo and folder), **utilioc** (a synApps-built IOC).

Checklist, all of it before the IOC is called done:

1. **Prefix.** The user approves it (new PVs need an approved prefix), format `15IDC:<name>:`. Check it
   is unused: no answer from `caget` on the subnet, and nothing in the central host's configs (the user
   or the maintainer does that read-only).
2. **Port.** A procServ console port, next free is **20128** (20125-20127 are taken here; the central
   host's table uses 20001-20124, 20050-20095 and a few others, so keep above 20127 and confirm with the
   user). Bound to 127.0.0.1 by `start_ioc`.
3. **Code location.** Either a folder in the cmc-services repo (`ioc/<name>/`) or your own repo checked
   out under `~$SVC/<name>`, shipped from a commit with the commit written to `.deployed-commit` (copy
   `scripts/ship-to-host.sh`'s idea: `git archive HEAD`, never rsync a dirty tree).
4. **Start script**, modelled on `ioc/utilioc/iocBoot/iocutil/start_utilioc`: it must
   (a) `cd` to its own folder (start_ioc does not), (b) set `PATH` (cron's is minimal and `ip` is in
   `/usr/sbin`), (c) wait, bounded (120 s), for a global IPv4 address before the IOC starts (CA and PVA work
   out beacon addresses from the interfaces at startup), (d) set `EPICS_CA_AUTO_ADDR_LIST=YES`,
   (e) keep its own `logs/console.log` (start_ioc deletes the procServ log at every start: follow it
   with `tail -F --pid=$$`), (f) create an `autosave/` directory, (g) `exec` the IOC so procServ owns it.
5. **Autosave everything an operator can set**, including enables and on/off, so a restart or a power cut
   resumes operation (user's standing rule). Write the request file or `autosave` module setup, and test
   a save, a stop and a restore.
6. **A heartbeat PV** that counts (one per second is fine) and an alarm when the IOC cannot do its job.
   `start_ioc` runs procServ with `--noautorestart`: after a crash nobody restarts the IOC, so the
   heartbeat stopping is how people know. The root screen and the health check rely on it.
7. **One writer per output.** Route every hardware or outside write through one gated function; no
   database link points at hardware; refuse writes at start-up and while disabled. (cmc-epics-ioc
   principles.) A "can't act" state must alarm, not just show text.
8. **Confine tests.** A test server started from a plain shell broadcasts to the whole subnet. Test on
   loopback with the CA server and beacon variables set (`EPICS_CAS_INTF_ADDR_LIST=127.0.0.1`,
   `EPICS_CAS_BEACON_ADDR_LIST=127.0.0.1`, and a non-default `EPICS_CA_SERVER_PORT`), or on your own
   machine, never with a prefix that is already served.
9. **Register it** (needs the user's OK): append one line to `~$SVC/ioclist.conf`, in the form
   `NAME PORT 1 /absolute/path/to/start_script`, without touching the other lines (`start_ioc -l` shows
   the table). ONBOOT 1 makes the `@reboot` cron line start it. Start it with `start_ioc -s NAME`.
10. **Make the host know about it**, in the same change (the verify script, section 10, fails when one
    is missing):
    - `docs/process-placement.md`: a row with `match` text that finds the process, its tier, nice and cpuset;
      `scripts/latency-snapshot.sh` then reports drift.
    - `scripts/backup.sh`: its autosave folder, in the list near the top.
    - `screens/iocs.yaml` and the root screen: see `screens/README.md`, "Adding your IOC".
    - `HEALTH_CHECK.md`: the process (row 5), network dependencies (row 8), ports (row 9), health PVs.
    - your IOC's own `OPERATOR.md` and `HANDOFF.md`, in your repo or in this one.
11. **Two IOCs must never serve the same prefix.** `check-host.sh` fails when it sees a second server for
    `15IDC:util:` or `15IDC:zb:`; give yours the same check.

## 8. Operations on the host

### Which account does what
`$SVC` runs and owns the IOCs, builds into its own home and has no sudo. `$OPS` is for what needs root:
`check-host.sh`, the event log script, anything touching `/etc`. Do not hand `$SVC` sudo or put it in `wheel`.

### Looking at things (read-only)
```bash
~$SVC/bin/start_ioc -l                              # the IOC table
ps -eo pid,user,ni,args | grep [p]rocServ           # who is running, and under which port
tail -n 50 ~$SVC/ioc_logs/utilioc.log               # procServ console log of an IOC
sudo -n bash ~$SVC/cmc-services/scripts/check-host.sh   # as $OPS: 0 failures expected
column -t -s $'\t' /var/tmp/host-test-events.tsv | tail     # the shared event log
```
The IOC's own console: `telnet 127.0.0.1 <port>` as `$SVC` shows the IOC shell. Prefer logs: the console
accepts keys that stop the IOC (procServ's default kill key is Ctrl-X). Leave with Ctrl-] then `quit`.

### Restarting an IOC (ask first)
`start_ioc` has no stop option, and procServ runs with `--noautorestart`:
- zbplugs and utilioc: `kill <procServ pid>` (the one with the IOC's `-n <name>_IOC`), then
  `~$SVC/bin/start_ioc -s <name>`. For utilioc, `bash ioc/utilioc/deploy_utilioc.sh --restart` is the
  supported way (it also handles a crash).
- After a restart, settings come back from autosave. Check `HEARTBEAT` counts and the slots you care about.
- A reboot restarts every IOC by itself with nobody logged in. It is the user's decision.

### Shipping code to the host
Commit first, then `git archive HEAD | ssh $SVC@$HOST "tar x -C <your folder>"`, then write the commit hash to
`<your folder>/.deployed-commit`. This repo's `scripts/ship-to-host.sh` does this for cmc-services and refuses
uncommitted tracked changes. `tar` never deletes: a file you remove in the repo stays on the host until you
remove it. Gitignored files on the host (virtualenvs, autosave, logs, site settings) are untouched.

### Sharing the host
Other sessions use f99: a latency tuning session runs hour-long tests with `stress-ng` that are spoiled by
extra load, and the confocalDT session records an experiment. Before any build, `make -j`, bootstrap, large
job, restart or reboot:
```bash
pgrep -af "latency-|timerlat|cyclictest|stress-ng"       # anything running means stop and ask
tail -n 5 /var/tmp/host-test-events.tsv                  # what the test sessions did last
```
If a test is running, light reads are fine; heavy work waits. To note a manual action there, as `$OPS`:
`sudo bash ~$SVC/cmc-services/scripts/f99-event.sh <your-name> "<what you did>"`. Never run
`systemd-run -p StandardInput=tty-force -p TTYPath=/dev/null` (it once left `/dev/null` unwritable for
26 s); keep a soft IOC's stdin open with `bash -c "sleep infinity | softIoc ..."`.

### Backups and the health check
`scripts/backup.sh` runs daily at 04:30 as `$SVC` (cron) and archives Zigbee2MQTT, Home Assistant, every
IOC's autosave folder and `site.env`; the maintainer's PC pulls the archives daily. It stops Zigbee2MQTT for
a few seconds at 04:30, so plug PVs go INVALID briefly: not a fault. Your IOC's autosave folder is only in
the backup if you added it (section 7, step 10). `HEALTH_CHECK.md` is the read-only "everything up?"
procedure: run it after any reboot, before audits and weekly, and extend it when you add an IOC.

## 9. Traps (each found the hard way)

- CA unicast to the host reaches one IOC only. Use the broadcast address.
- Link text over 39 characters comes back truncated after a restart.
- `Disable...` records pass on what is written: writing 1 enables.
- SDIS is not fail-safe, and clearing it while the loop is blocked leaves it blocked (`caput <epid>.DISA 0`).
- `start_ioc` deletes the procServ log on every start; the IOC must keep its own.
- `@reboot` cron has a minimal `PATH`; the IOC can start before the network is up.
- A crashed IOC stays down (`--noautorestart`): watch the heartbeat.
- Two copies of an IOC on one subnet serve every PV twice.
- A test server that is not confined broadcasts to the subnet.
- Heredocs corrupt Python (a backslash-n arrives as a real newline): write files with a file tool, copy
  them over, and re-run the tests after a scripted edit.
- Background tasks stopped on the Windows PC (`TaskStop`) can leave their shell loop running and act on
  the host hours later: check for leftovers by process list.
- The service account's checkout is a deployed copy. Edit in your repo and ship; an in-place edit is lost
  or overwritten by the next ship.

## 10. Keeping this document true

This is a permanent document. **It is changed in the same commit as whatever changes the fact it states.**

| When this changes | Update |
|---|---|
| An IOC is added, moved or retired; a port or prefix; `ioclist.conf` | sections 1, 4 and 7 (the port: "next free"); the verify script runs the cross-checks |
| Accounts, SSH access, who may use the key, sudo | sections 2 and 3, and `F99_ACCESS.md` |
| Tools or paths: EPICS base version, venvs, `start_ioc`, Python | sections 4, 5 and 8 |
| A rule from the user (permission, "ask first", a new prohibition) | section 2, and the Grants table below |
| Firewall, access security, network address of the host | sections 1 and 5, and `F99_ACCESS.md` |
| A trap is found | section 9 |
| The host role changes (centralization, February 2027) | the opening and sections 1 and 2 |

**Verify it:** `bash scripts/verify-f99-handoff.sh` as `$SVC` on the host (read-only, a few seconds). It
checks the facts this document states against the host (tools, paths, packages, table, ports, a live read
of both repo IOCs through the broadcast address) and that every IOC in `ioclist.conf` appears in
`backup.sh`, `process-placement.md` and `screens/iocs.yaml`. Run it after any change in this table and at
every health check; add a row to the log.

| Date | Verified by | Result | Notes |
|---|---|---|---|
| 2026-11-12 | implementer session, on the host (commit b8f2001) | 0 failures (36 checks); shown to fail on a doctored copy (3 failures) | written from the live host (ioclist, tools, venvs) and the repo docs; the write recipes in section 5 are the ones in utilioc OPERATOR and were not re-run against live PVs (read-only session while a latency test ran) |

## 11. Grants and open items

**Grants** (standing permissions the user has given; each states what, to whom, and until when). Nothing
here means "ask first" is waived beyond exactly what is written.

| Date | Granted by | To | What |
|---|---|---|---|
| 2026-11-12 | user | the agent of the physics-calculation project (and later projects of the same scope, until the user says otherwise) | "for now it can write to any slot it wants, these are the first slots to be used": it may write any utilioc slot PV (fields, links, expression, Enables) on `15IDC:util:` without asking each time. **Not covered, still ask:** an output or link pointing outside `15IDC:util:`, restarting an IOC, changing the number of slots, any EPID turned on against a real actuator, everything in the "Never" row. Slots are free, so the slot inventory is the only record: keep your install script and tell the user what you left. "For now" means the user may withdraw this; ask if unsure. |

**Open items**
1. A loopback scratch copy of utilioc, to test slots before touching the deployed IOC. Write the verified
   recipe here once it exists (the CA and PVA variables that keep it off the subnet, a scratch autosave
   directory, a different CA server port).
2. CA access security: none of the IOCs restricts writes (utilioc HANDOFF open item 1).
3. Port 20128 as the next free: not yet confirmed against the central host's `start_ioc` table.
4. If the IOCs are centralized, the central host replaces `$HOST` throughout: stop and unregister here first
   (RUNBOOK section 2).
