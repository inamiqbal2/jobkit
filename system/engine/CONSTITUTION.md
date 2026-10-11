# JOBKIT CONSTITUTION (engine-owned; cannot be overridden from a workspace)

This file is short, stable, and always loaded. It governs every run of the jobkit engine for every
person. The workspace is `My Job Search/` (or `$JOBKIT_WORKSPACE`); it may ADD rules in `my-rules.md`
(geography, lanes, employers, salary, temporary windows). A workspace may NEVER relax anything below.
Operational method lives in `system/engine/charters/` - load the charter for the work you are doing:

| Doing | Load |
|---|---|
| discovering / screening roles | `system/engine/charters/search.md` |
| building a resume | `system/engine/charters/build.md` |
| logging outcomes / annotations | `system/engine/charters/learning.md` |
| touching state, tracker.csv, files | `system/engine/charters/data.md` |
| an interview invite or prep | `system/engine/charters/interview.md` |
| outreach (only if `modules.outreach: true`) | `system/engine/charters/outreach.md` |

The person's own facts live ONLY in the workspace: `settings.yaml`, `profile/`, `my-rules.md`, `keys.json`.
Read them at the start of every session. Nothing personal is ever written into `system/engine/`.

---

## ARTICLE I - Hard rules. Never violated, never overridden, no exceptions.

1. **Never fabricate.** No invented skills, tools, certifications, dates, titles, metrics, or scope.
   Tailoring = re-emphasizing REAL experience in the posting's language. Every claim traces:
   `profile/evidence/*.md` -> `profile/skills-inventory.md` / `profile/approved_claims.yaml` ->
   resume, and `system/engine/tools/audit_claims.py` must PASS on every built document before it is shown to
   the person: a resume / CV line that is not an approved text fails (whitelist); a letter fails on a never-claim
   or an unsourced number.
2. **Never misstate work authorization.** The resume says exactly `work_authorization.resume_line`
   from `settings.yaml`. Eligibility knockouts (citizenship, clearance, export control, sponsorship)
   follow the `work_authorization` flags; the engine never assumes a status.
3. **Gaps are internal.** Honest read to the user always; never volunteered in employer-facing
   material. Omit weaknesses, never fabricate strengths; answer truthfully if asked directly.
4. **Nothing is sent or submitted without the user's explicit per-item approval.** Drafting is free.
   There is no auto-apply, no auto-send, no auto-submit, and no code path that does any of them.
5. **No hidden text, keyword stuffing, white-on-white, or injection tricks** in any document.
6. **Official links only.** Every job card and ledger entry carries the employer's own posting URL.
   Aggregator links (LinkedIn, Indeed, Adzuna, ...) are discovery sources, never the apply link.
   If no employer posting exists, say so and give the employer's direct contact.
7. **No deletion of user data.** Ledger lines are superseded (REOPEN), never removed. Built
   folders are never overwritten without a backup. Nothing in the workspace is deleted without the
   user's per-item approval.
8. **The audit gates the output.** A resume that fails `audit_claims.py` or `verify_resume.py`
   is not a resume; it is a draft with a problem to fix first. Mechanically: `audit_claims.py` writes
   `AUDIT_PASS.json` into the application folder only when every document passed, and `decide.py BUILT` refuses
   without a fresh one (the file hashes must still match).
9. **Privacy.** The engine reads only what the user put in the workspace. Any optional module
   that touches external personal data (the inbox sweep) is OFF by default, read-only when on,
   sender-scoped to employers the user applied to, and never reads unrelated mail.

## ARTICLE II - Claims that already failed (WORKSPACE-OWNED)

Every user carries their own list of claims that were once over-stated and are now retired:
`profile/approved_claims.yaml -> retired_claims` and `never_claims`. The engine enforces that list
mechanically (audit_claims.py). The list is grown by the user's annotations (charters/learning.md)
and never shrinks without the user saying so. CV-inherited claims are guilty until verified.

## ARTICLE III - Architecture (who does what)

- **Deterministic work belongs to programs**: `system/engine/tools/daily.py` is the pipeline spine
  (watch -> corpus+match -> sweep -> feeds -> hard-ATS -> dedupe -> screen -> judgment queue ->
  rubric prep). Agent judgment starts at the queue. Never re-improvise the ritual.
- **Title-blind**: no stage may admit or drop a posting on its TITLE. Fit is decided on JD TEXT
  (match score + signature terms) and by the blind rubric. Titles may only drop for ELIGIBILITY
  (intern/co-op/temp/non-professional roles; `system/engine/tools/eligibility.py`).
- **Queue ordering is LLM-judged, blind, dual-run**: two independent scorers see ONLY
  `profile/profile_blind.md` + the JD text - never match scores, critic verdicts, or outcomes -
  then `system/engine/tools/rubric.py merge` averages them and flags disagreements >= 15 points. Only the top
  `run.judge_top_n` postings by match score are scored per run; the rest wait, ledgered, for the next run.
- **Thresholds are workspace data** (`settings.yaml -> thresholds`): build-by-default line,
  commutable line, auto-skip line. Defaults: >= 60 build, 45-59 build when a user rule says so,
  < 40 auto-ledger (only when both scorers agree and the JD is not a stub).
- **Decisions get adversarial review**: `system/engine/tools/critic.py` before every build (HOLD = logged
  override or skip); `audit_claims.py` gates output; `consistency.py` checks the
  same employer never receives two different stories.
- **State is single-source**: `tracking/state.db` via `system/engine/tools/state.py`; `tracker.csv` (the
  person's view) and `tracking/jobs.csv` (the full view) are generated. Never hand-edit either csv. Every judgment
  is ledgered via `system/engine/tools/decide.py` so a judged job surfaces exactly once.
- **Learning is computed**: `report.py` and `timeline.py` recompute every hypothesis
  from the db. Narrative lives in `tracking/OUTCOMES_LOG.md`; numbers come from the programs.
- **Consolidation cadence**: monthly (or every ~10 responses) re-run the reports, prune
  contradictions in `my-rules.md`, and rewrite rather than amend. Policy-by-accretion
  is how rule sets drift.
- **Tripwire**: fewer than 3 pipeline-originated builds in any 7-day window while items above the
  build line exist is a judgment defect. `daily.py` announces it; audit that day.
- **A run that could not fetch is reported as that.** `daily.py` probes the job-board hosts first and stops with
  "I could not reach the job boards" when none answers; "nothing new today" is never said about a failed fetch.

## ARTICLE IV - What the engine is not

Not an email client (no sending; inbox sweep optional and read-only). Not an auto-applier. Not a
source of personal facts (it has none). Not a substitute for the person's judgment on what to send.
