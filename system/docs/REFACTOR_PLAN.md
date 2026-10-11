# REFACTOR PLAN - the non-mechanical de-personalizations

**STATUS 2026-10-08: DONE. All 31 `JOBKIT-TODO` markers are resolved (0 remain in `system/engine/`); regression
against the original's live run of the same day is zero-difference (`system/docs/REGRESSION_2026-10-08.md`).**
The sections below are the original plan, kept as the design record, each with a "DONE" note stating the
shape actually shipped and why it differs from the proposal where it does.

### Shapes as shipped (deviations from the proposals below, and why)
1. Signature terms, thresholds and lane gates live in **`profile/signals.yaml`**, not in `settings.yaml lanes[]`:
   they are a large, regex-heavy, calibrated table that changes on its own cadence; settings.yaml stays short
   and human-readable. Lanes there carry `role: home | transferable | gate` so several home lanes merge into
   SIG, the transferable set stays one table (SIGX), and each gate lane keeps its own terms / lane_ref / minimums.
   Terms are `[{pattern, weight}]` (plus optional `negatives`), which YAML renders more readably than
   `{regex: weight}` with backslashes as keys; both shapes are accepted.
2. Priority tiers: `signals.yaml priority_patterns` (lists of regexes per tier) + `settings.yaml lanes[].priority`.
3. Critic/screen: **`profile/critic_rules.yaml`** with `hard_checks` (critic HOLD) and `screen_block` (min-quals
   knockouts) kept as SEPARATE tables rather than one shared `hard` list, because the original's two regex sets
   for the same topic differ on purpose (the screen is tighter, scoped to the minimum-quals block) and merging
   them would have changed gate results. Closed lanes are COMPUTED from state.db (`closed_lanes.rule`, default
   advisory); the original's hand-written closed-lane check is simply one of the user's `hard_checks`.
4. Lexicon: `profile/lexicon.yaml`; generic fallback of universally claimable business terms; UTIL hedges printed
   from `approved_claims.yaml hedged_phrases`.
5. Search terms: **`tracking/registries/queries.yaml`** (`workday_terms`, `hard_ats_terms`, `board_terms`, `adzuna`,
   `linkedin`, `indeed`) rather than `lanes[].search_terms` - one list per ARM is what the code consumes, and the
   original's per-arm lists were not per lane. Boards: packs gained a `feeds` section; `registries.py assemble`
   writes `feeds_registry.json` too; the custom NANO scraper became a `custom_html` entry with its `card_regex` as data.
6. daily.py: dead regexes deleted; geography via `geo.py`; cache-date special case dropped; tripwire reads
   `thresholds.build_default_min_rubric`; the hard-coded `'bio'` auto-exclude became `screen_auto_exclude_soft`.
7. eligibility: `exclusions.role_types` is a regex list (plain words work), word-bounded.
8. `lane_templates.py` deleted outright (decision).
Country handling: `system/engine/tools/geo.py` table (US/CA/UK) + three optional overrides in `settings.yaml location`.
`INELIG` split into `CITIZEN_ONLY` / `CLEARANCE`, each active only when its flag is closed.

---
## The original plan (design record)

Order of work: 1 (lanes/signatures) unblocks 2-4; 5-7 are independent; 8 is cleanup.

## 1. match.py - signatures and thresholds -> `settings.yaml lanes[]` + `thresholds`

Markers: `SIG` (home-lane terms), `SIGX` (transferable terms), `FIN_SIG` + `lane_ref_finance.md` (per-lane
domain signature + reference text), `JD_GATE / JD_SIGX / JD_SIG / JD_SIG_FLOOR / FIN_T / FIN_COS / FIN_SX`,
`US` regex, `INELIG` split.

Proposed shape (already stubbed in `settings.yaml.example`):
```yaml
lanes:
  - name: process-engineering
    signal_terms: {"\\bscale-?up\\b": 3, "\\bpilot plant\\b": 4, "\\bGMP\\b": -3}   # -> SIG for the HOME lane(s)
    domain_terms: {...}            # optional, -> FIN_SIG-style per-lane domain signature
    reference_text: profile/lane_ref_<name>.md   # optional, -> cos_<lane> (plain description of the REQUIRED work)
    gate: {sig_min: 4, sigx_min: 8, domain_min: 15, cos_min: 0.05}   # per-lane second door (lane_gate generalized)
transferable_terms: {"\\bpython\\b": 1, "\\bstatistic": 2, ...}        # -> SIGX (one set, not per lane)
thresholds: {jd_gate: 0.28, jd_sigx: 12, jd_sig: 4, jd_sig_floor: -4}
```
Code change: `SIG = merge(lanes[*].signal_terms where lane.home)`, `SIGX = transferable_terms`, a dict of
per-lane `(domain_terms, reference_text, gate)` replacing the single FIN_* block; `lane_gate(lane, ...)`.
`INELIG`: split into `CITIZEN_ONLY` and `CLEARANCE` and apply each only when the matching auth flag is false.
`US`: derive from `location.country` (ship a small country->regex table: US state codes, CA provinces, UK/EU
city lists) or accept a user-supplied `location.in_country_regex`.
**Calibration ritual** (must be documented in search.md): after the user's first corpus run, print the score
distribution and the top-40; the user labels ~30 JDs good/bad; pick `jd_gate` so no labelled-bad JD passes.
The original thresholds were fit to one corpus and WILL be wrong for another field.

## 2. lanes.py - priority-lane regex tiers -> `settings.yaml lanes[].priority`

```yaml
lanes:
  - name: ai-for-materials
    priority:
      exclude: ["robot", "autonomous\\s+(vehicle|driving)", "bioinformatic", ...]
      strong:  ["a\\.?i\\.?[\\s-]*(for|in)[\\s-]*(material|chemistr)", "molecular\\s+dynamics", ...]
      weak:    ["applications?\\s+(engineer|scientist)", "machine\\s+learning", ...]
      anchor:  ["material", "metallurg", "alloy", ...]
```
`is_priority()` keeps its exact 3-rule logic; the regexes are compiled from the first lane that has a
`priority:` block (or OR-ed across lanes). Empty block = no priority lane = function returns False.

## 3. critic.py / screen_minquals.py - knockout rules -> `profile/critic_rules.yaml`

Markers: critic `CHECKS` (12 personal entries), `SOFT`, `INSTRUMENT_OWNER`, `lane_history`; screen `BLOCK`.
```yaml
hard:                       # critic CHECKS and screen BLOCK share these (name -> regex); in MIN quals = fatal
  - {name: "NEVER-CLAIM CORE: DFT/electronic structure", regex: "\\bDFT\\b|density functional|ab initio"}
  - {name: "WRONG DOMAIN: petroleum / bio", regex: "petroleum|reservoir|cell culture"}
  - {name: "CLOSED-LANE: electronics FA (12 applied, 0 positive)", regex: "hardware reliability|PCBA|HALT|HASS"}
soft:                       # warn only
  - {name: "soft: FEA/CFD named", regex: "ANSYS|COMSOL|Abaqus|\\bCFD\\b"}
instrument_owner: {verbs: "(develop|validate|optimize|maintain|calibrat)", instruments: ["EBSD","XRD","EDS"], min_named: 4}
lane_history: {"process/semi": "process engineer|module development", "FA/reliability": "failure analysis|reliability"}
```
Generic entries that stay in code: GRAD-GATE, CONTRACT-GIG (switched by `exclusions.contract_work`),
BELOW LEVEL (hourly/HS), INELIGIBLE (switched by auth flags), clearance/citizen-only blocks, negation and
alternatives guards, the LPR/permanent-resident leniency (switched by `permanent_resident`).
Screen `BLOCK` keys "clearance" and "citizen-only" remain built-in; everything else comes from `hard`.

## 4. keywords.py - lexicon -> `profile/lexicon.yaml` (hook already in place)

```yaml
SEM: {syn: ["scanning electron microscop"], claim: YES}
EDS: {syn: ["EDX", "energy dispersive"], claim: UTIL}
XPS: {syn: [], claim: NEVER}
```
Remaining work: move the in-code `LEX` dict out (ship it as `system/docs/EXAMPLES_FROM_ORIGINAL.md` material /
`system/engine/examples/lexicon_materials.yaml`), make the hedged phrasing for UTIL come from
`approved_claims.yaml hedged_phrases`, and have the onboarding skill seed lexicon.yaml from the
skills inventory (CORE/WORKING -> YES, "used not operated" -> UTIL, NEVER CLAIM -> NEVER).

## 5. feeds.py / sweep.py / hard_ats.py - search terms and in-code registries

Markers: sweep `TERMS`; feeds `KW`, `GETRO`, Adzuna/LinkedIn/Indeed query tuples, `_SR_TENANTS`, `nano()`, `_MISC`;
hard_ats `KW`.
```yaml
lanes:
  - name: process-engineering
    search_terms: ["process engineer", "scale-up", "pilot plant"]     # Workday TERMS + hard-ATS KW + getro KW
    aggregator_queries: ["\"process engineer\"", "\"process development\""]   # Adzuna / LinkedIn / Indeed
```
Registries: already split into `system/engine/registries/packs/*.json` with `boards`, `workday`, `hard`, `misc`,
`watch`. Write `tools/registries.py assemble` that reads `lanes[].packs` + `My Job Search/tracking/registries/custom.json`
and writes the four active files + watchlist.json. `feeds.misc()` should iterate the assembled `misc` list
(kinds bamboo/breezy/jobvite/wprss/rippling/smartrecruiters_search); the NANO custom scraper becomes kind
`custom_html` with its regex in the data or is dropped. `GETRO` and the a16z/ACerS/AIST arms are field-specific
(VC boards, ceramics/steel societies): make them a pack `feeds` section, off unless a pack enables them.

## 6. daily.py leftovers

Markers: `_LANE` closed-lane title annotation -> `lanes[].closed_title_hint` (annotation only, never a drop);
dead `_KEEP`/`_DROP` -> delete; `_US/_NONUS` -> item 1's country handling; `_ELIG_FIX` cache date -> drop the
special case (new workspaces have no pre-fix cache). Also: the tripwire and the `>=60` constant should read
`thresholds.build_default_min_rubric`.

## 7. eligibility.py - role types

Marker: `ELIG` hard-codes buyer/procurement/recruiter/operator/driver. Append `exclusions.role_types` (escaped,
word-bounded) to the compiled regex. Keep intern/co-op/temp/new-grad generic.

## 8. lane_templates.py

Entirely one person's resume prose (`PROJ/RUT/LAN/MAX`), charter-designated emergency-only. Recommend deleting
it from the engine; if kept, make `build()` read `approved_claims.yaml -> lane_templates{lane: {summary, bullets_by_entry, projects, skills}}`.

## Also worth doing (not markers)

- `rubric.py` PROMPT_HEADER: the generic default is in place; the onboarding skill should write
  `profile/rubric_prompt_header.txt` only if the user wants different scorer emphasis.
- `state.py` COLS: "Resume Used", "Custom Ans", "Tier", "Sector" are generic; keep.
- `verify_resume.py` fill window 90-93% is LibreOffice-specific; document in build.md (done).
- The `tracking/lane_ref_finance.md` reference-text idea generalizes well (item 1) and is the right fix for
  "my new lane cannot pass a gate anchored on my old profile" - the original's open structural finding.
- A `tools/doctor.py` that checks: workspace exists, settings.yaml parses, required fields, approved_claims.yaml
  present, evidence files referenced exist, registries assembled, soffice/pdftoppm found.
