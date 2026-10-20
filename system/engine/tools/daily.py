#!/usr/bin/env python3
"""DAILY — the pipeline as a program (2026-08-28 restructure; v1.0 audit M30: one stage per function).
The deterministic spine runs itself; the agent's judgment starts where the queue ends.
  Step 0  watch.py          — diff watched boards (perishable roles first)
  Step 1  corpus.py+match.py — FULL-PROFILE vs FULL-JD matching over all board text (title-blind)
  Step 1a sweep.py --wd-only — Workday tenants (keyword search; API can't bulk-return text)
  Step 2  dedupe vs state.db
  Step 3  screen_minquals   — fetch + knockout-screen the top of the pool
  Step 4  emit tracking/queue_<date>.md — CLOSE→STRETCH→LOOSE, for agent judgment + critic + build
Usage: <jobkit python> tools/daily.py [--window DAYS] [--top N]   (the old positional form `daily.py [window_days] [screen_top_n]` still works)

v1.0 (audit M30): `main()` only sequences the stage functions below over one RunState; every stage reads and writes the
state it needs, and the dedupe / mirror-collapse algorithm is a set of PURE functions (lists in, lists + ledger lines out, no
file or network access) so `tests/test_daily_dedupe.py` can exercise it. Printed output, files written and the shape of
tracking/run_summary.json are unchanged from v0.9: the daily skill and the report reader quote them."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import subprocess, sys, os, json, datetime, re, argparse
import threading as _thr, concurrent.futures as _cfut
import unicodedata as _ud
ENGINE_TOOLS=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENGINE_TOOLS)
from userconfig import WS as ROOT, MODULES as _MODULES, location as _loc_cfg, critic_rules as _critic_rules, thresholds as _thresholds   # JOBKIT: workspace = data root
import geo as _geo
from urlcanon import canon as _curl   # pure (string in, string out); the dedupe functions below depend on nothing else
T=ENGINE_TOOLS; TR=os.path.join(ROOT,"tracking")   # tools run from the engine; everything else lives in the workspace
PY=sys.executable
os.environ.setdefault("PYTHONUTF8","1")   # children (critic, screen, feeds) print utf-8 on every OS
try: sys.stdout.reconfigure(encoding="utf-8",errors="replace",line_buffering=True)   # keep step headers in order with child output when stdout is a file/pipe
except Exception: pass
from userconfig import get as _cfg, validate_or_exit as _validate, run_options as _run_opts

_ERRLINE=re.compile(r"\b(error|failed|did not answer|RATE-LIMITED|TENANT DEAD|refused|timed out|timeout)\b",re.I)   # kept for the offline test only
_ERRMARK=re.compile(r"^\s*(?:[\w-]+(?: arm)? error[ :(]|.*\b(?:EVERY board failed|fetch failed|TENANT DEAD|RATE-LIMITED|registry load error)\b|Traceback \(most recent)",re.I)
_BAND_ORDER={'FRESH':0,'RECENT':1,'OPEN':2}
_FIT_ORDER={"CLOSE":0,"STRETCH":1,"LOOSE":2}
_CUR=("misc:","sr:","custom:")   # curated arms: hand-registered companies, no corpus score
_DISC=("li:","in:","adzuna:")    # discovery (aggregator) arms

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PURE DEDUPE / MIRROR ALGORITHM (v1.0, audit M30). Nothing in this block touches a file, the network or the clock; every
# function takes plain lists / sets and returns new ones, so the behaviour that bit us twice (2026-10-01: 341 distinct
# requisitions collapsed; Mondelēz / Corning / Leidos re-surfacing) is now covered by tests/test_daily_dedupe.py.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _canon(x):
    """Lower-case alphanumerics only, accents folded (2026-10-05: Mondelēz re-surfaced because 'ē' broke the key)."""
    return re.sub(r"[^a-z0-9]","",_ud.normalize("NFKD",x or "").encode("ascii","ignore").decode().lower())

def applied_set(rows):
    """state.db (Company, Position) rows -> the applied-set the dedupe filters compare against.
    2026-10-04: strip trailing "(req 78269)" etc. - Corning 78269 re-surfaced; 2026-10-05: also strip "(NETL)" from the company - Leidos ESR re-surfaced."""
    return {(_canon(re.sub(r"\s*\([^)]*\)","",r[0] or ""))[:10],re.sub(r"\s*\([^)]*\)\s*$","",r[1] or "").strip()) for r in rows}

def is_applied(src,title,applied):
    """The one applied-test both the main path and the backfill arm use (2026-09-11: full-title equality, not a 32-char prefix;
    v0.8 M5 made the backfill arm use the same expression). Case- and accent-insensitive through _canon."""
    return any(a[:8] in _canon(src) and _canon(b)==_canon(title) for a,b in applied)

def not_applied(cands,applied):
    """Drop every candidate whose (employer, title) is already in the applied-set."""
    return [x for x in cands if not is_applied(x.get('src',''),x.get('title',''),applied)]

def ledger_judged(lines):
    """dispositions.jsonl lines -> (judged canonical urls, unreadable lines). LAST decision per CANONICAL URL wins (2026-09-15; canon
    2026-10-01); WATCH / REOPEN / DEFER are not decisions that hide a job (DEFER, v0.5 run.judge_top_n: not scored yet, comes back).
    v0.8 (M6): a blank line is not a decision; v0.9 (H8): a malformed line is reported, never fatal."""
    last={}; bad=[]
    for l in lines:
        if not l.strip(): continue
        try: d=json.loads(l)
        except ValueError: bad.append(l); continue
        last[_curl(d['url'])]=d['decision']
    return {u for u,d in last.items() if d not in ("WATCH","REOPEN","DEFER")},bad

def _company_key(x):
    """Employer key for the mirror grouping: the src prefix for aggregators, the board slug for official arms, "" when unknown
    (getro/misc/custom/sr sources carry no employer; the caller falls back to the location)."""
    src=str(x.get('src','') or ''); low=src.lower()
    for pre in ("li:","in:","adzuna:"):
        if low.startswith(pre): return _canon(src[len(pre):])[:14]
    if low.startswith(("getro:","misc:","custom:","sr:")): return ""
    return _canon(src)[:14]

def _src_rank(x):
    """Sort key inside a mirror group: official sources first (0), then LinkedIn, Indeed, Adzuna, getro/misc."""
    low=str(x.get('src','') or '').lower()
    return 1 if low.startswith("li:") else 2 if low.startswith("in:") else 3 if low.startswith("adzuna:") else 4 if low.startswith(("getro:","misc:")) else 0

def _city(x):
    """First comma-field of the location, canonical; "" when absent or a Workday "N Locations" placeholder."""
    loc=str(x.get('loc','') or '')
    if not loc or re.search(r"\d+ Locations?",loc,re.I): return ""
    return _canon(loc.split(",")[0])[:12]

def _kind(x):
    low=str(x.get('src','') or '').lower()
    for pre in ("li:","in:","adzuna:","getro:"):
        if low.startswith(pre): return pre
    return "official"

def _is_mirror(o,anchor):
    """2026-10-01 (same day) REGRESSION FIX: the first version keyed on (title, employer) alone and collapsed 341 DISTINCT
    requisitions (same title, same Workday board, different city / req id) as "duplicates". A mirror is ONLY an AGGREGATOR
    copy (LinkedIn/Indeed/Adzuna/getro) of a job that also exists from another source - same title, same employer, and the
    same city when both state one. Two official postings are never mirrors of each other, and two listings from the same
    aggregator are never mirrors (LinkedIn lists each location separately)."""
    ko,ka=_kind(o),_kind(anchor)
    if ko=="official": return False          # an official posting is never dropped as a mirror
    if ko==ka: return False                    # same aggregator twice = separate listings
    co,ca=_city(o),_city(anchor)
    return (not co) or (not ca) or co==ca

def collapse_mirrors(fresh,judged,today):
    """2026-10-01 audit H3 (data audit: 13% of scorer reads were mirrors; one job was BUILT on LinkedIn and SKIP on Indeed the same
    day): collapse cross-feed mirrors of the same job BEFORE the ledger/screen. Key = canonical title + employer (employer from the
    src prefix for aggregators, the board slug for official arms, the location when unknown).
    Returns (kept, mirror_ledger_lines, n_mirror, n_mirror_judged, judged_after) - `judged_after` is a NEW set with every
    collapsed mirror added, so the caller's ledger count includes them exactly as before. `today` is an ISO date string."""
    judged=set(judged)
    groups={}
    for x in fresh:
        k=(_canon(x.get('title','')), _company_key(x) or _canon(x.get('loc',''))[:12])
        groups.setdefault(k,[]).append(x)
    keep=[]; mirror_lines=[]; n_mirror=0; n_mirror_judged=0
    for k,grp in groups.items():
        if len(grp)==1: keep.append(grp[0]); continue
        grp.sort(key=lambda x:(_src_rank(x),int(x.get('age',99))))
        kept=[]
        for o in grp:
            already=_curl(o['url']) in judged
            anchor=next((a for a in kept if _is_mirror(o,a)),None)
            if anchor is None:
                kept.append(o); continue
            if already: continue
            if _curl(anchor['url']) in judged: n_mirror_judged+=1
            else: n_mirror+=1
            mirror_lines.append(json.dumps(dict(date=today,url=_curl(o['url']),decision="SKIP",
                reason=f"DUPLICATE(mirror of {_curl(anchor['url'])} via {o.get('src','')[:20]})")))
            judged.add(_curl(o['url']))
        keep.extend(kept)
    return keep,mirror_lines,n_mirror,n_mirror_judged,judged

def not_judged(cands,judged):
    """Drop every candidate whose canonical URL already carries a hiding decision (BUILT/SKIP/APPLIED/DUPLICATE...)."""
    return [x for x in cands if _curl(x['url']) not in judged]

def screen_order(fresh,backfill):
    """The order INTO the screen (pure). GUARANTEED screen slots: backfill first, then ALL scored profile-matches, then unscored
    fill (audit 2026-09-03: band-sorting alone let OPEN-band scored matches fall past the top-N cut). Curated-arm items
    (hand-registered companies, no corpus score) get guaranteed slots too (2026-09-05: misc-arm finds died at the 110-cap because
    unscored+undated sorted last). 2026-09-11 FUNNEL AUDIT: 63/110 screen slots were going to Workday keyword noise while ~23 FRESH
    LinkedIn/Indeed finds sat at positions 111-134, never fetched, then expired: discovery finds now come right after curated arms.
    2026-09-28 (original user): TITLE-BLIND - no title sort anywhere; under a cap a title sort is a title gate.
    Returns (scored, curated, discovery, rest) - the caller concatenates backfill+scored+curated+disc+rest."""
    fresh=sorted(fresh,key=lambda x:(_BAND_ORDER.get(x.get('band'),3),-float(x.get('score') or 0),int(x.get('tier',3))))   # freshness band, then score desc, then tier
    scored=[x for x in fresh if x.get('score')]
    curated=[x for x in fresh if not x.get('score') and str(x.get('src','')).startswith(_CUR)]
    disc=[x for x in fresh if not x.get('score') and str(x.get('src','')).startswith(_DISC)]
    disc.sort(key=lambda x:(int(x.get('age',99)),int(x.get('tier',3))))
    rest=[x for x in fresh if not x.get('score') and not str(x.get('src','')).startswith(_CUR+_DISC)]
    rest.sort(key=lambda x:int(x.get('age',99)))
    return scored,curated,disc,rest

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# RUN STATE + the arm wrapper
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
class RunState:
    """Everything the stages hand to each other (v1.0, audit M30). `summary` is the v0.5 RUN SUMMARY (audit bug 6 + finding 24):
    what each arm did, what failed, what could not be read - written to tracking/run_summary.json and printed last, so the
    report's first lines can say it in plain words. Its keys (arms[name].ok/exit/errors/first_error/count/idle, judge, queue,
    candidates, online, notes, could_not_read, screened) are read by other tools and do not change."""
    def __init__(self,win,topn):
        self.win=str(win); self.topn=str(topn)          # strings: `win` is passed to sweep.py as an argument, `topn` to the screener
        self.today=datetime.date.today(); self.today_iso=self.today.isoformat()
        self.summary=dict(date=self.today_iso,online=None,arms={},could_not_read=0,notes=[])
        self.sump=os.path.join(TR,"run_summary.json")
        self.print_lock=_thr.Lock()
        self.cands=[]        # every candidate after the eligibility / geo / employer filters (summary["candidates"])
        self.applied=set()   # applied_set() from state.db
        self.judged=set()    # hiding decisions from the ledger (+ collapsed mirrors)
        self.fresh=[]        # candidates after dedupe + ledger + caches
        self.backfill=[]     # older-but-open strong matches (STEP 2b)
        self.scored=[]; self.curated=[]; self.disc=[]; self.rest=[]   # the screen order
        self.scache={}; self.ncache={}; self.ncut=""   # screen_cache.json / noise_cache.json + the 7-day noise cut
        self.scr=[]          # minquals_screened.json
        self.ok=[]           # the judgment queue
        self.nq=0            # screened-in before the title-blind gate (the "judgment gate" line)
        self.qp=os.path.join(TR,f"queue_{self.today_iso}.md")
    def save_summary(self):
        try: json.dump(self.summary,open(self.sump,"w",encoding="utf-8"),indent=1)
        except Exception: pass
    def age(self,d):
        """Days since an ISO date; 99 when unreadable (undated -> OPEN band)."""
        try: return (self.today-datetime.date.fromisoformat(d)).days
        except Exception: return 99

def _arm(st,name,cmd,check=False,cwd=None,header=None):
    """Run one discovery arm, echo its output, and record how it went (exit code, error lines, its own count line).
    `header` (v0.9, M2): printed with the output once the arm is done, so arms run concurrently without interleaving."""
    r=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",cwd=cwd)
    out=(r.stdout or "")+(("\n"+r.stderr) if r.stderr and r.stderr.strip() else "")
    with st.print_lock:
        if header: print("\n"+"="*20,header,"="*20)
        print(out.rstrip())
    # v0.9 (audit H7): an error is a line an arm PRINTS AS an error ("<arm> error (...)", "fetch failed", a traceback), never
    # a word that happens to appear in a job title or in a success sentence ("3 of 40 boards did not answer")
    errs=[l.strip() for l in out.splitlines() if _ERRMARK.search(l)]
    # the count is what the arm handed on: unique candidates when it says so, else its first number
    count=re.search(rf"^{re.escape(name)}[^:]*:[^\n]*?(\d[\d,]*)\s+unique",out,re.M|re.I) or re.search(rf"^{re.escape(name)}[^:]*:\s*(\d[\d,]*)",out,re.M|re.I)
    idle=bool(re.search(r"\barm is idle\b",out))   # v0.9 (audit M13): "no search terms / no boards" is said, not shown as "0 found; ok"
    st.summary["arms"][name]=dict(ok=(r.returncode==0),exit=r.returncode,errors=len(errs),first_error=(errs[0][:140] if errs else ""),
                               count=(int(count.group(1).replace(",","")) if count else None),idle=idle)
    if check and r.returncode!=0:
        st.save_summary(); raise SystemExit(f"{name} failed (exit {r.returncode}); see the output above")
    return out

def _jdtext(pth):
    try: return open(pth,encoding='utf-8',errors='ignore').read()
    except Exception: return ''

def _offline_exit(st,note,sentence):
    """The one way the run says "offline" (audit bug 6): a saved summary, two plain sentences, exit 3 - never a "nothing new" report."""
    st.summary["online"]=False; st.summary["notes"].append(note); st.save_summary()
    print(sentence)
    print("Nothing was judged, skipped or ledgered. Check the connection and say 'run my job search' again.")
    sys.exit(3)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# STAGES, in run order
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _probe_hosts(hosts,timeout=6):
    import socket, urllib.request as _ur
    for h in hosts:
        try:
            socket.create_connection((h,443),timeout=timeout).close(); return h
        except Exception:
            try:
                _ur.urlopen(_ur.Request(f"https://{h}/",method="HEAD",headers={"User-Agent":"Mozilla/5.0"}),timeout=timeout); return h
            except Exception: continue
    return None

def probe(st):
    """STEP -1: CONNECTIVITY PROBE. Three well-known job-board hosts; if none answers, the run stops with a plain sentence
    instead of a "nothing new today" report (audit bug 6). JOBKIT_PROBE_HOSTS=host1,host2 overrides (tests)."""
    hosts=[h.strip() for h in os.environ.get("JOBKIT_PROBE_HOSTS","boards-api.greenhouse.io,api.lever.co,www.bing.com").split(",") if h.strip()]
    reached=_probe_hosts(hosts)
    st.summary["online"]=bool(reached)
    if not reached:
        _offline_exit(st,"offline: none of the probe hosts answered",
            "I could not reach the job boards (no internet?). None of "+", ".join(hosts)+" answered, so nothing was searched today.")
    print(f"connectivity: ok ({reached} answered)")

def watch(st):
    """STEP 0: the watch list diff, plus the optional read-only inbox sweep (STEP 0b, OFF by default: settings.yaml modules.inbox_sweep)."""
    print("="*20,"STEP 0: WATCH LIST","="*20)
    w=subprocess.run([PY,os.path.join(T,"watch.py")],capture_output=True,text=True,encoding="utf-8",errors="replace")
    print(w.stdout)
    open(os.path.join(TR,"watch_last_diff.txt"),"w", encoding="utf-8").write(w.stdout)  # diff survives display clipping
    st.summary["arms"]["watch"]=dict(ok=(w.returncode==0),exit=w.returncode,errors=len([l for l in w.stdout.splitlines() if "fetch failed" in l]),first_error=next((l.strip()[:140] for l in w.stdout.splitlines() if "fetch failed" in l),""),count=None)
    if _MODULES.get("inbox_sweep"):
        print("\n"+"="*20,"STEP 0b: INBOX SWEEP (agent, READ-ONLY)","="*20)
        try:
            sw=subprocess.run([sys.executable, os.path.join(T, "inbox_sweep.py"), "--quiet"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            print(sw.stdout.strip() or sw.stderr.strip())
        except Exception as e:
            print(f"  inbox_sweep failed: {type(e).__name__}: {e}")
        print("  AGENT MUST DO THIS: run the mail searches in that plan file, READ ONLY. Log every")
        print("  rejection and every next step to state.db and OUTCOMES_LOG.md before judging the queue.")
        print("  Never send, reply, label, archive or trash. Replies are drafted in the repo for approval.")
    else:
        print("\n  STEP 0b: inbox sweep SKIPPED (modules.inbox_sweep is false in settings.yaml)")

def discover(st):
    """STEP 1 (corpus + match, title-blind) and the three concurrent arms 1a/1b/1c; then the "every arm failed" offline check."""
    print("\n"+"="*20,"STEP 1: PROFILE MATCH (corpus + match, title-blind)","="*20)
    co=_arm(st,"corpus",[PY,os.path.join(T,"corpus.py")],check=True)
    cm=re.search(r"corpus: (\d+) full-text postings from (\d+) boards(?: -> \S+)?(?: \((\d+) of \d+ boards did not answer)?",co)
    if cm: st.summary["arms"]["corpus"].update(count=int(cm.group(1)),boards=int(cm.group(2)),boards_failed=int(cm.group(3) or 0))
    mo=_arm(st,"match",[PY,os.path.join(T,"match.py")],check=True)   # v0.9 (audit H6): a failure is a sentence, never a raw traceback
    open(os.path.join(TR,"match_out.txt"),"w",encoding="utf-8").write(mo)
    print(open(os.path.join(TR,"match_out.txt"), encoding="utf-8").read().split("TOP 40")[0])
    # v0.9 (audit M2): the three arms hit disjoint hosts and write disjoint files, so they run at the same time (2-3 min saved);
    # each one's output is printed whole, under its own banner, when it finishes
    with _cfut.ThreadPoolExecutor(3) as ex:
        fs=[ex.submit(_arm,st,"sweep",[PY,os.path.join(T,"sweep.py"),st.win,"--wd-only"],True,None,"STEP 1a: SWEEP (Workday tenants only)"),
            ex.submit(_arm,st,"feeds",[PY,os.path.join(T,"feeds.py")],False,None,"STEP 1b: FEEDS (VC boards, aggregators, small ATS, custom pages)"),
            ex.submit(_arm,st,"hard-ATS",[PY,os.path.join(T,"hard_ats.py")],False,None,"STEP 1c: HARD-ATS (Oracle/ADP/Eightfold/Phenom/SAP/iCIMS)")]
        for f in fs: f.result()   # a check=True failure (sweep) re-raises its SystemExit sentence here
    # every arm failed = effectively offline (a captive portal, a firewall): say so, do not report "nothing new"
    a=st.summary["arms"]; boards=a.get("corpus",{}).get("boards") or 0; bfail=a.get("corpus",{}).get("boards_failed") or 0
    arm_results=[(a.get(k,{}).get("count") or 0) for k in ("corpus","sweep","feeds","hard-ATS")]
    if (boards and bfail==boards) and sum(arm_results)==0 and any(a.get(k,{}).get("errors") for k in ("sweep","feeds","hard-ATS","watch","corpus")):
        _offline_exit(st,"every discovery arm failed to fetch anything",
            "I could not reach the job boards (no internet?). Every job board failed to answer, so nothing was searched today.")

def gather(st):
    """STEP 2, first half: merge the arms' candidate files into one funnel and apply the ELIGIBILITY filters (geo, never-places,
    employer exclusions). Fit is never decided here (title-blind rule): only eligibility.py and geo.py act on these arms."""
    print("\n"+"="*20,"STEP 2: DEDUPE vs state.db","="*20)
    from state import conn as _state_conn   # creates tracking/state.db + the applications table on a fresh workspace (fresh-install test 2026-10-09)
    c=_state_conn()
    st.applied=applied_set(c.execute("SELECT Company,Position FROM applications"))
    cands=json.load(open(os.path.join(TR,"candidates.json"), encoding="utf-8"))
    import funnel as _funnel   # v0.8 (M10): one definition of band / tier / stub
    # arm A: profile matches — every in-window matched.json doc that passes the judgment gate; closed-lane titles ANNOTATED, never dropped.
    # The annotation regex is workspace data: profile/critic_rules.yaml -> closed_lanes.title_hint_regex ("" = no annotation).
    LANE_HINT=re.compile((_critic_rules().get("closed_lanes") or {}).get("title_hint_regex") or r"(?!x)x",re.I)
    nm=0; ngate=0
    # recency runs on UPDATED date (original user 2026-08-31: activity signal — a bumped req is an active req);
    # true posted age is kept alongside so judgment can see old-but-bumped postings for what they are.
    # 2026-09-29 audit fix: the corpus arm's fixed top-75 cap hid 136 in-window docs that pass the JD gate (e.g.
    # every transferable-skill posting ranked 82+). Admit EVERY in-window doc that passes the same title-blind JD
    # gate the other arms use; no count cap.
    import match as _match
    for m in json.load(open(os.path.join(TR,"matched.json"), encoding="utf-8")):
        sg=int(m.get('sig') or 0); sx=int(m.get('sigx') or 0)
        # ONE title-blind judgment gate (match.judgment_gate): the JD-match bar with the home signature (or the transferable
        # rescue), else a per-lane LANE GATE (profile/signals.yaml lanes.<name>.role: gate) on domain terms + lane_ref cosine.
        via=_match.judgment_gate(float(m.get('score') or 0),sg,sx,m.get('gates') or {},stub=bool(m.get('stub',False)))
        if not via: continue
        age=st.age(m.get('updated') or m['posted'])
        if not (0<=age<=int(st.win)): continue
        loc=m['loc'] or ''
        cands.append(dict(band=_funnel.band(age),
            tier=_funnel.tier(loc),age=age,
            posted_age=st.age(m['posted']),
            src=m['src'],title=m['title'],loc=loc,url=m['url'],
            score=m['score'],lane=("lane?" if LANE_HINT.search(m['title']) else ""),gate=(via if via!='std' else "")))
        nm+=1; ngate+=int(via!='std')
    print(f"profile-match arm contributed {nm} candidates ({ngate} via a LANE GATE)")
    # Title gates on the hard-ATS/feed/sweep arms are RETIRED (title-blind rule): fit is decided by the JD-content gate at
    # judgment. Only ELIGIBILITY (eligibility.py) and GEOGRAPHY (geo.py + eligibility.non_us) act on these arms.
    from eligibility import ELIG as _ELIG, non_us as _NONUS_ANY, excluded_employer as _EXCL_EMP
    for path,srckey in (("feed_candidates.json","src"),("hard_candidates.json","company")):
        try: extra=json.load(open(os.path.join(TR,path), encoding="utf-8"))
        except Exception: continue
        for x in extra:
            t=x.get('title','') or ''
            loc=x.get('loc','') or ''
            if _ELIG.search(t): continue                 # 2026-09-29: shared eligibility filter (tools/eligibility.py)
            if path=="hard_candidates.json":
                # TITLE-BLIND: geo only (loose test: placeholders count as inside). Some hard-ATS recipes return NO location;
                # the shared non_us() test below reads the URL path and title too. Geo is eligibility, not fit.
                if loc and not _geo.in_country_loose(loc): continue
            try: ag=(st.today-datetime.date.fromisoformat(str(x.get('posted'))[:10])).days
            except Exception: ag=99
            ag=max(ag,0)
            cands.append(dict(band=_funnel.band(ag),
                tier=_funnel.tier(loc),
                age=ag,src=str(x.get(srckey,'feed')),title=x.get('title',''),loc=loc,url=x.get('url',''),
                **({'desc':x['desc']} if x.get('desc') else {})))   # 2026-10-16 port: listing snippet = screen fallback text
    # 2026-10-01 audit H1/H4: ONE geo test for every arm (loc text, URL path, title). Workday "N Locations" placeholders
    # and corpus "Remote" matches leaked Onto Remote-Germany / AMAT Bangalore / CuspAI Berlin into the queue.
    n_geo=len(cands); cands=[x for x in cands if not _NONUS_ANY(x.get('loc',''),x.get('url',''),x.get('title',''))]
    # v0.8 (code audit M4): places the person said they would NEVER move to (settings.yaml location.never_places) are dropped
    # here, in code, not only by the agent; remote postings are kept (they are not "in" a place)
    never=[p for p in _loc_cfg().get("never_places",[]) if str(p).strip()]
    if never:
        NEVER_RE=re.compile("|".join(r"\b"+re.escape(str(p).strip())+r"\b" for p in never),re.I)
        n_nev=len(cands); cands=[x for x in cands if not (NEVER_RE.search(x.get('loc','') or '') and not re.search(r"\bremote\b",x.get('loc','') or '',re.I))]
        print(f"never-places filter: {n_nev-len(cands)} candidates in places you would never move to dropped (settings.yaml location.never_places)")
    print(f"geo filter (all arms): {n_geo-len(cands)} candidates outside {_geo.COUNTRY_NAME} dropped")
    # employer exclusions (settings.yaml exclusions.employers) - matched on src/URL only, never JD text
    n_emp=len(cands); cands=[x for x in cands if not _EXCL_EMP(x.get('src',''),x.get('url',''))]
    print(f"employer exclusion: {n_emp-len(cands)} candidates dropped (settings.yaml exclusions.employers)")
    st.cands=cands

def dedupe(st):
    """STEP 2, second half: applied-set, dispositions ledger, cross-feed mirror collapse (ledgered as DUPLICATE), screen cache
    (14 d, INELIGIBLE/EXPIRED only) and noise cache (7 d). The algorithm itself is the pure block above; this stage only does I/O."""
    fresh=not_applied(st.cands,st.applied)
    # dispositions ledger: a judged job (BUILT/SKIP/APPLIED) never re-surfaces
    try:
        judged,bad=ledger_judged(open(os.path.join(TR,"dispositions.jsonl"), encoding="utf-8"))
        for l in bad: print(f"ledger: skipping one unreadable line in dispositions.jsonl ({l[:60]!r})")   # v0.9 (H8)
    except FileNotFoundError: judged=set()
    fresh,mirror_lines,n_mirror,n_mirror_judged,judged=collapse_mirrors(fresh,judged,st.today_iso)
    if mirror_lines:
        with open(os.path.join(TR,"dispositions.jsonl"),"a", encoding="utf-8") as f: f.write("\n".join(mirror_lines)+"\n")
    print(f"mirror dedupe: {n_mirror} cross-feed duplicates collapsed, {n_mirror_judged} mirrors of already-judged jobs dropped (ledgered as DUPLICATE)")
    fresh=not_judged(fresh,judged)
    st.judged=judged
    scp=os.path.join(TR,"screen_cache.json")
    try: st.scache=json.load(open(scp, encoding="utf-8"))
    except Exception: st.scache={}
    cut=(st.today-datetime.timedelta(days=14)).isoformat()
    # 2026-09-29: FETCHFAIL is TRANSIENT (rate limits, timeouts) and must never hide a job for 14 days - a single
    # throttled run cached ~5,300 live Workday postings as dead. Only INELIGIBLE/EXPIRED skip; FETCHFAIL entries
    # stay in the file for diagnostics but are retried every run.
    dead={u for u,v in st.scache.items() if v.get("date","")>=cut and v.get("verdict") in ("EXPIRED","INELIGIBLE")}
    n0=len(fresh); fresh=[x for x in fresh if x['url'] not in dead]
    print(f"screen cache: {n0-len(fresh)} recently-ineligible/dead URLs skipped (14-day cache)")
    # 2026-10-01 audit H5: 5,109 of 5,651 NOISE items were NOISE the day before and were re-fetched daily (11.5 min/run).
    # A JD that failed the title-blind JD gate is cached 7 days by canonical URL; a changed JD text (md5) re-enters.
    ncp=os.path.join(TR,"noise_cache.json")
    try: st.ncache=json.load(open(ncp, encoding="utf-8"))
    except Exception: st.ncache={}
    st.ncut=(st.today-datetime.timedelta(days=7)).isoformat()
    n1=len(fresh); fresh=[x for x in fresh if not (st.ncache.get(_curl(x['url']),{}).get('date','')>=st.ncut)]
    print(f"noise cache: {n1-len(fresh)} URLs that failed the JD gate within 7 days skipped")
    print(f"{len(st.cands)} candidates -> {len(fresh)} after dedupe+ledger ({len(judged)} judged urls on file)")
    st.fresh=fresh

def backfill(st):
    """STEP 2b: BACKFILL — strong profile matches OUTSIDE the window (older-but-open; often hard-to-fill).
    Deterministic: score>=0.42, not applied, not judged; the ledger makes each appear exactly once."""
    import funnel as _funnel
    bf=[]
    for m in json.load(open(os.path.join(TR,"matched.json"), encoding="utf-8")):
        if m['score']<0.42: break
        if _curl(m['url']) in st.judged: continue   # 2026-10-01: canonical compare (backfill arm re-surfaced judged SES AI / Redwood)
        if is_applied(m['src'],m['title'],st.applied): continue   # v0.8 (M5): full-title equality, same as the main path
        age=st.age(m.get('updated') or m['posted'])
        if age<=int(st.win): continue  # in-window (by activity date) ones already joined above
        loc=m['loc'] or ''
        bf.append(dict(band="OPEN",tier=_funnel.tier(loc),
            age=age,posted_age=st.age(m['posted']),src=m['src'],title=m['title'],loc=loc,url=m['url'],score=m['score'],backfill=True))
    st.backfill=bf[:10]
    print(f"backfill arm: {len(st.backfill)} older-but-open strong matches added")

def order_screen(st):
    """Write tracking/queue_input.json in screen order (backfill, scored, curated, discovery, sweep/hard-ATS)."""
    st.scored,st.curated,st.disc,st.rest=screen_order(st.fresh,st.backfill)
    json.dump(st.backfill+st.scored+st.curated+st.disc+st.rest,open(os.path.join(TR,"queue_input.json"),"w", encoding="utf-8"),indent=1)
    print(f"screen order: {len(st.backfill)} backfill + {len(st.scored)} corpus-gated + {len(st.curated)} curated + {len(st.disc)} discovery + {len(st.rest)} sweep/hard-ATS")

def screen(st):
    """STEP 3: MIN-QUALS SCREEN (screen_minquals.py through the arm wrapper) + the 14-day screen cache update."""
    print("\n"+"="*20,"STEP 3: MIN-QUALS SCREEN","="*20)
    # 2026-09-29 audit fix #1: the screen cap may never bind - every candidate is screened (~10 items/s). Under a
    # fixed 600 cap the discovery arm (~440 items since the title gates went) starved the sweep/hard-ATS arms
    # (9/29: 116 of 995 screened, TSMC 0 of 48).
    qlen=len(st.backfill)+len(st.scored)+len(st.curated)+len(st.disc)+len(st.rest)
    st.topn=str(max(int(st.topn),qlen))
    print(f"screen cap: {st.topn} (queue {qlen}) - no candidate is left unscreened")
    so=_arm(st,"screen",[PY,os.path.join(T,"screen_minquals.py"),os.path.join(TR,"queue_input.json"),st.topn],check=True,cwd=ROOT)   # v0.9 (H6)
    open(os.path.join(TR,"screen_out.txt"),"w",encoding="utf-8").write(so)
    st.scr=json.load(open(os.path.join(TR,"minquals_screened.json"), encoding="utf-8"))
    print(f"screened {len(st.scr)}")
    st.summary["could_not_read"]=sum(1 for x in st.scr if x.get('verdict')=="FETCHFAIL")
    st.summary["screened"]=len(st.scr)
    for x in st.scr:
        v=x.get('verdict') or ("EXPIRED" if x.get('minq')=="EXPIRED posting" else None)
        if v in ("INELIGIBLE","FETCHFAIL","EXPIRED"): st.scache[x['url']]=dict(date=st.today_iso,verdict=v,title=x.get('title','')[:60])
    json.dump(st.scache,open(os.path.join(TR,"screen_cache.json"),"w", encoding="utf-8"),indent=0)

def queue(st):
    """STEP 4: the judgment queue - the title-blind JD gate on every screened item, NOISE marking, and the 7-day noise cache."""
    print("\n"+"="*20,"STEP 4: JUDGMENT QUEUE","="*20)
    import match as _match
    from lanes import is_priority as _LANE   # PRIORITY LANE: the user's declared target lane is screened FOR and never dropped (tools/lanes.py)
    scr=st.scr
    ok=[x for x in scr if x.get('fitclass') in _FIT_ORDER]
    # soft-flag classes the user auto-excludes from judgment (critic_rules.yaml screen_auto_exclude_soft, e.g. a domain never
    # once applied to); default none
    AXS=set(str(k) for k in ((_critic_rules().get("screen_auto_exclude_soft") or [])))
    ok=[x for x in ok if not (AXS and AXS.intersection(x.get('soft') or []))]
    st.nq=len(ok)
    # TITLE-BLIND ("the only thing that matters is a match with the job description. The title could be whatever."):
    # every screened item without a corpus score is scored on its fetched JD TEXT with the same scorer and bar the
    # corpus arm uses (match.score_texts + match.judgment_gate).
    need=[x for x in ok if not x.get('score') and not x.get('backfill') and x.get('jd')]
    js=_match.score_texts([(x.get('title',''),_jdtext(x['jd'])) for x in need]) if need else []
    for x,(v,sg,sx,gt) in zip(need,js): x['jdmatch']=v; x['jdsig']=sg; x['jdsigx']=sx; x['jdgates']=gt
    # The SAME title-blind gate as the corpus arm (match.judgment_gate): JD-match bar + home signature, or the
    # transferable-skill rescue (guarded by the home-signature floor), or a per-lane LANE GATE. JD TEXT only, never title.
    def passes(x):
        if x.get('score') or x.get('backfill'): return True
        if _LANE(x.get('title','') or '', _jdtext(x.get('jd','') or '')): return True   # priority lane reads the JD TEXT
        m=float(x.get('jdmatch') or 0); sg=int(x.get('jdsig') or 0); sx=int(x.get('jdsigx') or 0)
        via=_match.judgment_gate(m,sg,sx,x.get('jdgates') or {},stub=_match.is_stub_text(_jdtext(x.get('jd','') or '')))
        if via and via!='std': x['gate']=via
        return bool(via)
    ok=[x for x in ok if passes(x)]
    for x in scr:
        if x.get('fitclass') in _FIT_ORDER and x not in ok: x['fitclass']="NOISE"
    # 2026-10-01 audit H5: cache the NOISE verdict (7 days, keyed by canonical URL + JD md5) so tomorrow does not re-fetch it
    import hashlib as _hl
    for x in scr:
        if x.get('fitclass')=="NOISE" and x.get('jd'):
            try: h=_hl.md5(open(x['jd'],'rb').read()).hexdigest()[:12]
            except Exception: h=""
            st.ncache[_curl(x['url'])]=dict(date=st.today_iso,md5=h,title=str(x.get('title',''))[:60])
    st.ncache={u:v for u,v in st.ncache.items() if v.get('date','')>=st.ncut}
    json.dump(st.ncache,open(os.path.join(TR,"noise_cache.json"),"w", encoding="utf-8"),indent=0)
    st.ok=ok

def critic_pass(st):
    """STEP 3b: the adversarial critic on every queue item (in-process, v0.9 H9), then the deterministic AUTO-LEDGER of
    critic-HOLD items in hard eligibility classes (GRAD-GATE, CONTRACT-GIG)."""
    print("\n"+"="*20,"STEP 3b: CRITIC (auto, per queue item)","="*20)
    # run the adversarial critic on every screened JD; verdict travels with the queue entry
    # v0.9 (audit H9): the critic runs IN THIS PROCESS (one import, ~0.01 s/item) instead of one interpreter per item
    # (~0.5 s/item, ~70 s per run); its printed review goes to tracking/critic_out.txt, and the verdict is data, not stdout.
    import io as _io, contextlib as _ctx, critic as _critic
    ok=st.ok
    with open(os.path.join(TR,"critic_out.txt"),"w",encoding="utf-8") as cf:
        for x in ok:     # 2026-10-01 audit H5: critic runs on gate-passers only (was 5,734 items for 75 survivors)
            if x.get('jd'):
                buf=_io.StringIO()
                try:
                    with _ctx.redirect_stdout(buf): v=_critic.review(x['jd'])
                except Exception as e:
                    v=_critic.Verdict(hold=False,flags=[],softs=[("CRITIC-ERROR",f"{type(e).__name__}")],lane_advisory=False,n_flags=0)
                cf.write(f"=== {x.get('src','')} - {x.get('title','')}\n{buf.getvalue()}\n")
                x['critic']=_critic.queue_line(v)
    print("critic ran on all queue items")
    # AUTO-LEDGER (determinism directive): critic-HOLD items in hard eligibility classes are skipped by CODE.
    # The judgment queue now contains ONLY critic-CLEAR items; agent judgment shrinks to spine-reading.
    led=set()
    try: led={_curl(json.loads(l)['url']) for l in open(os.path.join(TR,"dispositions.jsonl"), encoding="utf-8")}
    except FileNotFoundError: pass
    auto=0
    with open(os.path.join(TR,"dispositions.jsonl"),"a", encoding="utf-8") as f:
        for x in ok:
            hc=str(x.get('critic',''))
            # 2026-10-01 audit H2: the critic's document-wide clearance regex auto-ledgered 226 postings on boilerplate
            # (EEO/preferred text). Citizenship/clearance is decided by the SCREEN (min-quals block + hard-eligibility
            # phrases -> verdict INELIGIBLE, never in `ok`). The critic's INELIGIBLE is now ADVISORY (shown as HOLD).
            hard_auto=("GRAD-GATE" in hc) or ("CONTRACT-GIG" in hc)   # CONTRACT-GIG only fires when settings.yaml exclusions.contract_work is false (critic.py)
            if hc.startswith("HOLD") and hard_auto and _curl(x.get('url','')) not in led:
                f.write(json.dumps(dict(date=st.today_iso,url=_curl(x['url']),decision="SKIP",
                    reason=f"AUTO(critic): {x['critic'][:150]}"))+"\n")
                led.add(_curl(x['url'])); auto+=1
                x['fitclass']="AUTOSKIP"
                print(f"  AUTO-SKIP: {x.get('src','')[:16]} - {x.get('title','')[:52]} [{x['critic'][:60]}]")
    st.ok=[x for x in ok if x.get('fitclass')!="AUTOSKIP"]
    print(f"auto-ledgered {auto} critic-HOLD skips (deterministic)")

def write_queue(st):
    """Write tracking/queue_<date>.md (CLOSE -> STRETCH -> LOOSE, then band, then tier) and the final minquals_screened.json."""
    import match as _match
    from lanes import is_priority as _LANE
    from eligibility import EXPORT as _EXPORT
    ok=st.ok; scr=st.scr
    print(f"judgment gate (title-blind; {_match.gate_description()}): {st.nq} screened-in -> {len(ok)} pass ({sum(1 for x in ok if x.get('gate'))} via a lane gate; rest -> NOISE)")
    json.dump(scr,open(os.path.join(TR,"minquals_screened.json"),"w", encoding="utf-8"),indent=1)
    ok.sort(key=lambda x:(_FIT_ORDER[x['fitclass']],_BAND_ORDER.get(x.get('band'),3),int(x.get('tier',3))))
    with open(st.qp,"w", encoding="utf-8") as f:
        f.write(f"# Judgment queue - {st.today_iso}\n\nFor each: read the min-quals, the CRITIC line (critic.py already ran on the saved JD), decide, ledger it with `<jobkit python> system/engine/tools/decide.py`, build the BUILDs (build skill).\n\n")
        for x in ok:
            sc=f" m={x['score']:.2f}" if x.get('score') else ""
            fl=f" ⚠{x['lane']}" if x.get('lane') else ""
            bf=" BACKFILL" if x.get('backfill') else ""
            pa=f" (posted {x['posted_age']}d)" if x.get('posted_age') not in (None,x.get('age')) else ""
            it=" ⚠ITAR" if _EXPORT.search(_jdtext(x.get('jd','') or '')) else ""
            f.write(f"## [{x['fitclass']} · {x.get('band')} T{x.get('tier')} {x.get('age')}d{pa}{sc}{fl}{bf}{it}] {'★LANE ' if _LANE(x.get('title','') or '', _jdtext(x.get('jd','') or '')) else ''}{('◆'+str(x['gate']).split(':',1)[-1]+' ') if x.get('gate') else ''}{x['src']} — {x['title']}\n")
            f.write(f"{x.get('loc','')} | yrs{x.get('yrs',[])} | soft-flags: {x.get('soft',[])} | CRITIC: {x.get('critic','?')}\n{x['url']}\n")
            mq=" ".join(x.get('minq','').split())[:400]
            f.write(f"> MQ: {mq}\n\n")
    excl=len(scr)-len(ok)
    print(f"queue written: {st.qp} - {len(ok)} for judgment ({excl} auto-excluded)")

def prep_judges(st):
    """STEP 5: RUBRIC PREP. Benchmark 2026-09-04 (tracking/matchbench): blind rubric AUC 0.91 vs deterministic 0.58 at ranking
    interview-producers. Deterministic code preps the batch; the agent spawns two blind scoring subagents and merges — see
    tools/rubric.py docstring for the ritual."""
    print("\n"+"="*20,"STEP 5: RUBRIC PREP (blind LLM ranking pass)","="*20)
    _arm(st,"rubric prep",[PY,os.path.join(T,"rubric.py"),"prep"],check=True,cwd=ROOT)   # v0.9 (H6): a failed prep stops here with a sentence
    print("\nNEXT: run the rubric ritual above (scorer A -> rubric.py prep-b -> scorer B -> rubric.py merge), then judge the")
    print("rubric-ordered queue top-down, build CLOSE-first, log every decision via")
    print("tools/decide.py <url> SKIP|BUILT|APPLIED \"reason\". Human approves sends.")

def judgment_check(st):
    """JUDGMENT CHECK (v0.7; replaces the original user's "3 builds a week" tripwire). Strong matches must never sit without a
    decision: every job that scored at or above the build line in the last 7 days (rubric/score_history.jsonl) should have a
    BUILT, WATCH or SKIP-with-reason line in the ledger. settings.yaml run.judgment_check: false turns it off."""
    BUILD_LINE=_thresholds()['build_default_min_rubric']
    try:
        if _run_opts().get("judgment_check", True):
            cut=(st.today-datetime.timedelta(days=7)).isoformat(); hi=set()
            hp=os.path.join(TR,"rubric","score_history.jsonl")
            if os.path.exists(hp):
                for l in open(hp,encoding="utf-8"):
                    try: h=json.loads(l)
                    except Exception: continue
                    if h.get('date','')>=cut and float(h.get('rubric',0))>=BUILD_LINE: hi.add(h['url'])
            dec={}
            for l in open(os.path.join(TR,"dispositions.jsonl"),encoding="utf-8"):
                try: d=json.loads(l); dec[_curl(d['url'])]=d['decision']
                except Exception: pass
            open_=[u for u in hi if dec.get(_curl(u)) not in ("BUILT","WATCH","SKIP","APPLIED")]
            if open_:
                print("\n"+"!"*78+f"\n!! JUDGMENT CHECK: {len(open_)} job(s) scored >={BUILD_LINE} in the last 7 days and have no decision yet.\n!! Decide each one today (build, watch, or skip with the reason).\n"+"!"*78)
            else:
                print(f"\njudgment check OK: every job >={BUILD_LINE} in the last 7 days has a decision ({len(hi)} such jobs)")
    except Exception as e: print("judgment check error:",e)

def summary(st):
    """RUN SUMMARY (v0.5): the lines the report opens with. Also in tracking/run_summary.json."""
    S=st.summary
    S["queue"]=len(st.ok); S["candidates"]=len(st.cands)
    try:
        jp=json.load(open(os.path.join(TR,"rubric","judge_plan.json"),encoding="utf-8"))
        S["judge"]=jp if jp.get("date")==st.today_iso else dict(top_n=0,scored=0,deferred=0)   # v0.9 (M12): never yesterday's counts
    except Exception: pass
    st.save_summary()
    print("\n"+"="*20,"RUN SUMMARY (put these facts in the report's first lines)","="*20)
    a=S["arms"]
    c=a.get("corpus",{}); print(f"employer job boards (full text): {c.get('count') or 0} postings from {c.get('boards') or 0} boards"+(f"; {c.get('boards_failed')} board(s) did not answer" if c.get("boards_failed") else ""))
    for k,lab in (("sweep","Workday boards"),("feeds","listing feeds"),("hard-ATS","other employer sites (Oracle/ADP/iCIMS/...)"),("watch","watched employers")):
        x=a.get(k,{})
        if not x: continue
        if x.get("idle"): print(f"{lab}: idle - no search terms / boards registered for this arm (tracking/registries/queries.yaml)"); continue
        stt=("failed to run" if not x.get("ok") else (f"{x['errors']} fetch error(s)" if x.get("errors") else "ok"))
        print(f"{lab}: "+(f"{x['count']} found; " if x.get("count") is not None else "")+stt+(f" - {x['first_error']}" if x.get("first_error") else ""))
    print(f"postings that could not be read (page refused or timed out): {S['could_not_read']}")
    print(f"for judgment: {len(st.ok)} posting(s)"+(f"; blind scorers: about {S['judge'].get('scored',0)} posting(s) scored, {S['judge'].get('deferred',0)} deferred below the top {S['judge'].get('top_n')}"+(f" (about {S['judge'].get('runs_to_clear')} more run(s) to reach them all at this rate)" if S['judge'].get('runs_to_clear') else "") if S.get("judge") else ""))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def parse_args(argv=None):
    """v1.0 (audit M30): argparse instead of hand-parsed sys.argv[1]/[2]. `--window DAYS` / `--top N`; the old positional form
    (`daily.py [window_days] [screen_top_n]`, which the daily skill and CLAUDE.md still use) is accepted, a flag wins over it.
    Defaults are resolved by main() AFTER settings.yaml is validated: window = run.window_days else 30; top = 600."""
    p=argparse.ArgumentParser(prog="daily.py",description="jobkit daily pipeline: discover, dedupe, screen, critic, queue, rubric prep.")
    p.add_argument("pos_window",nargs="?",type=int,metavar="window_days",help="(old positional form) same as --window")
    p.add_argument("pos_top",nargs="?",type=int,metavar="screen_top_n",help="(old positional form) same as --top")
    p.add_argument("--window",type=int,metavar="DAYS",help="recency window in days (default: settings.yaml run.window_days, else 30)")
    p.add_argument("--top",type=int,metavar="N",help="screen cap floor (default 600; never binds: every candidate is screened)")
    a=p.parse_args(argv)
    if a.window is None: a.window=a.pos_window
    if a.top is None: a.top=a.pos_top
    return a

def main(argv=None):
    """The daily pipeline, stage by stage (v0.8: wrapped so importing this module runs nothing; v1.0 M30: one function per stage)."""
    args=parse_args(argv)
    _validate("the job search")   # v0.5: a wrong settings value stops here with a plain sentence, never a traceback later
    win=args.window if args.window is not None else (_cfg("run.window_days",30) or 30)   # window: argument, else settings.yaml run.window_days, else 30
    topn=args.top if args.top is not None else 600   # the screen cap never binds (see screen()); every candidate is screened
    os.makedirs(TR,exist_ok=True)
    st=RunState(win,topn)
    probe(st)
    watch(st)
    discover(st)
    gather(st)
    dedupe(st)
    backfill(st)
    order_screen(st)
    screen(st)
    queue(st)
    critic_pass(st)
    write_queue(st)
    prep_judges(st)
    judgment_check(st)
    summary(st)
    return st


if __name__ == "__main__":
    main()
