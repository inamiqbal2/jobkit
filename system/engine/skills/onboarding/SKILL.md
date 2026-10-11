---
name: jobkit-onboarding
description: "set me up" - first-time setup of jobkit for a person who is not technical, in any field, as a conversation. Claude does every technical step; the person only answers plain-English questions one at a time and confirms what is read back. Resumes from My Job Search/ONBOARDING_STATUS.md. Also "read my documents": the person dropped old resumes / CVs / letters / papers into My Job Search/intake; Claude extracts them, drafts the profile, and runs the same interview in CONFIRMATION mode. Use when the person says "set me up" or "read my documents", when the workspace has no filled settings.yaml, or when a build is requested before evidence and approved claims exist.
---

# jobkit onboarding - the conversation script

You are setting up jobkit for a person whose field, facts and rules you do not know, and who will never
open a terminal or a file. You do all of that. They talk; you ask, write, read back, confirm.
Read `system/engine/CONSTITUTION.md` first (never fabricate; nothing sent; per-item confirmation).

## How to run this script
- **Resume rule.** If `My Job Search/ONBOARDING_STATUS.md` exists, read it. The first phase that is not `done`
  is where you continue. Open with one line: "Welcome back. Last time we finished <phase>; next is <phase>."
- **One question at a time.** Each question carries an example of a good answer. Never ask two things in
  one message. Never show YAML, file names or commands to the person; those are your side of the work.
- **Examples fit the person.** The examples in this script rotate across three lives - a registered nurse, a
  software engineer, a field biologist - so you see the shape. Once the person has named their field (phase 5),
  give examples from THEIR field, not from these.
- **Conditional phases.** Phases 9, 11 and 12 (publications, teaching, references) are asked only when the
  person chose an academic or research track in phase 5; otherwise mark them `done - not applicable` and move
  on without asking. Phase 16's USAJobs step runs only when they said government jobs interest them;
  otherwise say "I will skip the government-jobs key; you can add it any time" and offer Adzuna only.
- **Read back before writing.** Every fact is quoted back ("I have: ... Correct?") and written only after a
  yes. Edits are applied and read back again. "Skip" / "later" is always accepted for optional items.
- **After every phase**: update the phase row in `ONBOARDING_STATUS.md` (status `done`, notes = which files
  you wrote, anything left open), and add open questions under "Open questions". Then say what comes next
  in one sentence and ask whether to continue now or stop here (stopping is fine; nothing is lost).
- **Files.** Workspace = `$JOBKIT_WORKSPACE` or `<jobkit>/My Job Search/`. Key documentation lives in the shipped
  templates (`My Job Search/*.example`, `*.TEMPLATE.md`); complete filled examples of every file are
  `system/examples/jordan_example/` (nurse, industry/clinical, one-page resume), `system/examples/taylor_example/` (engineer,
  industry) and `system/examples/marina_example/` (biologist, academic CV); `system/examples/sam_example/` is the
  line-by-line annotated reference for `settings.yaml` and `approved_claims.yaml`. The live files start as EMPTY
  templates (placeholders such as `<your name>`): every value you write replaces a placeholder, never a fake fact.
  Copy the examples' SHAPE, never a fact.
  Use the jobkit python (`system/.venv/bin/python`; `system\.venv\Scripts\python.exe` on Windows; written `<jobkit python>`) for every tool after phase 0.
- **No build until** at least one evidence file is `CONFIRMED-BY-USER`, `profile/approved_claims.yaml` holds
  claims confirmed one by one, and `audit_claims.py` passes on a test document. If the person asks for a
  resume earlier, say why not in one sentence and continue.
- **Where you draft, say so.** "Here is what I drafted from what you told me" is fine; passing a draft off as
  their words is not.
- If they have a resume or CV file (PDF/Word), or any other document about their work, the way in is the intake
  folder (`My Job Search/intake/`) and "read my documents": see **Confirmation mode** below. Every item from a
  document is still read back and confirmed; a resume is a source of questions, never of approved claims.
- **Quote every path.** The folder is called `My Job Search` (with spaces); tools take `$JOBKIT_WORKSPACE` or find it
  on their own, but any path you type on a command line goes in quotes.

## Time and tone
Whole interview: 2-4 hours, in as many sittings as they like. Phases 7-13 are the long ones. Say so up front.
Short questions. No jargon. When you explain a rule, one sentence, then the question.

---

## Phase 0 - Environment (no questions)
Run `<launcher> setup` from the jobkit folder (it creates `system/.venv`, copies the templates into
`My Job Search/`, writes `tracker.csv`, checks and locks the engine). `<launcher>` = `python3 system/jobkit.py` on
macOS / Linux, `py -3 system\jobkit.py` on Windows (CLAUDE.md, "The jobkit python"). If Python is missing or older
than 3.11, follow the "If Python is missing" section of `CLAUDE.md` (ask before installing anything system-wide).
Explain the result in two plain lines (e.g. "Your computer is ready. LibreOffice is not installed, so I
cannot count pages of a finished resume yet; I can add it later if you want."). setup.py created
`ONBOARDING_STATUS.md` with every phase pending and marked phase 0 done.

## Phase 1 - Welcome and what to expect
Say (in your words, five lines): jobkit finds postings, judges fit, and builds an honest resume and letters
from facts you confirm; it never applies, never sends anything, never reads your email; setup is an
interview of 2-4 hours in as many sittings as you like; if government jobs interest you there is one free
key to get from a website near the end (I will walk you through it), otherwise nothing; you can say "skip"
or "stop" any time.
Then offer the short cut, in these words or close to them:
"If you have an old resume, CV, essays, papers or reports, drop them into the folder **My Job Search/intake**
and say **'read my documents'**; I will fill in most of the interview from them and you will only confirm and
fill gaps. Otherwise we start from scratch, one question at a time."
Ask (one at a time):
1. "Do you want to drop documents into the intake folder first, or start from scratch?" (If they drop files,
   continue with **Confirmation mode** below. If they paste a resume into the chat instead, save it as
   `My Job Search/intake/pasted_resume_<date>.txt` and do the same.)
2. "Shall we start?"
Write: status row 1 done; note "intake: <n> files read <date>" or "no documents; from scratch".

## Confirmation mode - "read my documents" (any time; usually right after phase 1)
The person dropped files into `My Job Search/intake/`. You turn them into DRAFTS and then run phases 2-13 as a
read-back instead of an interrogation. Nothing from a document becomes an approved claim without the read-back
(CONSTITUTION II: claims inherited from an old resume are guilty until verified).
1. **Extract.** `system/.venv/bin/python system/engine/tools/intake.py`. Say what it found in one line ("I read 3
   files: a 2024 resume, a cover letter and your thesis abstract; one photo I cannot read."). A PDF that came out
   empty is a scan: ask for a Word or text version. Read `intake/_extracted/INDEX.md` and then EVERY extracted
   file in full (they are short; never skim the one that matters most).
2. **Draft, with a source on every fact.** Write, all marked DRAFT:
   - `profile/evidence/<slug>.md` for every job, degree, thesis, project or volunteer role you can see, from
     `_TEMPLATE.md`, header line `Status: DRAFT (from intake, unconfirmed)` and, under every fact you took from a
     document, a line `Source: intake/<file>` (the file name, not a quote). Fill only what the document says; leave
     the template's questions where it is silent (operated vs used, provenance of numbers, NDA, a story).
   - `profile/skills-inventory.md` with every tool, system, method and certificate the documents mention, each
     tagged `UNCONFIRMED` (never hands-on / used / never yet) and with its source file.
   - `profile/publications.md` as a DRAFT list when the documents list any (citation as written, `Source:` each,
     status unknown until verified) - any track; the person may volunteer them.
   - a short block at the top of `ONBOARDING_STATUS.md`: "Drafted from intake <date>: identity (<what>), <n>
     positions, <n> degrees, <n> skills, <n> publications, certifications (<list>) - ALL PENDING CONFIRMATION".
   Do NOT write settings.yaml, approved_claims.yaml, signals.yaml or my-rules.md from a document; those are written
   in their phases after the read-back.
3. **Then run phases 2-13 in confirmation mode.** The rule for every phase: read back what the drafts say in one
   message, ask "Correct?", take edits, and ask ONLY the questions the documents did not answer.
   - Phases 2-4, 6: one read-back each ("From your resume: Sam Example, sam@example.com, 614-555-0100, Columbus,
     Ohio; links: LinkedIn. Correct?"). Work authorization (phase 3) is never in a resume in a usable form: ask it in
     full. Salary (phase 6): ask in full.
   - Phase 5: field, track, lanes, titles come from the documents as a proposal ("Your documents say chemical
     process engineering in polymers; I would set the field to that and aim at industry. Right?"); exclusions
     and the never-skip lane are asked in full.
   - Phase 7: for EACH drafted position, read the 6-10 line summary back, then ask only what is missing of the
     eight questions - almost always 3 (operated vs used), 5 (numbers: "your resume says 'cut cycle time 12%';
     where does that number come from, and could you defend it?"), 7 (anything not to disclose) and 8 (one story).
     A number without a provenance stays DRAFT. On yes, `Status: CONFIRMED-BY-USER <date>`; keep the Source lines.
   - Phase 8: present the UNCONFIRMED list in groups of 5-8 and have them tag each hands-on / used / never; then
     the CORE / WORKING / FAMILIAR / NEVER CLAIM questions as written.
   - Phase 9 (if any publications were found, or the track is academic): read the draft list item by item.
   - Phase 10: read back the certificates found, with years; ask what is missing and what they do not hold.
   - Phase 13: as written - every bullet read back; the old resume's wording is a starting point only. A bullet
     that implies operating something they said they only used is rewritten with the hedge, not approved.
   Mark each phase `done` with the note "confirmed from intake draft" or "asked in full".
4. **What never happens here.** Copying a sentence from an old resume straight into approved_claims.yaml;
   treating a number, a title or a date as confirmed because it was printed somewhere; modifying, moving or
   deleting a file in `intake/`; reading anything outside `intake/`.

## Phase 2 - Identity and contact  -> `settings.yaml: identity`
Ask, one at a time, each with an example:
1. "What is your full name exactly as it should appear at the top of your resume? (e.g. Jordan A. Example)"
2. "Which email address should employers use? (e.g. jordan.example@gmail.com)"
3. "Which phone number, written the way you want it printed? (e.g. 720-555-0133)"
4. "Which city and state do you live in? (e.g. Denver, CO)"
5. "Any links to print: LinkedIn, a portfolio or GitHub, ORCID or Google Scholar, a website? Give them in the
   order you want, or say none. (e.g. linkedin.com/in/jordan-example; or github.com/sam-example; or
   orcid.org/0000-0001-2345-6789)"
Write `identity` (name, first_name = first word of the name, email, phone, city_state, links[]).
Read back: "Your contact line will read: <phone> | <email> | <links> | <city, state>. Correct?"

## Phase 3 - Work authorization  -> `settings.yaml: work_authorization`
Say: "One rule of this tool: it never guesses your work status. Postings that need a status you do not
have are dropped only according to what you tell me now." Then ask:
1. "Are you a U.S. citizen?" (if the search country is not the U.S., ask the same for that country)
   - yes -> resume_line "U.S. Citizen"; citizenship_only_roles_open true; export_controlled_open true;
     permanent_resident false; sponsorship_needed false; then ask 2 only.
   - no -> ask: "Are you a permanent resident (green card)?"
     - yes -> resume_line "U.S. Permanent Resident"; permanent_resident true; citizenship_only false;
       export_controlled_open true; sponsorship_needed false; then ask 2.
     - no -> ask: "Will you need an employer to sponsor a visa, now or later? (e.g. 'yes, I am on F-1 OPT'
       or 'no, I have an open work permit')" -> sponsorship_needed; export_controlled_open false;
       citizenship_only false; then: "How do you want your status written on the resume, in your own words?
       (e.g. 'F-1 OPT, STEM extension eligible' or leave it off)" -> resume_line ("" to omit).
2. "Could you obtain a U.S. security clearance if a job needed one? Most people can say yes if they are a
   citizen; say no if you are not sure." -> clearance_possible.
Write the block. Read back: "On your resume: '<resume_line>'. I will drop postings that require: <the classes
that are closed>. I will keep everything else. Correct?" Note the date in the status file.

## Phase 4 - Location, commuting, relocation  -> `settings.yaml: location`
Ask:
1. "Which country are you searching in? (e.g. United States)"
   -> `country` (US / CA / UK have built-in geography; any other country: draft `in_country_regex`,
   `in_country_regex_loose`, `foreign_regex_extra` yourself from the country's place names and read them
   back as a plain list of place words).
2. "Where could you commute from home? Name the towns or areas. (e.g. anywhere in the Denver metro, up to
   Boulder)" -> commutable_metros, commute_radius_miles (ask "roughly how many miles is too far?" only if unclear).
3. "Would you move for a job: yes, no, or only for the right one?" -> relocation yes / no / case-by-case.
4. If yes or case-by-case: "Which places would you be glad to move to? (e.g. Salt Lake City, Phoenix,
   anywhere in the Pacific Northwest)" -> draft `tier2_regex` from these; `tier1_regex` from the commutable area +
   "Remote".
Write the block. Read back: "Home: <home>. Within commuting reach: <metros>. Moving: <stance>. Places I will
rank second: <tier2 places in words>. Remote jobs count as close. These only order the list; they never hide
a posting. Correct?"

## Phase 5 - Your field and track, what you are looking for  -> `settings.yaml: lanes[], targets, exclusions, build.format`; `my-rules.md` TARGET + EXCLUSIONS; `tracking/registries/queries.yaml` (first draft)
Ask:
1. "What is your field, in a few words? (e.g. 'critical-care nursing', 'backend software engineering',
   'wildlife field biology')" -> remember it; from here on every example you give comes from this field.
2. "Which kind of employer are you aiming at: (a) industry or private companies, (b) academic or research
   positions, (c) government, (d) nonprofit, or (e) a mix - say which ones?" -> `targets.track`
   (industry | academic | government | nonprofit | mix). Consequences you apply silently:
   - academic or research in the mix -> phases 9, 11, 12 are asked; otherwise they are marked not applicable.
   - government in the mix -> phase 16 offers the USAJobs key; otherwise it is skipped.
   - academic -> ask 3 below; otherwise targets.phd_positions false.
3. (academic/research only) "Are you looking for (a) PhD positions, (b) paid research or professional jobs,
   (c) both?" -> targets.phd_positions (a or c -> true); then "Are fixed-term, grant-funded posts of 1-2 years
   fine? Most research posts are." -> fixed_term_ok. (Everyone else: fixed_term_ok false unless they say
   contract-length roles are fine.)
4. "Are the jobs you want sometimes paid hourly or open to people without a degree? (e.g. nursing shifts,
   technician work, trades)" -> targets.hourly_ok (true = the critic stops flagging hourly / high-school-minimum
   postings as below your level).
5. "What is your highest degree, and in what? (e.g. 'BSN, nursing, 2019'; 'B.S. Computer Science, 2021';
   'M.S. Wildlife Biology, 2022')" -> if no PhD: exclusions.postdocs false (postdoc titles dropped) and say so
   only if academic; if PhD: ask whether postdocs are wanted.
6. "Describe the work you want in two or three sentences, as if to a stranger. (e.g. 'Staff nurse in an ICU
   or step-down unit at a hospital; or a clinical educator role teaching new nurses.' / 'Backend or platform
   engineer on a product team, Python or Go, at a company of 50-2,000 people.' / 'Field and lab work on
   wildlife populations: surveys, telemetry, habitat assessment, at an agency, university or NGO.')" -> lane 1
   description.
7. "What would that job be called? Give 3-8 titles you have seen. (e.g. ICU Registered Nurse, Critical Care
   RN, Clinical Nurse Educator / Software Engineer II, Backend Engineer, Platform Engineer / Wildlife Biologist,
   Field Technician, Research Associate)" -> example_titles (breadth only; titles never decide fit).
8. "Is there a second kind of work you would also take, maybe a little outside your field? (e.g. case
   management or quality roles / developer-tools or data engineering / environmental consulting field work)"
   -> lane 2 (transferable) or none. Repeat once more at most (max 4 lanes, one of them PhD positions if 3a/3c).
9. "Which one of these kinds of job must I never skip, even when a score looks low?" -> `priority: true` on that lane.
10. "What kinds of jobs should I never show you? (e.g. travel-nurse agencies, home health / recruiting, sales
    engineering / anything that is really a sales job)" -> exclusions.role_types (plain words -> word-bounded
    regexes), my-rules.md EXCLUSIONS with the reason as they said it.
11. "Any employers you do not want to see? Say none if none." -> exclusions.employers.
12. "Contract, agency or freelance gigs: in or out?" -> exclusions.contract_work.
13. "For applications, do you want a one-page resume (usual for industry, hospitals, government and
    nonprofits) or a multi-page academic CV (usual for research and PhD applications)?" Default the question
    to the track: offer the resume unless the track is academic. -> build.format resume | academic_cv;
    resume_filename "Resume_<First>_<Last>.docx" / cv_filename "CV_<First>_<Last>.docx"; cv pages 2-3 default.
Write lanes (name = short slug, description, example_titles, never_claims [] for now, priority, packs []
for now), targets (track, phd_positions, fixed_term_ok, hourly_ok, employers [] for now), exclusions, build;
my-rules TARGET IN PLAIN WORDS (priority order) and EXCLUSIONS; queries.yaml first draft (3-10 short
`board_terms` from the titles and the field words; the other lists are written in phase 17).
Read back: "You are looking for: <lane 1 in one line>; also <lane 2>. Track: <track>. Never: <exclusions>.
Documents: <resume or CV>. The kind of job I will never skip: <lane>. Correct?"

## Phase 6 - Salary  -> `settings.yaml: salary`; `my-rules.md` SALARY
Ask: "What is the lowest yearly salary you would accept, and what are you aiming for? (e.g. 'at least
$85,000, hoping for $100,000'). Hourly is fine too; I will convert." (Academic: "PhD stipends are judged on
their own terms.") -> floor, target, currency.
Say: "This never hides a posting; it only shows up as a note when I judge one."
Read back the two numbers.

## Phase 7 - Evidence: one file per job, degree, project  -> `profile/evidence/<slug>.md`; `settings.yaml: education[]`
Say: "Now the part that matters most. I will ask about each position one at a time. Facts, not polished
sentences; I write the sentences later and you approve them."
For the most recent position first, then backwards (jobs, residencies, internships, seasonal work, thesis /
degree research, volunteer work, teaching roles). For EACH, ask one at a time:
1. "Tell me about your most recent position: where, from when to when, and your title. (e.g. Example Regional
   Medical Center, March 2024 to now, Registered Nurse, Medical ICU / Acme Software, June 2021 to now,
   Software Engineer II / State Wildlife Agency, May 2023 to now, Field Biologist)"
2. "What did you actually do there, day to day? Two to four sentences a colleague would recognise."
3. "Which tools, systems, methods or equipment did you personally operate or do yourself? (e.g. ventilators and
   CRRT, Epic charting / Python services on Kubernetes, PostgreSQL / radio telemetry, mist-netting, R)"
4. "Which did you only use results from, work alongside, or watch someone else run? (e.g. the perfusionist ran
   ECMO; I managed the patient / the data team owned the warehouse; I queried it / the genetics lab ran the
   sequencing; I used the data)" - say: "This distinction keeps the resume honest; it matters to employers."
5. "Any numbers you can defend if asked? Where does each number come from? (e.g. 24-bed unit, 1:2 patient ratio,
   from the unit's staffing plan / a service handling about 40,000 requests a minute, from the dashboard / 140
   nest boxes checked weekly, from the field protocol)"
6. "Who did you report to, how big was the team, how was it funded, how long were you there?"
7. "Anything you must not disclose from this work? (e.g. patient details, unreleased product names, site
   locations of a protected species)"
8. "One story from this job you would tell in an interview: a problem, what you did, what happened."
Write `profile/evidence/<slug>.md` from `_TEMPLATE.md` (sections: what the work was; technical specifics;
tools/equipment OPERATED vs USED; real numbers with provenance; outcomes; scope; interview stories; NDA line
at the top), `Status: DRAFT`. Read back a 6-10 line summary ("Here is what I wrote down: ..."). On yes,
change to `Status: CONFIRMED-BY-USER <date>`. Then: "Next position, or is that everything?"
Degrees: ask institution, degree, dates, honours, and (academic track) thesis title and advisor; write
`settings.yaml education[]` (newest first, line = "<degree> in <field>, <city, state>" plus "| Thesis: <title>"
when there is one) and an evidence file for thesis / capstone / degree research when it was real work.
Status note: list the files and which are confirmed. Unconfirmed files are not sources.

## Phase 8 - Skills inventory with the three honest tags  -> `profile/skills-inventory.md`, `profile/lexicon.yaml`, `profile/critic_rules.yaml` (hard_checks, instrument_owner, screen_block)
Say: "I will list every tool, system, method and piece of equipment that came up, plus the ones jobs in your
field usually ask for. For each, tell me one of three things: hands-on (I did it myself), used (I worked
with it or its results but did not run it), or never."
Draft the list from the evidence files and the field (10-30 items). Present it in groups of 5-8 with
numbers; ask "For these, which are hands-on, which used, which never? (e.g. '1,2,4 hands-on; 3 used; 5 never')".
Then ask:
- "Which 5-10 skills would you defend in a tough interview? Those lead your resume." -> CORE.
- "Which have you used on real work but would not call yourself expert in?" -> WORKING.
- "Which do you only know from coursework or reading?" -> FAMILIAR.
- "Is there anything people in your field often claim that you must never claim? (e.g. a CCRN certification you
  do not hold / Kubernetes administration / a drone pilot licence)" -> NEVER CLAIM, with the reason.
Write skills-inventory.md (CORE / WORKING / FAMILIAR / HANDS-ON REALITY / CERTIFICATIONS placeholder /
NEVER CLAIM), lexicon.yaml (CORE+WORKING -> YES with synonyms; used -> UTIL; never -> NEVER; unsure -> ASK),
critic_rules.yaml (`hard_checks`: one "NEVER-CLAIM CORE: ..." per never-item a posting could make its main
duty; `instrument_owner.instruments` = used + never tools/equipment; `screen_block` = the same as short
key: regex pairs; leave `lane_rules`, `closed_lanes` for phase 17).
Read back the HANDS-ON / USED / NEVER lists and the NEVER CLAIM list line by line: "This is where resumes get
people into trouble, so please check each line."

## Phase 9 - Publications and presentations (academic / research track only)  -> `profile/publications.md`
Skip (mark `done - not applicable`) unless the track includes academic or research, or the person volunteers
publications. Otherwise ask: "Do you have publications, a thesis, talks or posters? If you have a Google
Scholar or ORCID page, or your CV lists them, point me to it and I will read them out for you to confirm."
If a link is given, fetch it; then for EACH item: "Is this right: <citation>? Published, under review, in
preparation, or other?" Verify published papers by DOI or publisher page when you can; say when you could not.
Write publications.md with the exact counts and THE RULE paragraph ("Exactly N peer-reviewed publications
(k first-author)") and the approved short line. No publications -> write "none" so the rule is explicit.
Read back: "I will say: '<approved line>'. Never more. Correct?"

## Phase 10 - Licenses and certifications  -> `profile/skills-inventory.md` CERTIFICATIONS; later `approved_claims.yaml cv.certifications` / a skills line
Ask: "Which licenses or certifications matter in your field, with the year and whether they are current?
Think of the ones a posting in your field lists: a professional license (RN, PE, CPA, a teaching license, a
bar admission), board or specialty certifications (CCRN, PMP, AWS, CISSP), safety and field cards (BLS, ACLS,
first aid, HAZWOPER, scientific diver, drone licence), languages, driver's licence classes." Then: "Any you do
NOT hold that people in your field might assume? (e.g. CCRN / a Kubernetes certification / a captain's licence)"
-> NEVER CLAIM additions.
Write the section with years and expiry dates. Read back the list with years.

## Phase 11 - Teaching and mentoring (academic / research track only; otherwise precepting / training counts in phase 7)  -> evidence (if not covered) and later `cv.teaching`
Skip (mark `done - not applicable`) unless the track includes academic or research. Otherwise ask: "Have you
taught, assisted a course, trained staff or volunteers, or mentored students? For each: what, where, when,
roughly how many people. (e.g. TA for Introductory Ecology Lab, 2 semesters, about 40 students each)" Write
the facts into the relevant evidence file (or a `teaching.md` evidence file). Read back.
(For other tracks, precepting new hires, running trainings or mentoring juniors was already captured as a fact
in phase 7; it becomes a bullet, not a section.)

## Phase 12 - References (academic / research track only)  -> later `cv.references`
Skip (mark `done - not applicable`) unless the track includes academic or research or the person asks. Otherwise
ask: "Do you want the CV to say 'References available upon request', or list people? If you list people I need
their permission to be on your CV first; give name, title, organisation, email only for those who have agreed."
Record the answer. Read back. (One-page resumes never carry references.)

## Phase 13 - Approved claims and never-claims  -> `profile/approved_claims.yaml`, `profile/profile_blind.md`, `settings.yaml: build, verification`
Say: "I will now draft the sentences that may appear on your resume, from what you confirmed. You approve each
one; I never use a sentence you did not approve."
Draft from the confirmed evidence + inventory (+ publications if any) (shape: `system/examples/jordan_example/profile/
approved_claims.yaml` for a resume, `system/examples/marina_example/...` for an academic CV; keys documented in
`My Job Search/profile/approved_claims.yaml.example`): summaries (one per lane, opening with the role noun),
tenure (line / short / years; ask "Counting from when? Does graduate research or a residency count?"),
experience entries (key, org, dates, role, loc, always_include for the current role, evidence, nda, 2-5 named
bullets each), projects, skills_lines (hands-on vs used wording fixed; a LICENSES & CERTIFICATIONS line when
phase 10 produced any), publications line (if any), hedged_phrases (the "run by ..." wordings), never_claims
(forbidden_terms from NEVER CLAIM + operator_patterns for used-not-operated tools), retired_claims [],
banned_words ["local"], consistency_items, pending (anything they hesitated on, with the question).
Academic CV: also the `cv:` block (education with thesis/advisor, publications, presentations, field or lab
experience, certifications, technical_skills, teaching, grants_awards, service, references) and `section:` on
every experience entry.
Read back EVERY bullet, one entry at a time: "Entry: <org>, <dates>, <role>. Bullet 1: '<text>'. True exactly
as written? yes / edit / drop." Then the summaries, the tenure line, the skills lines, the publications line.
Then the never-claims list: "I will never write these words on your resume: <list>. Add any?"
Run `approved_claims.py`; it must load with 0 errors; report the count in plain words.
Then draft `profile/profile_blind.md` (what the two blind judges read: HAS / DOES NOT HAVE / TARGET / LIMITS
/ LOCATION / LEVEL, under 80 lines, no employer names you are interviewing with). Read the whole file back
in plain prose: "Two independent judges will read this one-page description of you for every posting.
Here it is: ... Anything wrong or missing?"
Write `settings.yaml verification.employer_tokens` (the employer names on the resume) and finalise `build`.

## Phase 14 - Your own rules  -> `my-rules.md`, `settings.yaml: thresholds, modules, run`
Ask: "Any rule I should always follow that we have not covered? Say it in your words. (e.g. 'never show me
jobs in Alaska', 'always tell me if a job needs night shifts', 'prefer jobs that start after May')"
Write each as a dated entry with the revert condition. Explain in one sentence each and keep defaults
unless they ask: build line 60 / 100, stretch line 45 inside commuting reach, auto-skip below 40 when both
judges agree. Modules: inbox sweep OFF, outreach OFF (say: "I never read your email; that stays off").
Search feeds: the employers' own boards and the packs are always on. Then say: "Two extra listing feeds
exist, LinkedIn and Indeed. They are read by scraping public pages, which those sites' terms restrict, and
they break without notice. They are off unless you want them on - do you?" -> run.linkedin_guest /
run.indeed_jobspy only on an explicit yes (Indeed also needs one extra free package installed in this folder;
run `setup.py` again). Adzuna (an official free API) is offered in phase 16.
Read back the rules list.

## Phase 15 - Job boards and target employers  -> `settings.yaml: lanes[].packs, targets.employers`, `tracking/registries/custom.json`, assembled registries, watch list
Offer the packs as a plain menu (the "say it as" column of `system/engine/registries/packs/README.md`, one line
each: "Hospitals and clinical employers", "Big tech and software companies", "Government jobs: federal,
state, city, county", "Nonprofits, foundations, advocacy, NGOs", "Colleges, universities, schools", "Big
employers for business, marketing, sales", plus the science/engineering packs when the field fits). Ask:
"Which of these should I search? Pick any." -> packs on the matching lanes.
Then: "Name up to 10 employers you would love to work for; I will find their job pages. (e.g. UCHealth,
Denver Health / Stripe, Notion / the state wildlife agency, a university lab)" -> `targets.employers`.
Run `system/.venv/bin/python system/engine/tools/discover_boards.py --assemble` (it reads targets.employers; or pass the names).
It probes Greenhouse / Lever / Ashby / SmartRecruiters / Workable / iCIMS / NEOGOV under variants of each name,
web-searches the careers page and scans it for Workday / Oracle / ADP / Eightfold / Phenom / Radancy boards,
verifies each with a live call, registers verified boards in custom.json, and makes a MANUAL watch entry for
the rest. Read its line for each employer back in plain words ("Denver Health: found their Workday job site,
368 openings. HealthONE: their site refuses automated reading, so I will check it by hand each run."). The
tool names the host it found; when an employer has namesakes (UCHealth Colorado vs UC Health Cincinnati),
ask which one and fix custom.json by hand if needed. For an employer the tool could not find at all, ask for
the careers-page link and run `discover_boards.py --watch "<name>=<link>"`.
Then run `registries.py assemble` (if not already) and `watch.py --init`.
Read back: "I will search <N> job boards from the <pack names> and these employers: <list>. <M> of them
have no searchable board, so I will check their careers page by hand each run. Anything to add or remove?"

## Phase 16 - Optional keys (the one website step, only when it applies)  -> `keys.json`
If government jobs are NOT in the track: say "Federal jobs are searched through USAJobs, which needs a free
personal key. You did not ask for government jobs, so I will skip it; say 'add the USAJobs key' any time."
Mark the USAJobs part done - skipped. Continue with Adzuna below.
If government jobs ARE in the track, say: "Federal jobs (every agency, including the VA, the Park Service,
the Forest Service, NIH, the labs) are only searchable with a free personal key from USAJobs. It takes two
minutes and it is the one thing I cannot do for you, because it is tied to your email. Here is how: open
https://developer.usajobs.gov/apirequest/ in your browser, enter your name and email, agree to the terms,
and they email you a key (a long string of letters and numbers). Paste the key here when you have it, or say
'later'."
On receipt: write `usajobs_key` and `usajobs_email` (the email they registered with) into `keys.json`;
never repeat the key back in chat; say "Stored. Federal postings are now in the search." Add 3-6 USAJobs
search terms to queries.yaml (`usajobs:`). "later" -> status note "USAJobs key pending", nothing else changes.
Everyone: "Adzuna is a free job-listings API with an official key (https://developer.adzuna.com, two minutes).
It adds a broad listings feed from many employers. Want it, or skip?" -> keys.json adzuna_id / adzuna_key
+ run.adzuna true, or skip.

## Phase 17 - Field words for the matcher and the search terms  -> `profile/signals.yaml`, `profile/critic_rules.yaml: lane_rules`, `tracking/registries/queries.yaml`
Say: "The matcher decides whether a posting is 'talking to you' from the words in the posting's text, never
from the title. I drafted the words from everything you told me."
Draft (shape: `system/examples/jordan_example/profile/signals.yaml` or `system/examples/marina_example/...`; comments in
`My Job Search/profile/signals.yaml.example`): one `role: home` lane with 10-15 regexes and weights (4 = only your
field says this; 1 = weak hint), negatives for the excluded domains; one `role: transferable` lane if there
is a second lane; thresholds at the example defaults (phase 18 calibrates); `priority_patterns` for the
priority lane; `lane_rules` in critic_rules.yaml (JD words -> lane label).
Read back in plain words: "Strong signs of your field: <words>. Weaker signs: <words>. Words that push a
posting away: <words>. Anything missing, or anything that would fire on the wrong kind of job?"
Priority-lane dry test (only when a lane has `priority: true`): the `priority_patterns` decide which postings are
never auto-skipped, so test them before keeping them. `strong` words must be unambiguous on their own (a title
word that only your lane uses); `weak` words count only with an `anchor` word within 200 characters of them; an
anchor that every posting in the field mentions ("high school", "hospital") makes the whole field priority. Run
`<jobkit python> system/engine/tools/lanes.py --test 200` once postings exist (after phase 18's first run, or on the
saved postings of a dry run) and tell the person the number in plain words: "Of the last 200 postings, 37 would be
marked as your never-skip kind: <three examples>. Does that look like the right set, or too many?" More than half
= too broad; narrow `strong` / `anchor` and run it again.
Then write the FULL `queries.yaml` from the same field words and the titles of phase 5 (shape:
`My Job Search/tracking/registries/queries.{nurse,software,biologist}.yaml.example`): `workday_terms` (3-15 short
terms), `hard_ats_terms` (3), `board_terms` (3-6), `usajobs` (3-6; only if the key exists or is pending),
`adzuna` (quoted phrases; only if the key exists), `linkedin` / `indeed` (only if those arms were switched on
in phase 14; otherwise leave them empty). Read back: "I will search the keyword boards for: <terms>. These are
nets, not filters; everything caught is judged on its text. Add or remove any?"

## Phase 18 - First dry run and calibration (20 postings)  -> `profile/signals.yaml: thresholds`, `my-rules.md` calibration table
Say: "I will now search for real postings for the first time. It takes 10-40 minutes depending on how many
boards you chose; nothing is applied to, nothing is sent. Then I will show you 20 postings and you tell me
which ones you would honestly apply to."
Run `<launcher> setup --quick`, then `daily.py` (from the jobkit folder, with the venv python;
log to `tracking/daily_run.log`). Do NOT judge or build anything this time.
Pick 20 screened postings from `tracking/minquals_screened.json`: about 10 that passed the draft gate and 10
near-misses, mixed. Show them in batches of 5: number, title, employer, location, one line from the posting,
official link. Ask per batch: "Which of these would you honestly apply to? (e.g. '2 and 4')". Record fit /
not-fit per posting.
Calibrate per `system/engine/charters/search.md` "Calibration ritual": rescore the cached JD texts offline (a
throwaway script in your scratch folder, never in the workspace) under candidate thresholds; choose
`jd_gate` / `sig_min` / `sigx_min` so that no labelled not-fit posting passes while the most fit postings do;
a fit posting with a near-zero signature means a missing word in signals.yaml - add it. Write the
before/after table (dated) into my-rules.md and the thresholds into signals.yaml.
Read back: "With the new settings, <k> of your <n> 'yes' postings pass and <j> of the <m> 'no' postings are
kept out. The top of the list now reads: <5 titles>. Does that look like your jobs?"

## Phase 19 - First live run, you watching
1. Test build first: pick one labelled-fit posting; build its document per `system/engine/skills/build/SKILL.md`
   (the full chain: critic, entry scorer, build script importing approved claims only, verify, keywords,
   audit, consistency). Show the file. Ask: "Would you send this? Tell me anything wrong." Classify each
   correction FACT (fix the evidence file) / PHRASING (fix approved_claims.yaml) / TARGETING (my-rules.md),
   fix the source, rebuild. Never edit the audit to make it pass.
2. Then the real thing: follow `system/engine/skills/daily/SKILL.md` from its step 3 (the search already ran
   today), with the person watching: two blind judges, merge, judge the list top-down explaining each in
   one line, build the approved ones, write the report, present it.
3. Say: "You apply yourself, on the employer's page, using the file in the folder I named. When you have
   applied, tell me 'I applied to <employer>' and I will record it in your tracker (`My Job Search/tracker.csv`)."
Write `tracking/OUTCOMES_LOG.md` first entry (date, what ran, what was built).

## Phase 20 - The daily ritual explained
Say, in your words: "From now on, type 'run my job search' whenever you like (daily is ideal; weekly works).
I check the boards, judge every new posting, build documents for the good ones, and give you a short report:
what I found, what I built and where the files are, what I skipped and why, and what needs your decision.
You apply on the employer's site and tell me 'I applied to <employer>'. Tell me about every reply you get -
'<employer> rejected me', '<employer> wants an interview'; the search learns from them and your tracker
(`My Job Search/tracker.csv`, open it with Excel or Numbers) always shows where every application stands. Type
'where am I?' any time for a status, 'build my documents for <link>' for a posting you found yourself, 'add
employer <name>' when you think of another company, or 'read my documents' when you drop new files into the
intake folder. The program itself is locked; if you ever want it to behave differently, say 'modify: <what>'
and I will explain the change before making it; 'revert to original' undoes every such change."
Mark phase 20 done; the status file header becomes "ONBOARDING COMPLETE <date>" with the open-questions
list (keys pending, unconfirmed files, pending claims) kept at the bottom.

## What you never do during onboarding
Invent a fact to fill a field. Copy anything from an example workspace. Assume the person's field or track.
Turn a module or a scraping arm on because it would be convenient. Send, submit, post or create anything in an
external system. Skip a read-back. Show the person a command, a file name or a YAML snippet as something they
must handle.
