# jobkit - developer manual (the technical side; the person using jobkit does not need this page)

jobkit is a job-search pipeline that runs on the user's own computer with Claude: it discovers postings from
employer job boards, screens them against the user's real profile, ranks them with two blind scorers, helps judge
them, and builds a tailored CV / resume per role from claims the user has confirmed - with an audit that refuses
anything they have not. Derived from a working personal pipeline (2026-08 to 2026-10, ~190 applications) and split
into a shareable **engine** (no personal fact, no field-specific rule) and a private **workspace** (every fact,
rule, term and threshold). v0.3 (2026-10-11) made the user-facing layer field-neutral: the interview asks field +
track and conditions the academic and government questions on it; six generic job-board packs (healthcare, tech,
government, nonprofit, education, business) ship live-verified; `discover_boards.py` finds any employer's board
from its name. v0.4 (2026-10-11) is the shipping layout for non-programmers: the top level holds only `README.md`,
`CLAUDE.md` and `My Job Search/` (the person's area, formerly `workspace/`); everything technical sits under `system/`.
It adds the intake folder (`intake.py` + "read my documents" with a confirmation-mode interview), the plain-English
`tracker.csv` regenerated after every state change, and the source lock (`MANIFEST.sha256` + read-only engine + the
`modify:` / `show my modifications` / `revert to original` commands on a `modified` git branch). The non-technical
surface is `CLAUDE.md` + the three skills; this page is what sits under it.

## Layout
```
README.md          for the person
CLAUDE.md          loaded by Claude Code when the folder is opened: the commands, the hard rules, where things are
My Job Search/     the person's data (git-ignored except templates): settings.yaml · keys.json · my-rules.md · profile/ ·
                   intake/ (their documents; _extracted/ is written by intake.py) · tracking/ · applications/ · reports/ ·
                   tracker.csv · ONBOARDING_STATUS.md   ($JOBKIT_WORKSPACE overrides the location)
system/
  engine/          CONSTITUTION.md (non-negotiable) · MANIFEST.sha256 (source lock; release-time) · charters/ (method) ·
                   tools/ (32 scripts incl. setup.py, intake.py, manifest.py, discover_boards.py) · registries/packs/ (13 packs) ·
                   skills/{onboarding,daily,build}/SKILL.md (what Claude follows). READ-ONLY on disk after setup.py.
  .venv/           created by setup.py (a .pth there makes engine/tools importable by any script run with that Python)
  jobkit.py        the launcher: `python3 system/jobkit.py <tool>` (macOS / Linux) or `py -3 system\jobkit.py <tool>` (Windows)
                   runs any tool with the jobkit python (system/.venv), creating it through setup.py when absent;
                   `<launcher> setup` is the first command on a new computer. Docs write `<launcher>` and `<jobkit python>`.
  requirements.txt, requirements-optional.txt
  examples/        jordan_example/ (registered nurse, one-page resume; live run 2026-10-11), taylor_example/ (power-systems
                   engineer), marina_example/ (marine biologist, academic CV + PhD targets) - complete FABRICATED copies of
                   "My Job Search" with the same inner layout (settings.yaml, my-rules.md, profile/, applications/, ...);
                   sam_example/ (fictional process engineer) = the annotated FILLED reference for settings.yaml and
                   approved_claims.yaml. The templates in My Job Search/ ship EMPTY (v0.5): placeholders, packs: [],
                   experience: [] - a fresh install assembles no board list and loads no bullet until the interview.
  docs/            ARCHITECTURE.md (engine/workspace contract, every schema) · HANDOFF_TO_NEW_USER.md (plain) · this file ·
                   REFACTOR_PLAN.md · EXAMPLES_FROM_ORIGINAL.md (a fictional user's rules) · REGRESSION_2026-10-08.md · UX_TEST_2026-10-09.md
  release.sh       builds the shippable zip (fresh clone, single commit, tag original-v0.8, manifest, token grep; the token list lives outside the repo)
```
The folder name `My Job Search` contains spaces on purpose (it is what a non-programmer expects to see); every tool
resolves it through `userconfig.WS` and every documented command quotes it.

## Setup by hand (what `system/engine/tools/setup.py` does for the user)
1. Python 3.11+ (tested on 3.13). Optional: LibreOffice + poppler for the page/fill checks
   (macOS `brew install --cask libreoffice && brew install poppler`; Debian `apt install libreoffice-writer poppler-utils`);
   without them `verify_resume.py` skips the page checks and says so.
2. `python3 -m venv system/.venv && system/.venv/bin/pip install -r system/requirements.txt` (Windows: `py -3 -m venv system\.venv`
   and `system\.venv\Scripts\pip`), then a
   `jobkit_engine.pth` in the venv's site-packages pointing at `system/engine/tools` (so `from resume_builder import Resume`
   works from any script run with that interpreter). `requirements-optional.txt` (python-jobspy for the Indeed arm) only
   when `settings.yaml run.indeed_jobspy: true`; `feeds.py` skips the arm when it is absent.
3. Workspace from the templates shipped in `My Job Search/` (every file documented inside): `settings.yaml.example`,
   `keys.json.example`, `profile/{signals,critic_rules,lexicon,approved_claims}.yaml.example`,
   `profile/{profile_blind,publications,skills-inventory}.TEMPLATE.md`, `my-rules.TEMPLATE.md`,
   `tracking/registries/queries.yaml.example` -> their live names; `custom.json` starts empty; `intake/README.md` is copied.
   `JOBKIT_WORKSPACE=/path` moves the workspace (every tool honors it). `tracking/` is created by the tools.
   A v0.3 workspace still works: `userconfig.py` falls back to `user.yaml`, `secrets.json` and `charters/user-rules.md`
   when the v0.4 names are absent.
4. `setup.py` is idempotent: `<launcher> setup` (full) / `--quick` (no installs unless missing). It creates
   `ONBOARDING_STATUS.md` with the 21 onboarding phases pending, initialises `tracking/state.db`, writes `tracker.csv`,
   reports LibreOffice / poppler / keys, runs the self-checks, checks `MANIFEST.sha256`, locks `system/engine` and prints
   a status table. `--unlock` / `--lock` toggle the lock; `--no-lock` skips it (development). Exit 1 only when Python is
   too old or the venv cannot be made.

## The source lock (v0.4)
- `system/engine/MANIFEST.sha256`: SHA-256 of every file under `system/engine/` (minus itself, `__pycache__`, OS litter),
  written by `manifest.py generate` (the release script runs it). `manifest.py check` / `status` compare the tree to it;
  setup.py prints `Engine: original (v0.8)` or `Engine: MODIFIED - N files (see 'show my modifications')`.
- `manifest.py lock` makes every file AND folder under `system/engine` read-only (`chmod a-w`; Windows `attrib +R` on
  files). Python keeps importing and running everything; it just stops writing `.pyc` caches there. `unlock` reverses it.
  Git needs the unlock before it can check files out into the folder, which is why the commands below unlock first.
  The same applies to deleting an install from a shell: `rm -rf` refuses read-only folders, so `setup.py --unlock`
  (or `chmod -R u+w system/engine`) first. Finder / Explorer move the folder to the trash as usual.
- Git: the release ships with `.git` initialised, one commit, tag `original-v0.8`. "modify: <what>" = explain, yes,
  `setup.py --unlock`, change, commit on branch `modified` (`MOD <date>: <what> - <why>`), `setup.py --lock`. The
  manifest is NOT regenerated after a modification: it stays the fingerprint of the original, which is what makes
  setup.py report `MODIFIED - N files`. "show my modifications" = `git log original-v0.8..modified` + `git diff --stat`.
  "revert to original" = unlock, `git rm -r -q system/engine` (so files a modification added go too), `git checkout
  original-v0.8 -- system/engine`, commit `REVERT to original-v0.8`, lock -> `Engine: original (v0.8)`. None of it
  touches `My Job Search/` (which is git-ignored apart from its templates anyway). `manifest.py generate` is for the
  release script only.

## Intake (v0.4): `system/engine/tools/intake.py`
Lists `My Job Search/intake/`, extracts text from .docx (python-docx, paragraphs + tables + headers), .pdf (pypdf), .txt and
.md into `intake/_extracted/<name>.txt` (re-extracted only when the source is newer; `--force` redoes all; `--list` only
lists), and writes `_extracted/INDEX.md` + `index.json` (file, type, size, words, status). Originals are never touched.
The onboarding skill's "Confirmation mode" then drafts `profile/evidence/<slug>.md` (Status: DRAFT, a `Source: intake/<file>`
line under every fact), a skills inventory with every tag `UNCONFIRMED`, and a draft publications list, and runs phases
2-13 as read-backs: for each drafted position only the unanswered questions of the eight are asked (operated vs used,
numbers with provenance, NDA, a story). Nothing from intake reaches `approved_claims.yaml` without the read-back.

## The tracker (v0.4): `My Job Search/tracker.csv`
`state.py tracker` writes it; `export_csv()` calls it after every `set` / `add` / `applied` / `outcome`, and `decide.py` calls
it after every BUILT / WATCH / REOPEN / APPLIED. Columns: Employer, Role, Location, Posted, Applied, Status, Outcome, Salary,
Fit, Official link, Documents folder, Notes. Rows = every `state.db` application (newest first; Status words: "applied -
waiting", "interviewing", "rejected", ...) followed by every BUILT ("built - not applied yet") and WATCH ("watching") ledger
item not yet applied to, with employer / role / location pulled from the built folder's `JobDescription.txt` header or the
day's screened list. `state.py applied "<employer>"` fills a new row from the built folder (Position, Job Link, Resume Used) or
stamps the open row; `state.py outcome "<employer>" rejected|interview ["note"]` sets Status, Rejection/Interview, Reject Type
(UNKNOWN until the person says why), Days to Resp, and appends to `tracking/OUTCOMES_LOG.md`. `jobs.csv` stays the full
generated view; `tracker.csv` is the plain one and is never read back.

## Self-checks
```
system/.venv/bin/python system/engine/tools/userconfig.py        # workspace, modules, lanes, build format, targets
system/.venv/bin/python system/engine/tools/registries.py list   # packs (* = selected); `assemble` writes the active registries
system/.venv/bin/python system/engine/tools/approved_claims.py   # loaded claims summary (bullets, frozen, pending, cv sections)
system/.venv/bin/python system/engine/tools/geo.py               # the geography table in use
system/.venv/bin/python system/engine/tools/discover_boards.py --dry-run "Employer"   # what the employer-discovery tool would register
```
Smoke paths: `JOBKIT_WORKSPACE="$PWD/system/examples/"marina_example system/.venv/bin/python system/examples/marina_example/build_test_cv.py`
(academic CV + statement, audit clean), the same with `taylor_example/build_test_example.py` (one-page resume) and
`jordan_example/build_test_example.py` (one-page nursing resume).

## Employer discovery (`system/engine/tools/discover_boards.py`, v0.3)
Given employer names (CLI or `settings.yaml targets.employers`), it (1) probes Greenhouse / Lever / Ashby / SmartRecruiters /
Workable / iCIMS / NEOGOV under token variants of the name (lowercase, no-space, hyphen, suffix-stripped, +careers/+jobs,
CamelCase, acronym) with a company-name check against the board (a GH board's `name`, the Lever/Ashby page title, the
SmartRecruiters `company.name`, the NEOGOV/iCIMS page title) so `denver` does not register "Animal Health Care Denver";
(2) web-searches `"<employer>" careers` (Bing; DuckDuckGo fallback - it bot-challenges after a few queries), keeps results
whose host carries the name words, fetches those careers pages and scans them for Workday / Oracle CX / ADP / Eightfold /
Phenom / Greenhouse / Lever / Ashby / SmartRecruiters / NEOGOV / Workable URLs and Radancy or PageUp / PeopleAdmin
server-rendered listings; (3) verifies every candidate with the arm's own API call (Workday = the CXS POST, HTTP 200 +
`jobPostings`; 422 means wrong tenant/host); (4) registers one best source per employer (full-text board > Workday >
Oracle > Eightfold/Phenom > iCIMS/ADP/NEOGOV > scraped listing) in `custom.json`, or a MANUAL watch entry with the careers
URL. `--watch "Name=URL"` adds a watch entry by hand. Known limit: a board found via the web search is verified as live,
not as that employer's (namesakes); the output names the host so Claude can read it back.

## Discovery arms and terms of service
The employer boards (packs + custom.json) are public job-board APIs and careers pages and are always on. Three aggregator
arms exist in `feeds.py`: **Adzuna** uses an official API with a free key (developer.adzuna.com) - the recommended one,
`run.adzuna`; **LinkedIn** (`run.linkedin_guest`) reads LinkedIn's public guest search cards and **Indeed** (`run.indeed_jobspy`)
goes through python-jobspy's mobile GraphQL route - both are unofficial scrapes of sites whose terms of service restrict
automated access, both break without notice (rate limits, unversioned endpoints), and since v0.3 both default to OFF in
`settings.yaml.example` and in `feeds.py`. The onboarding interview (phase 14) describes the caveat in plain words and turns
them on only on an explicit yes. Everything found by any arm is still judged on the employer's own posting text and the
apply link is always the employer's (CONSTITUTION I.6).

## The pipeline (`system/engine/tools/daily.py`; details in `system/docs/ARCHITECTURE.md` and `system/engine/charters/search.md`)
```
daily.py [window_days]
  0  watch.py          diff watched boards
  0b inbox_sweep.py    ONLY if modules.inbox_sweep (read-only; OFF by default)
  1  corpus.py+match.py full JD text from GH/Lever/Ashby/Workable/SmartRecruiters boards, title-blind scoring
  1a sweep.py          Workday tenants (keyword search)
  1b feeds.py          VC boards, aggregators (Adzuna/LinkedIn/Indeed per run.*), small ATS, RSS, listserv archives,
                       NEOGOV, JSON listings, USAJobs (user key)
  1c hard_ats.py       Oracle/ADP/Eightfold/Phenom/SAP/iCIMS
  2  dedupe            state.db, dispositions ledger, mirror collapse, caches
  3  screen_minquals   fetch + knockouts per settings.yaml work_authorization flags
  3b critic.py         adversarial review; hard classes auto-ledgered
  4  queue_<date>.md   judgment queue
  5  rubric.py prep    batch + prompt for TWO blind scorers -> `rubric.py merge run_A run_B` re-orders the queue
judgment (Claude) -> decide.py per item -> build (build.py + resume_builder) -> verify_resume, keywords, audit_claims,
consistency -> job card -> the USER applies on the employer site -> state.py add ...
```
The skills `system/engine/skills/daily/SKILL.md` and `system/engine/skills/build/SKILL.md` are the exact rituals Claude follows around
this spine; `system/engine/skills/onboarding/SKILL.md` is the 21-phase interview that fills the workspace.

## Where every field-specific thing lives (the engine has none)
| what | workspace file |
|---|---|
| identity, work authorization, geography, lanes, targets, thresholds, exclusions, switches, build, education | `settings.yaml` |
| JD-text signature terms, gate thresholds, lane gates, priority-lane patterns | `profile/signals.yaml` |
| critic knockouts, soft flags, instrument-owner list, lane rules, screen knockouts | `profile/critic_rules.yaml` |
| keyword-coverage lexicon (YES / UTIL / NEVER / ASK) | `profile/lexicon.yaml` |
| the only phrasings a document may use; never/retired claims; the `cv:` block | `profile/approved_claims.yaml` |
| evidence, skills inventory, publications, blind profile | `profile/` |
| search terms for every keyword-searched arm (written by onboarding phase 17 from the person's field words; three worked examples ship: `queries.{nurse,software,biologist}.yaml.example`) | `tracking/registries/queries.yaml` |
| the user's own job boards (filled by `discover_boards.py` from `settings.yaml targets.employers`); packs are chosen in `settings.yaml lanes[].packs` | `tracking/registries/custom.json` |
| field and track (industry / academic / government / nonprofit / mix) - decides which interview phases run and the resume vs CV default | `settings.yaml targets.track`, `build.format` |
| dated personal rules, calibration table | `my-rules.md` |
| API keys (Adzuna, USAJobs) | `keys.json` |
With all of these empty the engine still runs (cosine-only ranking, generic knockouts, idle keyword arms) and says so.

## The honesty audit, in detail (v0.8, after the 2026-10-20 code audit)
`audit_claims.py` reads EVERY text channel of a .docx through `docxtext.py` (body, table cells, headers, footers, text
boxes); a resume / CV may carry text outside the body only in the CV builder's own page footer. The document's KIND decides
how strictly it is checked and the decision fails closed: `resume_builder` stamps `core_properties.subject` with
`jobkit:resume` / `jobkit:cv`; a letter or statement written by the build skill is stamped `jobkit:letter` with
`docxtext.py --stamp-letter <file>` (a file named CoverLetter_* / Statement_* / Letter_* counts as a letter by name); a file
with no stamp and no such name is audited as a resume. Structural exemptions are structural: a heading is a paragraph the
builder drew with its bottom border, the contact line is the line under the name carrying the email or phone, a
`Label : text` line needs an approved label (skills line, constant, project title), and a summary prefix is a short
role noun with no digits. Unreadable files are FAIL lines; `~$` lock files and `.bak-<date>` folders are ignored.
`approved_claims.py` exports YAML names to the module only after a reserved-name check (`ReservedClaimName`), and the
whitelist is built from the keys that hold approved wording (`_APPROVED_KEYS`), never from the whole file.
`system/engine/tools/tests/test_audit_channels.py` holds the probes that once passed and must now fail.

## Cost knobs and the blind judges (v0.5; conditional scorer B since 2026-10-16)
Scorer B reads only the postings scorer A placed in the borderline band (`settings.yaml rubric.b_band`, default [30, 70]):
`rubric.py prep-b <run_A>` writes `prompt_B_<date>.txt` and `b_ids_<date>.json`; `merge` accepts a run B covering exactly
that subset (or every id) and tags single-judge scores "A-only". Every merged score is appended to
`tracking/rubric/score_history.jsonl`; `rubric.best_recent(url)` is the 14-day best, used by the auto-skip guard and by
`decide.py`'s SKIP guard (`skip_guard`: REQ:"..." quote or a hard tag needed at or above the build line).
`settings.yaml run.judge_top_n` (default 40) caps how many postings the two blind scorers read per run (ranked by the
deterministic match score, priority-lane postings first); the rest are written to `tracking/deferred.jsonl` by `rubric.py prep` (v0.9; one line per
posting per day, with the first deferral date) and re-surface on the next run; the decision ledger holds decisions only. `run.jd_text_cap_chars` (default 6000) trims each posting for the
scorers (`rubric.cap_text`: the opening plus the requirements block, written to `tracking/rubric/jd_<id>_<date>.txt`; the
full text stays in `tracking/jds/` for the critic and the build). `tracking/rubric/judge_plan.json` records scored / deferred
/ characters per scorer; the daily report's first lines say "about N postings scored". Both scorers are spawned with the
same prompt file verbatim so the prompt prefix is cached once. Isolation of the scorers is by INSTRUCTION, not by sandbox:
a subagent could in principle read other files on disk; the prompt names only `profile_blind.md` and the JD files, and the
skill forbids handing it anything else. Measured on the v0.4 audit run (78 postings, no cap): ~173k input tokens per scorer;
with the default cap of 40 postings at 6,000 characters, roughly 60-65k per scorer.

## Honesty rules (short form; full text `system/engine/CONSTITUTION.md`)
Never fabricate; work authorization printed exactly as written and used as the only eligibility source; gaps internal;
nothing sent without per-item approval; official links only; no ATS tricks; the audit gates every output; no deletion
of user data. The academic path (multi-page CV, PhD targets, listserv archives read-only, USAJobs with the user's key) is
described in `system/docs/ARCHITECTURE.md` and shown filled in `system/examples/marina_example/`.

## Release (`system/release.sh`)
`system/release.sh [version] [out_dir]` does the whole thing: fresh `git clone` of this repo into a temp folder, strip
`.git`, `git init`, `manifest.py generate`, single commit `jobkit v0.5`, tag `original-v0.8`, grep the staged tree for personal
tokens (the pattern list is `~/Downloads/jobkit_release/scrub_patterns.txt`, outside the repo; `SCRUB_PATTERNS=` overrides; must be 0
hits), zip to `<out_dir>/jobkit_v0.5_<date>.zip`. `release.sh` itself is removed from the stage and never ships without `.venv`, `__pycache__`, run artifacts or extracted
intake, and write `EMAIL_NOTE_<date>.md` next to it. The shipped `My Job Search/` holds templates, the intake README and
the registries README only. Fresh-install smoke after a release: unzip, `<launcher> setup`, drop one
.docx into intake and run `intake.py`, then `JOBKIT_WORKSPACE=system/examples/jordan_example system/.venv/bin/python
system/examples/jordan_example/build_test_example.py` + `audit_claims.py`.

## Status
2026-10-08: all 31 field-specific items of `system/docs/REFACTOR_PLAN.md` moved to workspace data; regression against the
original pipeline identical (`system/docs/REGRESSION_2026-10-08.md`). 2026-10-09: academic path + marina example with a live
smoke run (`system/examples/marina_example/SMOKE_RUN_2026-10-09.md`); v0.2: `CLAUDE.md`, `setup.py`, the three skills, and a
simulated non-technical run (`system/docs/UX_TEST_2026-10-09.md`). 2026-10-11, v0.3: field-neutral copy and conditional interview
(field + track in phase 5; academic phases 9/11/12 and the USAJobs step conditional; certifications generic; queries.yaml
generated in phase 17), `discover_boards.py` + the "add employer" command, six generic packs live-verified (see
`system/engine/registries/packs/README.md` for what failed), LinkedIn/Indeed opt-in, the jordan nurse example with a live run
(`system/examples/jordan_example/reports/2026-10-11.md`). 2026-10-11, v0.4: shipping layout (`My Job Search/` + `system/`),
`intake.py` + confirmation-mode onboarding, `tracker.csv` + the applied / outcome commands, the source lock (manifest,
read-only engine, `modify:` / `show my modifications` / `revert to original` on branch `modified`), `release.sh`.
