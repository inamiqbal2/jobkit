# jobkit v0.4 - pre-ship audit (2026-10-11)

Method: fresh clone -> `system/release.sh` -> unzipped the real zip twice (`/tmp/jobkit_ship/jobkit` and `/tmp/O'Brien Docs/jobkit`,
spaces + apostrophe). Read every doc, skill, charter, template and all 32 tools. Ran `setup.py` from nothing, then acted as Claude for a
fictional person (Priya Nandakumar, high-school chemistry teacher in Columbus OH) with a 2-page resume .docx, an essay .pdf, a scanned
PDF and an .rtf in `intake/`: intake, phases 1-8 in confirmation mode, phases 9-17 filled in the jordan shape, employer discovery,
a live `daily.py` (Adzuna/LinkedIn/Indeed off, packs education_general + nonprofit_social), two blind Sonnet scorers, merge, one real
build (Achievement First chemistry teacher), the tracker commands, modify/show/revert, and the break tests. Raw logs: `/tmp/jobkit_audit_logs/`.
macOS 24 / Python 3.13 / LibreOffice present. Windows was reviewed by reading and by simulating cp1252 encoding.

## 1. Verdict
Ship after fixes. The shape is right: setup is one command and took 17 s, intake reads real documents sensibly, the locked engine with
modify/show/revert works exactly as documented, and the build chain refused nothing it should have accepted. Three things must be fixed
first because they silently give wrong results or block a platform: (a) `urlcanon` drops `gh_jid`, so every Greenhouse job embedded on
an employer's own site shares one ledger key (62 of 520 corpus postings here) and one decision hides all of them; (b) the one-page resume
audit does not check that bullets come from `approved_claims.yaml` - an invented bullet passed; (c) Windows will crash on the first
`print("═")` or JD write because 36 file writes and the console output have no encoding. Everything else is fixable in days, not weeks.

## 2. Bugs, ranked
**BLOCKS A NEW USER**
1. **Windows: UnicodeEncodeError on the first run.** `daily.py` prints box-drawing characters; `rubric.py`, `screen_minquals.py`,
   `feeds.py`, `decide.py`, `state.py` write files with `open(..., "w")` and no `encoding=` (36 such writes). Simulated with
   `PYTHONIOENCODING=cp1252`: `print("═"*20 ...)` -> crash; writing the rubric prompt ("══"), a queue line ("⚠ITAR") or a typical JD
   ("→", "≥") under cp1252 -> crash. On Windows (Python 3.11-3.14, stdout redirected to `daily_run.log` as the skill says) the pipeline
   dies at step 0 and the screen thread dies on the first non-cp1252 JD. Fix: add `encoding="utf-8"` to every text `open()`, put
   `os.environ.setdefault("PYTHONUTF8","1")` + `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at the top of `daily.py`,
   `rubric.py`, `watch.py`, `critic.py`; or replace the decorative glyphs with ASCII.
2. **`python3` does not exist on most Windows machines** (`py -3` / `python`). CLAUDE.md, both skills and setup.py's own hints say
   `python3`. Claude will probably recover, but the first command the person sees fail is the setup. Fix: say "`python3` on macOS/Linux,
   `py -3` on Windows" in CLAUDE.md and the onboarding skill; let setup.py print the right interpreter path for the OS.
3. **No validation of settings.yaml.** `build_default_min_rubric: "sixty"` makes `critic.py`, `match.py` and `daily.py` die with a
   traceback (`int()` in `userconfig.thresholds`). `window_days: -5` silently yields zero candidates; `relocation: "maybe"` passes;
   `country: "FR"` only warns. `setup.py --quick` does not catch any of this because its self-check never calls `thresholds()`.
   Fix: a `userconfig.validate()` (types, ranges, enums, lanes non-empty, packs exist) run by `setup.py` and printed as one plain line.

**WRONG RESULT**
4. **`urlcanon.canon` strips `gh_jid`, collapsing employer-site Greenhouse embeds to one key.** All 62 Achievement First postings ->
   `https://www.achievementfirst.org/careers/career-opportunities-apply-teaching-roles`; same for KIPP-style `?gh_jid=` links. After my one
   `decide.py BUILT`, the other 61 are "judged" forever (`daily.py` excludes judged canonical URLs), the mirror dedupe treats them as one job,
   and `state.py applied` writes the canonical (jobless) link into `tracker.csv` as the "Official link" (confirmed: the tracker row lost
   `?gh_jid=5735741004` after "I applied"). Fix: keep `gh_jid` (it identifies the job when the host is not greenhouse.io); better, canonicalize
   employer-site embeds to `https://job-boards.greenhouse.io/<board>/jobs/<id>` when the board slug is known, and store `raw_url` in the tracker.
5. **An invented bullet passes the resume audit.** `audit_claims.py` checks forbidden/operator/retired terms, frozen entries, the work-auth
   line and banned words - traceability to `approved_claims.yaml` runs only in CV mode (`_is_cv`). A build script with
   "Led a cross-functional team of 12 engineers to deliver a $4M capital project" and a paraphrase of the *pending* claim ("Reduced solvent
   use 40%") -> `AUDIT CLEAN`, `PASS 1/1 clean`. The same text saved as `CV_*.docx` -> FAIL (2 untraceable lines). The only guard on resumes
   is the skill's sentence "never type a sentence the YAML does not approve". Fix: run `_cv_traceability` on every document (allow the
   `"<role noun>: <summary>"` prefix it already allows), and add `pending[].claim` to the retired-pattern check.
6. **No-network run reports "nothing new".** With every request refused, `daily.py` exits 0: "corpus: 0 full-text postings from 52 boards",
   0 candidates, "tripwire OK". The daily skill then tells the person "Nothing new passed the fit gate today". Fix: a connectivity probe in
   `setup.py --quick` / `daily.py` step 0 (one HEAD to boards-api.greenhouse.io) that exits non-zero with "no internet connection".
7. **Employer discovery registers wrong watch pages.** "Columbus City Schools" -> `https://www.columbusstate.edu/careers` (a Georgia university),
   "Dublin City Schools" -> `https://www.visitdublin.com/careers` (Irish tourism). `_same_org` strips "city"/"schools" as place words and
   accepts any host containing "columbus"/"dublin". The Greenhouse namesake guard worked ("Dublin Veterinary Hospital" rejected); the watch
   fallback has no guard. The person is told "I will watch their careers page by hand each run (https://www.visitdublin.com/careers)".
   Fix: for the MANUAL fallback require the page title to pass `title_matches`, else register with `slug: ""` and ask for the link.
8. **Repeated "I applied to X" creates a duplicate application row; outcomes land on the duplicate.** `state.applied` only updates a row whose
   `Date Applied` is empty, so the second call adds row 3; "Denver rejected me" then marks row 3 rejected while row 2 stays
   "applied - waiting". tracker.csv showed Denver Health twice with two statuses. Fix: if an open row has the same Job Link or
   Company+Position, update it (or refuse with "already recorded on <date>").
9. **Ambiguous employer names resolve silently.** `state.applied "Denver"` picked Denver Water (last folder alphabetically) with two Denver
   folders present; `outcome "Denver"` picked the most recent row. `consistency.py` treats "Denver Water" as a prior application to
   "Denver Health" (6-character prefix test). Fix: when more than one folder/row matches, print the candidates and exit 2 so Claude asks.
10. **Fresh install silently assembles the semiconductor pack and loads fake claims.** The shipped `settings.yaml.example` is a chemical
    engineer with `packs: ["materials_semiconductor"]` and `approved_claims.yaml.example` holds 5 bullets ("Scaled a two-step synthesis
    from 5 L to 500 L"). First `setup.py` on a teacher's machine: "Assembling the job-board lists from the selected packs... watch list
    snapshot taken" (fetched two semiconductor companies' boards), "Approved claims load: 5 approved bullets". If Claude ever appends
    instead of rewriting in phase 13, Jane's bullets reach a resume and the audit (bug 5) will not notice. Fix: ship the templates with
    `packs: []`, `experience: []`, name "FILL-IN", and make `setup.py` refuse to assemble while `identity.name` is the placeholder.
11. **Priority-lane patterns admit the whole school.** With `weak: ["\\bteacher\\b"]` and `anchor: ["\\bhigh school"]` (the shape the
    skill prescribes: "generic title words that count only with an anchor word in the JD text"), 49 of 78 queue items were ★LANE,
    including "High School Visual Arts Teacher", English, Math and History teachers - all exempt from auto-skip, all hand-judged. The
    marina example had the same problem (20 of 26). Fix: require the anchor within N characters of the weak word, or make phase 17 test
    the patterns on the first corpus and report "N of M titles would be priority" before accepting them.
12. **`critic.py` negation window is 130 characters.** "No security clearance required. Pay $22/hour. Requirements: HS diploma." ->
    "NO RED FLAGS": the "No" 60 characters earlier suppressed the BELOW LEVEL match. The screen uses 22 characters for the same reason.

**COSMETIC / HYGIENE**
13. `system/release.sh` ships inside the zip and contains the owner's personal token list (`TOKENS='<the owner's name, phone and employer tokens>'`) -
    the grep that keeps personal data out of the release is itself the leak. Exclude `release.sh` from the zip or move the tokens to an
    untracked file. `state.py` lines 28-30 still narrate the original user's lane drift ("his AI-for-materials work").
14. The materials pack's watch entries print "Bruker: see coverage/majors_probe.md" (a file that does not exist in jobkit).
15. `keywords.py` says "lexicon: generic fallback (profile/lexicon.yaml missing)" when the file exists but is the all-comment template.
16. `audit_claims.py` prints paths with `split("/")` (Windows shows the full backslash path); `state.py` opens csv files without
    `encoding="utf-8"` (cp1252 crash on "Mondelēz"-type names).
17. `verify_resume.jd_terms` is crude: on the AF posting it asked for "ll create", "ambitious goals.&nbsp", "achievement first invites"
    (2/28 "coverage"). `keywords.py` (the lexicon pass) is the one that matters; the verify line should be dropped or labelled advisory.
18. Jordan's `build.py` comment says `JOBKIT` but the path resolves to `system/`; harmless, confusing.
19. `discover_boards` wording: "found their ADP WorkforceNow job site at ADP, 2 openings" (host missing for ADP).

## 3. Honesty architecture
- **Can an unconfirmed fact reach a resume?** Yes, through the build script (bug 5): the resume-mode audit is a blacklist, not a whitelist.
  Cover letters and statements are prose and are only blacklist-checked (forbidden/operator/retired) - that part works: a letter with
  "Six Sigma Black Belt who led a team of 8, I ran NMR analyses daily" failed on all three. `pending` claims are not blacklisted, so a
  paraphrase of a pending claim passes everywhere.
- **Can the build skill bypass the audit?** The skill runs it and says a failing document is not a document; nothing mechanical enforces
  that `decide.py BUILT` follows a PASS. A one-line guard in `decide.py` (refuse BUILT unless `audit_claims.check()` passes on every
  .docx in the folder) would close it.
- **Are never-claims enforced in letters/statements?** Terms yes (word-bounded), operator patterns yes, retired regexes yes; the
  work-auth line is correctly not required there. The `[CLAIM: ...]` markers in the templates are convention only.
- **Work authorization:** printed verbatim, required on resumes, used as the only eligibility source; the negation and PR-admits guards
  behaved on the test JDs. **Official links:** every tracker row carried the employer's link except where bug 4 truncated it.
- **Blind judges:** the prompt file names only `profile_blind.md` and JD paths; no scores or critic lines leak. The subagent I spawned
  could in principle read anything on disk - the isolation is by instruction, not by sandbox; acceptable, say so in DEVELOPER.md.
- **Phase 13 says "approved_claims.py must load with 0 errors"** but the loader validates nothing (no schema, no check that `evidence:`
  files exist or are CONFIRMED). A `validate()` here is the single highest-value honesty addition after bug 5.
- **Templates ship real-looking fake facts** (bug 10) that live in the person's folder from minute one.

## 4. Usability (what the person would actually see)
Good: "I read 2 of your 4 files: your 2024 resume and your teaching-philosophy essay. The scanned license has no readable text - a photo
or a Word version would let me read it - and old_cover_letter.rtf is a format I cannot open." (intake output supports exactly this).
Good: the read-backs in phases 2-4 and 13 are concrete and plain; the "48% to 65% vs 'boosting AP pass rates by 35%' - which is right and
where does it come from?" question is the kind of thing that makes the tool trustworthy.
Bad or risky lines:
- "I will watch their careers page by hand each run (https://www.visitdublin.com/careers)." - wrong site, said confidently (bug 7).
- "Nothing new passed the fit gate today." - said when the internet was down (bug 6). Also "fit gate" is jargon the skill tells Claude to use.
- Phase 5 script: "Which one of these must I never skip, even when a score looks low?" and "The lane I will never skip" - "lane" is
  internal vocabulary; say "kind of job".
- Phase 18: "I will now search for real postings for the first time. It takes 10-40 minutes" - here it took 2 minutes with two packs; with
  the government pack (44 NEOGOV portals x 4 terms) it will be far longer. Say "between a few minutes and an hour, depending on the boards".
- README says 15 minutes to get started "then a long conversation"; the honest number for `read my documents` + confirmation was ~2 hours
  of questions for a 2-page resume (3 jobs x 4 unanswered questions + 34 skill tags + ~20 bullets read back one by one).
- The status table and the daily log are full of "TRIPWIRE ... JUDGMENT DEFECT", "🛑 HOLD", "AUTO-SKIP", "NOISE" - fine for Claude, but
  Claude Code shows tool output in the transcript, so the person will see them scroll past. Consider `--quiet` modes that print one line.
- `tracker.csv` Outcome column shows "2026-10-11 rejection UNKNOWN" - "UNKNOWN" (the reject type) is jargon in the one file they open.
- Three unsupported intake formats people actually have: `.doc`, `.pages`, `.rtf` (and `.odt`). LibreOffice, when present, converts all of
  them (`soffice --convert-to docx`); intake.py could do that automatically.
- "where am I?" works from the four files, but there is no `status.py`; Claude re-derives it every time (fine, slow).

## 5. Efficiency (measured)
- `setup.py` from nothing: 17 s warm pip cache (cold: 1-5 min). Venv rebuild after deletion: 17 s. Intake of 4 files: <1 s.
- `discover_boards.py` for 3 employers: 30 s; "add employer Battelle": 8 s (found the Phenom site, 179 openings).
- `daily.py`: **1 min 58 s** on this workspace (520 corpus postings, 281 scored, 964 feed listings, 883 screened in one pass, 78 passed
  the gate, 6 fetch failures). The marina run was 25 min with 1,985 listings and Indeed on. The screen is the slow step: ~10 items/s with
  14 threads, so 5,000 candidates = ~8 min; the 7-day noise cache makes the second run much cheaper.
- Blind scorers: batch of 78 JDs = 682 KB of JD text + 8 KB prompt + 3 KB profile = **~173k input tokens per scorer** (chars/4; the Opus
  4.7+ tokenizer may be 10% more), ~3.5k output each. Measured: the harness billed **~306k tokens per Sonnet scorer** (82 file reads each; context re-sent per
  read, mostly cache hits), **1.5-2 min wall each, run in parallel**; both agreed within a median 1 point (no Δ>=15).
- Judgment pass (Claude in the session): reads the queue and, per the skill, every JD it decides on (here 78 x ~9 KB = another ~170k
  tokens over many tool calls, mostly cache reads), plus build/verify/audit tool calls (~10 per build).
- Cost at list API prices (Sonnet 5.5 $2/$10 per MTok; Opus 5.5 $4/$20, cache read $0.20; Fable 5.1 $10/$50, cache read $0.25):
  scorers on Sonnet ~$0.75/run, on Opus ~$1.5, on Fable (the daily skill says "Fable where available") ~$3.8. Session judgment+builds on
  Opus 5.5 ~$2-4/run (≈6M cached-read tokens across ~60 turns + ~150k fresh input + ~15k output); on Fable ~$3.5-6. **Per run: $3-5 on
  Opus, $7-10 on Fable; daily use ≈ $90-150/month on Opus, $200-300 on Fable.** Most recipients will run it inside the Claude app on a
  subscription, where the same numbers show up as usage-limit consumption: a 78-item run is a large fraction of a day's allowance.
- Biggest savings, in order: (1) do not send JDs the deterministic gate already ranked below ~0.30 to both judges - score the top 40 and
  let the rest wait a day; (2) cap JD text at 6 KB for the judges (requirements block + first 3 KB); (3) one judge at low effort for items
  the matcher scored < 0.35 and two only above; (4) `prompt_<date>.txt` + profile as a cached prefix for both judges.

## 6. Cross-platform risks (by reading; not run)
- Encoding (bug 1) is the blocker. Also `print()` of emoji in `watch.py`, `critic.py`, `rubric.py`.
- `python3` naming (bug 2). The venv path switch (`Scripts\python.exe`) is correct everywhere I checked.
- **No `.gitattributes`.** With Git for Windows' default `core.autocrlf=true`, "revert to original" (`git checkout original-v0.4 -- system/engine`)
  writes CRLF files, so `MANIFEST.sha256` no longer matches and the status says "MODIFIED - 57 files" right after a revert. Ship
  `* text eol=lf` (or `-text`) in `.gitattributes`, and have `manifest.py` hash with `\r\n` normalized.
- `manifest.lock()` on Windows sets `attrib +R` on files only (folders cannot be made read-only), so new files can still be dropped into
  `system/engine`; the manifest will report them as "added". Acceptable; document it.
- LibreOffice detection covers PATH, `/Applications`, `~/Applications`, both Program Files; `pdftoppm` must be on PATH on Windows (the hint
  says so). Fine.
- `release.sh` is bash+zip+git (macOS/Linux only) - fine, it is the owner's tool, but it ships (bug 13).
- Paths with spaces and an apostrophe: setup, venv `.pth`, tools and tracker all worked under `/tmp/O'Brien Docs/jobkit`.
- Workday/Oracle/NEOGOV endpoints and Bing scraping are the same on every OS; nothing platform-specific there.

## 7. Improvement ideas, ranked by value/effort
1. **Whitelist audit for every document** (bug 5) + `decide.py BUILT` gated on audit PASS. Half a day. Closes the honesty hole.
2. **`validate()` for settings.yaml / approved_claims.yaml** with plain-English messages, run by `setup.py --quick`. Half a day.
3. **Gap-driven profile deepening loop.** `keywords.py` already classifies JD terms as ASK; `rubric` sub-scores already say "skills low".
   Keep a `tracking/gaps.jsonl` of (term, times requested, times it cost a build); when a term is REQUIRED in >= 3 postings in 14 days,
   the daily report ends with one question: "Six postings this week required 'IB experience'. Have you taught IB, or should I keep
   treating it as a gap?" - answer updates lexicon/inventory/never-claims through the normal read-back. One day; this is what makes the
   profile converge instead of staying at the interview's resolution.
4. **Federal resume for USAJobs.** USAJobs expects multi-page, hours-per-week, supervisor name/phone, salary, series/grade - the opposite
   of the one-page resume. Add `build.format: federal` -> `resume_builder.FederalResume` (same approved claims, extra per-entry fields
   `hours_per_week`, `supervisor`, `may_contact`, `salary`, GS-series line), `verify_resume` page range 3-5, and a phase-7 question set
   that only fires when government is in the track. Two days. Without it the government pack is half useful.
5. **Weekly digest mode** (`run.cadence: weekly` or "run my weekly search"): window 7 days, one combined report, judges only the top 40,
   builds nothing until the person picks ("build 2 and 5"). Cuts cost ~70% for people who apply a few times a week. One day.
6. **Interview prep from the built profile.** `charters/interview.md` exists but nothing fills it. "`<employer> wants an interview`" should
   offer, and a `prep.py` scaffold should write `InterviewPrep_<Co>.md` from evidence stories (every evidence file already has "Interview
   stories"), the JD's required block, the never-claims (honest answers for gaps), and the salary band. One day; high perceived value.
7. **Connectivity + health probe** (bug 6) and a `status.py` that prints the five "where am I?" lines. Hours.
8. **Priority-lane proximity rule** (bug 11) and a phase-17 dry test ("N of M titles would be priority"). Hours.
9. **Intake conversion via LibreOffice** for .doc/.rtf/.pages/.odt, and OCR hint for scans. Hours.
10. **Quieter tool output** (`--quiet` on setup/daily/critic) so the transcript is not a wall of glyphs. Hours.
11. **Per-employer link canonicalization** (bug 4) with a unit test over the packs' `absolute_url` forms. Hours.
12. **Cost control knobs** in settings: `judges.max_items`, `judges.max_jd_chars`, `judges.model`. Hours.
13. **Two-sided calibration report** after phase 18: "with these words, 12 of your 20 yes-postings pass and 2 of 20 no-postings pass" as a
    table the person sees (the skill describes it; no tool computes it).
14. Longer term: a referral/outreach draft per build (charter exists, off by default), and a "what changed since last run" diff of the
    watch list in the report.

## 8. Before shipping vs later
**Fix before shipping:** bugs 1-7 (encoding, `python3`, validation, `gh_jid`, resume whitelist audit, no-network message, watch-page
namesake), bug 10 (placeholder templates), bug 13 (tokens in release.sh), `.gitattributes`, and the four stale documents: CONSTITUTION.md
(`user.yaml`, `charters/user-rules.md`, `tracking/jobs.csv`, `tools/x.py` paths), `charters/data.md` ("jobs.csv is what the user reads"),
the `step N` numbers in the three `.example` files (phases are now 8/17/18), and the `tools/critic.py` hint written into every queue file.
**Later:** bugs 8-9, 11-12, 14-19; ideas 3-14.

Appendix - what was verified working: setup idempotent (second "set me up" after phases 1-3: nothing overwritten, resumed at phase 4);
venv deleted -> `--quick` rebuilt it; engine lock refuses writes and Python runs without `__pycache__`; modify -> "MODIFIED - 1 file",
show -> commit list + diffstat, revert -> "original (v0.4)" (a second revert says "nothing to commit", exit 1 - harmless, Claude should
say "already original"); scan PDF reported as empty with the right hint; RTF listed as unsupported; aggregator links (Indeed/LinkedIn/
Adzuna) fail cleanly in `fetch()` so the build skill's "find the employer's posting" rule applies; path with spaces + apostrophe fine;
`I applied` / `wants an interview` / `rejected` update tracker.csv and OUTCOMES_LOG correctly for an unambiguous employer; build chain
(critic, entry scorer, build, verify 1 page 91%, keywords, audit PASS, consistency) on a real posting in 2 s; `report.py`/`timeline.py`
run on a near-empty db; `rubric.py merge` averaged 78 items (1 at 60: an organic-chemistry instructor at Columbus State CC, in
Columbus; 77 under 40, nearly all for location), auto-ledgered 27, withheld one thin JD, and 72 `decide.py` calls took 2.0 s in total.

Findings from the merge step (add to section 2, cosmetic unless noted):
20. **(wrong result, small)** 50 of the 51 items left for hand judgment were under 25/100 but could not auto-skip because the priority
    lane exempts them (bug 11 again); the person's Claude session will spend most of its tokens re-reading sub-25 postings.
21. RSS links are not HTML-unescaped: Chronicle/Inside Higher Ed URLs carry `&amp;utm_source=rss` into the queue, ledger and tracker;
    `urlcanon` then keeps `amp;utm_source` as a real parameter. One `html.unescape` in `feeds.rss()`.
22. Feed-arm items reach `tracker.csv` with the feed as the employer ("Chronicle of Higher Education Jobs" in the Employer column, the
    employer inside the Role column) and an aggregator link as the "Official link" - the constitution's Article I.6 is not enforced for
    WATCH rows; the daily skill should make Claude find the employer's own page before `decide.py WATCH`.
23. `rubric.py` writes raw URLs into the ledger while `decide.py` writes canonical ones; `daily.py` canonicalizes on read so it works,
    but `tracker.csv` and `decide.py --list` show both forms.
24. The person-facing report I wrote from the skill's template reads well (40 lines, `/tmp/jobkit_audit_logs/report_priya.md`); the one
    thing the template lacks is a line for "what I could not read" (6 fetch failures, two hand-check employers with bad URLs).
