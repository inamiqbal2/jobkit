# system/examples/jordan_example - a FABRICATED workspace for a registered nurse (clinical / hospital track, one-page resume)

"Jordan Example" does not exist. Every fact was invented on 2026-10-11 to show what a workspace looks like after the
onboarding skill has run for a registered nurse (BSN 2019; four years medical-surgical/telemetry, two years medical ICU;
BLS, ACLS, CCRN; Denver; U.S. citizen; no relocation) who wants an ICU / critical-care staff nurse job or a unit-based
clinical educator role at a hospital system, salary floor $85,000, one-page resume. It is the first example of the v0.3
field-neutral path:
- `settings.yaml targets.track: industry`, `targets.hourly_ok: true` (bedside nursing is hourly), `targets.employers` (five
  Denver-area systems that `system/engine/tools/discover_boards.py` registered or parked as watch entries - see custom.json)
- the `healthcare_clinical` pack; LinkedIn / Indeed arms OFF (opt-in), Adzuna off (no key); no USAJobs key (not a
  government track, so the interview skipped it)
- phases 9, 11 and 12 (publications, teaching, references) marked not applicable; certifications asked generically
  (RN license, BLS, ACLS, CCRN) and printed as a skills line
Nothing here is a template to copy facts from; it is a template to copy the SHAPE from.

Run the engine against it:
```
export JOBKIT_WORKSPACE="$PWD/system/examples/"jordan_example
system/.venv/bin/python system/engine/tools/userconfig.py
system/.venv/bin/python system/engine/tools/registries.py assemble
system/.venv/bin/python system/engine/tools/approved_claims.py
system/.venv/bin/python system/engine/tools/discover_boards.py --dry-run     # what it finds for the five employers in settings.yaml
system/.venv/bin/python system/engine/tools/daily.py                          # live run (network)
system/.venv/bin/python system/examples/jordan_example/build_test_example.py  # the one-page resume test build
```
`tracking/` run artifacts (corpus, caches, state.db, queue) are generated and git-ignored.

## Live run 2026-10-11
`reports/2026-10-11.md` is the plain-language report the daily skill produced for this workspace on a live run: healthcare
pack + the five discovered employers -> 886 postings read in full (Denver Health 153, GoHealth 276, Mayo 93, CVS 64, Mount
Sinai 63, UC Health Cincinnati 57, CommonSpirit 47, Cedars-Sinai 39, Kaiser 38, Mass General Brigham 29, Cleveland Clinic 22,
Children's Colorado 5) -> 157 passed the title-blind gate -> two blind judges (each run split into three parallel scorers of
~52 postings, concatenated into run_A / run_B, then `rubric.py merge`) -> 97 auto-set-aside (<40, both agreeing) -> 60 judged:
1 BUILT (Denver Health MICU, judges 94/100), 15 WATCH (Denver postings above the line, queued for the person), 44 SKIP
(out of area, not an RN role, permanent charge). The resume: 1 page, 91% fill, parse 5/5, readability warn only, audit PASS,
consistency n/a (first build). `applications/DenverHealth_RegisteredNurse_MedicalICU/build.py` is committed; the JD file and
the .docx are run artifacts and not committed. Two phrasing corrections came out of the build (a 34-word bullet split; the
never-claim "ECMO specialist" narrowed to an operator pattern so the approved hedge "run by the ECMO specialist" passes).
