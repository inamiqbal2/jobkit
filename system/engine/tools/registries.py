#!/usr/bin/env python3
"""REGISTRIES - assemble the ACTIVE job-board registries a workspace runs on.

  <jobkit python> system/engine/tools/registries.py assemble        # write the active files from the selected packs + custom.json
  <jobkit python> system/engine/tools/registries.py list            # show the packs and what each contributes
  <jobkit python> system/engine/tools/registries.py check           # report dead/duplicate entries (no writes)

Inputs
  settings.yaml -> lanes[].packs                      pack names from system/engine/registries/packs/*.json (union)
  My Job Search/tracking/registries/custom.json       the user's own entries, same shape as a pack (optional)
Outputs (My Job Search/tracking/registries/ unless noted; every file is REWRITTEN, a dated .bak of the old one is kept)
  registry.json        [kind, slug, note]                 corpus.py (gh/lever/ashby/workable/smartrecruiters full text)
  wd_registry.json     [host, tenant, site, note]         sweep.py (Workday keyword search)
  registry2.json       []                                 legacy; kept empty (Workday goes in wd_registry.json)
  hard_registry.json   {arm: [entries], "_readme"}        hard_ats.py (oracle/adp/eightfold/phenom/sap_html/icims_html)
  feeds_registry.json  {"feeds": [entries]}               feeds.py (packs' `misc` + `feeds` sections)
  ../watchlist.json    {"companies": [entries]}           watch.py
Duplicates (same kind+slug / host+tenant+site / arm+name / name+base) are collapsed, first one wins.
A pack entry is never deleted by this tool; to retire a board, remove the pack from settings.yaml or note it in custom.json.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json, os, sys, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS, REGISTRIES, ENGINE, selected_packs, path as _wspath

PACKS_DIR = os.path.join(ENGINE, "registries", "packs")
CUSTOM = os.path.join(REGISTRIES, "custom.json")
WATCHLIST = _wspath("tracking", "watchlist.json")


def _packs():
    return {os.path.basename(p)[:-5]: json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(PACKS_DIR, "*.json")))}


def _selected():
    packs = _packs()
    names = selected_packs()
    missing = [n for n in names if n not in packs]
    if missing:
        print(f"registries: settings.yaml names packs that do not exist: {missing} (available: {sorted(packs)})", file=sys.stderr)
    out = [(n, packs[n]) for n in names if n in packs]
    if os.path.exists(CUSTOM):
        try:
            out.append(("custom", json.load(open(CUSTOM, encoding="utf-8"))))
        except Exception as e:
            print(f"registries: custom.json unreadable ({e}) - skipped", file=sys.stderr)
    return out


def _backup(p):
    if os.path.exists(p):
        b = f"{p}.bak-{datetime.date.today().isoformat()}"
        if not os.path.exists(b):
            os.replace(p, b)


def _write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    _backup(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def assemble(verbose=True):
    sel = _selected()
    boards, wd, hard, feeds, watch = [], [], {}, [], []
    seen = set()
    for name, p in sel:
        for b in p.get("boards", []) or []:
            if len(b) < 2: continue
            k = ("b", str(b[0]), str(b[1]))
            if k in seen: continue
            seen.add(k); boards.append([b[0], b[1], b[2] if len(b) > 2 else ""])
        for w in p.get("workday", []) or []:
            if len(w) < 3: continue
            k = ("w", str(w[0]), str(w[1]), str(w[2]))
            if k in seen: continue
            seen.add(k); wd.append([w[0], w[1], w[2], w[3] if len(w) > 3 else ""])
        for arm, entries in (p.get("hard", {}) or {}).items():
            if arm.startswith("_") or not isinstance(entries, list): continue
            for e in entries:
                k = ("h", arm, str((e or {}).get("name", "")).lower())
                if k in seen: continue
                seen.add(k); hard.setdefault(arm, []).append(e)
        for e in (p.get("misc", []) or []) + (p.get("feeds", []) or []):
            if not isinstance(e, dict) or not e.get("kind"): continue
            k = ("f", e.get("kind"), str(e.get("name", "")).lower(), str(e.get("base", e.get("tenant", ""))).lower())
            if k in seen: continue
            seen.add(k); feeds.append(e)
        for c in p.get("watch", []) or []:
            if not isinstance(c, dict): continue
            k = ("c", str(c.get("name", "")).lower())
            if k in seen: continue
            seen.add(k); watch.append(c)
    hard = {"_readme": f"assembled {datetime.date.today().isoformat()} by system/engine/tools/registries.py from packs {[n for n, _ in sel]}", **hard}
    _write(os.path.join(REGISTRIES, "registry.json"), boards)
    _write(os.path.join(REGISTRIES, "wd_registry.json"), wd)
    _write(os.path.join(REGISTRIES, "registry2.json"), [])
    _write(os.path.join(REGISTRIES, "hard_registry.json"), hard)
    _write(os.path.join(REGISTRIES, "feeds_registry.json"), {"feeds": feeds})
    _write(WATCHLIST, {"companies": watch})
    if verbose:
        print(f"registries assembled from {[n for n, _ in sel]} -> {REGISTRIES}")
        print(f"  registry.json       {len(boards)} boards")
        print(f"  wd_registry.json    {len(wd)} Workday tenants")
        print(f"  hard_registry.json  {sum(len(v) for k, v in hard.items() if k != '_readme')} employers in {len(hard) - 1} arms")
        print(f"  feeds_registry.json {len(feeds)} feed/small-ATS entries")
        print(f"  watchlist.json      {len(watch)} watched companies")
        if not sel:
            print("  (no packs selected and no custom.json: every arm is idle - set settings.yaml lanes[].packs or add custom.json)")
    return dict(boards=boards, workday=wd, hard=hard, feeds=feeds, watch=watch)


def list_packs():
    packs = _packs()
    sel = set(selected_packs())
    for n, p in packs.items():
        h = sum(len(v) for k, v in (p.get("hard", {}) or {}).items() if isinstance(v, list))
        print(f"{'*' if n in sel else ' '} {n:24} boards {len(p.get('boards', [])):3}  workday {len(p.get('workday', [])):3}  hard {h:3}  "
              f"misc+feeds {len(p.get('misc', []) or []) + len(p.get('feeds', []) or []):3}  watch {len(p.get('watch', []) or []):3}  - {p.get('description', '')[:60]}")
    print("* = selected in settings.yaml lanes[].packs;", "custom.json present" if os.path.exists(CUSTOM) else "no custom.json")


def check():
    sel = _selected()
    dead = []
    for name, p in sel:
        for b in p.get("boards", []) or []:
            note = str(b[2]) if len(b) > 2 else ""
            if any(w in note.lower() for w in ("dead", "404", "re-verify", "gone")):
                dead.append((name, b[0], b[1], note))
    print(f"{len(dead)} board(s) carry a dead/re-verify note:")
    for d in dead: print("  ", d)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "assemble": assemble()
    elif cmd == "check": check()
    else: list_packs()
