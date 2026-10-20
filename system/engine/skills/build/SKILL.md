---
name: jobkit-build
description: "build my documents for <link or pasted posting>" - one posting the person found themselves. Claude fetches it, judges the fit honestly (and says so when it is poor), builds the CV / resume and any statement from approved claims only, audits, and presents a job card. Never applies. Use when the person gives a job link, pastes a posting, or asks for a CV / resume / cover letter / statement for a specific job.
---

# jobkit build - "build my documents for ..."

Read `system/engine/CONSTITUTION.md` and `system/engine/charters/build.md`. Every tool runs with the jobkit python
(`system/.venv/bin/python`; `system\.venv\Scripts\python.exe` on Windows) from the jobkit folder; workspace =
`$JOBKIT_WORKSPACE` or `My Job Search/`. Preconditions: onboarding phase 13 (approved
claims) is done; if not, say "I can only build from claims you have approved; say 'set me up' and we
finish that first" and stop.

Say first: "Reading the posting and judging the fit, two minutes."

## Step 1 - Get the posting text
- A link: fetch the employer's own page (prefer it over any aggregator copy; if the link is LinkedIn /
  Indeed / Adzuna, find the employer's posting and use that as the apply link). Use the same fetch path the
  screen uses when a plain fetch fails (`screen_minquals.py` handles Workday / Oracle / iCIMS / Phenom pages).
- Pasted text: use it as given; ask for the link once ("Do you have the employer's link? I put it on the
  job card so you apply in the right place.") and accept "no".
- If the page is a stub (under ~700 characters, no requirements), say so and ask for the full text.

## Step 2 - Judge honestly, before building
- Eligibility first (`settings.yaml work_authorization`, `exclusions`, country): if it is closed, say so in one
  line and stop ("This one requires a master's degree / U.S. citizenship / a license you do not hold; I would not build it.
  Want it anyway?"). Build only on an explicit yes, and note the override in the build script.
- Fit: run `match.score_texts([(title, text)])` for the gate numbers and read the REQUIRED block yourself
  against `profile/profile_blind.md`. Tell the person the honest read in two lines: what matches, what is
  missing. A poor fit is said plainly ("This is a desk job in billing; your bedside skills would not be used. I
  will build it if you want, but I would not expect a reply." / "This wants five years of Go; you have Python.").  Then build unless they say stop.

## Step 3 - Folder and JD file
`applications/<Employer>_<Role>/` (CamelCase, no spaces). Save `JobDescription.txt` with a header:
```
SOURCE: <employer>  |  FIT: <one line>  |  POSTED: <date or ?>  |  CLOSES: <date or ?>
APPLY: <employer's own posting URL>
==========
<full posting text>
```
Never overwrite an existing folder without backing it up (`<folder>.bak-<date>`).

## Step 4 - Critic and entry scorer
`critic.py <folder>` - a HOLD needs a logged override line in the build script (or stop and explain).
`entry_scorer.py <folder>/JobDescription.txt` - which experience entries to lead with; overrides noted in
the build script comments.

## Step 5 - Build script (approved claims only)
Write `<folder>/build.py` that imports from `approved_claims` by NAME (tuples, named bullets, skills lines,
summaries, `CV_*` lists) and from `resume_builder` (`Resume` for `build.format: resume`, `AcademicCV` for
`academic_cv`; see `system/examples/taylor_example/build_test_example.py` and `system/examples/marina_example/build_test_cv.py`
for the exact shape). Rules: open the summary with the posting's role noun; tenure line only when the JD has a
numeric years bar at or below the person's years; hands-on vs used wording exactly as approved; at least
`build.min_experience_entries` entries; the location line per `build.location_line_default` or the metro
when commutable; file name = `build.cv_filename` / `build.resume_filename`. Never type a sentence into the
script that the YAML does not already approve. A statement or cover letter (statement of purpose / research statement /
academic cover letter) is composed from `profile/templates/` and the person's confirmed facts; it is checked for
never-claims and for every number's source, not line by line, so write only what the evidence files say. After saving it,
mark it as a letter: `<jobkit python> system/engine/tools/docxtext.py --stamp-letter <file.docx>` (a file named
CoverLetter_*/Statement_* counts as a letter by name; anything else unmarked is audited as a resume and will fail).
The script needs no path tricks: `system/.venv` carries a `.pth` that makes `system/engine/tools` importable, so
`from resume_builder import Resume` and `from approved_claims import ...` work as they are (the example scripts
still add the engine to `sys.path` by hand; that is harmless). Run it with the venv python; the workspace is found
through `$JOBKIT_WORKSPACE` or the default `My Job Search/`.

## Step 6 - Verify
`verify_resume.py <docx> --jd <folder>/JobDescription.txt` (page count or page range; parse test; date
order; readability; without LibreOffice the page checks are skipped and say so), `keywords.py <docx> <jd>`
(add MISSING-CLAIMABLE terms verbatim where true; UTIL only hedged; NEVER = honest gap, never added;
ASK -> ask the person first), `audit_claims.py <folder>` (must PASS on EVERY .docx in the folder: the resume / CV is checked line by line
against approved_claims.yaml - any sentence the YAML does not approve fails it; a letter or statement is checked for
never-claims and for numbers with no approved or confirmed source), `consistency.py <folder>` (PASS or a noted
deliberate difference). Fix the build script and rebuild until clean. A failing audit is never shown as a finished
document. A clean folder run writes `<folder>/AUDIT_PASS.json`; `decide.py BUILT` refuses without it, or when a
document changed after the audit - rebuild, then audit the folder again, in that order.

## Step 7 - Present the job card, then record
In chat, plain language:
- employer, title, official apply link (first line)
- the file(s): folder and name ("open it with Word or Pages")
- fit in one line; honest gaps in one line (these stay OFF the document and ON the card)
- anything to confirm before sending (an ASK term, a pending claim)
- "You apply on the employer's page. Tell me 'I applied to <employer>' when you have."
Then `decide.py "<url>" BUILT "<reason>"` so the posting never re-surfaces (it also refreshes
`My Job Search/tracker.csv`, where the posting now shows as "built - not applied yet" with its folder). The url must be
the APPLY line of the folder's JobDescription.txt and the folder must hold a fresh `AUDIT_PASS.json` (step 6);
otherwise decide.py refuses and says why - never work around it. Append the
card to today's report file (`My Job Search/reports/<today>.md`, create it if absent).

## Corrections from the person
FACT -> fix the evidence file; PHRASING -> approved_claims.yaml (read back, then confirm); TARGETING ->
my-rules.md; then rebuild. Ask for facts, never for finished bullets. Never add a claim they did not confirm.
