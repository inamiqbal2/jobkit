# sam_example - the annotated reference for settings.yaml and approved_claims.yaml

"Sam Example" is the fictional chemical / process engineer of `system/docs/EXAMPLES_FROM_ORIGINAL.md`. The two files here
are the FILLED, fully commented versions of the two files a workspace needs most:

- `settings.yaml` - every key the engine reads, with a comment on each
- `profile/approved_claims.yaml` - every section the builder and the audit understand (experience, bullets, skills lines,
  never-claims, retired claims, pending claims, the optional `cv:` block)

They exist so Claude can see the shape of a complete file. The templates that ship in `My Job Search/` are EMPTY on
purpose (placeholders such as `<your name>`, `packs: []`, `experience: []`): a fresh install must not search anyone
else's boards or load anyone else's bullets. Nothing here is ever copied into a real workspace as a fact; the three full
example workspaces (jordan, taylor, marina) show complete folders for other lives.
