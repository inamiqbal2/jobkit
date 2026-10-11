# CHARTER: SEARCH & TARGETING (load when discovering / screening roles)

Generic method. Personal targeting (lanes, geography, exclusions, salary, temporary windows) lives in
`My Job Search/settings.yaml` and `My Job Search/my-rules.md`; read both before judging a queue.

## Daily spine - run the PROGRAM, don't improvise the ritual
`<jobkit python> system/engine/tools/daily.py [window_days] [screen_top_n]` =
watch -> (inbox sweep plan, if enabled) -> corpus+match -> Workday sweep -> feeds -> hard-ATS ->
dedupe (applied set, ledger, mirrors, caches) -> min-quals screen -> JD-text gate -> critic ->
`tracking/queue_<date>.md` -> rubric prep. Agent judgment starts at the queue.

## Title-blind, everywhere (engine rule)
No stage may drop or admit a posting on its TITLE. Fit is decided by (1) the JD-text match
(`match.judgment_gate`: the same fixed scales and bar for the corpus arm and for every screened item; the
signature terms, thresholds and lane gates are `profile/signals.yaml`) and (2) the two-blind rubric. The only title-based drops are ELIGIBILITY (intern / co-op / temp /
non-professional; `tools/eligibility.py` + `exclusions.role_types`). Search TERMS are breadth, not gates.

## Rubric ritual (after daily.py)
1. `rubric.py prep` wrote `tracking/rubric/batch_<date>.json` and `prompt_<date>.txt`.
2. Spawn TWO independent blind scoring subagents. Each sees ONLY the prompt file (profile_blind.md + JD
   paths). Never give them match scores, critic verdicts, outcomes, or each other's output.
3. `<jobkit python> system/engine/tools/rubric.py merge <run_A> <run_B>` averages, auto-ledgers clear rejects, re-orders.
4. Judge top-down. `⚠Δ` = the runs disagreed by >= 15 points: read that JD yourself.
Benchmark basis (original project, 27 labelled JDs, 5 real interview-producers): blind rubric AUC 0.91
vs deterministic matcher 0.58. Single scores wobble up to 20 points on borderline cases - that is why
two runs are averaged and large disagreements are flagged, never trusted.

## Threshold policy (settings.yaml thresholds; defaults 60 / 45 / 40)
1. `>= build_default_min_rubric` -> BUILD BY DEFAULT. A skip requires hard ineligibility or a never-claim
   QUOTED FROM THE REQUIRED BLOCK, written into the ledger row.
2. `commutable_min_rubric .. build_default-1` -> BUILD if a user rule says so (commutable area, a lane the
   user asked to stretch into, PhD/degree-credit years language, a responding sector). Otherwise skip,
   naming the specific required-block gap.
3. Below the commutable line -> the user's call, or a `⚠Δ` read.
4. `< auto_skip_below_rubric` -> auto-ledgered by `rubric.py merge` ONLY when both runs agree (Δ<15), the JD
   is not a stub, and the item is not in a protected archetype or the priority lane.
5. NEVER a skip ground alone: an agency's pay band; a working condition; a never-claim outside the required
   block; a lane's "0%" with fewer than 3 rejections; a years bar when the JD credits an advanced degree;
   a judgment made on a truncated JD (fetch the full text first - employer page over aggregator stubs).
6. TRIPWIRE: fewer than 3 pipeline-originated builds in any 7-day window while items above the build line
   exist is a judgment defect - audit that day. "Maximize success, not volume" does NOT mean fewer builds.
7. "When in doubt, build." Drafting is free; the user decides what is sent.

## Processing order within the queue
Rubric order first. Within ties: fit class CLOSE -> STRETCH -> LOOSE; recency FRESH (<=7 d) -> RECENT
(8-14 d) -> OPEN; geography tier T1 -> T2 -> T3. Fresh close-fit roles are perishable; long shots are not.

## Tiers (geography)
T1 = commutable + remote (`location.tier1_regex`); T2 = nearby (`tier2_regex`); T3 = everything else.
Quality bar rises with distance. Relocation stance (`location.relocation`) decides whether T3 is presented
at all and how: when "case-by-case", state the location in the first line of every card.

## Recency (UPDATED date, not first-published)
The window and the FRESH/RECENT bands run on the posting's UPDATED date (GH `updated_at`, Lever
`updatedAt`, Ashby `updatedAt`, Workday `postedOn`; fallback = posted). A req touched recently is an
actively-hiring req even if posted months ago. Hazard managed, not ignored: ATSs auto-bump evergreen reqs,
so the queue shows BOTH ages ("0d (posted 117d)") and the match-score bar keeps unmatched bumped junk out.
TRUE posted date is still captured on every record (`Date Posted` in state.db = first publish).
Freshness is a tie-breaker, not a priority: the original project's own data showed positives from reqs
90+ days old.

## Eligibility (settings.yaml work_authorization + exclusions) - the only hard drops
Citizenship-only, clearance, export-control and sponsorship gates are knockouts ONLY according to the
user's flags; the engine assumes nothing. Negated statements ("no clearance required"), conditional
boilerplate ("may be contingent upon ability to obtain") and alternatives lists ("one or more of") never
trip a knockout (`_hit` / `_elig_hit` guards). An explicit "permanent residents are eligible" sentence
overrides a clearance line (soft flag, routed to judgment). Employer exclusions match SOURCE/URL only.

## Verification
Card = fetched live JD from the employer's ATS. Links = employer URLs, never aggregators (Article I.6).
Ashby trap: hosted page can 404 while the API is live - use the company-embed `?ashby_jid=` URL.
Capture the LISTED salary band into `Salary Range` (pass 1) on every card; market corroboration (pass 2)
at build/apply time. Watch list: `tracking/registries/watchlist.json` + `tools/watch.py` (diff-based).

## Discovery loop (weekly)
The registry only knows boards somebody registered. Weekly: 2-3 ATS dorks via web search
(`site:job-boards.greenhouse.io "<lane term>"`, same for jobs.lever.co / jobs.ashbyhq.com), probe each new
slug, add live boards to the active registry (`tracking/registries/custom.json`, then re-assemble).
Discovery arms (LinkedIn/Indeed/Adzuna, per `run.*`) print `NEW-COMPANY` lines into
`tracking/registries/li_discovery.jsonl`; review them daily, register the ones with real in-lane roles.
Employers on ATSs with no API go on the watch list as MANUAL instead of being silently absent.

## Arms and their honest limits
- corpus arm (GH/Lever/Ashby/Workable/SmartRecruiters): full JD text, title-blind, the backbone.
- Workday: keyword search only (API cannot bulk-return text) - one paced task per tenant, Retry-After
  honoured, per-tenant cooldown on repeated 429s. Terms are lane data.
- hard-ATS (Oracle/ADP/Eightfold/Phenom/SAP/iCIMS): keyword recipes per employer; fragile; re-verify quarterly.
- LinkedIn guest cards (48 h), Indeed via JobSpy (72 h, JDs cached at ingest), Adzuna (7 d, needs a key):
  rate-limited and unversioned; errors degrade to zero results and never block the run.
- Mirror collapse: an aggregator copy of a job that also exists from another source (same title, employer,
  city) is ledgered DUPLICATE; two official postings are never mirrors; one aggregator twice is two listings.
- Caches: INELIGIBLE/EXPIRED URLs 14 d; JD-gate NOISE 7 d keyed by canonical URL + JD md5; FETCHFAIL is
  transient and retried every run.

## Stub-JD guard and REOPEN
A permanent skip must never rest on unread text: a saved JD under 700 chars or without any
qualifications/responsibilities language is a STUB and goes to the human, never to the auto-ledger.
`decide.py <url> REOPEN` puts a job back in scope without deleting a ledger line (last decision wins).

## Judgment hygiene
- Every judged item is ledgered with `decide.py` (SKIP/BUILT/APPLIED/WATCH/REOPEN + reason). Unlogged = it
  will re-surface tomorrow.
- Read the REQUIRED block, not the preferred block, before citing a never-claim.
- Prefer the employer's full posting over any aggregator text when they differ.
- Level/band: `thresholds.band_midpoint_ceiling` (if set) makes the critic print an advisory above it;
  senior/staff/principal titles get an advisory to check the years bar against the tenure line. Advisories
  inform the build; they never block it.
- Sector vs lane: keep both columns in state.db. A TARGET lane is not a PROVEN converter.

## Calibration ritual (first week on a new workspace, and after any lane change)
The gate (`match.judgment_gate`) is: `score >= jd_gate AND (sig >= sig_min OR (sigx >= sigx_min AND sig > sig_floor))`,
else a per-lane LANE GATE (`sigx`, domain signature and cosine to a `lane_ref` text all above their minimums, and
the JD is not a stub). All four thresholds, every term and every lane gate live in `profile/signals.yaml`.
An EMPTY signals.yaml runs cosine-only (sig_min 0, no rescue, no lane gates) and warns on every run.
1. Run `corpus.py` + `match.py`; read the score distribution and the top 40 (title-blind).
2. Label ~30 JDs good/bad by hand. Set `thresholds.jd_gate` so no labelled-bad JD passes. Read the `sig`
   and `sigx` of the labelled-good ones: `sig_min` = the smallest sig a good JD carries (a labelled-good JD
   with sig near zero means a MISSING home term - add it); `sigx_min` = above the sigx of the junk JDs.
3. A target field the home profile cannot reach on cosine (the original's finance lanes: 3 of 208 live JDs
   passed the bar) gets a `role: gate` lane: write `profile/lane_ref_<lane>.md` as a plain description of the
   REQUIRED WORK (never a claim about the candidate), add 10-20 domain terms, and set `gate.domain_min` /
   `gate.cos_min` from the labelled-good JDs of that field against the full corpus (report recall and leakage).
4. Record the table in `my-rules.md` with the date. Re-run after every signature-term change and
   report "gate pass before -> after, 0 lost" (the standing corpus test).

## Learning hooks (see learning.md)
Reject Type TIMING / MERIT / UNKNOWN / POST-HM on every rejection; posting age at apply recorded; the
watch list's GONE events mark TIMING before the mail lands.
