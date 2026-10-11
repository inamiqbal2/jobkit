# CHARTER: LEARNING LOOP & ANNOTATIONS

## The loop is COMPUTED
`<jobkit python> system/engine/tools/report.py` recomputes every standing hypothesis cold from state.db:
H1 domain fit by lane · H2 tier · H3 custom answers · H4 years bar · H5 stretch-vs-clean · outreach
effect · response speed · 30-day ghosting sweep (flags rows; set Status=ghosted only after the cutoff).
`<jobkit python> system/engine/tools/timeline.py`: posting age at apply vs outcome; decision latency; requisition
lifetime; by sector; stale-req watch. TIMING rejections are excluded from merit rates by construction.
`tracking/OUTCOMES_LOG.md` = narrative journal (findings, corrections, method notes). Numbers come
from the programs, never from memory.
Review cadence: every ~10 responses or monthly. Rewrite the rule set (my-rules.md) rather than amend.

## Every response the user forwards
1. `state.py set <row> Status=... "Rejection/Interview=..." "Days to Resp=N" "Reject Type=TIMING|MERIT|UNKNOWN|POST-HM"`.
2. OUTCOMES_LOG row with the hypothesis it bears on. 3. Pattern check at the next review.
Reject Type: TIMING = the req was already decided (explicit "position filled", or the posting vanished from
the employer's board at or just before the mail); MERIT = evidence a human read the packet and passed;
UNKNOWN = form email, the default - never silently treated as MERIT; POST-HM = lost after a hiring-manager
interview - a different event from a screen-out, reported separately ("how deep do we get").

## Annotation protocol (the user's resume feedback -> system)
Classify each note: FACT -> evidence file (+ inventory if it unlocks claims) · PHRASING ->
approved_claims.yaml · TARGETING -> my-rules.md / settings.yaml · CORRECTION -> fix the source FIRST, then
check contamination of already-sent resumes, log in OUTCOMES_LOG. Ask for facts, never finished bullets.
Every number needs provenance. Every instrument gets operated-vs-used. DRAFT -> CONFIRMED-BY-USER.
Proactive: 3-5 open questions at natural moments; thinnest evidence files first.

## Rules for rules
- A rule from n<10 is a hypothesis; write it with its n and the date.
- A "0% lane" with fewer than 3 rejections is censored data, not a closure.
- Falsified rules are struck through with the date and the refuting numbers, not deleted (the history is
  what stops the same rule from being re-adopted).
- An over-broad inventory claim silently steers TARGETING, not just phrasing. CV-inherited claims are
  guilty until verified.
