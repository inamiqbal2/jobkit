# Skills & Claims Inventory - canonical source for every resume (created <date>)

> Every line here is a CLAIM the user has confirmed. The resume may use these words; the audit
> (tools/audit_claims.py) blocks everything under NEVER CLAIM. Status of each section:
> DRAFT | CONFIRMED-BY-USER. Nothing DRAFT reaches a resume.

## CORE - may lead a summary
Skills you would defend in a hostile technical interview. 5-10 items, each with where it was
exercised (evidence file).
- <skill> - <evidence/<file>.md>

## WORKING - bullets and skills lines, never the lead
Skills you have used on real work but would not call yourself an expert in.
- <skill> - <evidence file>

## FAMILIAR - skills-list mention at most; NEVER a pitch or summary lead
Coursework-level or read-about. Phrased as "coursework in X" or "familiar with X" only.
- <skill>

## HANDS-ON REALITY (the audit-critical section)
For every instrument / tool / platform in the JDs you target, exactly one of:
- OPERATED (hands-on): <list>  -> may be called "hands-on"
- USED, NOT OPERATED (data used in R&D): <list> -> always phrased with a hedge (approved_claims.yaml hedged_phrases)
- NEVER: <list> -> never appears on a resume in any form

## MANDATORY PHRASING (copy verbatim)
The exact skills-line text for the hands-on/used distinction, as it appears in
approved_claims.yaml -> skills_lines. Never paraphrase it.

## NEVER CLAIM (fabrication or known-shallow - hard NOs regardless of JD)
Mirrors approved_claims.yaml -> never_claims.forbidden_terms. One per line with the reason.
- <term> - <reason>

## EXPERIENCE ENTRIES - the full set
One line per entry in approved_claims.yaml -> experience: key, org, dates, role, what it is USED FOR
(which JDs it strengthens), and NDA constraints.

## COURSEWORK & TEACHING (verified from transcripts / syllabi)
Teaching > coursework > nothing. Coursework is NEVER phrased as experience.

## APPROVED METRICS (real numbers only - each with its home)
- <number> - <what it measured, over what baseline> - <evidence file:line>

## SUMMARY TEMPLATE (all lanes)
"<Role noun from the JD> (<degree>) with <tenure line> ... " - see charters/build.md rule 1.
