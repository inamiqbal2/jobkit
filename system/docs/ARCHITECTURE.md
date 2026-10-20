# jobkit architecture: engine vs workspace

jobkit turns one person's job-search pipeline into a template another person can run on their own
computer, in their own field, with their own facts. The split is strict:

| | **system/engine/** (shared, versioned, personal-free) | **My Job Search/** (one per user, private, git-ignored) |
|---|---|---|
| code | `tools/*.py` | none (build scripts are generated per application, under `applications/`) |
| rules | `CONSTITUTION.md` (non-negotiable), `charters/*.md` (method) | `my-rules.md` (geography, lanes, exclusions, salary, temporary windows) |
| data | `registries/packs/*.json` (job-board packs by field: six generic ones since v0.3 plus the science/engineering ones), `tools/geo.py` (country tables) | `settings.yaml`, `profile/` (incl. `signals.yaml`, `critic_rules.yaml`, `lexicon.yaml`), `tracking/registries/queries.yaml` + `custom.json` (filled by `tools/discover_boards.py`), `tracking/`, `applications/`, `keys.json` |
| skills | `skills/onboarding/SKILL.md` (the 21-phase interview + "read my documents" confirmation mode), `skills/daily/SKILL.md` ("run my job search"), `skills/build/SKILL.md` ("build my documents for ...") | `ONBOARDING_STATUS.md`, `reports/<date>.md`, `tracker.csv`, `intake/` (the person's documents; `_extracted/` by `tools/intake.py`) |
| integrity | `MANIFEST.sha256` (every engine file; `tools/manifest.py`), read-only on disk after setup, git tag `original-v0.8`, changes on branch `modified` | never locked; never touched by modify / revert |

**Rule of thumb:** if a value would be wrong for the next user, it belongs in the workspace. If the
engine ever needs a personal value, it reads it through `system/engine/tools/userconfig.py`.

## Workspace resolution

`userconfig.WS` = `$JOBKIT_WORKSPACE` if set, else `<jobkit>/My Job Search` (`../My Job Search` relative to
`system/engine`). The v0.3 names are read as fallbacks (`user.yaml`, `secrets.json`, `charters/user-rules.md`). Every tool imports
`from userconfig import WS as ROOT` and builds its data paths from it (`tracking/`, `profile/`,
`applications/`, `keys.json`). Tool paths (for `subprocess`) come from the engine folder.
A user may keep several workspaces (e.g. two searches) and switch by environment variable.

v1.0 (audit M26): importing `userconfig` reads no settings (`load()` runs on the first `get()`; `MODULES` fills itself on first use).
`userconfig.configure(ws)` re-points `WS` and every WS-derived constant (`TRACKING`, `PROFILE`, ..., `SECRETS`, `USER_YAML`,
`SIGNALS_YAML`, `QUERIES_YAML`), exports `JOBKIT_WORKSPACE` and clears every cache. Call it before importing the engine modules:
a module that already ran `from userconfig import WS as ROOT` keeps its old path, because Python copied the value at import.
The import-time rule is unchanged: a `JOBKIT_WORKSPACE` that is not a folder exits 2 (v0.9, audit M21).

## Workspace layout

```
My Job Search/
  settings.yaml                      identity, work authorization, location, lanes, thresholds, exclusions,
                                 salary, modules, run switches, build settings, education, verification
  keys.json                      API keys only (adzuna, usajobs). git-ignored.
  tracker.csv                    GENERATED plain-English view (state.py tracker): applications + built/watched items
  ONBOARDING_STATUS.md           the 21-phase progress file
  intake/                        the person's own documents (.docx .pdf .txt .md); never modified by the engine
    _extracted/<name>.txt, INDEX.md, index.json   written by tools/intake.py (draft material only)
  profile/
    evidence/<job-or-project>.md one RAW-FACT file per job/project (template: _TEMPLATE.md); NDA rules at top
    skills-inventory.md          CORE / WORKING / FAMILIAR / HANDS-ON REALITY / NEVER CLAIM
    publications.md              verified master list; governs every publication count
    approved_claims.yaml         the ONLY phrasings a build may use (see schema below)
    profile_blind.md             what the two blind rubric scorers read (has + does-not-have + target + limits)
    signals.yaml                 match.py: lanes.<name>.{role: home|transferable|gate, terms, negatives, lane_ref, gate},
                                 thresholds {jd_gate, sig_min, sigx_min, sig_floor}, priority_patterns (lanes.py)
    lane_ref_<lane>.md           (gate lanes) plain description of the REQUIRED work of that lane; never a claim
    critic_rules.yaml            critic.py / screen_minquals.py / daily.py: hard_checks, soft_flags, instrument_owner,
                                 lane_rules, closed_lanes {rule, action, title_hint_regex}, priority_advisory,
                                 screen_block, screen_auto_exclude_soft
    lexicon.yaml                 keywords.py: {term: {syn: [...], claim: YES|NEVER|UTIL|ASK}} (generic fallback if absent)
    rubric_prompt_header.txt (optional) overrides the scorer instructions
  my-rules.md         dated personal rules (template provided)
  tracking/
    state.db, jobs.csv           single source of truth + generated full view (tracker.csv is the plain view)
    OUTCOMES_LOG.md              narrative journal; state.py applied / outcome append to it
    dispositions.jsonl           judgment ledger (SKIP/BUILT/APPLIED/WATCH/REOPEN per canonical URL)
    registries/                  queries.yaml (search terms per arm) · custom.json (own boards) · ACTIVE files
                                 written by `registries.py assemble` from the selected packs + custom.json:
                                 registry.json, wd_registry.json, registry2.json, hard_registry.json,
                                 feeds_registry.json (+ ../watchlist.json)
    jds/, rubric/, caches        generated
    inbox_sender_tokens.json     (optional, inbox_sweep module only) employer -> sender-token overrides
  applications/<Company>_<Role>/ JobDescription.txt, build script, Resume_<name>.docx, prep files
```

## settings.yaml schema (authoritative copy with comments: `My Job Search/settings.yaml.example`; same keys as the v0.3 user.yaml)

v1.0 (audit M27): the one source is `SCHEMA` in `system/engine/tools/userconfig.py` (type, default, required phase, choices,
range, consumers, one-line doc). The accessors take their defaults from it, `validate()` iterates it, and the table below is
`userconfig.py --schema` pasted between the markers - do not edit the rows by hand; `tests/test_settings_schema.py` fails
when the two drift or when a tool reads a key that is not in `SCHEMA`. "filled in" = the onboarding phase that writes the
key (`required` = a "missing" note until then; `optional` = set by hand; `reserved` = accepted but read by nothing yet).
Keys that are not read by the engine itself (`location.home`, `salary.*`, `lanes[].description`, `targets.track`) are what the
onboarding skill and the judgment agent read from the file; they stay in the schema so a filled file validates.

<!-- schema:begin (generated by `system/engine/tools/userconfig.py --schema`) -->
| key | type | default | filled in | consumed by | what it does |
|---|---|---|---|---|---|
| `identity` | section |  | required (phase 2) | resume_builder (contact line, core properties), verify_resume (parse test), audit_claims (person pool) | who the resume is for |
| `identity.name` | str | `""` | required (phase 2) | resume_builder, audit_claims, verify_resume | full name as it prints at the top of the resume |
| `identity.first_name` | str | `""` | phase 2 | verify_resume | used by the resume parse test (must survive docx -> pdf -> text) |
| `identity.email` | str | `""` | required (phase 2) | resume_builder, verify_resume, audit_claims | contact line |
| `identity.phone` | str | `""` | phase 2 | resume_builder, verify_resume, audit_claims | printed verbatim; the parse test looks for this exact string |
| `identity.city_state` | str | `""` | phase 2 | resume_builder | ATS location prefill; OFF the contact line by default (see build.location_line_default) |
| `identity.links` | list | `[]` | phase 2 | resume_builder, audit_claims | printed in this order on the contact line; [] for none |
| `work_authorization` | section |  | required (phase 3) | eligibility.AUTH, screen_minquals (knockout classes), critic (INELIGIBLE), match (INELIG corpus drop), resume_builder, audit_claims | Article I.2: the engine never assumes a status |
| `work_authorization.resume_line` | str | `""` | required (phase 3) | resume_builder contact line; audit_claims | the exact words printed on the resume contact line ("" prints nothing); audit_claims requires it verbatim |
| `work_authorization.citizenship_only_roles_open` | bool | `false` | required (phase 3) | eligibility, screen_minquals, critic, match | true if "must be a U.S. citizen" roles are open to you |
| `work_authorization.clearance_possible` | bool | `false` | required (phase 3) | eligibility, screen_minquals, critic, match | true if you can obtain or hold a security clearance |
| `work_authorization.export_controlled_open` | bool | `false` | required (phase 3) | eligibility, screen_minquals, critic, match | true if ITAR / "U.S. person" / export-controlled roles are open |
| `work_authorization.sponsorship_needed` | bool | `false` | required (phase 3) | eligibility, screen_minquals, critic, match | true if you need visa sponsorship (adds a knockout for "no sponsorship") |
| `work_authorization.permanent_resident` | bool | `false` | required (phase 3) | eligibility, screen_minquals, critic, match | true if you hold permanent residency: postings that explicitly admit permanent residents are then open even when citizenship_only_roles_open is false |
| `location` | section |  | required (phase 4) | geo, eligibility, daily, sweep, decide, rubric, funnel, feeds; judgment agent + profile_blind | where the search happens and how much location matters |
| `location.home` | str | `""` | phase 4 | judgment agent + profile_blind (not read by the engine) | home city and state, in plain words |
| `location.country` | str | `"US"` | required (phase 4) | geo.py table selection used by match/sweep/daily/eligibility | ONE two-letter country of search; US / CA / UK have built-in geography tables (geo.py), any other code needs the three regex overrides |
| `location.in_country_regex` | regex | `""` | phase 4 | geo.py | override: a location string that reads as INSIDE the country (strict; corpus arm); required for a country without a geo table |
| `location.in_country_regex_loose` | regex | `""` | phase 4 | geo.py | override: same, loose (Workday / hard-ATS placeholders like "3 Locations") |
| `location.foreign_regex_extra` | regex | `""` | phase 4 | geo.py | override: extra foreign-place cues to drop (e.g. "United States\|USA" for a non-US user) |
| `location.commute_radius_miles` | int 0-1000 | `0` | phase 4 | judgment agent + profile_blind (not read by the engine) | commuting radius in miles |
| `location.commutable_metros` | list | `[]` | phase 4 | validate() stay-local guard; judgment agent + profile_blind | plain words for the judgment agent and the rubric profile, e.g. ["Denver CO", "Boulder CO"]; must be filled for a local_only / local_first / unsure search |
| `location.relocation` | yes \| no \| case-by-case | `"case-by-case"` | phase 4 | location_mode() fallback | kept for older workspaces; location.mode is what the engine follows (missing mode: no -> local_only, yes -> fit_first, else local_first) |
| `location.mode` | local_only \| local_first \| fit_first \| unsure | `""` | phase 4 | location_mode(): decide.skip_guard, rubric prompt, scoring() default | local_only = stay local, jobs elsewhere are set aside before judging \| local_first = jobs elsewhere need away_bar \| fit_first = location barely matters \| unsure = like local_first, but every strong job elsewhere is put to you as a question |
| `location.away_bar` | int 0-100 | `70` | phase 4 | decide.skip_guard | local_first / unsure: the score a job elsewhere needs before a resume is built for it |
| `location.never_places` | list of str | `[]` | phase 4 | rubric / decide (never_places), judgment agent | places you would never move to, in plain words |
| `location.remote` | ok \| preferred \| no | `"ok"` | phase 4 | rubric prompt, judgment agent | how remote work is treated |
| `location.other_countries` | list of str | `[]` | phase 4 | eligibility.non_us | other countries you would work in (names or codes); ["any"] = anywhere |
| `location.other_countries_regex` | regex | `""` | phase 4 | eligibility.non_us | place words for those countries when they are not US / CA / UK (drafted at setup) |
| `location.tier1_regex` | regex | `"Remote"` | phase 4 | daily.py / sweep.py geography tiers | commutable places + remote as a pattern, e.g. "Denver\|Boulder\|Colorado\|\\bCO\\b\|Remote" (T1 = commutable + remote) |
| `location.tier2_regex` | regex | `""` | phase 4 | daily.py / sweep.py geography tiers | nearby places you would consider (T2); "" = none (the engine's default never matches) |
| `lanes` | list of blocks |  | required (phase 5) | state.py canonical lanes; lanes.py (priority); registries.py assemble (packs) | 1-6 target lanes in plain words; packs pick the job boards. Signature terms live in profile/signals.yaml, search terms in tracking/registries/queries.yaml |
| `lanes[].name` | str | `""` | required (phase 5) | state.py, lanes.py | short canonical label (state.db Lane column warns on anything else) |
| `lanes[].description` | str | `""` | phase 5 | onboarding / judgment agent (not read by the engine) | the work in one or two sentences |
| `lanes[].example_titles` | list | `[]` | phase 5 | onboarding / judgment agent (not read by the engine) | titles that belong to the lane |
| `lanes[].never_claims` | list | `[]` | phase 5 | onboarding (approved_claims never_claims) | things people in this lane claim that you must never claim |
| `lanes[].priority` | bool | `false` | phase 5 | lanes.py via priority_lane_names() | true = the lane is screened FOR and never auto-skipped (patterns: profile/signals.yaml priority_patterns) |
| `lanes[].packs` | list | `[]` | phase 5 | registries.py assemble via selected_packs() | job-board packs from system/engine/registries/packs/ ([] = none); every name must exist |
| `targets` | section |  | phase 5 | eligibility.ELIG, critic, discover_boards | what KINDS of positions are in scope, and who you would love to work for |
| `targets.track` | industry \| academic \| government \| nonprofit \| mix | `""` | phase 5 | onboarding (not read by the engine) | onboarding only: which phases are asked (publications / teaching / references for academic; the USAJobs key step for government) and the resume-vs-CV default |
| `targets.position_types` | list of str | `[]` | phase 5 | targets(): each type switches off the matching title drop / critic gate | what you are looking for: full_time, part_time, internships, co_ops, new_grad, fellowships, unpaid_research, phd_positions, postdocs, contract, temporary, hourly; anything NOT listed is set aside |
| `targets.phd_positions` | bool | `false` | phase 5 | eligibility.ELIG, critic GRAD-GATE | legacy flag (v0.6): funded PhD positions / studentships are targets - the new-grad / campus title drop and the critic's GRAD-GATE are off |
| `targets.fixed_term_ok` | bool | `false` | phase 5 | eligibility.ELIG | legacy flag: "temporary" / fixed-term titles are not an eligibility drop |
| `targets.hourly_ok` | bool | `false` | phase 5 | critic | legacy flag: hourly-paid / high-school-minimum postings are NOT flagged "BELOW LEVEL" by the critic |
| `targets.internships_ok` | bool | `false` | phase 5 | eligibility.ELIG | legacy flag: internship titles are kept (same as position_types: [internships]) |
| `targets.coops_ok` | bool | `false` | phase 5 | eligibility.ELIG | legacy flag: co-op / apprenticeship titles are kept (same as position_types: [co_ops]) |
| `targets.new_grad_ok` | bool | `false` | phase 5 | eligibility.ELIG, critic GRAD-GATE | legacy flag: new-grad / early-career / graduate-program titles are kept (same as position_types: [new_grad]) |
| `targets.unpaid_ok` | bool | `false` | phase 5 | eligibility.ELIG | legacy flag: unpaid / volunteer postings are kept (same as position_types: [unpaid_research]) |
| `targets.part_time_ok` | bool | `true` | phase 5 | eligibility.ELIG | legacy flag: part-time titles are kept (absent = kept; position_types: [part_time] says the same) |
| `targets.employers` | list | `[]` | phase 5 | discover_boards.py: finds and verifies each employer's board, writes custom.json (or a watch entry) | up to ~10 employers you would be glad to work for, by name |
| `scoring` | section |  | phase 14 | rubric.py prompt header | what the blind judges score BESIDES skills and experience (always scored) |
| `scoring.location` | yes \| a little \| no | `""` | phase 14 | rubric.py | yes \| a little \| no; missing = yes, or no when location.mode is fit_first |
| `scoring.career_fit` | yes \| no | `"yes"` | phase 14 | rubric.py | yes = a job that does not use / grow your strengths scores lower; no = any job you can get |
| `scoring.pay` | yes \| no | `"no"` | phase 14 | rubric.py | yes = posted pay against the profile's PAY line counts |
| `scoring.remote` | yes \| no | `"no"` | phase 14 | rubric.py | yes = remote / hybrid terms count |
| `thresholds` | section |  | phase 14 | critic (band advisory), screen (LOWBAND), daily tripwire, decide, rubric, match | the score lines; auto_skip_below_rubric <= commutable_min_rubric <= build_default_min_rubric |
| `thresholds.build_default_min_rubric` | int 0-100 | `60` | phase 14 | decide, rubric, daily, critic | dual-blind average at / above this = build by default |
| `thresholds.commutable_min_rubric` | int 0-100 | `45` | phase 14 | decide | inside commutable_metros, build from this line |
| `thresholds.auto_skip_below_rubric` | int 0-100 | `40` | phase 14 | decide, rubric | below this, both scorers agreeing, non-stub JD -> auto-ledger SKIP |
| `thresholds.jd_gate` | number 0-1 | `0.28` | phase 14 | match (fallback) | FALLBACK only: profile/signals.yaml thresholds.jd_gate wins when present |
| `thresholds.band_midpoint_ceiling` | int or null >= 0 | `null` | phase 14 | critic | e.g. 140000 -> critic prints an ADVISORY above it; null = off |
| `thresholds.low_band_top` | int or null >= 0 | `null` | phase 14 | screen_minquals | e.g. 90000 -> queue tags LOWBAND below it; null = off |
| `exclusions` | section |  | phase 5 | eligibility, critic | what is never shown |
| `exclusions.employers` | list of regex | `[]` | phase 5 | eligibility.excluded_employer | regex or plain names, matched on SOURCE / URL only, never JD text |
| `exclusions.role_types` | list of regex | `[]` | phase 5 | eligibility (appended to the title filter) | title-level eligibility drops (regexes, word-bounded, case-insensitive); only what YOU name |
| `exclusions.contract_work` | bool | `false` | phase 5 | critic CONTRACT-GIG | false = contract / 1099 / freelance / contract-to-hire postings are OUT (absent = OUT) |
| `exclusions.postdocs` | bool | `true` | phase 5 | eligibility.ELIG | false = postdoctoral TITLES are dropped; the template ships false, an ABSENT key keeps them (the v0.2 reading) |
| `salary` | section |  | phase 6 | onboarding -> profile_blind PAY line; judgment agent | pay expectations; judgment notes only, never a silent filter |
| `salary.floor` | int or null >= 0 | `null` | phase 6 | onboarding / judgment agent (not read by the engine) | lowest yearly pay you would accept (a number, e.g. 85000) |
| `salary.target` | int or null >= 0 | `null` | phase 6 | onboarding / judgment agent (not read by the engine) | the pay you are aiming for |
| `salary.currency` | str | `"USD"` | reserved | none yet | currency of floor and target (reserved: accepted, read by nothing yet) |
| `modules` | section |  | phase 14 | daily.py STEP 0b, inbox_sweep.py, outreach charter | optional engine modules, OFF by default |
| `modules.inbox_sweep` | bool | `false` | phase 14 | daily.py STEP 0b, inbox_sweep.py | Gmail read-only sweep; requires the agent's Gmail tool |
| `modules.outreach` | bool | `false` | phase 14 | outreach charter | outreach drafting charter |
| `run` | section |  | phase 14 | feeds.py, daily.py, rubric.py, setup.py | discovery arms (employer boards always run; these are extras) and the cost knobs |
| `run.adzuna` | bool | `false` | phase 16 | feeds.py | OFFICIAL free API (developer.adzuna.com); true needs adzuna_id / adzuna_key in keys.json |
| `run.linkedin_guest` | bool | `false` | phase 16 | feeds.py | OPT-IN: public guest cards scraped from linkedin.com (terms of service; unversioned, rate-limited) |
| `run.indeed_jobspy` | bool | `false` | phase 16 | feeds.py, setup.py (installs jobspy) | OPT-IN, same caveat (Indeed's terms); needs python-jobspy (requirements-optional.txt) |
| `run.window_days` | int 1-365 | `30` | phase 14 | daily.py | recency window on UPDATED date (charters/search.md) |
| `run.judge_top_n` | int 0-500 | `40` | phase 14 | rubric.py prep | only the top N postings by the deterministic match score go to the two blind scorers each run; the rest are deferred (0 = score everything) |
| `run.jd_text_cap_chars` | int 500-100000 | `6000` | phase 14 | rubric.cap_text | the scorers read at most this many characters of each posting (the requirements block is always kept whole) |
| `run.judgment_check` | bool | `true` | phase 14 | daily.py | warn when a job at or above the build line goes 7 days without a decision |
| `run.judge_model` | str | `""` | phase 14 | daily skill (scorer spawn) | light mode: model for the two judges, e.g. "sonnet"; "" = the strongest available |
| `rubric` | section |  | optional | rubric.py | the blind judges |
| `rubric.b_band` | list of int | `[30, 70]` | optional | rubric.py prep-b / merge | scorer B re-reads only postings scorer A put in this band (rubric.py prep-b) |
| `rubric.protect_title_regex` | regex | `""` | optional | rubric.py auto-skip guard | titles the judges are known to under-score for YOU; never auto-skipped ("" = none) |
| `build` | section |  | phase 5 | resume_builder, verify_resume, audit_claims, consistency | how the documents are built |
| `build.format` | resume \| academic_cv | `"resume"` | phase 5 | resume_builder, verify_resume, audit_claims, consistency | resume = one-page industry resume (verify = 1 page, 90-93% fill) \| academic_cv = multi-page CV (resume_builder.AcademicCV; verify = cv_min_pages..cv_max_pages; audit_claims checks EVERY line) |
| `build.resume_filename` | .docx filename | `"Resume.docx"` | phase 5 | consistency, audit_claims | every built resume uses this exact filename (phase 5 sets "Resume_<First>_<Last>.docx") |
| `build.cv_filename` | .docx filename | `"CV.docx"` | phase 5 | consistency, audit_claims | academic_cv only: the CV filename (must start with "CV" for the audit's CV mode) |
| `build.cv_min_pages` | int 1-20 | `2` | phase 5 | verify_resume | academic_cv: the page range verify_resume enforces (lower bound) |
| `build.cv_max_pages` | int 1-20 | `3` | phase 5 | verify_resume | academic_cv: the page range verify_resume enforces (upper bound) |
| `build.min_experience_entries` | int 0-10 | `3` | phase 5 | resume_builder | resume_builder warns below this many experience entries |
| `build.location_line_default` | str | `"Open to relocation"` | phase 5 | resume_builder | contact-line text for roles outside commutable_metros |
| `build.no_pdf_copies` | bool | `false` | optional | verify_resume | true = verify_resume fails when a Resume_ / CV_ / CoverLetter_ PDF sits in the folder (send .docx only) |
| `education` | list of blocks |  | phase 7 | resume_builder.education(), audit_claims (person pool) | printed by resume_builder.education(); newest first |
| `education[].institution` | str | `""` | required (phase 7) | resume_builder, audit_claims | the school |
| `education[].dates` | str | `""` | phase 7 | resume_builder, audit_claims | e.g. "Sep 2018 - May 2022" |
| `education[].line` | str | `""` | phase 7 | resume_builder, audit_claims | "<degree> in <field>, <city, state>  \|  Thesis: <title>" |
| `verification` | section |  | phase 13 | verify_resume | verify_resume.py parse test |
| `verification.employer_tokens` | list of str | `[]` | phase 13 | verify_resume parse test | the employer names on your resume; checked only when the resume mentions them |
<!-- schema:end -->

## profile/approved_claims.yaml schema (authoritative copy: `My Job Search/profile/approved_claims.yaml.example`)

| key | shape | consumed by |
|---|---|---|
| `summaries{name: text}` | dict | build scripts |
| `tenure.{line, short, years}` | | build scripts (`TENURE`, `TENURE_SHORT`); build.md tenure rule |
| `experience[].{key, org, dates, role, loc, always_include, frozen, evidence, nda, bullets{NAME: text}, keywords}` | list | approved_claims exports `<KEY>`, `<KEY>_BULLETS`, each `NAME`; entry_scorer; audit_claims (frozen) |
| `projects{key: {title, bullet, evidence}}` | dict | `PROJECTS` |
| `skills_lines{LABEL: [label, text]}` | dict | `<LABEL>` tuples |
| `publications.{line, short, counts}` | | `PUBS`, `PUBS_SHORT` |
| `hedged_phrases[]` | list | audit: operator patterns do not trip inside a hedged clause |
| `never_claims.{forbidden_terms[], operator_patterns[]}` | lists | audit HARD / BADPAT |
| `retired_claims[]` | regex list | audit RETIRED |
| `banned_words[]` | list | audit (default `["local"]`) |
| `consistency_items[]` | `{label, kind, match[]}` | consistency.py |
| `pending[]` | `{claim, question}` | onboarding: unusable until confirmed |
| `entry_variants{NAME: {base, role, ...}}` (optional) | dict | approved_claims exports `NAME` = (org, dates, role, loc) - same employer, different title read |
| `bullet_bank{NAME: text}` (optional) | dict | approved bullets not tied to one entry (thesis / publication bullets) |
| `constants{NAME: text | [label, text]}` (optional) | dict | approved phrasings exported by name |
| `experience[].section` (optional: research \| professional \| field \| teaching) | str | AcademicCV groups entries by section (default research) |
| `cv.{education[], publications[], presentations[], field_experience[], certifications[], technical_skills{}, teaching[], grants_awards[], service[], references}` (optional, 2026-10-09) | lists of str \| {text/citation, evidence} | approved_claims `CV_*` exports -> resume_builder.AcademicCV sections; audit_claims CV traceability (`approved_texts()`) |

## The pipeline (unchanged in shape; see `system/engine/charters/search.md`)

```
daily.py
  0  watch.py        diff watched boards (watchlist.json)
  0b inbox_sweep.py  ONLY if modules.inbox_sweep (read-only plan file for the agent)
  1  corpus.py       full JD text for every GH/Lever/Ashby/Workable/SmartRecruiters board in registry.json
     match.py        title-blind score vs profile (evidence + inventory + publications)
  1a sweep.py        Workday tenants (keyword search; wd_registry.json + registry2.json)
  1b feeds.py        VC boards, aggregators (Adzuna/LinkedIn/Indeed per run.*), small ATS, misc, RSS boards, listserv
                     archives (pipermail), NEOGOV, JSON listings, USAJobs (user key); listings that carry their description
                     are cached to tracking/jds/feed_<md5>.txt and screen_minquals reads the cache first
  1c hard_ats.py     Oracle/ADP/Eightfold/Phenom/SAP/iCIMS (hard_registry.json)
  2  dedupe          vs state.db applications, dispositions ledger, mirror collapse, caches
  3  screen_minquals fetch each JD, extract min-quals, knockouts (eligibility per settings.yaml flags)
  3b critic.py       adversarial review per JD (HOLD classes; hard eligibility auto-ledgers)
  4  queue_<date>.md judgment queue
  5  rubric.py prep  batch + prompt for TWO blind scorers -> rubric.py merge re-orders the queue
judgment (agent)  -> decide.py per item -> build (build script + resume_builder) -> verify_resume,
keywords, audit_claims, consistency -> user approves -> user applies on the employer site -> state.py
```

## Registry packs

`system/engine/registries/packs/<pack>.json` hold job-board registrations grouped by field
(healthcare_clinical, tech_software, government_public, nonprofit_social, education_general, business_marketing_sales
since v0.3; materials_semiconductor, nuclear_aerospace, finance_quant, ai_for_science, consulting, life_sciences_pharma,
deeptech_other, academic_marine_bio). `tools/discover_boards.py` adds the person's own employers to `custom.json` in the same shape. Each pack has `boards` (gh/lever/ashby/workable/smartrecruiters
slugs), `workday` (host, tenant, site), `hard` (per-ATS recipes), `misc` (small ATS / custom pages),
`feeds` (keyword-searched boards: getro / ats_links / rss / html_links, and since 2026-10-09 pipermail / neogov /
json_list / usajobs - see `system/engine/tools/feeds.py`), `watch` (watchlist entries). A pack may carry an `international`
key the assembler ignores (inactive entries kept for a later scope).
`settings.yaml -> lanes[].packs` names the packs to enable; `tools/registries.py assemble` writes the active
`My Job Search/tracking/registries/*.json` (+ `tracking/watchlist.json`) from the selected packs plus `custom.json`.

## The one judgment gate (`match.judgment_gate`)

Every arm (corpus docs in `matched.json`, every screened item scored on its fetched JD text) passes the SAME
title-blind rule, with every number from `profile/signals.yaml`: `score >= jd_gate AND (sig >= sig_min OR
(sigx >= sigx_min AND sig > sig_floor))`, else any `role: gate` lane whose `sigx`, domain signature and
cosine-to-`lane_ref` minimums are met on a non-stub JD. Priority-lane postings (lanes.py) always pass.
Empty signals = cosine-only with `sig_min 0`, no rescue, no lane gates, and a warning on every run.

## Non-negotiables

`system/engine/CONSTITUTION.md`. A workspace cannot override: never fabricate; nothing sent without per-item
approval; drafts only; official links only; no auto-submission; audit must pass; no deletion of user
data; privacy of optional modules. Article II (claims that failed) is workspace-owned data
(`approved_claims.yaml -> retired_claims / never_claims`) enforced by engine code.

## What is deliberately NOT in jobkit

Email sending, auto-apply, any scheduled unattended run (the original's scheduled runner was retired
because unattended runs stall on permission prompts), any personal fact, and any assumed field: the engine learns the
field from the workspace (lanes, signals, lexicon, queries, packs, employers), and the interview asks for it.
