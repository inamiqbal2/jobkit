---
name: jobkit-daily
description: "run my job search" - the daily ritual. Claude runs the pipeline, has two blind judges score every new posting, judges the list by the charters, builds documents for the good ones, and ends with a plain-language report in chat. Never applies, never sends. Use when the person says "run my job search", "anything new?", "check the boards", or similar.
---

# jobkit daily - the "run my job search" ritual

You run everything. The person sees one line when you start, a progress line now and then, and a plain
report at the end. Read `system/engine/CONSTITUTION.md` and `My Job Search/my-rules.md` at the start of the
session. Method references: `system/engine/charters/search.md` (judging), `system/engine/charters/build.md` (building).
`<jobkit python>` = `system/.venv/bin/python` (`system\.venv\Scripts\python.exe` on Windows); `<launcher>` =
`python3 system/jobkit.py` (`py -3 system\jobkit.py` on Windows); both run from the jobkit folder (CLAUDE.md).
Workspace = `$JOBKIT_WORKSPACE` or `My Job Search/`.

Say first: "Starting your job search. This takes 10-40 minutes; I will report when it is done."

## Step 1 - Quick check
`<launcher> setup --quick`. Fix anything `[MISSING]` yourself. If the "settings.yaml check" line names wrong values,
the problems are listed in plain words under the table (a number in quotes, a pack name that does not exist, a
relocation answer that is not yes / no / case-by-case): fix settings.yaml and run the check again; `daily.py` refuses
to start on such a file. If `ONBOARDING_STATUS.md` shows
phase 18 (calibration) not done, stop and say: "Setup is not finished (we stopped at <phase>). Say 'set me
up' and we continue from there." Nothing else runs on an unfinished setup (it would judge on placeholder
facts).

## Step 2 - The pipeline
`system/.venv/bin/python system/engine/tools/daily.py` (window from settings.yaml), output to `tracking/daily_run.log`
(the run can take long; run it in the background and read the log). It discovers, screens, dedupes
against the ledger, runs the critic, writes `tracking/queue_<today>.md` and `tracking/rubric/batch_<today>.json`
+ `prompt_<today>.txt`. Arms that lack a key print one line and are skipped (USAJobs, Adzuna); an arm that
errors degrades to zero results and never blocks the run. If daily.py exits with "I could not reach the job
boards (no internet?)" (exit code 3: the connectivity probe failed, or every board failed to answer), STOP and tell
the person exactly that in one sentence ("I could not reach the job boards - is the internet connection up? Nothing
was searched; say 'run my job search' again when it is back."). Never report "nothing new" on a run that could not
fetch. If daily.py fails some other way, read the traceback, fix the cause (a missing package, a bad regex in a
workspace YAML, a moved folder), re-run; tell the person only if it stays broken ("The search could not run today
because <one sentence>; I need <x>."). The log ends with a RUN SUMMARY block (also `tracking/run_summary.json`):
postings per arm, which arms had fetch errors, how many postings could not be read, how many go to the scorers.
Those facts open the report (step 7). If the queue is empty AND the run summary shows the boards answered: skip to
step 7 and say so plainly ("The boards answered; nothing new fits well enough today").

## Step 3 - Two blind judges
`rubric.py prep` already ran inside daily.py; read `tracking/rubric/prompt_<today>.txt`. Only the top
`run.judge_top_n` postings by match score (default 40; priority-lane postings first) are in it - the rest were
written to `tracking/deferred.jsonl` and come back next run (the run summary says about how many runs that takes); each posting is trimmed to `run.jd_text_cap_chars` (default 6000) with its
requirements block whole (`tracking/rubric/judge_plan.json` has the counts; settings.yaml documents both knobs).
Two blind scorers, the second only where it matters (2026-10-16):
1. **Scorer A** - spawn ONE subagent (Agent tool). Model: `settings.yaml run.judge_model` when set (light mode: sonnet);
   otherwise the strongest model the account offers, Fable where available, else the session's own model. Scorer B uses
   the same model. Give it the prompt file's text verbatim, nothing added, nothing reordered. It reads
   only the files the prompt names (`profile/profile_blind.md` + the JD files) and writes `tracking/rubric/run_A_<today>.json`
   (JSON only, every id, the exact schema in the prompt). With more than ~120 postings, split A into two subagents over the
   two halves of the id list (same header, each half's lines) and join their JSON into run_A yourself.
2. `system/.venv/bin/python system/engine/tools/rubric.py prep-b tracking/rubric/run_A_<today>.json` writes
   `prompt_B_<today>.txt` with only the postings A scored 30-69 (settings.yaml rubric.b_band). Below 30 A alone is a clear
   reject, 70+ a clear build; the borderline band is where a second blind reading changes decisions.
3. **Scorer B** - spawn a second, independent subagent on `prompt_B_<today>.txt`, verbatim; it writes `run_B_<today>.json`.
Never give either scorer match scores, critic lines, the queue, outcomes, or the other's output.
Then `system/.venv/bin/python system/engine/tools/rubric.py merge tracking/rubric/run_A_<today>.json tracking/rubric/run_B_<today>.json`
(use the absolute workspace paths). It averages where both scored (A-only elsewhere, tagged in the queue), auto-ledgers clear
rejects (< 40, judges agreeing, non-stub, not the priority lane, and not at or above the build line in the last 14 days)
and rewrites the queue in rubric order. If merge refuses because the id sets differ, re-run the scorer whose file is
incomplete. (Scoring all ids with both scorers still works: merge accepts a full run B.)

## Step 4 - Judge the queue, top-down
Read `tracking/queue_<today>.md`. Thresholds from `settings.yaml thresholds` (defaults 60 / 45 / 40). For EACH
item, read the posting's saved JD (path on the queue line), the critic line, the eligibility read, then:
- score >= build line -> BUILD by default. A skip needs hard ineligibility or a never-claim quoted from the
  REQUIRED block, written into the ledger reason.
- stretch line .. build line-1 -> BUILD when the location mode allows it (see LOCATION below) or a user rule says so (a
  lane they asked to stretch into, the priority lane, degree-credit years language); else SKIP naming the specific
  required-block gap.
- below the stretch line, or `⚠Δ` (the judges disagreed) -> read the JD yourself; usually SKIP with the gap
  named, WATCH if it may become relevant, or put it under "needs your decision" in the report when it is
  genuinely a judgment call for the person (salary, location, a role they might like). Before `decide.py WATCH`
  on a posting that came from a listing FEED (the Chronicle, HigherEdJobs, a VC board, a listserv: the queue line's
  source is the feed, the employer is inside the title), find the employer's own posting page and use THAT url;
  the tracker's "Official link" must never be an aggregator (CONSTITUTION I.6).
- LOCATION follows the mode the person chose at setup (settings.yaml `location.mode`; their reasons are in my-rules.md
  GEOGRAPHY). "Local" = inside the commuting area or remote.
  - `local_only` (stay local): away postings were already set aside by rubric prep; build local ones from the stretch line.
  - `local_first` (local first, would move for a strong fit): local from the stretch line; away only at or above
    `location.away_bar` (default 70); away postings between the build line and the away bar go under "needs your decision"
    as "worth a look if you would move to <place>".
  - `unsure`: like local_first, but EVERY away posting at or above the build line goes under "needs your decision" with the
    direct question ("Would you move to <place> for this?"); record the answer in my-rules.md GEOGRAPHY. After about five
    answers, say which mode their answers point to and offer to switch.
  - `fit_first` (location barely matters): no location bar; judge on fit alone. Never skip for location by itself.
  - Never build or present a posting in a place listed in `location.never_places`.
- Never a skip ground alone: an agency pay band, a working condition, a never-claim outside the required
  block, a years bar when the JD credits an advanced degree, a judgment on a truncated JD (fetch the full
  text first). "When in doubt, build": drafting is free; the person decides what is sent.
Ledger every decision: `system/.venv/bin/python system/engine/tools/decide.py "<url>" SKIP|BUILT|WATCH "<reason in one line>"`.
decide.py refuses a SKIP of a posting at or above the build line (today or in the last 14 days) unless the reason quotes the
failed requirement as `REQ:"<the posting's words>"` or carries a hard tag (INELIGIBLE, EXPIRED, CLOSED, NOT-IN-COUNTRY,
NEVER-CLAIM, USER-RULE:<rule>, DUPLICATE:<ledgered url or folder>); it also refuses a location-only skip in the stretch band
unless the person never relocates. When it refuses, either supply the real reason or record WATCH and ask the person.
Unlogged items re-surface tomorrow. Before BUILT, the build must have actually succeeded (step 5).

## Step 5 - Build documents for every BUILD
Per item, follow `system/engine/skills/build/SKILL.md` steps 3-7 (folder, JD file with header, critic, entry
scorer, build script importing approved claims only, verify / keywords / audit / consistency, job card).
CV mode comes from `settings.yaml build.format` (`academic_cv` -> `resume_builder.AcademicCV`, plus a statement
from `profile/templates/` when the posting asks for one; `resume` -> `resume_builder.Resume`, one page).
A build that fails the audit is not a document: fix the build script (never the audit, never the YAML
without the person), or downgrade to "needs your decision" with the reason. Run `audit_claims.py <folder>` on the
whole folder after the last rebuild: it writes `AUDIT_PASS.json`, and `decide.py BUILT` refuses without it.

## Step 6 - Record
`decide.py` lines for everything judged (done in step 4; BUILT after a successful build). Do NOT add rows to
`state.db` for builds: a row is added only when the person says they applied ("I applied to X" ->
`state.py applied "X"`, which fills Position / Job Link / Resume Used from the built folder; add `Lane=...`
when known). Then refresh the tracker: `system/.venv/bin/python system/engine/tools/state.py tracker` (decide.py
already does this after every BUILT / WATCH; this call makes sure `My Job Search/tracker.csv` reflects today's run
before the report is written).

## Step 7 - The report  -> `My Job Search/reports/<today>.md`, then paste it in chat
Plain language, no tool output, no jargon, in this order:
1. **What I found** - from the RUN SUMMARY: boards checked, new postings seen, how many fit well enough to be
   judged, and the cost line "about N postings scored by the two judges" (from `judge_plan.json`; add "M more wait
   for the next run" when some were deferred). Then, still in the first lines, every
   arm that was idle or failed, one line each ("Federal postings: off, no USAJobs key - say the word if you want
   them", "the Workday boards did not answer today (3 fetch errors), so those employers were not searched"), and
   **what I could not read**: "N postings could not be read (page refused or timed out)" plus any watched employer
   whose page failed. A run that reached no board at all is reported as exactly that, never as "nothing new".
2. **Built for you (apply on the employer's page)** - one block per build: employer and title; the official
   posting link; the folder and file name of the document(s); fit in one line (what matches); honest gaps
   in one line (what the posting wants that you do not have); the one-line judge score if useful ("both
   judges 72/100"). Closing dates when known.
3. **Needs your decision** - items you did not decide: title, employer, link, the question in one line
   ("$38k, below your floor; want it anyway?").
4. **Skipped** - one line each: title, employer, why (plain: "needs a master's degree", "requires a license you
   do not hold", "a sales job dressed as something else", "not in the U.S.", "night shifts only, which you ruled out"). Group auto-skips as a count with three examples.
5. **Watching** - items parked as WATCH, one line each.
6. **Next** - "You apply yourself; tell me 'I applied to <employer>' when you do, and tell me about every
   reply ('<employer> rejected me', '<employer> wants an interview'). Your tracker (My Job Search/tracker.csv)
   lists everything built and applied." Plus anything blocked ("LibreOffice is missing, so I could not count pages; the file is fine to
   open and check yourself").
Write the file, then present the same text in chat. Never say "applied"; nothing was.

## What this skill never does
Apply, submit, send, post, fill a web form, read email, add a never-claim to a document, edit the audit to
make it pass, delete a ledger line, run unattended on a schedule.
