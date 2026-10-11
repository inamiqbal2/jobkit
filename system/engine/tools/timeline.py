#!/usr/bin/env python3
"""HIRING-TIMELINE ANALYSIS.

Idea (from the original user): correlate timing with when the posting was first live, to get statistics on
the hiring timelines of companies.

THE IDEA: a posting's age when we apply is a PREDICTOR, not just a record. A req that has been live
for months is more likely to be already decided - somebody is further along - so a rejection from it
is a TIMING outcome, not a verdict on the application. This module measures that.

THREE QUESTIONS IT ANSWERS
 1. Posting age at application vs outcome. Does applying to a fresh req beat applying to an old one?
 2. Requisition lifetime: first-live -> decision. How long does each employer actually take?
 3. Which employers decide fast and which sit on applications, so the queue can be ordered by it.

EXCLUSIONS: TIMING rejections are reported SEPARATELY, never mixed into merit rates (charters/search.md
2026-09-17). UNKNOWN rejections are not treated as merit judgments.
Usage: <jobkit python> tools/timeline.py [--csv]
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sqlite3, os, datetime, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT   # JOBKIT: workspace = data root
DB   = os.path.join(ROOT, "tracking", "state.db")

def _d(x):
    try: return datetime.date.fromisoformat((x or "").strip()[:10])
    except Exception: return None

def load():
    from state import conn as _state_conn   # creates the db/table on a fresh workspace
    c = _state_conn(); c.row_factory = sqlite3.Row
    out = []
    for r in c.execute('SELECT * FROM applications WHERE "Date Applied"!=""'):
        posted, applied = _d(r["Date Posted"]), _d(r["Date Applied"])
        if not applied: continue
        age = (applied - posted).days if posted else None
        days = None
        try: days = int(r["Days to Resp"]) if str(r["Days to Resp"]).strip().isdigit() else None
        except Exception: pass
        st = (r["Status"] or "").strip()
        rt = (r["Reject Type"] or "")
        if st in ("interviewing", "advanced"): outcome = "POSITIVE"
        elif rt.startswith("TIMING"):          outcome = "TIMING"
        elif st in ("rejected", "closed"):     outcome = "REJECT"
        else:                                  outcome = "OPEN"
        out.append(dict(row=r["#"], co=r["Company"], sector=r["Sector"] or "unclassified",
                        age=age, days=days, outcome=outcome, posted=posted, applied=applied))
    return out

def bucket(age):
    if age is None: return "unknown"
    if age <= 3:   return "0-3d   (fresh)"
    if age <= 7:   return "4-7d"
    if age <= 14:  return "8-14d"
    if age <= 30:  return "15-30d"
    if age <= 90:  return "31-90d"
    return "90d+   (stale)"

def main():
    rows = load()
    print(f"HIRING TIMELINES - {len(rows)} applications, "
          f"{sum(1 for r in rows if r['age'] is not None)} with a known posting date\n")

    print("1) POSTING AGE WHEN WE APPLIED  vs  OUTCOME")
    print(f"{'age bucket':<16}{'n':>4}{'positive':>10}{'reject':>8}{'timing':>8}{'open':>6}   positive rate")
    order = ["0-3d   (fresh)","4-7d","8-14d","15-30d","31-90d","90d+   (stale)","unknown"]
    agg = defaultdict(lambda: defaultdict(int))
    for r in rows: agg[bucket(r["age"])][r["outcome"]] += 1
    for b in order:
        v = agg.get(b)
        if not v: continue
        n = sum(v.values()); pos = v["POSITIVE"]
        decided = pos + v["REJECT"]            # TIMING excluded from the denominator on purpose
        rate = f"{100*pos/decided:.0f}% of decided" if decided else "-"
        print(f"{b:<16}{n:>4}{pos:>10}{v['REJECT']:>8}{v['TIMING']:>8}{v['OPEN']:>6}   {rate}")

    print("\n2) HOW LONG A DECISION TOOK (days from our application to their answer)")
    for oc in ("POSITIVE", "REJECT", "TIMING"):
        ds = sorted(r["days"] for r in rows if r["outcome"] == oc and r["days"] is not None)
        if ds:
            print(f"  {oc:<9} n={len(ds):<3} median {statistics.median(ds):>4.0f}d   range {ds[0]}-{ds[-1]}d")

    print("\n3) REQUISITION LIFETIME (first live -> their answer), the employer's real cycle")
    life = [(r["age"] + r["days"], r) for r in rows
            if r["age"] is not None and r["days"] is not None and r["outcome"] != "OPEN"]
    if life:
        vals = sorted(x for x, _ in life)
        print(f"  n={len(vals)}  median {statistics.median(vals):.0f}d  range {vals[0]}-{vals[-1]}d")
        print("  longest-lived reqs that ended in a decision:")
        for x, r in sorted(life, key=lambda t: -t[0])[:6]:
            print(f"    {x:>4}d  row {r['row']:>3} {r['co'][:26]:<28}{r['outcome']}")

    print("\n4) BY SECTOR - median posting age we applied at, and how it went")
    sec = defaultdict(list)
    for r in rows: sec[r["sector"]].append(r)
    print(f"{'sector':<20}{'n':>4}{'med age':>9}{'positive':>10}{'reject':>8}{'timing':>8}")
    for s, rs in sorted(sec.items(), key=lambda kv: -len(kv[1])):
        ages = [r["age"] for r in rs if r["age"] is not None]
        med = f"{statistics.median(ages):.0f}d" if ages else "-"
        print(f"{s:<20}{len(rs):>4}{med:>9}"
              f"{sum(1 for r in rs if r['outcome']=='POSITIVE'):>10}"
              f"{sum(1 for r in rs if r['outcome']=='REJECT'):>8}"
              f"{sum(1 for r in rs if r['outcome']=='TIMING'):>8}")

    stale = [r for r in rows if r["age"] is not None and r["age"] > 60 and r["outcome"] == "OPEN"]
    if stale:
        print(f"\n5) STALE-REQ WATCH - {len(stale)} open applications sent to reqs already 60+ days live")
        print("   (high TIMING risk: someone was probably further along before we arrived)")
        for r in sorted(stale, key=lambda r: -r["age"])[:10]:
            print(f"    {r['age']:>4}d old at apply   row {r['row']:>3} {r['co'][:34]}")

if __name__ == "__main__":
    main()
