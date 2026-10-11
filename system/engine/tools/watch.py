#!/usr/bin/env python3
"""WATCH-LIST MONITOR (built 2026-08-28).

WHY DIFF-BASED, NOT FILTER-BASED: the daily sweep finds roles whose TITLE matches our search regex.
A watch list has a different job — catch anything NEW at a company we already care about, even if
the title would slip the regex. So this snapshots each watched board's full req set and reports what
APPEARED (and what DISAPPEARED) since last run. Radical AI is the motivating case: they had exactly
the right roles and both were filled before we ever saw them.

Usage:
  <jobkit python> tools/watch.py            # check all, print NEW/GONE, update snapshot
  <jobkit python> tools/watch.py --init     # take first snapshot silently (no diff)
Snapshot lives in tracking/watch_snapshot.json. Manual-ATS entries are listed for the user to check.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json, urllib.request, sys, os, datetime, re, concurrent.futures as cf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT   # JOBKIT: workspace = data root
WL   = os.path.join(ROOT, "tracking", "watchlist.json")
SNAP = os.path.join(ROOT, "tracking", "watch_snapshot.json")

def _get(u):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20))

def fetch(ats, slug):
    """Return {req_id: (title, location, url)} for a board."""
    try:
        if ats == "gh":
            d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            return {str(j['id']): (j['title'], j['location']['name'], j['absolute_url']) for j in d['jobs']}
        if ats == "lever":
            d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            return {j['id']: (j['text'], j['categories'].get('location',''), j['hostedUrl']) for j in d}
        if ats == "ashby":
            d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            return {j['jobUrl'].rsplit('/',1)[-1]: (j['title'], j.get('location',''), j['jobUrl']) for j in d['jobs']}
    except Exception as e:
        return {"__ERROR__": (f"{type(e).__name__}", "", "")}
    return {}

def main():
    init = "--init" in sys.argv
    wl = json.load(open(WL, encoding="utf-8"))
    snap = json.load(open(SNAP, encoding="utf-8")) if os.path.exists(SNAP) else {}
    today = datetime.date.today().isoformat()
    manual, alerts, errors = [], [], []

    live = [c for c in wl["companies"] if c["ats"] != "MANUAL"]
    manual = [c for c in wl["companies"] if c["ats"] == "MANUAL"]

    with cf.ThreadPoolExecutor(10) as ex:
        results = list(ex.map(lambda c: (c, fetch(c["ats"], c["slug"])), live))

    for c, cur in results:
        name = c["name"]
        if "__ERROR__" in cur:
            errors.append(f"{name}: fetch failed ({cur['__ERROR__'][0]})"); continue
        prev = snap.get(name, {}).get("reqs", {})
        new  = {k: v for k, v in cur.items() if k not in prev}
        gone = {k: v for k, v in prev.items() if k not in cur}
        if prev and not init:
            pat = re.compile("|".join(c.get("watch_for", ["."])), re.I)
            for k, (t, loc, url) in new.items():
                flag = "** MATCHES WATCH PATTERN" if pat.search(t) else "  (off-pattern)"
                alerts.append(f"NEW  [{name}] {flag}\n     {t}  |  {loc}\n     {url}")
            for k, (t, loc, url) in gone.items():
                alerts.append(f"GONE [{name}] {t}  |  {loc}")
        snap[name] = {"reqs": cur, "last_checked": today, "count": len(cur)}

    json.dump(snap, open(SNAP, "w", encoding="utf-8"), indent=1)

    if init:
        print(f"snapshot initialised for {len(results)} boards on {today}")
        for c, cur in results: print(f"  {c['name']:16} {len(cur)} reqs")
    else:
        print(f"=== WATCH LIST - {today} ===")
        print(" | ".join(f"{c['name']}:{len(cur)}" for c, cur in results))
        if alerts:
            print(f"\n{len(alerts)} CHANGE(S):\n" + "\n".join(alerts))
        else:
            print("\nno changes since last check.")
    if errors: print("\nWARN: " + "; ".join(errors))
    if manual:
        print("\nMANUAL CHECK (no fetchable API - ask the user weekly):")
        for c in manual: print(f"   {c['name']}: {c['slug'][:90]}")

if __name__ == "__main__":
    main()
