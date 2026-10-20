# CHARTER: RESUME BUILD (load when building / tailoring)

## Build from approved lines only (there is no template factory, and no rewording on the fly)
Per posting you choose WHICH approved lines appear and in WHAT ORDER: the summary for the lane, the experience entries
and bullets the entry scorer ranks highest, the projects, the skills lines. Every sentence on the page must equal a
line in `profile/approved_claims.yaml` word for word; `audit_claims.py` refuses anything else. Facts never change and
neither does wording, except by two legal routes: (1) a wording the person already confirmed as equivalent
(`profile/claim_lexicon.yaml`; `keywords.py --category` lists the swaps that apply to this posting), or (2) a new
sentence the person confirms now (read it back, add it to the YAML, then use it). The posting's own words appear on the
resume only through those two routes.

## Source-of-truth chain (nothing reaches a resume without a trail)
`profile/evidence/<job>.md` (RAW FACTS; NDA rules at the top) -> `profile/skills-inventory.md` +
`profile/approved_claims.yaml` (approved phrasings) -> build script -> `tools/audit_claims.py` (MUST pass).
Coursework is never experience: "graduate coursework in X"; teaching = "instructor of record" (stronger).
No build until evidence files + approved_claims.yaml exist and `audit_claims.py` passes (CONSTITUTION I.1, I.8).

## Hard claim rules
- Hands-on vs used: the inventory's HANDS-ON REALITY section decides. Operated tools may be called
  hands-on; tools only used get the hedged phrasing in `approved_claims.yaml hedged_phrases`; NEVER items
  never appear.
- Publications: `profile/publications.md` governs every count; "under review" is never "published".
- Metrics: real numbers only, each with provenance in an evidence file; unverifiable metrics are RETIRED
  (regex in `retired_claims`) and replaced with event-based bullets.
- Frozen entries (`frozen: true`): every bullet under that employer equals an approved constant verbatim.
- Minimum `build.min_experience_entries` (default 3) experience entries. Cut a project or a skills line
  before a job entry; a two-entry resume reads as a thin career regardless of content.

## Process per role
1. Save the full JD to `applications/<Company>_<Role>/JobDescription.txt` (header: fit, dates, APPLY url -
   the employer's own posting).
2. `<jobkit python> system/engine/tools/critic.py <folder>` - HOLD needs a logged override in the build script.
3. `<jobkit python> system/engine/tools/entry_scorer.py <folder>/JobDescription.txt` - advises which experience entries to
   use; overrides are logged in the build-script comments (that disagreement data is deliberately collected).
4. Build script in the application folder, importing `approved_claims` (every tuple/bullet/skills line by
   name) and `resume_builder.Resume`. Never type a claim into a build script that is not in the YAML.
5. Verify: `verify_resume.py <docx> --jd <jd>` -> 1 page · 90-93% LibreOffice fill (Word renders ~1 line
   looser; above 93% risks a page-2 spill) · parse test · date order · readability (summary <= 45 words,
   bullets <= 22 words, <= 4 bullets per entry target) · no repeated adjacent openers · American English.
   `audit_claims.py` PASS. `consistency.py <folder>` PASS or a deliberate, noted difference.
6. Keyword coverage pass (mandatory): `keywords.py <docx> <jd>` - a MISSING-CLAIMABLE term is one the person HAS; it
   reaches the page only by choosing an approved line that contains it, a confirmed lexicon equivalent, or a new
   sentence the person confirms (read back first). UTIL only with the hedged phrasing; ASK -> confirm with the user
   first; NEVER -> report as an honest gap, never add. Recruiters search literal strings, so prefer the approved line
   that carries the exact term over one that carries a synonym.
7. Job card for the user: [FIT · BAND · TIER] + employer apply link first; resume path; honest gaps stated.
Folder = `applications/<Company>_<Role>/`; file ALWAYS `build.resume_filename`.

## Build rules that came from the original project's resume audit (structure doesn't drive interviews; targeting does)
1. The SUMMARY opens with the JD's role noun verbatim ("Process engineer (M.S.) ...", "Research scientist
   ..."). Never re-label the user into a lane they are not in.
2. TENURE line when the JD has a numeric years bar: `approved_claims.yaml tenure.line / short`; say
   "including <graduate research>" when it is counted. No tenure line on reqs whose bar EXCEEDS the user's
   years - it converts an implicit question into an explicit disqualifier.
3. On ENGINEER reqs lead with the engineering title variant of the current role if the YAML defines one;
   teaching/adjunct work goes in a bullet.
4. Readability caps as in step 5; `verify_resume` warns above them and fails at 70/30.
5. Record the apply CHANNEL (company-ATS / Easy Apply / Indeed / referral / email) in state.db at apply
   time; never Easy Apply when a company-site route exists.
6. Cover letter (one page, requirement-by-requirement, in the user's voice) for small/mid companies and any
   form with a free-text box - only if the user wants them; drafts need approval like everything else.
7. Location line: `build.location_line_default` for non-commutable roles; the metro name for commutable
   ones; never the word "local" (banned by the audit).
8. Contact line: phone | email | links | location | work-auth line (`work_authorization.resume_line`).
   City/state prefill (`identity.city_state`) is OFF by default because it may not fit on one line - measure.

## Annotation handling (after the user reviews a build)
FACT -> evidence file; PHRASING -> approved_claims.yaml; TARGETING -> my-rules.md; CORRECTION -> fix the
source FIRST, then check every sent resume for contamination, log it (learning.md). Ask for facts, never
for finished bullets. Every number needs provenance. Every instrument gets operated-vs-used.
