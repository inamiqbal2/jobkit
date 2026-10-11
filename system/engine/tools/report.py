#!/usr/bin/env python3
"""REPORT — the learning loop as a computation, not an essay (2026-08-28).
Recomputes every standing hypothesis cold from state.db. Usage: <jobkit python> tools/report.py"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sqlite3, os, datetime, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT   # JOBKIT: workspace = data root
from state import conn as _state_conn   # creates the db/table on a fresh workspace instead of "no such table"
c=_state_conn()
POS=('interviewing','advanced','closed')
def g(q,*a): return c.execute(q,a).fetchall()
print(f"=== COMPUTED BOARD - {datetime.date.today()} ===")
tot=g("SELECT COUNT(*) FROM applications")[0][0]
resp=g(f"SELECT COUNT(*) FROM applications WHERE Status NOT IN ('open','')")[0][0]
pos=g(f"SELECT COUNT(*) FROM applications WHERE Status IN {POS}")[0][0]
print(f"applications {tot} | responses {resp} ({100*resp//max(tot,1)}%) | positive {pos} of {resp} responses")
print("\nH1 DOMAIN-FIT (by lane):")
for lane,n,p,r in g(f"""SELECT Lane,COUNT(*),SUM(Status IN {POS}),SUM(Status='rejected')
    FROM applications WHERE Lane!='' GROUP BY Lane ORDER BY 3 DESC"""):
    print(f"  {lane:16} {n:2} applied | +{p or 0} -{r or 0}")
print("\nH2 TIER (local vs not):")
for t,n,p,r in g(f"SELECT Tier,COUNT(*),SUM(Status IN {POS}),SUM(Status='rejected') FROM applications WHERE Tier!='' GROUP BY Tier"):
    print(f"  T{t}: {n:2} applied | +{p or 0} -{r or 0}")
print("\nH3 CUSTOM ANSWERS:")
for ca,n,p in g(f"SELECT [Custom Ans],COUNT(*),SUM(Status IN {POS}) FROM applications WHERE [Custom Ans]!='' GROUP BY [Custom Ans]"):
    print(f"  custom={ca}: {n:2} applied | +{p or 0}")
print("\nH4 YEARS-BAR:")
for yb,n,p,r in g(f"SELECT [Yrs Bar],COUNT(*),SUM(Status IN {POS}),SUM(Status='rejected') FROM applications WHERE [Yrs Bar]!='' GROUP BY [Yrs Bar]"):
    print(f"  {yb:8} {n:2} applied | +{p or 0} -{r or 0}")
print("\nH5 STRETCH vs CLEAN (fit):")
for f,n,p,r in g(f"SELECT Fit,COUNT(*),SUM(Status IN {POS}),SUM(Status='rejected') FROM applications WHERE Fit!='' GROUP BY Fit"):
    print(f"  {f:8} {n:2} applied | +{p or 0} -{r or 0}")
print("\nOUTREACH EFFECT:")
for o,n,p in g(f"SELECT CASE WHEN Outreach!='' THEN 'yes' ELSE 'no' END,COUNT(*),SUM(Status IN {POS}) FROM applications GROUP BY 1"):
    print(f"  outreach={o}: {n:2} applied | +{p or 0}")
print("\nRESPONSE SPEED (days, responded rows):")
for d,in_ in g("SELECT [Days to Resp],COUNT(*) FROM applications WHERE [Days to Resp]!='' GROUP BY 1 ORDER BY CAST([Days to Resp] AS INT)"):
    print(f"  {d:>3}d: {in_}")
g30=g("SELECT COUNT(*) FROM applications WHERE Status='open' AND [Date Applied]!='' AND [Date Applied] <= date('now','-30 days')")[0][0]
print(f"\nGHOSTING SWEEP: {g30} open rows past the 30-day cutoff", "-> run: state.py set <row> Status=ghosted" if g30 else "(none yet)")
