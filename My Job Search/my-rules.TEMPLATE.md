# USER RULES - <name> (workspace-owned; loaded after system/engine/CONSTITUTION.md every session)

This file holds the rules that are TRUE FOR YOU and would be wrong for anyone else. The engine's
constitution cannot be relaxed here; it can only be made more specific. Write rules as dated
entries. Rewrite (consolidate) monthly; do not let the file grow by accretion.

Format for every entry:
`## <YYYY-MM-DD> - <RULE NAME> (standing | temporary until <date> | retired <date>)`
followed by 1-5 lines: the rule, how the pipeline applies it, and what would revert it.

See `system/docs/EXAMPLES_FROM_ORIGINAL.md` for the kinds of rules that have proven useful.

## <date> - TARGET IN PLAIN WORDS (standing)
What you are looking for, in two sentences a stranger could act on. Lanes are in settings.yaml;
this is the "why" and the priority order between them.

## <date> - GEOGRAPHY (standing)
Commutable area, relocation stance, how location changes the build bar
(settings.yaml: location.*, thresholds.commutable_min_rubric).

## <date> - EMPLOYER EXCLUSIONS (standing)
Employers never to build for, with the reason or "reason not stated". Mirror the list in
settings.yaml -> exclusions.employers (that is what the code reads; this is the explanation).

## <date> - ROLE-TYPE EXCLUSIONS (standing)
Contract gigs, postdocs, management-only, sales, etc. Mirror settings.yaml -> exclusions.

## <date> - SALARY (standing)
Floor and target (settings.yaml -> salary). How a posted band above/below changes judgment.

## <date> - TEMPORARY WINDOWS (temporary until <date>)
E.g. "prefer non-export-controlled roles for the next two rounds". State the revert condition.

## <date> - LIVE PROCESSES (rolling)
Employers you are currently interviewing with. The pipeline must not run outreach around them and
must flag duplicates. Update on every change.

## <date> - ANNOTATIONS LOG (rolling)
Your feedback on built resumes, classified FACT / PHRASING / TARGETING / CORRECTION
(system/engine/charters/learning.md). FACTs go to profile/evidence; PHRASINGs to approved_claims.yaml;
TARGETINGs stay here; CORRECTIONs fix the source first, then check sent resumes.
