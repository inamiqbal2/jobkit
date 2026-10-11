# CHARTER: DATA & STATE

## Single source of truth: `My Job Search/tracking/state.db` (SQLite). Both csv files are GENERATED VIEWS.
`My Job Search/tracker.csv` is what the person reads (plain columns: employer, role, status, outcome, link, folder);
`tracking/jobs.csv` is the full analysis view. NEVER hand-edit either - `<jobkit python> system/engine/tools/state.py
set|add|applied|outcome ...` changes the db and rewrites both. `Application ID` is filled by the person only. The agent fills
`Rejection/Interview` in a fixed format: `Rejected <date> (form email)` /
`INTERVIEW <date> - <detail> (<who, TITLE - screen type>)`.
Analysis columns MANDATORY at insert: Tier · Lane · Sector · Fit · Cov% · Yrs Bar · Custom Ans ·
Salary Range · Status · Channel (+ Outreach if that module is on).
`Lane` = function (one of `settings.yaml lanes[].name`; the CLI warns otherwise); `Sector` = industry.
Keep both: a rule that keys on lane alone hides sector effects.
**Salary Range - two-pass.** Format `L:$X-$Y` (listed in the JD) `|G:<finding>` (market corroboration).
Pass 1 automatic at insert; pass 2 by the agent at build/apply or when comp comes up. `n/d` = employer
discloses nothing; still do pass 2 for active roles.
**Reject Type**: TIMING / MERIT / UNKNOWN (default) / POST-HM. Never pool them (learning.md).
Folders are protected by APPLIED STATUS in the db, never by link presence: a folder with a built resume is
never overwritten; back it up first if a rebuild is truly required.

## Where things live
```
My Job Search/            (= the workspace; $JOBKIT_WORKSPACE overrides)
  settings.yaml · keys.json · my-rules.md · tracker.csv (the person's generated view) · intake/ (the person's documents, read-only)
  profile/      evidence/ · skills-inventory.md · publications.md · approved_claims.yaml · profile_blind.md
  tracking/     state.db · jobs.csv (full generated view) · dispositions.jsonl · registries/ · jds/ · rubric/ · run_summary.json · caches · queues · logs
  applications/ <Company>_<Role>/ (JobDescription.txt, build.py, the .docx files, AUDIT_PASS.json once the audit passed)
system/engine/         tools/ · charters/ · registries/packs/ · skills/ · CONSTITUTION.md
```
Python env: `system/.venv` INSIDE the jobkit folder (never a temp/scratch venv - those evaporate between
sessions). Run tools with the jobkit python (`system/.venv/bin/python`, `system\.venv\Scripts\python.exe` on Windows)
or the launcher `system/jobkit.py` (CLAUDE.md). Workspace override: `JOBKIT_WORKSPACE`.

## Dispositions ledger (judgment memory)
`tracking/dispositions.jsonl`: EVERY decision on a specific posting - SKIP (with reason), BUILT, APPLIED,
WATCH, REOPEN - is logged via `<jobkit python> system/engine/tools/decide.py <url> <decision> "<reason>"`. URLs are
canonicalized (`urlcanon.py`) so one job has one key (job-identifying parameters such as `gh_jid` stay in the key).
BUILT is refused unless the application folder for that url carries a fresh `AUDIT_PASS.json` (CONSTITUTION I.8). `daily.py` excludes ledgered URLs, so a judged job
surfaces exactly once; the LAST decision per URL wins (REOPEN re-admits without deleting history).
If you decide anything about a posting and don't log it, the pipeline WILL show it again - logging is part
of the decision. `decide.py --list` shows recent entries.
The screen saves every fetched JD to `tracking/jds/<md5>.txt`; critic verdicts travel with queue entries.

## No deletion
Nothing in the workspace is deleted or overwritten without the user's per-item approval. Backups
(`<file>.bak-<date>`) before any in-place rewrite of a data file. Registry pruning (dead boards) is a
user-approved action, not an automatic one.

## Secrets
`My Job Search/keys.json` only; never printed, never committed (.gitignore), never copied into a report.
