# Worked examples - what personal rules and data look like after a few weeks of use

These are NOT rules of jobkit. They show the KINDS of entries a person's `my-rules.md`, `settings.yaml` and
`profile/` files end up holding after a few weeks of real use, so a new user and the onboarding agent know what to
aim for. The person in every example is **Sam, a fictional chemical engineer in Ohio**: B.S. and M.S. in chemical
engineering, five years in specialty-polymer process development at two plants, a U.S. citizen, aiming at industry
R&D and process-engineering roles. Sam does not exist; every number below was invented to show a shape.

## 1. Rules that belong in my-rules.md (dated, with revert conditions)

- **Geographic preference (standing):** "I would rather not have to move." Commutable band listed as the metros Sam
  can reach (Columbus, Dayton, Cincinnati); relocation roles still in scope but the location stated first in the
  report; build bar lowered to 45-59 inside the band (`thresholds.commutable_min_rubric`).
- **Temporary window:** "for the next couple of rounds, prefer roles that start after June" (Sam is finishing a
  plant qualification) - implemented as a queue TAG, not a drop, with the revert condition "ask me in June".
- **Employer exclusion:** "stop building roles at <one chemical company>" - reason not given; matched on
  employer/URL only, never on JD text (other employers mention that company as a customer).
- **Role-type exclusions:** no contract/1099/freelance gigs; no field-service or sales-engineering roles ("anything
  that is really a sales job"); plant-operator and buyer titles out (title-level eligibility drops).
- **Title-blind, everywhere:** "the only thing that matters is a match with the job description. The title
  could be whatever." (This became an engine rule, not a user rule.)
- **Transferable-skill targeting:** "roles that are not polymers but where my scale-up and DOE skills transfer would
  also work" - the home lane stays, the boundary widens; implemented as a second signature set (`role: transferable`).
- **Priority lane:** after applying to one specific scale-up role: "this is the type of job I am looking for; make
  sure jobs like that are screened for and never skipped" - `priority: true` on that lane (`lanes.py`).
- **Salary:** asks researched per role, never anchored to the current salary; the floor came from two offers in hand.
- **Live processes (rolling):** a short list of employers currently interviewing Sam, with dates, so the agent
  avoids duplicates and resolves scheduling conflicts.

## 2. Outcome-driven findings a person may add after an audit (examples of the learning loop)

- **Level/band ceiling:** at n=100 applications, every positive response came from postings with a salary midpoint
  at or below a certain figure, and senior/staff/principal titles produced none - so the critic prints an
  ADVISORY above that ceiling (`thresholds.band_midpoint_ceiling`). Not a knockout; two interviews came from
  roles just under it.
- **Company size does not matter** (a rule from n=30 refuted at n=100) - "do not rank or filter on size".
- **Sector beats lane:** one sector (coatings) converted 4 of 15 with zero rejections; Sam's declared target lane
  (polymers R&D) was 0 of 5. Lesson: a TARGET lane is not a PROVEN converter; keep both facts visible.
- **"Apply within 48 h" not supported by own data:** two of eight positives came from postings 90+ days old.
  Freshness became a tie-breaker, not a priority.
- **Rejection types:** TIMING (req already filled) vs MERIT vs UNKNOWN (form email, the default) vs POST-HM
  (lost after a hiring-manager interview). Never pool them; UNKNOWN is not MERIT.
- **Silence is not ghosting:** replies landed at 12, 18, 19 and 22 days; `report.py` uses a 30-day cutoff.
- **Aggregator-only applications:** 0 of 13 produced a response; all positives came through employer ATSes -
  hence "official links only" became an engine rule.
- **Referrals:** 0 of 90 applications had one; the literature says 2-5x odds -> the REFERRAL STEP (find one
  person per >=60 item; the person decides whether to reach out).

## 3. Claims that failed once (the shape of approved_claims.yaml -> retired_claims / never_claims)

- Instruments: "hands-on" allowed for exactly two (the pilot-scale reactor line, DSC); four others phrased "used in
  process development" (GPC, rheometer, FTIR, the plant DCS); several never claimed (NMR, Aspen HYSYS dynamic
  modelling, Six Sigma Black Belt, PLC programming). An old resume had implied operating an instrument Sam had only
  sent samples to - this is where the operator-pattern audit comes from.
- Publications: "3 total; 1 peer-reviewed, 2 conference" - never "3 peer-reviewed"; a journal was once named as
  published before it had published the paper; the count line was corrected with a dated note and a backup.
- Metrics: two percentage metrics from an internship were RETIRED as unverifiable ("by the person's own
  statement"); replaced with event-based bullets ("qualified the second line into production", "root-caused the
  gel-defect excursion").
- Scope: "Supervised a team" on a role that was individual-contributor -> retired; a "$12M" program figure
  unverified -> retired; "used across three plants" -> no source -> retired. Each retirement is a regex in
  `retired_claims` and a line in the log.
- Tenure: "five years (2021-present, including graduate research)" - always say "including"; no tenure line on
  postings whose years bar exceeds it (it converts an implicit question into an explicit disqualifier).
- Entry freeze: every bullet under one employer must equal an approved constant verbatim (NDA on an unreleased
  product) - the `frozen: true` flag.

## 4. What the inbox-sweep sender map looks like (tracking/inbox_sender_tokens.json)

```json
{"dow": "dow.com", "ppg industries": "ppg.com OR ppgcareers", "3m": "3m.com OR mmm.com", "apple": "apple.com"}
```
Domain-form tokens for employers whose plain name is also a surname or a consumer brand, so personal mail
never matches. The module is OFF by default in jobkit.

## 5. The keyword lexicon (profile/lexicon.yaml) - a few rows to show the four claim classes

| term | synonyms | claim |
|---|---|---|
| DOE | design of experiments | YES |
| GPC | gel permeation chromatography | UTIL (only with the hedged phrasing) |
| NMR | - | NEVER |
| Aspen HYSYS | - | ASK (coursework-level; not on paper until confirmed) |
| scale-up | scale up, pilot plant | YES |
| PLC programming | ladder logic, Allen-Bradley | NEVER (Sam reads the DCS; Sam does not program it) |

Rows are added per posting ("targeting annotation"): when a posting uses a term the lexicon lacks, the person
classifies it, and the classification persists.

## 6. Outreach voice (if modules.outreach is ever turned on)

Advice-seeking, not team intel; no reference to the application; two-sentence identity; ~90 words;
altitude = team lead / senior IC, never VP; one contact per role; nothing sent without approval.

## 7. Geography tiers (settings.yaml location.tier1_regex / tier2_regex)

Tier 1 = commutable + remote, tier 2 = a day's drive, tier 3 = everything else; the quality bar rises with
distance. The onboarding interview writes the two regexes from the place names the person gives in phase 4
("anywhere in the Columbus metro, Dayton, Cincinnati" -> tier 1 with `Remote`; "Pittsburgh, Indianapolis,
Louisville" -> tier 2) and reads them back as a plain list of place words. They only order the list; they never
hide a posting. `settings.yaml.example` shows the shape for a different placeholder city.

## 8. A lane in plain words (settings.yaml lanes[].description)

"A process engineer who takes a polymer or specialty-chemical process from lab to plant: scale-up, DOE,
qualification, troubleshooting on a running line. NOT: pure QC, EHS-only roles, sales engineering, field service."
