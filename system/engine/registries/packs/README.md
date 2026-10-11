# Registry packs - the job-board menu

A pack is a STARTING SET of job boards for a field. The person picks packs in the interview (phase 15), names
employers they would love to work for (`discover_boards.py` finds and verifies those boards), and the
discovery arms (Adzuna with its free official key; LinkedIn / Indeed only if they opt in) add the rest.
Every active entry in a pack was fetched live the day it was added (the count is in its note); re-verify any
board before relying on it, and read the pack's `source` line for what FAILED that day and why.

## The menu (plain words, for the person)
| pack | say it as | what is in it (live counts on the date in the file) |
|---|---|---|
| `healthcare_clinical` | "Hospitals and clinical employers" | Cleveland Clinic, Mass General Brigham, Intermountain, Denver Health, GoHealth, CVS/MinuteClinic (Workday); Mayo Clinic, Mount Sinai, UC Health Cincinnati (Oracle); Kaiser Permanente, Cedars-Sinai, CommonSpirit, Children's Hospital Colorado (careers sites); VA and other federal clinical jobs through USAJobs with your key. Watching by hand: HCA/HealthONE, UCHealth Colorado, NYU Langone, UPMC, Johns Hopkins (their sites refuse automated reading). 2026-10-11 |
| `tech_software` | "Big tech and software companies" | 32 Greenhouse boards (Stripe 728, Databricks 892, Cloudflare 424, Datadog 435, Anthropic 645, DoorDash 463, Waymo 372, ...), 7 Ashby (OpenAI 815, Snowflake 358, Notion 132, Ramp, Plaid, Linear, Supabase), Palantir (Lever), Canva, and 8 Workday tenants (NVIDIA, Adobe, Salesforce, PayPal, Autodesk, HP, Zendesk, Workday). Watching: Shopify, Atlassian, Zoom. 2026-10-11 |
| `government_public` | "Government jobs: federal, state, city, county" | USAJobs with your key; 44 NEOGOV portals (Washington 745, Colorado 518, Michigan 526, Hawaii 463, Pennsylvania 583, Massachusetts; LA County 409, LA, Houston, San Antonio, San Diego, San Jose, Oakland, Sacramento, Seattle, King County, Portland, Boston, Honolulu, DC, Detroit, Nashville, Columbus, Indianapolis, Louisville, Raleigh, Albuquerque, Cleveland, Cincinnati, Pittsburgh, Minneapolis, Las Vegas; Harris, Travis, San Bernardino, Riverside, Contra Costa, Santa Clara, Fairfax, Montgomery MD, Hennepin, Clark, Broward counties); New York State (1,761 vacancies), NYC, Maryland, Oregon (Workday), Florida (SAP), Philadelphia (SmartRecruiters). Watching: California, Texas, Chicago, Virginia, Phoenix, Dallas, Austin. 2026-10-11 |
| `nonprofit_social` | "Nonprofits, foundations, advocacy, NGOs" | ACLU, Wikimedia, Mozilla, Code for America, GiveDirectly, Human Rights Watch, RTI, Sunrise, ProPublica, MSF-USA (Greenhouse); Planned Parenthood Federation, charity: water, Brookings, Sierra Club, Common Cause (Lever); American Red Cross 363, Teach For America, Habitat for Humanity (Workday); United Way (ADP); Chronicle of Philanthropy keyword feed. Watching: Idealist, Work for Good, Bridgespan, Foundation List, IRC, Mercy Corps, Save the Children, Feeding America, WWF. 2026-10-11 |
| `education_general` | "Colleges, universities, schools" | AcademicJobsOnline (343, every field), Chronicle of Higher Education and Inside Higher Ed keyword feeds, University of Hawaii system (723), KIPP 508, Uncommon Schools 102, Achievement First 62, Khan Academy; federal education jobs through USAJobs with your key. Watching: SchoolSpring, K12JobSpot, EdJoin, HigherEdJobs (recipe for its category feeds inside the file). 2026-10-11 |
| `business_marketing_sales` | "Big employers for business, marketing, sales, operations" | 12 Workday tenants that post generically: Salesforce, P&G 362, Target, Home Depot 220, Mastercard, Visa, PayPal, Disney, T-Mobile, 3M 229, Truist 302, PNC 216. Small on purpose: discovery arms and your own employers do most of the work here. 2026-10-11 |
| `academic_marine_bio` | "Academic marine biology" | academic job boards (RSS), a listserv archive, NEOGOV / PageUp / PeopleAdmin / Oracle / Phenom / ADP / Workday HR systems of US marine institutions, marine labs and NGOs, USAJobs with your key. 2026-10-09 |
| `materials_semiconductor` | "Materials, metals, batteries, semiconductor equipment" | 52 boards / 19 Workday / 15 hard-ATS / 2 misc / 4 watch (from the original project, 2026-10-07) |
| `nuclear_aerospace` | "Nuclear, fusion, launch, satellites, defense, national labs" | 62 / 10 / 9 / 7 / 3 (2026-10-07) |
| `finance_quant` | "Trading firms, banks, asset managers, insurers" | 24 / 11 / 3 / 0 / 0 (2026-10-07) |
| `ai_for_science` | "AI-for-science labs and scientific-software vendors" | 14 / 1 / 0 / 2 / 12 (2026-10-07) |
| `consulting` | "Consulting (advanced-degree and experienced-hire)" | 0 / 2 / 2 / 0 / 5 (2026-10-07) |
| `life_sciences_pharma` | "Pharma and medical devices" | 0 / 4 / 0 / 0 / 0 (2026-10-07) |
| `deeptech_other` | "Robotics, autonomy, quantum, climate, AI infrastructure" | 52 / 1 / 2 / 0 / 3 (2026-10-07; review before enabling) |

The seven older packs were split from the original project's registries by company, by the agent that built
them, from public knowledge of each company; a handful of ambiguous slugs (e.g. `lattice`, `espace`,
`roadrunner-studios`, `until`, `dodmg`, `canopy-ad`, `inertia`, `union-tech`) landed in `deeptech_other` or
`nuclear_aerospace` on a best guess. Two boards were reported dead by the source on 2026-10-07 (`mat3ra`,
`deepmind` Greenhouse 404) and are carried unchanged. International sources are parked (`international` key,
ignored by the assembler) until a non-US scope exists.

## Adding your own employers
`system/.venv/bin/python system/engine/tools/discover_boards.py "Employer Name" [...] --assemble` probes the public job-board
APIs under variants of the name, web-searches the employer's careers page and scans it for an embedded ATS,
verifies every candidate with a live call, and appends verified entries to `My Job Search/tracking/registries/custom.json`
(unverifiable employers become MANUAL watch entries with the careers URL). It is what onboarding phase 15 and
the "add employer <name>" command run. Limit: a board found through the web search is verified as a live board,
not as THAT employer's board; a namesake can be picked up, so the output names the host and Claude reads it back.

## File shape
```json
{"pack": "...", "description": "...", "source": "...",
 "boards":  [["gh"|"lever"|"ashby"|"workable"|"smartrecruiters", "<slug>", "<note or job count>"], ...],
 "workday": [["<host>", "<tenant>", "<site>", "<note or count>"], ...],
 "hard":    {"oracle": [...], "adp": [...], "eightfold": [...], "phenom": [...], "sap_html": [...], "icims_html": [...]},
 "misc":    [{"kind": "bamboo|breezy|jobvite|wprss|rippling|smartrecruiters_search|custom_html", "name": "...", "base": "..."}],
 "feeds":   [{"kind": "getro|ats_links|rss|html_links|pipermail|neogov|json_list|usajobs", "name": "...", "base": "..."}],
 "watch":   [{"name": "...", "ats": "gh|lever|ashby|greenhouse|MANUAL|...", "slug": "...", "watch_for": ["..."]}]}
```
Keys starting with `_` (e.g. `_howto`) and `international` are ignored by the assembler.
`misc` and `feeds` are both consumed by `feeds.py` (via the assembled `feeds_registry.json`); `misc` = one fetch per
small-ATS company, `feeds` = keyword-searched boards (searched with `queries.yaml -> board_terms`). A `custom_html`
entry carries its own `card_regex` (positional groups title, location[, url] - or named groups `title`, `loc`, `url`,
`id`, `posted` with `url_template` "{id}", `loc_default`, `posted_format`).

### Feed kinds (feeds.py; every kind is generic and config-driven - a new source is a JSON entry, not code)
| kind | entry keys | what it fetches |
|---|---|---|
| `rss` | `base` (optional `{kw}`), `loc_regex`, `headers` | RSS 2.0 or RSS 1.0 items; `{kw}` = one fetch per board term, else the whole feed |
| `html_links` | `base` (optional `{kw}`), `href_regex` and/or `title_regex`, `headers` | anchors of a server-rendered listing (PageUp `/en-us/job/\d+`, PeopleAdmin `/postings/\d+`, Radancy careers sites `/job/<city>/<title>/<n>/<n>`, NY State vacancy table, NYC Jobs) |
| `custom_html` | `base`, `card_regex`, `url_template`, `loc_default`, `posted_format`, `headers` | one careers page, one regex |
| `pipermail` | `base` (archive root), `subject_regex`, `strip_regex` | a Mailman archive, READ-ONLY: this month's `date.html` subject index. Archives only - never subscribe or post from the engine |
| `neogov` | `host`, `agency` | governmentjobs.com / schooljobs.com agency board (JSON `loadJobsOnMaps`); descriptions cached for the screen |
| `json_list` | `base`, `root`, `fields{title,loc,url,posted,desc,id}`, `url_template`, `headers` | any public JSON listing; `desc` cached |
| `usajobs` | `days`, `organization` | USAJobs API; idle until `keys.json` has `usajobs_key` + `usajobs_email` (the person's free key). Named `usajobs` in every pack so the assembler keeps one copy |
| `getro`, `ats_links`, `smartrecruiters_search`, `bamboo`, `breezy`, `jobvite`, `wprss`, `rippling` | as before | |
`headers` on any entry overrides the request headers (a full browser User-Agent gets past Incapsula / Cloudflare fronts
that answer the bare engine UA with a challenge page: HigherEdJobs, Radancy sites, Mote, CRF).

### What was live-verified and what failed when each pack was built
The `source` line of every pack file lists the failures of that day. Highlights:
- 2026-10-11 (v0.3 generic packs): Bing answers automated searches when the employer name is quoted and nothing is
  appended (`"Cleveland Clinic" careers`); DuckDuckGo shows a bot challenge after a handful of queries. Workday's
  landing pages answer 406 to any automated GET; the CXS POST is the verifier (HTTP 200 + `jobPostings`; 422 = wrong
  tenant/host). HigherEdJobs' feed index is Incapsula-walled and the site blocked this IP after a category scan.
  Hospital sites on Akamai/Phenom fronts (HCA, UCHealth, Johns Hopkins) answer 403 to automation. NYU Langone and
  UPMC render search results in the browser only. jobs.kaiserpermanente.org fails the certificate chain; the
  kaiserpermanentejobs.org site works. Idealist has no RSS; Work for Good's board is gone; EdJoin/SchoolSpring/K12JobSpot
  are browser apps. USAJobs answers 401 without a key (registered, idle).
- 2026-10-09 (`academic_marine_bio`): see the file's notes (Nature/Science RSS, Conservation Job Board, AJO, HigherEdJobs
  categories 100/103/108, ES_JOBS_NET archive, Hawaii NEOGOV, FIU JSON, UF/NSU PageUp, Guam PeopleAdmin, TAMU RWFM,
  UC Recruit, Mote, CRF, WHOI Workday, USF Oracle, Miami Phenom, Florida SAP, Ocean Conservancy ADP). Failed: ECOLOG-L,
  Coral-List, FindAPhD, SCB, Sea Grant, ASLO, AAUS, MTS, Smithsonian OHR, RCUH, TNC, UCSD staff, WWF-US, Reef Check, CORAL.

## How packs are selected
`My Job Search/settings.yaml -> lanes[].packs: ["healthcare_clinical", ...]`. The union of the selected
packs plus `My Job Search/tracking/registries/custom.json` (same shape, the user's own additions) becomes
the ACTIVE registries the tools read:

| active file (My Job Search/tracking/registries/) | built from |
|---|---|
| `registry.json` | `boards` -> `[kind, slug, note]` |
| `wd_registry.json` | `workday` -> `[host, tenant, site, note]` |
| `registry2.json` | always `[]` (legacy; Workday entries go in wd_registry.json) |
| `hard_registry.json` | `hard` merged per arm + `"_readme"` |
| `feeds_registry.json` | `{"feeds": misc + feeds}` |
| `../watchlist.json` | `{"companies": watch}` |

Run `<jobkit python> system/engine/tools/registries.py assemble` after changing `lanes[].packs` or `custom.json`
(`list` shows the packs, `check` reports entries carrying a dead/re-verify note).
