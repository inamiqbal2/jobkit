# system/examples/marina_example - a FABRICATED workspace for the ACADEMIC path (coral-reef marine biologist, M.S.)

"Marina Example" does not exist. Every fact was invented on 2026-10-09 to show what a workspace looks like after the
onboarding skill has run for a marine biologist with a master's degree who wants (a) funded PhD positions and (b) paid
research jobs (research assistant / technician / lab manager / field scientist / program coordinator) in coral-reef
research, United States incl. territories. It is the first example that uses:
- `settings.yaml build.format: academic_cv` (multi-page CV, 2-3 pages, `resume_builder.AcademicCV`)
- `settings.yaml targets.phd_positions: true` + `targets.fixed_term_ok: true` (PhD studentships / GRAs in scope; fixed-term OK)
- `settings.yaml exclusions.postdocs: false` (an M.S. holder: postdoc titles are dropped)
- the `academic_marine_bio` registry pack (RSS boards, listserv archive, NEOGOV, PageUp, PeopleAdmin, Oracle, Phenom,
  ADP, Workday, custom pages, USAJobs-with-user-key) - see `system/engine/registries/packs/README.md`
- `profile/approved_claims.yaml -> cv:` (education, publications, presentations, field experience, certifications,
  technical skills, teaching, grants/awards, service, references) and `profile/templates/` statements
Nothing here is a template to copy facts from; it is a template to copy the SHAPE from.

Run the engine against it:
```
export JOBKIT_WORKSPACE="$PWD/system/examples/"marina_example
system/.venv/bin/python system/engine/tools/userconfig.py
system/.venv/bin/python system/engine/tools/registries.py assemble
system/.venv/bin/python system/engine/tools/approved_claims.py
system/.venv/bin/python system/engine/tools/daily.py              # live run (network)
system/.venv/bin/python system/examples/marina_example/build_test_cv.py   # the CV + statement test build
```
`tracking/` run artifacts (corpus, caches, state.db, queue) are generated and git-ignored.

## Smoke run 2026-10-09 (live)
See SMOKE_RUN_2026-10-09.md next to this file for the per-source counts, 25 sample titles, the hand labels and the
calibration before/after.

## "run my job search" sample (2026-10-09, v0.2 UX test)
`reports/2026-10-09.md` is the plain-language report the daily skill produced for this workspace on a live run (1,985 postings
seen, 26 scored by two blind judges, 3 CVs built, 2 parked for the user's decision, 19 skipped with a one-line reason each).
The three `applications/*/build.py` scripts are the builds it wrote (approved claims only; the JD files and .docx are run
artifacts and not committed). Re-run: `JOBKIT_WORKSPACE=system/examples/marina_example system/.venv/bin/python system/examples/marina_example/applications/<folder>/build.py`.
