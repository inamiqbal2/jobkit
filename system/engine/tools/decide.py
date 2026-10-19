#!/usr/bin/env python3
"""DECIDE - append one judgment decision to the dispositions ledger.
Every build/skip/apply decision goes here so the pipeline NEVER re-surfaces a judged job.
Usage: <jobkit python> decide.py <url> SKIP|BUILT|APPLIED|WATCH|REOPEN "<reason>"
       SKIP is GUARDED (2026-10-16): see skip_guard() - a strong posting needs REQ:"<required line>" or a hard tag.
       REOPEN supersedes an earlier decision (last decision per URL wins) so a job can re-enter
       the queue WITHOUT deleting any ledger line. Added 2026-09-15 for stub-JD recovery.
       <jobkit python> decide.py --list [n]     show last n decisions
BUILT is GATED (v0.5, CONSTITUTION I.8): it is refused unless an application folder whose JobDescription.txt APPLY line
is this URL exists AND carries a fresh AUDIT_PASS.json (written by audit_claims.py when every .docx in the folder passed;
the sha256 of each .docx must still match). Exit 2 with a plain message otherwise - nothing is ledgered."""
import sys,json,os,datetime,re
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
# ── 2026-10-16 port: SKIP GUARDS. An audit of past decisions found strong postings hand-skipped on weak grounds (a location
# guess, a "duplicate" nobody could point to). A SKIP is now refused, with the reason why, when:
#   1. the posting scored at or above the build line (settings.yaml thresholds.build_default_min_rubric, default 60) today
#      or in the last 14 days, and the reason neither quotes the posting's REQUIRED block (REQ:"...") nor carries a hard
#      tag (INELIGIBLE, EXPIRED, CLOSED, NOT-IN-COUNTRY, NEVER-CLAIM, USER-RULE:<rule>, DUPLICATE:<url or folder>);
#   2. the reason says DUPLICATE but does not cite a ledgered URL or an applications/ folder;
#   3. the score is in the stretch band (45 up to the build line) and the only reason is location/relocation while
#      settings.yaml location.relocation is not "no".
_HARD_TAGS=re.compile(r"\b(?:INELIGIBLE|EXPIRED|CLOSED|NOT-IN-COUNTRY|NEVER-CLAIM|USER-RULE:\S+|DUPLICATE:\S+)",re.I)
_REQ=re.compile(r'REQ:\s*"[^"]{8,}"')
_LOCATION_ONLY=re.compile(r"^\s*(?:location|relocat\w*|not commutable|outside (?:the )?(?:metro|area|commute)|too far)\b",re.I)
def _score_now(cu):
    try:
        for x in json.load(open(os.path.join(ROOT,"tracking","minquals_screened.json"),encoding="utf-8")):
            if canon(x.get('url',''))==cu and x.get('rubric') is not None: return float(x['rubric'])
    except Exception: pass
    return None
def skip_guard(cu,reason):
    """(ok, message) for a SKIP decision."""
    from userconfig import get as _cfg
    build=float(_cfg("thresholds.build_default_min_rubric",60) or 60)
    try:
        from rubric import best_recent; best=best_recent(cu)
    except Exception: best=None
    now=_score_now(cu); top=max([v for v in (now,best) if v is not None],default=None)
    from userconfig import location_mode as _lm0
    if _lm0()=="local_only" and _LOCATION_ONLY.search(reason) and not re.search(r"\bDUPLICATE\b",reason,re.I):
        return True,""   # v0.7: the person chose to stay local - outside the commuting area is their own reason
    if re.search(r"\bDUPLICATE\b",reason,re.I):
        m=re.search(r"DUPLICATE:\s*(\S+)",reason,re.I); ref=(m.group(1) if m else "").strip('.,;')
        led={d.get('url') for d in load()}
        if not ref or not (canon(ref) in led or os.path.isdir(os.path.join(APPLICATIONS,ref))):
            return False,("SKIP refused: a DUPLICATE must cite what it duplicates - DUPLICATE:<ledgered url> or "
                          "DUPLICATE:<applications folder name>.")
    if top is not None and top>=build and not (_REQ.search(reason) or _HARD_TAGS.search(reason)):
        return False,(f"SKIP refused: this posting scored {top:.0f} (build line {build:.0f}"+(", best of the last 14 days" if best and best==top else "")+
                      "). Quote the REQUIRED line it fails as REQ:\"...\" or give a hard tag (INELIGIBLE, EXPIRED, CLOSED, "
                      "NOT-IN-COUNTRY, NEVER-CLAIM, USER-RULE:<rule>, DUPLICATE:<ref>).")
    # v0.7: a location-only skip follows the location mode the person chose at setup (settings.yaml location.mode)
    from userconfig import location_mode as _lm, location as _loc, thresholds as _th
    mode=_lm(); away=float(_loc()["away_bar"]); stretch=float(_th()["commutable_min_rubric"])
    if top is not None and _LOCATION_ONLY.search(reason):
        why=None
        if mode=="fit_first" and top>=stretch:
            why=f"you said location barely matters (fit first), and this job scored {top:.0f}"
        elif mode=="local_first" and top>=away:
            why=f"you said you would move for a strong fit, and this job scored {top:.0f} (your bar for moving is {away:.0f})"
        elif mode=="unsure" and top>=build:
            why=f"you are not sure about moving, and this job scored {top:.0f}: ask the person (WATCH + the question in the report)"
        if why:
            return False,f"SKIP refused for location alone: {why}. Build it, or record WATCH and ask the person."
    return True,""

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
    if decision=="SKIP" and not reason.startswith("AUTO("):
        ok,msg=skip_guard(cu,reason)
        if not ok:
            print(msg); sys.exit(2)
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
