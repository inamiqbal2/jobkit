#!/usr/bin/env python3
"""DECIDE - append one judgment decision to the dispositions ledger.
Every build/skip/apply decision goes here so the pipeline NEVER re-surfaces a judged job.
Usage: <jobkit python> decide.py <url> SKIP|BUILT|APPLIED|WATCH|REOPEN "<reason>"
       REOPEN supersedes an earlier decision (last decision per URL wins) so a job can re-enter
       the queue WITHOUT deleting any ledger line. Added 2026-09-15 for stub-JD recovery.
       <jobkit python> decide.py --list [n]     show last n decisions
BUILT is GATED (v0.5, CONSTITUTION I.8): it is refused unless an application folder whose JobDescription.txt APPLY line
is this URL exists AND carries a fresh AUDIT_PASS.json (written by audit_claims.py when every .docx in the folder passed;
the sha256 of each .docx must still match). Exit 2 with a plain message otherwise - nothing is ledgered."""
import sys,json,os,datetime
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from urlcanon import canon
from userconfig import WS as ROOT, APPLICATIONS   # JOBKIT: workspace = data root
LEDGER=os.path.join(ROOT,"tracking","dispositions.jsonl")
def load():
    try: return [json.loads(l) for l in open(LEDGER,encoding="utf-8") if l.strip()]
    except FileNotFoundError: return []
def _folders_for(cu):
    """Every applications/<folder> whose JobDescription.txt APPLY line canonicalizes to cu."""
    import re
    out=[]
    if not os.path.isdir(APPLICATIONS): return out
    for d in sorted(os.listdir(APPLICATIONS)):
        jd=os.path.join(APPLICATIONS,d,"JobDescription.txt")
        if not os.path.isfile(jd): continue
        try: head=open(jd,encoding="utf-8",errors="replace").read(2000)
        except OSError: continue
        m=re.search(r"^APPLY:\s*(\S+)",head,re.M)
        if m and canon(m.group(1))==cu: out.append(os.path.join(APPLICATIONS,d))
    return out
def built_gate(cu):
    """(ok, message) for a BUILT decision on canonical url cu."""
    folders=_folders_for(cu)
    if not folders:
        return False,(f"BUILT refused: no folder under {os.path.relpath(APPLICATIONS,ROOT)}/ has an 'APPLY: {cu}' line in its "
                      "JobDescription.txt. Build the documents first (build skill steps 3-6), then audit, then record BUILT.")
    import audit_claims
    msgs=[]
    for folder in folders:
        ok,msg=audit_claims.pass_status(folder)
        if ok: return True,f"{os.path.basename(folder)}: {msg}"
        msgs.append(f"{os.path.basename(folder)}: {msg}")
    return False,"BUILT refused for "+"; ".join(msgs)+". A document that has not passed the audit is not a document."
if __name__=="__main__":
    try: sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    except Exception: pass
    if len(sys.argv)>1 and sys.argv[1]=="--list":
        for d in load()[-int(sys.argv[2] if len(sys.argv)>2 else 20):]:
            print(f"{d['date']} {d['decision']:<8} {d['url'][:70]} - {d['reason'][:80]}")
        sys.exit(0)
    if len(sys.argv)<4:
        print(__doc__); sys.exit(2)
    url,decision,reason=sys.argv[1],sys.argv[2].upper(),sys.argv[3]
    if decision not in ("SKIP","BUILT","APPLIED","WATCH","REOPEN","DEFER"):
        print("decision must be SKIP|BUILT|APPLIED|WATCH|REOPEN (DEFER is written by rubric.py prep only)"); sys.exit(2)
    cu=canon(url)   # 2026-10-01 audit H3: one job, one ledger key (tracking params / greenhouse host variants collapsed)
    if decision=="BUILT":
        ok,msg=built_gate(cu)
        if not ok:
            print(msg); sys.exit(2)
        print(f"audit gate: {msg}")
    os.makedirs(os.path.dirname(LEDGER),exist_ok=True)
    with open(LEDGER,"a",encoding="utf-8") as f:
        f.write(json.dumps(dict(date=datetime.date.today().isoformat(),url=cu,decision=decision,reason=reason,**({"raw_url":url} if url!=cu else {})))+"\n")
    print(f"logged: {decision} {cu}")
    if decision in ("BUILT","WATCH","REOPEN","APPLIED"):   # v0.4: tracker.csv reflects every build / watch immediately
        try:
            import state; state.tracker(quiet=True)
        except Exception as e: print(f"tracker.csv not updated: {type(e).__name__}: {e}", file=sys.stderr)
