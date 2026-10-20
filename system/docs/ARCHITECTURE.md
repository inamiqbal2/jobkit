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

| key | type | consumed by |
|---|---|---|
| `identity.{name, first_name, email, phone, city_state, links[]}` | strings | resume_builder (contact line, core properties), verify_resume (parse test) |
| `work_authorization.resume_line` | string | resume_builder contact line; audit_claims requires it verbatim on resumes |
| `work_authorization.{citizenship_only_roles_open, clearance_possible, export_controlled_open, sponsorship_needed, permanent_resident}` | bool | eligibility.AUTH, screen_minquals (knockout classes), critic (INELIGIBLE check), match (INELIG corpus drop) |
| `location.{home, country, commute_radius_miles, commutable_metros[], relocation}` | mixed | judgment agent + profile_blind; `country` selects the `geo.py` table (US/CA/UK built in) used by match/sweep/daily/eligibility |
| `location.{in_country_regex, in_country_regex_loose, foreign_regex_extra}` (optional) | regex | overrides of the `geo.py` table (required for a country without one) |
| `location.{tier1_regex, tier2_regex}` | regex | daily.py / sweep.py geography tiers (T1 commutable+remote, T2 nearby, T3 rest) |
| `lanes[].{name, description, example_titles[], never_claims[], priority, packs[]}` | list | state.py canonical lanes; `priority: true` enables lanes.py (patterns in signals.yaml); `packs` -> registries.py assemble. Signature terms live in `profile/signals.yaml`, search terms in `tracking/registries/queries.yaml` |
| `thresholds.{build_default_min_rubric, commutable_min_rubric, auto_skip_below_rubric, jd_gate, band_midpoint_ceiling, low_band_top}` | numbers/null | critic (band advisory), screen (LOWBAND), daily tripwire, judgment agent; `jd_gate` here is only the fallback when signals.yaml has no thresholds |
| `exclusions.{employers[], role_types[], contract_work, postdocs}` | list/bool | eligibility.excluded_employer (src/URL only); `role_types` = regexes appended word-bounded to the title-eligibility filter; critic CONTRACT-GIG switch; `postdocs: false` drops postdoctoral TITLES (eligibility.ELIG, 2026-10-09); judgment |
| `salary.{floor, target, currency}` | numbers | judgment notes only, never a silent filter |
| `modules.{inbox_sweep, outreach}` | bool, default false | daily.py STEP 0b, inbox_sweep.py, outreach charter |
| `run.{adzuna, linkedin_guest, indeed_jobspy, window_days}` | bool/int | feeds.py arm switches; `linkedin_guest` and `indeed_jobspy` default OFF since v0.3 (unofficial scrapes; opt-in), `adzuna` = official API with a free key |
| `build.{resume_filename, min_experience_entries, location_line_default}` | mixed | resume_builder, consistency |
| `build.{format, cv_filename, cv_min_pages, cv_max_pages}` (2026-10-09) | `resume` \| `academic_cv`, str, int, int | `academic_cv`: resume_builder.AcademicCV (multi-page CV), verify_resume (page range instead of the 1-page/fill checks), audit_claims (every CV line must trace to approved_claims.yaml) |
| `targets.{phd_positions, fixed_term_ok, hourly_ok}` (2026-10-09, optional) | bool | eligibility.ELIG: `phd_positions` switches OFF the new-grad/campus title drop and critic GRAD-GATE; `fixed_term_ok` switches OFF the temp/temporary title drop; `hourly_ok` (v0.2) switches OFF the critic's "BELOW LEVEL: technician/HS tier" advisory |
| `targets.track` (v0.3) | `industry` \| `academic` \| `government` \| `nonprofit` \| `mix` | onboarding only: which phases are asked (publications/teaching/references for academic; the USAJobs key step for government) and the resume-vs-CV default |
| `targets.employers[]` (v0.3) | list of names | `tools/discover_boards.py`: finds and verifies each employer's board, writes `custom.json` (or a watch entry) |
| `education[].{institution, dates, line}` | list | resume_builder.education() |
| `verification.employer_tokens[]` | list | verify_resume parse test (only when present in the docx) |
| `rubric.protect_title_regex` (optional) | regex | rubric.py: archetype never auto-skipped on score |

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
