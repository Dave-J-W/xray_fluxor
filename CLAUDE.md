# CLAUDE.md: working rules for agents in this repository

<!--
Portable template, taken from the cmc-services repo (2026-11-12). Copy it to the new repo's root
as CLAUDE.md and fill in the section "This project" (marked FILL IN). The rest is general
and works unchanged. Delete this comment once it's filled in.
-->

## Roles
Work here is split between two agents, usually in separate sessions:
- **Implementer:** does the work in the plan, keeps the progress log, and asks for an audit at each gate.
- **Auditor:** checks the work against the plan, its gates and the scope guard, and records verdicts.
  The auditor **does not implement**. It reads, runs read-only checks, and writes findings. It edits
  project files only when the user directly tells it to (and then says so in the commit message).

If the user hasn't said which role you have, ask. If you are the only agent, you're the implementer,
and the self-checks below still apply.

The **user** decides. Only the user changes the plan, accepts a risk, or approves a deviation.
Agents bring the options and record the decision with its date and the user's words.

## The plan, gates and scope
- The plan (`PLAN.md`) is approved before work starts. Steps go in order. A step is done only when its
  **gate** is met **with evidence**: a command with its trimmed output, a file path, or a commit.
  "It works" is not evidence.
- The **scope guard** lists what counts as drift. Anything outside the plan: stop and ask first.
  Don't do it and explain afterwards. Gold-plating (features, tooling or PVs nobody asked for) is
  drift too.
- **Plan changes table:** every change the user approves is a row with the date, the change and
  who approved it (quote the user). Never edit an old row; add a new one that supersedes it.
- Audit verdicts are **PASS**, **PASS WITH NOTES**, **FAIL** (step reopened) or **DRIFT** (out of
  scope or a rule broken).

## Findings
Each finding gets:
- an ID (letter for the review round, then a number: A1, R3, H5);
- a one-line defect;
- a concrete failure scenario (inputs or state, then the wrong result);
- a severity;
- a **closing check**: the command or observation that proves it's fixed.

A finding is closed only when someone ran the closing check and logged the result, not when a
fix was committed. Accepted risks are closed with a plan-change row, not by deleting the finding.

## Progress log (implementer)
`PROGRESS.md` is **append only**: never rewrite or "fix" a past entry, even when wording rules change
later. Add one entry per work session, committed with the work:
```
## <date> — Step <n>: <title>
Status: in progress | ready for audit | blocked
Done:      - <change> (commit <sha> / file <path>)
Evidence:  - `<command>` → <key output, trimmed>
Deviations from the plan: <none | what, why, user approval yes/no>
Open questions / blockers:
Next:
```

## Documentation
- Each subproject has two documents:
  - `OPERATOR.md` for the people who use it: what it does, how to use it, what each alarm or
    error means and what to do. No internals.
  - `HANDOFF.md` for the next maintainer: design, rules, file map, install/upgrade/recover steps,
    pinned versions, dated decisions, known traps, open items.
- **A change isn't done until the OPERATOR.md and HANDOFF.md it affects are updated in the same commit.**
- `README.md` indexes the subprojects. `RUNBOOK.md` covers install from bare metal, migration and recovery.
- Define a term once and use it consistently. When a name changes, change it everywhere except
  the append-only log, and note the old name in the glossary.

## Privacy and secrets
- No host names, IP addresses, account names, e-mail addresses or secrets in tracked files. They go in
  gitignored files (`site.env`, `secrets.env`), with committed `*.template` versions. Planning and
  audit files that name real hosts stay local (gitignored).
- Never print a secret to the transcript. Line-based masking misses multi-line values (YAML lists,
  PEM blocks), so don't dump whole config files that contain keys.
- Before the first push to any remote that is or may become public, scan the **history**, not just
  HEAD. If old commits hold names, IPs or large blobs, push a squashed history instead.

## Live systems
- Read-only by default. Restarts, writes to devices or control variables, service changes and anything
  that moves hardware need the user's OK for that action. One approval doesn't cover the next.
- Where the permission system stops an action that drives hardware, give the user the exact command
  and then verify from outside.
- Shared machines: check for running tests or experiments before doing anything heavy.
- Everything must survive a reboot or power loss without anyone logging in. A setting that exists only
  in a running process or a shell isn't done. Persistent state is restored on start, and a
  restart must never actuate anything.
- Pin versions (image digests, bounded package versions). No `latest`.

## Health check
`HEALTH_CHECK.md` is a read-only "is everything up?" checklist with pass criteria, an
expected-values table, known harmless items, and a log with one row per run.
- When to run it: after any reboot or power event, before an audit, and weekly.
- When a service, process, device or dependency is added, add it to the checklist in the same change.
- When a known item is fixed, delete it from the list.

## Working habits
- Before reviewing, read the **current** files: check modification times and `git log`/`git status`.
  Don't trust a summary or an earlier read.
- Report outcomes faithfully. A failed test is reported with its output, and a skipped step is
  named as skipped.
- Commit only when asked, on a branch if the default branch is protected. Never skip hooks.

## This project (FILL IN)
- Purpose, in one or two sentences: absolute and relative x-ray incident flux normalization 
- Plan file and gate/audit file (local or tracked): `PLAN.md` (tracked), `PROGRESS.md` (tracked, append only)
- Subprojects (each with OPERATOR.md + HANDOFF.md):
- Never touch (systems, hosts, PV prefixes, data): Ask for now
- Hardware-actuating commands that always need the user: changing SR570 gain and offset 
- Terms / glossary:
- Relevant skills:
