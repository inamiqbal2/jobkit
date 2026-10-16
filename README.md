# jobkit

![jobkit in about a minute: set me up, drop in your documents, an in-depth interview, it reads every posting on employers' own boards, two blind judges score the fit, and your story is told for the job](system/docs/jobkit_demo.gif)

<sub>Fictional user ("Riley", a model-risk analyst in New York); the scores and counts shown come from a live jobkit run
in October 2026.</sub>

**Your story, told for the job you want.** Most resume tools match keywords against one resume you upload. jobkit
reads everything you have (old resumes, papers, transcripts, project reports), interviews you in depth, then reads every posting on the
employer's own job board, has two blind judges decide which ones are worth your time, and builds each resume to lead
with what that job needs, from your real experience, in words you confirmed. Your best self for the job you want,
never a made-up line.

It runs inside the Claude desktop app. You talk to it in plain English; no programming, ever. It works for
any field: nursing, software, field biology, teaching, sales, city planning.

## Why job searching broke

- **Applying got easy, so everyone applies to everything.** Applications per hire went from about 100 in
  2021 to 319 in 2024, and the share of applications that reach an interview fell from 7-8% to under 5%.[^1]
  Nearly half of job seekers say they "spray and pray" regularly, and three in four would apply more
  selectively if they had a signal for where to aim.[^2]
- **Stretched resumes get caught.** 65% of hiring managers say they have caught applicants using AI
  deceptively.[^3] A resume that beats the filter but not the interview costs everyone time, yours most.
- **Listings are not all what they seem.** About one listing in five is a "ghost job" that is not really
  being filled.[^4]
- **Fit and tailoring are what still work.** Resumes tailored to the posting convert to responses about 1.6
  times as often as generic ones.[^5] Yet only about one job seeker in four tailors their resume for every job, and
  68% spend under 30 minutes when they do.[^6]

Tools that help you send more applications, or stretch your resume past the keyword filter, feed the same
loop: more noise, lower odds, harder interviews. jobkit is built for the other direction.

## What jobkit does differently

**1. It learns you before it searches.** Setup is a real conversation, two to four hours in as many sittings
as you like (shorter if you drop in your old resumes and papers; it reads them and reads everything back to
you). For every job you have held it asks what you did yourself versus only used, which numbers you can
defend and where they come from, and one story you would tell in an interview. Every skill is tagged
hands-on, used, or never. Then it shows you about 20 real postings and learns from your honest yes or no.

**2. It matches on what the job asks, not what it is called.** Titles mislead: the same work hides under a
dozen names, and the same title means different work at different employers. jobkit reads the full text of
every posting against your profile and ignores the title, except to drop roles you are not eligible for.

**3. Two blind judges decide whether it is worth your time.** The best-matching postings are each scored
twice, separately, by judges that see only your profile and the posting, nothing else. Skills,
experience level, location and whether the role would use your real strengths all count. The two scores are
averaged; when they disagree, the posting gets a closer look.

**4. It tells you what to skip, and why.** A job that needs a license you do not hold, a clearance you
cannot get, or experience you never had is set aside with the reason in one plain line. Jobs above your line
get documents built for you, with an honest read of the fit and the gaps. Your hours go where an interview is
realistic.

**5. It goes to the employers' own job boards.** Out of the box: 265 company boards on Greenhouse, Lever,
Ashby, SmartRecruiters and Workable; 79 Workday career sites; 40 large-employer systems (Oracle, SAP,
iCIMS, Phenom and others); and 47 government job portals, in 14 field packs you pick from. Name any employer
and jobkit finds its board and adds it to your search. Every link it gives you is the employer's own posting.

**6. Your real experience, in the posting's terms. Never invented.** For each posting jobkit picks and
orders your most relevant confirmed experience and checks the posting's keywords against your skills: what
you have is used, what you have never done is shown to you as a gap and never added. Every resume line must
match a statement you approved, word for word, or the program refuses the document. No keyword stuffing, no
hidden text, no numbers without a source.

**7. It becomes your own tool.** Add rules in plain words ("never show me night-shift jobs", "always flag
relocation"). The program itself is locked and fingerprinted so nothing changes it by accident; ask for a
change with `modify:` and it explains, waits for your yes, records it, and can undo it with `revert to
original`.

**And it never** applies for you, sends anything, or reads your email. You decide, and you apply.

## What you need
The [Claude desktop app](https://claude.ai/download) and a Claude subscription; jobkit runs on it, and each
search run uses part of your usage. jobkit itself is free and open source (MIT).

**Status: early.** Its first users are trying it now, so there are no outcome numbers yet; real ones will go
here when there are. Built and tested on macOS; Windows and Linux are supported but not yet tried by a real
user. Problems and ideas: open an issue.

## Get it
Go to **Releases** (right side of this page), download `jobkit.zip` from the newest release, unzip it, and
follow **Getting started** below. Use the release zip rather than the green "Code" button: the release copy
includes the program history that `modify:` and `revert to original` need.

[^1]: Ashby, *Talent Trends Report*, April 2026 (109 million applications).
[^2]: Monster, *Job Application Behavior Report*, March 2026 (1,006 US job seekers).
[^3]: Greenhouse, *AI in Hiring Report*, November 2025, as reported by Fortune, Nov 18 2025.
[^4]: Greenhouse CEO Daniel Chait, interview with Fortune, Apr 9 2025.
[^5]: Huntr, *2025 Annual Job Search Trends Report* (1.78 million applications): 5.8% vs 3.73%.
[^6]: Novoresume, *Resume Report 2026*, May 2026 (survey of 2,000 US adults).

---

## What is in the folder
```
README.md         this page
CLAUDE.md         instructions for Claude (you can read it; you never need to)
My Job Search/    YOUR area - the only folder you ever open
   intake/        drop your old resumes, CVs, letters, essays, papers, reports, reviews here
   applications/  the documents Claude builds, one folder per posting
   reports/       one plain report per run
   tracker.csv    every posting Claude built for or you applied to: employer, role, status, outcome, link
   profile/, my-rules.md, settings.yaml, keys.json, tracking/   Claude fills these for you
system/           the program. Locked: you can ask for changes and undo them (see below)
```

## Getting started (about 15 minutes, then a long conversation)

1. **Install the Claude desktop app** from https://claude.ai/download and sign in.
2. **Put the jobkit folder somewhere permanent.** If it came as a zip, unzip it and move the `jobkit`
   folder to your Documents (not Downloads, which gets cleaned out).
3. **Open the folder in the app.** In the Claude app, go to the **Code** tab and open the `jobkit` folder.
4. **The easy way to start: drop your documents in.** Put any old resume or CV, cover letters, essays, your
   thesis, papers, reports, performance reviews or certificates into `My Job Search/intake` (Word, PDF, text or
   Markdown). Then type **`set me up`** and, when Claude offers it, **`read my documents`**. Claude reads them,
   drafts your profile from them, and reads every item back to you; you confirm, correct, and fill the gaps
   (which tools you ran yourself versus only used, where a number comes from, a story per job). Nothing from
   a document goes on a resume until you have said yes to it. No documents? Type `set me up` and answer the
   questions one at a time instead.
5. **Later, type `run my job search`** whenever you like. Claude checks the boards, judges every new
   posting, builds documents for the good ones, and gives you a short report with links and file names.
   You apply on the employer's own page and tell Claude **`I applied to <employer>`**. When you hear back, tell
   it **`<employer> rejected me`** or **`<employer> wants an interview`**; `My Job Search/tracker.csv` (open it
   with Excel or Numbers) always shows where everything stands.

Three more things you can type: **`build my documents for <link>`** for a posting you found yourself,
**`add employer <name>`** to have Claude find and watch a company's job board, and **`where am I?`** for a status.

## What it will ask you for
- Your name, email, phone, city, and the links you want printed (LinkedIn, a portfolio, ORCID, GitHub).
- Your work authorization in plain terms (citizen? permanent resident? need a visa?).
- Where you live, where you could commute, whether you would move.
- Your field and track: industry, academic or research, government, nonprofit, or a mix. What you are
  looking for in your own words, the titles you have seen, and what you never want to see.
- The lowest salary you would accept and what you are aiming for.
- Each job, degree and project you have done: where, when, title, what you actually did, which tools,
  methods, systems or equipment you personally used, numbers you can defend. Facts, not polished sentences;
  Claude writes the sentences and you approve each one. (With documents in `intake`, most of this is read back
  to you instead of asked.)
- Your skills with an honest tag: hands-on, used, or never.
- Licenses and certifications that matter in your field (an RN license, PE, PMP, AWS, CPA, a teaching
  license, a scientific-diving card: whatever applies to you), and any you do not hold that people might assume.
- Only if you are on an academic or research track: publications, thesis and advisor, teaching, references.
- Your own rules ("never show me jobs in Alaska", "always tell me if a job needs night shifts").
- Which job-board packs to search (healthcare, tech, government, nonprofit, education, business, and more)
  and up to ten employers you would love to work for; Claude finds their job boards itself.
- Only if government jobs interest you: one free key from USAJobs.gov. That is the only thing you do on a
  website yourself; Claude walks you through it and you paste the key into the chat. Otherwise it is skipped
  and you can add it later.
- About 20 yes/no answers on real postings, so the matcher learns what "fit" means for you.

Budget two to four hours for the whole setup from scratch (less with documents in `intake`), in as many
sittings as you like.

## The program is locked; you can ask for changes and undo them
Everything under `system/` is the program. After setup it is read-only on your disk and checked against a
list of fingerprints, so nothing changes it by accident; the status Claude prints says "Engine: original
(v0.6)". If you want it to behave differently ("stop showing me night-shift jobs in the report", "put the
summary before the skills"), say **`modify: <what you want>`**. Claude explains in one paragraph what it would
change, waits for your yes, makes the change, records it, and locks the program again; the status then says
"Engine: MODIFIED - 2 files". **`show my modifications`** lists every change in plain words, and **`revert to
original`** puts the program back exactly as shipped. Your own folder, `My Job Search`, is never touched by any
of this.

## What it will never do
- Submit an application, send an email, post anything, or fill in a form on a website.
- Read your email.
- Put anything on your resume that you did not confirm. Every line traces back to a fact you gave.
- Guess your work status, your skills, or a number.
- Delete anything you told it, or change, move or delete a file you put in `intake`. Decisions are recorded, never erased.
- Install anything on your computer outside the jobkit folder without asking you first.
- Spend money without asking.
- Scrape sites you did not opt in to. The LinkedIn and Indeed listing feeds are off unless you turn them on
  and accept that those sites restrict automated access; Adzuna (an official, free API) and the employers'
  own job boards are the defaults.

## If something goes wrong
Tell Claude what you see. Its rule is to fix technical problems itself and, if it cannot, to tell you in
one plain sentence what is blocked and what it needs from you.

## For the technically curious
`system/docs/DEVELOPER.md` is the technical manual; `system/docs/ARCHITECTURE.md` explains every file;
`system/engine/CONSTITUTION.md` is the set of honesty rules the tool cannot break. `system/examples/` holds three
made-up people's filled folders (a registered nurse, a power-systems engineer, a marine biologist), each laid out
exactly like `My Job Search`, so you can see what the result looks like, plus a fourth made-up person's two main
settings files with every line explained. Your own folder starts empty: nothing is searched or written about you until
you have said it.
