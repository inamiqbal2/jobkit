# tracking/registries - the ACTIVE job-board registries the tools read (inside My Job Search/)

Generated files (git-ignored): `registry.json`, `wd_registry.json`, `registry2.json`, `hard_registry.json`,
`feeds_registry.json`, `../watchlist.json`, `li_discovery.jsonl` (discovery output), `*.bak-<date>`.

They are ASSEMBLED by `system/engine/tools/registries.py assemble` from:
1. the packs you enabled in `settings.yaml -> lanes[].packs` (`system/engine/registries/packs/*.json`), and
2. `custom.json` in this folder - your own employers, same shape as a pack (see `custom.json.example`).

```
system/.venv/bin/python system/engine/tools/registries.py list       # packs and what each contributes (* = selected)
system/.venv/bin/python system/engine/tools/registries.py assemble   # (re)write the active files; old ones kept as .bak-<date>
system/.venv/bin/python system/engine/tools/watch.py --init          # first watch-list snapshot
```
Re-run `assemble` whenever you change `lanes[].packs` or `custom.json`.

`queries.yaml` (copy `queries.yaml.example`) holds the search terms for every keyword-searched arm (Workday,
hard-ATS, keyword boards, Adzuna, LinkedIn, Indeed). Empty lists leave that arm idle.

Never delete a registry entry without the user's approval (CONSTITUTION I.7); mark dead boards with a
note and a date in `custom.json`, or drop the pack from `settings.yaml`.
