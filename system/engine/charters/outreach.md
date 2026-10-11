# CHARTER: OUTREACH (only when `settings.yaml modules.outreach: true`; OFF by default)

jobkit never sends anything. This charter governs DRAFTS the user may choose to send themselves.

## Altitude
Team senior manager / lead / senior IC - never VP/Director (VPs are not IC hiring managers).

## Framing: informational, never a pitch, never presumes they are the hiring manager
Structure (~90 words): greeting -> identity (2 sentences) -> why them specifically (their trajectory)
-> the ask (a short conversation about THEIR experience) -> light close. Advice-seeking beats
team-intel; no reference to a pending application; one identity clause; no proof-point pitching;
no metrics or paper citations in the note. Second-degree contacts: connection request + <= 300-char note.
The user's own voice, learned from notes they have actually sent, overrides this template.

## Discipline
Draft freely; NOTHING goes out without the user's per-item approval, from the user's own account.
One contact per role. Verify the person is still in seat immediately before the user sends. Public
profiles only; never guess email addresses. No outreach around live interview processes. Log sends the
user reports in state.db `Outreach` column (`state.py set <row> Outreach=<date>:<name>`); outreach-vs-
response is a tracked hypothesis (report.py). Drafts and found contacts live in
`tracking/OUTREACH_DOSSIER.md`.

## Referral step (evidence-backed: referrals raise interview odds 2-5x in multi-firm studies)
For every item judged at or above the build line: find ONE person at the employer (hiring manager, team
lead, or an engineer on the team - via public profiles, company page, paper co-authorship) and draft the
note. The user decides whether to send. Log the person and status in the dossier.
