# Handoff to a new user (plain version)

You are receiving jobkit: a job-search assistant that one person ran for ten weeks and then emptied of
everything that was about him. It works for any field. This page says what you get, what you will be asked,
what the first day looks like, and the rules the tool will not let anyone break.

## What you get
- A folder you open in the Claude desktop app. From then on you talk to Claude in plain English; it does
  every technical step inside that folder. You never open a terminal or edit a file. The folder has three
  things at the top: `README.md`, `CLAUDE.md`, and `My Job Search/` - the only folder you ever look in. The
  program lives under `system/` and is locked (read-only, fingerprinted) once set up.
- The commands: `set me up` (the interview, 2-4 hours in as many sittings as you like), `read my documents`
  (you dropped old resumes, CVs, letters, papers or reports into `My Job Search/intake`; Claude drafts your
  profile from them and you only confirm and fill gaps), `run my job search` (the daily check, 10-40 minutes
  of Claude's time and 10-20 minutes of yours), `build my documents for <link>` (a posting you found yourself),
  `add employer <name>` (Claude finds that company's job board), `I applied to <employer>`, `<employer> rejected
  me` / `<employer> wants an interview` (your tracker is updated), `where am I?` (a status), and for the program
  itself `modify: <what>`, `show my modifications`, `revert to original`.
- `My Job Search/tracker.csv`: one line per posting Claude built documents for or you applied to - employer,
  role, location, dates, status, outcome, salary, fit, the employer's link, the folder with your documents, notes.
  Open it with Excel or Numbers; Claude keeps it current.
- Ready-made job-board packs by field (healthcare, tech, government, nonprofit, education, business, several
  science and engineering fields), plus whatever employers you name: Claude finds their boards itself.
- Three made-up example people (`system/examples/`: a nurse, an engineer, a biologist) so you can see what a
  finished setup looks like.

## What you bring
1. Facts about you, one position at a time, in your own words: where, when, what you actually did,
   which tools, methods, systems or equipment you personally used, numbers you can defend and where they
   come from.
2. Honesty tags on your skills: hands-on, used, never. (Tools you used are not tools you operated.)
3. What you want in plain words: your field; whether you are aiming at industry, academic or research,
   government, nonprofit work, or a mix; the titles you have seen; what is firmly out.
4. Where you live, where you could commute, whether you would move.
5. Your judgment, every run: Claude queues and drafts; you decide and you apply.
6. About 20 yes/no answers on real postings during setup, so the matcher learns your idea of "fit".
7. If government jobs interest you: one free USAJobs key (Claude explains how; two minutes on their
   website). Otherwise nothing: it is skipped.

## The first day
1. Install the Claude desktop app, put the folder in Documents, open it in the Code tab. The easy way: drop
   whatever documents you have (an old resume or CV, cover letters, essays, a thesis, papers, reports,
   performance reviews, certificates; Word, PDF, text) into `My Job Search/intake`, type `set me up`, and say
   `read my documents` when Claude offers it. Claude extracts the text (your files are never changed), drafts
   one evidence file per job and degree, a skills list and a publications list, each line marked as coming from
   which file, and then reads it all back to you: you confirm, correct, and answer only what the documents did
   not say (which tools you ran yourself versus only used, where each number comes from, anything you must not
   disclose, one story per job). No documents? `set me up` alone asks everything one question at a time.
2. Claude checks your computer and installs what it needs inside the folder (it asks before installing
   anything else, such as Python itself if your computer lacks it).
3. The interview starts: who you are, work status, location, your field and what you want, salary, then
   each job and degree, your skills, licenses and certifications, and (only if you are on an academic or
   research track) publications, teaching and references. Claude reads every sentence back before it counts.
   Stop whenever you like; `set me up` continues where you left off.
4. Near the end: the job-board packs and the employers you name, the optional keys, a first search, and 20
   postings for you to mark yes/no.
5. The first real run, with you watching: two independent judges score every new posting, Claude judges
   the list, builds documents for the good ones, and hands you a report with the employer's own link and
   the file to use. You apply on the employer's page.

## From then on
Type `run my job search` daily or weekly. Read the report. Apply to what you like, on the employer's page,
with the file Claude built. Tell Claude "I applied to <employer>" and tell it about every reply - "<employer>
rejected me", "<employer> wants an interview"; the search learns from them and `tracker.csv` shows where every
application stands.

## The program is locked, and changeable on request
After setup, everything under `system/` is read-only and checked against a fingerprint list; Claude's status
line says "Engine: original (v0.7)". Want it to behave differently? Say `modify: <what>`: Claude explains the
change in one paragraph, waits for your yes, makes it, records it, and locks the program again (the status then
says "MODIFIED - n files"). `show my modifications` lists every change in plain words; `revert to original` puts
the program back exactly as shipped. Your own folder is never touched by any of this.

## The rules, in plain words
- Nothing on your resume that you did not confirm. Every line traces to a fact you gave; an audit checks every
  built document and a document that fails is not shown to you as finished.
- Your work status is printed exactly as you wrote it, and postings are dropped for citizenship, clearance,
  export control or sponsorship only according to what you said. Nothing is assumed.
- Tools you used are not tools you operated; the wording stays honest.
- Gaps stay yours: Claude tells you honestly where you fall short of a posting; it never writes a weakness
  into a document and never papers over one.
- Nothing is sent, submitted or posted by the tool. Drafts only; you click. Links are the employer's own,
  never a job aggregator's.
- Your data is never deleted. Decisions are recorded, not erased. Files you put in `intake` are read, never
  changed, moved or deleted, and never leave your computer.
- Titles never decide fit. A posting is judged on its text and by two blind judges.
- A claim that once turned out to be overstated is retired for good.
- Your email is never read. (A read-only mail check exists and stays off.)
- Listing sites that restrict automated access (LinkedIn, Indeed) are not read unless you turn them on
  yourself; the defaults are employers' own boards and an official free API (Adzuna).

## If you are an academic (PhD applicant, research staff)
Say so in the interview. You get a 2-3 page academic CV instead of a one-page resume (education with thesis
and advisor, publications, presentations, field or lab experience, certifications, technical skills, teaching,
grants, service, references), statements of purpose / research statements / academic cover letters built
from your approved sentences, PhD positions and fixed-term research posts in scope, and academic job boards
and listserv archives read as public pages (never subscribed to or posted to). `system/examples/marina_example/`
shows all of it filled for a made-up marine biologist.

## If something looks wrong
Tell Claude what you see. It fixes technical problems itself; if it cannot, it says in one sentence what is
blocked and what it needs. The technical manual is `system/docs/DEVELOPER.md`.
