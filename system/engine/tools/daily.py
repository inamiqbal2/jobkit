#!/usr/bin/env python3
"""DAILY — the pipeline as a program (2026-08-28 restructure).
The deterministic spine runs itself; the agent's judgment starts where the queue ends.
  Step 0  watch.py          — diff watched boards (perishable roles first)
  Step 1  corpus.py+match.py — FULL-PROFILE vs FULL-JD matching over all board text (title-blind)
  Step 1a sweep.py --wd-only — Workday tenants (keyword search; API can't bulk-return text)
  Step 2  dedupe vs state.db
  Step 3  screen_minquals   — fetch + knockout-screen the top of the pool
  Step 4  emit tracking/queue_<date>.md — CLOSE→STRETCH→LOOSE, for agent judgment + critic + build
Usage: <jobkit python> tools/daily.py [window_days] [screen_top_n]"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import subprocess, sys, os, json, sqlite3, datetime, re
ENGINE_TOOLS=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENGINE_TOOLS)
from userconfig import WS as ROOT, MODULES as _MODULES, location as _loc_cfg, critic_rules as _critic_rules, thresholds as _thresholds   # JOBKIT: workspace = data root
import geo as _geo
T=ENGINE_TOOLS; TR=os.path.join(ROOT,"tracking")   # tools run from the engine; everything else lives in the workspace
PY=sys.executable
os.environ.setdefault("PYTHONUTF8","1")   # children (critic, screen, feeds) print utf-8 on every OS
try: sys.stdout.reconfigure(encoding="utf-8",errors="replace",line_buffering=True)   # keep step headers in order with child output when stdout is a file/pipe
except Exception: pass
from userconfig import get as _cfg, validate_or_exit as _validate, run_options as _run_opts

def main():
    """The daily pipeline, step by step (v0.8: wrapped so importing this module runs nothing)."""
    _validate("the job search")   # v0.5: a wrong settings value stops here with a plain sentence, never a traceback later
    win=sys.argv[1] if len(sys.argv)>1 else str(_cfg("run.window_days",30) or 30); topn=sys.argv[2] if len(sys.argv)>2 else "600"   # window: argv[1], else settings.yaml run.window_days, else 30  # the screen cap never binds (see STEP 3); every candidate is screened
    os.makedirs(TR,exist_ok=True)
    # ── v0.5 RUN SUMMARY (audit bug 6 + finding 24): what each arm did, what failed, what could not be read - written to
    # tracking/run_summary.json and printed last, so the report's first lines can say it in plain words. ──
    _SUMMARY=dict(date=datetime.date.today().isoformat(),online=None,arms={},could_not_read=0,notes=[])
    _SUMP=os.path.join(TR,"run_summary.json")
    def _save_summary():
        try: json.dump(_SUMMARY,open(_SUMP,"w",encoding="utf-8"),indent=1)
        except Exception: pass
    _ERRLINE=re.compile(r"\b(error|failed|did not answer|RATE-LIMITED|TENANT DEAD|refused|timed out|timeout)\b",re.I)   # kept for the offline test only
    _ERRMARK=re.compile(r"^\s*(?:[\w-]+(?: arm)? error[ :(]|.*\b(?:EVERY board failed|fetch failed|TENANT DEAD|RATE-LIMITED|registry load error)\b|Traceback \(most recent)",re.I)
    def _arm(name,cmd,check=False,cwd=None):
        """Run one discovery arm, echo its output, and record how it went (exit code, error lines, its own count line)."""
        r=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",cwd=cwd)
        out=(r.stdout or "")+(("\n"+r.stderr) if r.stderr and r.stderr.strip() else "")
        print(out.rstrip())
        # v0.9 (audit H7): an error is a line an arm PRINTS AS an error ("<arm> error (...)", "fetch failed", a traceback), never
        # a word that happens to appear in a job title or in a success sentence ("3 of 40 boards did not answer")
        errs=[l.strip() for l in out.splitlines() if _ERRMARK.search(l)]
        # the count is what the arm handed on: unique candidates when it says so, else its first number
        count=re.search(rf"^{re.escape(name)}[^:]*:[^\n]*?(\d[\d,]*)\s+unique",out,re.M|re.I) or re.search(rf"^{re.escape(name)}[^:]*:\s*(\d[\d,]*)",out,re.M|re.I)
        _SUMMARY["arms"][name]=dict(ok=(r.returncode==0),exit=r.returncode,errors=len(errs),first_error=(errs[0][:140] if errs else ""),
                                   count=(int(count.group(1).replace(",","")) if count else None))
        if check and r.returncode!=0:
            _save_summary(); raise SystemExit(f"{name} failed (exit {r.returncode}); see the output above")
        return out
    # ── STEP -1: CONNECTIVITY PROBE. Three well-known job-board hosts; if none answers, the run stops with a plain sentence
    # instead of a "nothing new today" report (audit bug 6). JOBKIT_PROBE_HOSTS=host1,host2 overrides (tests). ──
    def _probe(hosts,timeout=6):
        import socket, urllib.request as _ur
        for h in hosts:
            try:
                socket.create_connection((h,443),timeout=timeout).close(); return h
            except Exception:
                try:
                    _ur.urlopen(_ur.Request(f"https://{h}/",method="HEAD",headers={"User-Agent":"Mozilla/5.0"}),timeout=timeout); return h
                except Exception: continue
        return None
    _PROBE_HOSTS=[h.strip() for h in os.environ.get("JOBKIT_PROBE_HOSTS","boards-api.greenhouse.io,api.lever.co,www.bing.com").split(",") if h.strip()]
    _reached=_probe(_PROBE_HOSTS)
    _SUMMARY["online"]=bool(_reached)
    if not _reached:
        _SUMMARY["notes"].append("offline: none of the probe hosts answered")
        _save_summary()
        print("I could not reach the job boards (no internet?). None of "+", ".join(_PROBE_HOSTS)+" answered, so nothing was searched today.")
        print("Nothing was judged, skipped or ledgered. Check the connection and say 'run my job search' again.")
        sys.exit(3)
    print(f"connectivity: ok ({_reached} answered)")
    print("="*20,"STEP 0: WATCH LIST","="*20)
    _w=subprocess.run([PY,os.path.join(T,"watch.py")],capture_output=True,text=True,encoding="utf-8",errors="replace")
    print(_w.stdout)
    open(os.path.join(TR,"watch_last_diff.txt"),"w", encoding="utf-8").write(_w.stdout)  # diff survives display clipping
    _SUMMARY["arms"]["watch"]=dict(ok=(_w.returncode==0),exit=_w.returncode,errors=len([l for l in _w.stdout.splitlines() if "fetch failed" in l]),first_error=next((l.strip()[:140] for l in _w.stdout.splitlines() if "fetch failed" in l),""),count=None)
    # ── STEP 0b: INBOX SWEEP — OPTIONAL MODULE, OFF by default (settings.yaml modules.inbox_sweep). Read-only when on. ──
    if _MODULES.get("inbox_sweep"):
        print("\n"+"="*20,"STEP 0b: INBOX SWEEP (agent, READ-ONLY)","="*20)
        try:
            import subprocess as _sp
            _sw = _sp.run([sys.executable, os.path.join(T, "inbox_sweep.py"), "--quiet"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            print(_sw.stdout.strip() or _sw.stderr.strip())
        except Exception as _e:
            print(f"  inbox_sweep failed: {type(_e).__name__}: {_e}")
        print("  AGENT MUST DO THIS: run the mail searches in that plan file, READ ONLY. Log every")
        print("  rejection and every next step to state.db and OUTCOMES_LOG.md before judging the queue.")
        print("  Never send, reply, label, archive or trash. Replies are drafted in the repo for approval.")
    else:
        print("\n  STEP 0b: inbox sweep SKIPPED (modules.inbox_sweep is false in settings.yaml)")

    print("\n"+"="*20,"STEP 1: PROFILE MATCH (corpus + match, title-blind)","="*20)
    _co=_arm("corpus",[PY,os.path.join(T,"corpus.py")],check=True)
    _cm=re.search(r"corpus: (\d+) full-text postings from (\d+) boards(?: -> \S+)?(?: \((\d+) of \d+ boards did not answer)?",_co)
    if _cm: _SUMMARY["arms"]["corpus"].update(count=int(_cm.group(1)),boards=int(_cm.group(2)),boards_failed=int(_cm.group(3) or 0))
    _mo=_arm("match",[PY,os.path.join(T,"match.py")],check=True)   # v0.9 (audit H6): a failure is a sentence, never a raw traceback
    open(os.path.join(TR,"match_out.txt"),"w",encoding="utf-8").write(_mo)
    print(open(os.path.join(TR,"match_out.txt"), encoding="utf-8").read().split("TOP 40")[0])
    print("\n"+"="*20,"STEP 1a: SWEEP (Workday tenants only)","="*20)
    _arm("sweep",[PY,os.path.join(T,"sweep.py"),win,"--wd-only"],check=True)
    print("\n"+"="*20,"STEP 1b: FEEDS (VC boards, aggregators, small ATS, custom pages)","="*20)
    _arm("feeds",[PY,os.path.join(T,"feeds.py")])
    print("\n"+"="*20,"STEP 1c: HARD-ATS (Oracle/ADP/Eightfold/Phenom/SAP/iCIMS)","="*20)
    _arm("hard-ATS",[PY,os.path.join(T,"hard_ats.py")])
    # every arm failed = effectively offline (a captive portal, a firewall): say so, do not report "nothing new"
    _a=_SUMMARY["arms"]; _boards=_a.get("corpus",{}).get("boards") or 0; _bfail=_a.get("corpus",{}).get("boards_failed") or 0
    _arm_results=[(_a.get(k,{}).get("count") or 0) for k in ("corpus","sweep","feeds","hard-ATS")]
    if (_boards and _bfail==_boards) and sum(_arm_results)==0 and any(_a.get(k,{}).get("errors") for k in ("sweep","feeds","hard-ATS","watch","corpus")):
        _SUMMARY["online"]=False; _SUMMARY["notes"].append("every discovery arm failed to fetch anything"); _save_summary()
        print("I could not reach the job boards (no internet?). Every job board failed to answer, so nothing was searched today.")
        print("Nothing was judged, skipped or ledgered. Check the connection and say 'run my job search' again.")
        sys.exit(3)
    print("\n"+"="*20,"STEP 2: DEDUPE vs state.db","="*20)
    from state import conn as _state_conn   # creates tracking/state.db + the applications table on a fresh workspace (fresh-install test 2026-10-09)
    c=_state_conn()
    import unicodedata as _ud
    _canon=lambda x:__import__("re").sub(r"[^a-z0-9]","",_ud.normalize("NFKD",x or "").encode("ascii","ignore").decode().lower())   # 2026-10-05: fold accents (Mondelēz re-surfaced)
    applied={(_canon(re.sub(r"\s*\([^)]*\)","",r[0] or ""))[:10],re.sub(r"\s*\([^)]*\)\s*$","",r[1] or "").strip()) for r in c.execute("SELECT Company,Position FROM applications")}  # 2026-10-04: strip trailing "(req 78269)" etc. - Corning 78269 re-surfaced; 2026-10-05: also strip "(NETL)" from the company - Leidos ESR re-surfaced
    cands=json.load(open(os.path.join(TR,"candidates.json"), encoding="utf-8"))
    # merge feeds + hard-ATS arms into the same funnel (normalized; undated -> OPEN band)
    import re as _re
    import funnel as _funnel   # v0.8 (M10): one definition of band / tier / stub
    # arm A: profile matches — every in-window matched.json doc that passes the judgment gate; closed-lane titles ANNOTATED, never dropped.
    # The annotation regex is workspace data: profile/critic_rules.yaml -> closed_lanes.title_hint_regex ("" = no annotation).
    _LANE_HINT=_re.compile((_critic_rules().get("closed_lanes") or {}).get("title_hint_regex") or r"(?!x)x",_re.I)
    _today=datetime.date.today()
    _nm=0
    # recency runs on UPDATED date (original user 2026-08-31: activity signal — a bumped req is an active req);
    # true posted age is kept alongside so judgment can see old-but-bumped postings for what they are.
    def _age(d):
        try: return (_today-datetime.date.fromisoformat(d)).days
        except Exception: return 99
    # 2026-09-29 audit fix: the corpus arm's fixed top-75 cap hid 136 in-window docs that pass the JD gate (e.g.
    # every transferable-skill posting ranked 82+). Admit EVERY in-window doc that passes the same title-blind JD
    # gate the other arms use; no count cap.
    import match as _match
    _ngate=0
    for m in json.load(open(os.path.join(TR,"matched.json"), encoding="utf-8")):
        _sg=int(m.get('sig') or 0); _sx=int(m.get('sigx') or 0)
        # ONE title-blind judgment gate (match.judgment_gate): the JD-match bar with the home signature (or the transferable
        # rescue), else a per-lane LANE GATE (profile/signals.yaml lanes.<name>.role: gate) on domain terms + lane_ref cosine.
        _via=_match.judgment_gate(float(m.get('score') or 0),_sg,_sx,m.get('gates') or {},stub=bool(m.get('stub',False)))
        if not _via: continue
        age=_age(m.get('updated') or m['posted'])
        if not (0<=age<=int(win)): continue
        loc=m['loc'] or ''
        cands.append(dict(band=_funnel.band(age),
            tier=_funnel.tier(loc),age=age,
            posted_age=_age(m['posted']),
            src=m['src'],title=m['title'],loc=loc,url=m['url'],
            score=m['score'],lane=("lane?" if _LANE_HINT.search(m['title']) else ""),gate=(_via if _via!='std' else "")))
        _nm+=1; _ngate+=int(_via!='std')
    print(f"profile-match arm contributed {_nm} candidates ({_ngate} via a LANE GATE)")
    # Title gates on the hard-ATS/feed/sweep arms are RETIRED (title-blind rule): fit is decided by the JD-content gate at
    # judgment. Only ELIGIBILITY (eligibility.py) and GEOGRAPHY (geo.py + eligibility.non_us) act on these arms.
    from eligibility import ELIG as _ELIG, EXPORT as _EXPORT, non_us as _NONUS_ANY, excluded_employer as _EXCL_EMP
    from urlcanon import canon as _curl
    from lanes import is_priority as _LANE   # PRIORITY LANE: the user's declared target lane is screened FOR and never dropped (tools/lanes.py)
    for path,srckey in (("feed_candidates.json","src"),("hard_candidates.json","company")):
        try: extra=json.load(open(os.path.join(TR,path), encoding="utf-8"))
        except Exception: continue
        for x in extra:
            _t=x.get('title','') or ''
            loc=x.get('loc','') or ''
            if _ELIG.search(_t): continue                 # 2026-09-29: shared eligibility filter (tools/eligibility.py)
            if path=="hard_candidates.json":
                # TITLE-BLIND: geo only (loose test: placeholders count as inside). Some hard-ATS recipes return NO location;
                # the shared non_us() test below reads the URL path and title too. Geo is eligibility, not fit.
                if loc and not _geo.in_country_loose(loc): continue
            try: _a=(datetime.date.today()-datetime.date.fromisoformat(str(x.get('posted'))[:10])).days
            except Exception: _a=99
            _a=max(_a,0)
            cands.append(dict(band=_funnel.band(_a),
                tier=_funnel.tier(loc),
                age=_a,src=str(x.get(srckey,'feed')),title=x.get('title',''),loc=loc,url=x.get('url',''),
                **({'desc':x['desc']} if x.get('desc') else {})))   # 2026-10-16 port: listing snippet = screen fallback text
    # 2026-10-01 audit H1/H4: ONE geo test for every arm (loc text, URL path, title). Workday "N Locations" placeholders
    # and corpus "Remote" matches leaked Onto Remote-Germany / AMAT Bangalore / CuspAI Berlin into the queue.
    _n_geo=len(cands); cands=[x for x in cands if not _NONUS_ANY(x.get('loc',''),x.get('url',''),x.get('title',''))]
    # v0.8 (code audit M4): places the person said they would NEVER move to (settings.yaml location.never_places) are dropped
    # here, in code, not only by the agent; remote postings are kept (they are not "in" a place)
    _NEVER=[p for p in _loc_cfg().get("never_places",[]) if str(p).strip()]
    if _NEVER:
        _NEVER_RE=_re.compile("|".join(r"\b"+_re.escape(str(p).strip())+r"\b" for p in _NEVER),_re.I)
        _n_nev=len(cands); cands=[x for x in cands if not (_NEVER_RE.search(x.get('loc','') or '') and not _re.search(r"\bremote\b",x.get('loc','') or '',_re.I))]
        print(f"never-places filter: {_n_nev-len(cands)} candidates in places you would never move to dropped (settings.yaml location.never_places)")
    print(f"geo filter (all arms): {_n_geo-len(cands)} candidates outside {_geo.COUNTRY_NAME} dropped")
    # employer exclusions (settings.yaml exclusions.employers) - matched on src/URL only, never JD text
    _n_emp=len(cands); cands=[x for x in cands if not _EXCL_EMP(x.get('src',''),x.get('url',''))]
    print(f"employer exclusion: {_n_emp-len(cands)} candidates dropped (settings.yaml exclusions.employers)")
    fresh=[x for x in cands if not any(a[:8] in _canon(x['src']) and _canon(b)==_canon(x['title']) for a,b in applied)]  # 2026-09-11: full-title equality, not a 32-char prefix
    # dispositions ledger: a judged job (BUILT/SKIP/APPLIED) never re-surfaces
    try:
        _last={}
        for _l in open(os.path.join(TR,"dispositions.jsonl"), encoding="utf-8"):
            if not _l.strip(): continue   # v0.8 (M6): a blank line is not a decision
            try: _d=json.loads(_l)
            except ValueError: print(f"ledger: skipping one unreadable line in dispositions.jsonl ({_l[:60]!r})"); continue   # v0.9 (H8)
            _last[_curl(_d['url'])]=_d['decision']   # LAST decision per CANONICAL URL wins (2026-09-15; canon 2026-10-01)
        judged={u for u,d in _last.items() if d not in ("WATCH","REOPEN","DEFER")}   # DEFER (v0.5, run.judge_top_n): not scored yet, comes back
    except FileNotFoundError: judged=set()
    # 2026-10-01 audit H3 (data audit: 13% of scorer reads were mirrors; one job was BUILT on LinkedIn and SKIP on Indeed the
    # same day): collapse cross-feed mirrors of the same job BEFORE the ledger/screen. Key = canonical title + employer
    # (employer from the src prefix for aggregators, the board slug for official arms, the location when unknown).
    def _company_key(x):
        src=str(x.get('src','') or ''); low=src.lower()
        for pre in ("li:","in:","adzuna:"):
            if low.startswith(pre): return _canon(src[len(pre):])[:14]
        if low.startswith(("getro:","misc:","custom:","sr:")): return ""
        return _canon(src)[:14]
    def _src_rank(x):
        low=str(x.get('src','') or '').lower()
        return 1 if low.startswith("li:") else 2 if low.startswith("in:") else 3 if low.startswith("adzuna:") else 4 if low.startswith(("getro:","misc:")) else 0
    # 2026-10-01 (same day) REGRESSION FIX: the first version keyed on (title, employer) alone and collapsed 341 DISTINCT
    # requisitions (same title, same Workday board, different city / req id) as "duplicates". A mirror is now ONLY an
    # AGGREGATOR copy (LinkedIn/Indeed/Adzuna/getro) of a job that also exists from another source - same title, same
    # employer, and the same city when both state one. Two official postings are never mirrors of each other, and two
    # listings from the same aggregator are never mirrors (LinkedIn lists each location separately).
    def _city(x):
        loc=str(x.get('loc','') or '')
        if not loc or re.search(r"\d+ Locations?",loc,re.I): return ""
        return _canon(loc.split(",")[0])[:12]
    def _kind(x):
        low=str(x.get('src','') or '').lower()
        for pre in ("li:","in:","adzuna:","getro:"):
            if low.startswith(pre): return pre
        return "official"
    def _is_mirror(o,anchor):
        ko,ka=_kind(o),_kind(anchor)
        if ko=="official": return False          # an official posting is never dropped as a mirror
        if ko==ka: return False                    # same aggregator twice = separate listings
        co,ca=_city(o),_city(anchor)
        return (not co) or (not ca) or co==ca
    _groups={}
    for x in fresh:
        k=(_canon(x.get('title','')), _company_key(x) or _canon(x.get('loc',''))[:12])
        _groups.setdefault(k,[]).append(x)
    _keep=[]; _mirror_lines=[]; _n_mirror=0; _n_mirror_judged=0
    for k,grp in _groups.items():
        if len(grp)==1: _keep.append(grp[0]); continue
        grp.sort(key=lambda x:(_src_rank(x),int(x.get('age',99))))
        kept=[]
        for o in grp:
            _already=_curl(o['url']) in judged
            anchor=next((a for a in kept if _is_mirror(o,a)),None)
            if anchor is None:
                kept.append(o); continue
            if _already: continue
            if _curl(anchor['url']) in judged: _n_mirror_judged+=1
            else: _n_mirror+=1
            _mirror_lines.append(json.dumps(dict(date=datetime.date.today().isoformat(),url=_curl(o['url']),decision="SKIP",
                reason=f"DUPLICATE(mirror of {_curl(anchor['url'])} via {o.get('src','')[:20]})")))
            judged.add(_curl(o['url']))
        _keep.extend(kept)
    if _mirror_lines:
        with open(os.path.join(TR,"dispositions.jsonl"),"a", encoding="utf-8") as _f: _f.write("\n".join(_mirror_lines)+"\n")
    fresh=_keep
    print(f"mirror dedupe: {_n_mirror} cross-feed duplicates collapsed, {_n_mirror_judged} mirrors of already-judged jobs dropped (ledgered as DUPLICATE)")
    fresh=[x for x in fresh if _curl(x['url']) not in judged]
    _scp=os.path.join(TR,"screen_cache.json")
    try: _scache=json.load(open(_scp, encoding="utf-8"))
    except Exception: _scache={}
    _cut=(datetime.date.today()-datetime.timedelta(days=14)).isoformat()
    # 2026-09-29: FETCHFAIL is TRANSIENT (rate limits, timeouts) and must never hide a job for 14 days - a single
    # throttled run cached ~5,300 live Workday postings as dead. Only INELIGIBLE/EXPIRED skip; FETCHFAIL entries
    # stay in the file for diagnostics but are retried every run.
    _dead={u for u,v in _scache.items() if v.get("date","")>=_cut and v.get("verdict") in ("EXPIRED","INELIGIBLE")}
    _n0=len(fresh); fresh=[x for x in fresh if x['url'] not in _dead]
    print(f"screen cache: {_n0-len(fresh)} recently-ineligible/dead URLs skipped (14-day cache)")
    # 2026-10-01 audit H5: 5,109 of 5,651 NOISE items were NOISE the day before and were re-fetched daily (11.5 min/run).
    # A JD that failed the title-blind JD gate is cached 7 days by canonical URL; a changed JD text (md5) re-enters.
    _ncp=os.path.join(TR,"noise_cache.json")
    try: _ncache=json.load(open(_ncp, encoding="utf-8"))
    except Exception: _ncache={}
    _ncut=(datetime.date.today()-datetime.timedelta(days=7)).isoformat()
    _n1=len(fresh); fresh=[x for x in fresh if not (_ncache.get(_curl(x['url']),{}).get('date','')>=_ncut)]
    print(f"noise cache: {_n1-len(fresh)} URLs that failed the JD gate within 7 days skipped")
    print(f"{len(cands)} candidates -> {len(fresh)} after dedupe+ledger ({len(judged)} judged urls on file)")
    # STEP 2b: BACKFILL — strong profile matches OUTSIDE the window (older-but-open; often hard-to-fill).
    # Deterministic: score>=0.42, not applied, not judged; the ledger makes each appear exactly once.
    backfill=[]
    for m in json.load(open(os.path.join(TR,"matched.json"), encoding="utf-8")):
        if m['score']<0.42: break
        if _curl(m['url']) in judged: continue   # 2026-10-01: canonical compare (backfill arm re-surfaced judged SES AI / Redwood)
        if any(a[:8] in _canon(m['src']) and _canon(b)==_canon(m['title']) for a,b in applied): continue   # v0.8 (M5): full-title equality, same as the main path
        age=_age(m.get('updated') or m['posted'])
        if age<=int(win): continue  # in-window (by activity date) ones already joined above
        loc=m['loc'] or ''
        backfill.append(dict(band="OPEN",tier=_funnel.tier(loc),
            age=age,posted_age=_age(m['posted']),src=m['src'],title=m['title'],loc=loc,url=m['url'],score=m['score'],backfill=True))
    backfill=backfill[:10]
    print(f"backfill arm: {len(backfill)} older-but-open strong matches added")
    # priority order INTO the screen: freshness band, then profile-match score (desc), then tier.
    fresh.sort(key=lambda x:({'FRESH':0,'RECENT':1,'OPEN':2}.get(x.get('band'),3),-float(x.get('score') or 0),int(x.get('tier',3))))
    # GUARANTEED screen slots: backfill first, then ALL scored profile-matches, then unscored fill.
    # (Audit 2026-09-03: band-sorting alone let OPEN-band scored matches fall past the top-N cut.)
    _scored=[x for x in fresh if x.get('score')]
    # curated-arm items (hand-registered companies, no corpus score) get guaranteed slots too —
    # 2026-09-05: misc-arm finds died at the 110-cap because unscored+undated sorted last.
    _CUR=("misc:","sr:","custom:")
    _DISC=("li:","in:","adzuna:")
    # 2026-09-11 FUNNEL AUDIT: 63/110 screen slots were going to Workday keyword noise (NCG/co-op/
    # biotech titles) while ~23 FRESH LinkedIn/Indeed materials finds sat at positions 111-134,
    # never fetched, then expired from the 48-72h arm windows. Discovery finds now get guaranteed
    # slots right after curated arms, and the sweep arm gets the same title DROP as hard-ATS.
    _curated=[x for x in fresh if not x.get('score') and str(x.get('src','')).startswith(_CUR)]
    _disc=[x for x in fresh if not x.get('score') and str(x.get('src','')).startswith(_DISC)]
    _disc.sort(key=lambda x:(int(x.get('age',99)),int(x.get('tier',3))))
    _rest=[x for x in fresh if not x.get('score') and not str(x.get('src','')).startswith(_CUR+_DISC)]
    # 2026-09-28 (original user): TITLE-BLIND - the sweep-arm title DROP is retired; sweep noise is removed by the JD-match gate at judgment.
    _rest.sort(key=lambda x:int(x.get('age',99)))   # no title sort: under a cap a title sort is a title gate
    json.dump(backfill+_scored+_curated+_disc+_rest,open(os.path.join(TR,"queue_input.json"),"w", encoding="utf-8"),indent=1)
    print(f"screen order: {len(backfill)} backfill + {len(_scored)} corpus-gated + {len(_curated)} curated + {len(_disc)} discovery + {len(_rest)} sweep/hard-ATS")

    print("\n"+"="*20,"STEP 3: MIN-QUALS SCREEN","="*20)
    # 2026-09-29 audit fix #1: the screen cap may never bind - every candidate is screened (~10 items/s). Under a
    # fixed 600 cap the discovery arm (~440 items since the title gates went) starved the sweep/hard-ATS arms
    # (9/29: 116 of 995 screened, TSMC 0 of 48).
    _qlen=len(backfill)+len(_scored)+len(_curated)+len(_disc)+len(_rest)
    topn=str(max(int(topn),_qlen))
    print(f"screen cap: {topn} (queue {_qlen}) - no candidate is left unscreened")
    _so=_arm("screen",[PY,os.path.join(T,"screen_minquals.py"),os.path.join(TR,"queue_input.json"),topn],check=True,cwd=ROOT)   # v0.9 (H6)
    open(os.path.join(TR,"screen_out.txt"),"w",encoding="utf-8").write(_so)
    scr=json.load(open(os.path.join(TR,"minquals_screened.json"), encoding="utf-8"))
    print(f"screened {len(scr)}")
    _SUMMARY["could_not_read"]=sum(1 for x in scr if x.get('verdict')=="FETCHFAIL")
    _SUMMARY["screened"]=len(scr)
    for x in scr:
        v=x.get('verdict') or ("EXPIRED" if x.get('minq')=="EXPIRED posting" else None)
        if v in ("INELIGIBLE","FETCHFAIL","EXPIRED"): _scache[x['url']]=dict(date=datetime.date.today().isoformat(),verdict=v,title=x.get('title','')[:60])
    json.dump(_scache,open(_scp,"w", encoding="utf-8"),indent=0)
    print("\n"+"="*20,"STEP 4: JUDGMENT QUEUE","="*20)
    today=datetime.date.today().isoformat()
    qp=os.path.join(TR,f"queue_{today}.md")
    order={"CLOSE":0,"STRETCH":1,"LOOSE":2}
    ok=[x for x in scr if x.get('fitclass') in order]
    # soft-flag classes the user auto-excludes from judgment (critic_rules.yaml screen_auto_exclude_soft, e.g. a domain never
    # once applied to); default none
    _AXS=set(str(k) for k in ((_critic_rules().get("screen_auto_exclude_soft") or [])))
    ok=[x for x in ok if not (_AXS and _AXS.intersection(x.get('soft') or []))]
    _nq=len(ok)
    # TITLE-BLIND ("the only thing that matters is a match with the job description. The title could be whatever."):
    # every screened item without a corpus score is scored on its fetched JD TEXT with the same scorer and bar the
    # corpus arm uses (match.score_texts + match.judgment_gate).
    _need=[x for x in ok if not x.get('score') and not x.get('backfill') and x.get('jd')]
    def _jdtext(pth):
        try: return open(pth,encoding='utf-8',errors='ignore').read()
        except Exception: return ''
    _js=_match.score_texts([(x.get('title',''),_jdtext(x['jd'])) for x in _need]) if _need else []
    for x,(v,sg,sx,gt) in zip(_need,_js): x['jdmatch']=v; x['jdsig']=sg; x['jdsigx']=sx; x['jdgates']=gt
    # The SAME title-blind gate as the corpus arm (match.judgment_gate): JD-match bar + home signature, or the
    # transferable-skill rescue (guarded by the home-signature floor), or a per-lane LANE GATE. JD TEXT only, never title.
    def _passes(x):
        if x.get('score') or x.get('backfill'): return True
        if _LANE(x.get('title','') or '', _jdtext(x.get('jd','') or '')): return True   # priority lane reads the JD TEXT
        m=float(x.get('jdmatch') or 0); sg=int(x.get('jdsig') or 0); sx=int(x.get('jdsigx') or 0)
        via=_match.judgment_gate(m,sg,sx,x.get('jdgates') or {},stub=_match.is_stub_text(_jdtext(x.get('jd','') or '')))
        if via and via!='std': x['gate']=via
        return bool(via)
    ok=[x for x in ok if _passes(x)]
    for x in scr:
        if x.get('fitclass') in order and x not in ok: x['fitclass']="NOISE"
    # 2026-10-01 audit H5: cache the NOISE verdict (7 days, keyed by canonical URL + JD md5) so tomorrow does not re-fetch it
    import hashlib as _hl
    for x in scr:
        if x.get('fitclass')=="NOISE" and x.get('jd'):
            try: _h=_hl.md5(open(x['jd'],'rb').read()).hexdigest()[:12]
            except Exception: _h=""
            _ncache[_curl(x['url'])]=dict(date=datetime.date.today().isoformat(),md5=_h,title=str(x.get('title',''))[:60])
    _ncache={u:v for u,v in _ncache.items() if v.get('date','')>=_ncut}
    json.dump(_ncache,open(_ncp,"w", encoding="utf-8"),indent=0)
    print("\n"+"="*20,"STEP 3b: CRITIC (auto, per queue item)","="*20)
    # run the adversarial critic on every screened JD; verdict travels with the queue entry
    # v0.9 (audit H9): the critic runs IN THIS PROCESS (one import, ~0.01 s/item) instead of one interpreter per item
    # (~0.5 s/item, ~70 s per run); its printed review goes to tracking/critic_out.txt, and the verdict is data, not stdout.
    import io as _io, contextlib as _ctx, critic as _critic
    with open(os.path.join(TR,"critic_out.txt"),"w",encoding="utf-8") as _cf:
        for x in ok:     # 2026-10-01 audit H5: critic runs on gate-passers only (was 5,734 items for 75 survivors)
            if x.get('jd'):
                _buf=_io.StringIO()
                try:
                    with _ctx.redirect_stdout(_buf): _v=_critic.review(x['jd'])
                except Exception as _e:
                    _v=_critic.Verdict(hold=False,flags=[],softs=[("CRITIC-ERROR",f"{type(_e).__name__}")],lane_advisory=False,n_flags=0)
                _cf.write(f"=== {x.get('src','')} - {x.get('title','')}\n{_buf.getvalue()}\n")
                x['critic']=_critic.queue_line(_v)
    print("critic ran on all queue items")
    # AUTO-LEDGER (determinism directive): critic-HOLD items in hard eligibility classes are skipped by CODE.
    # The judgment queue now contains ONLY critic-CLEAR items; agent judgment shrinks to spine-reading.
    _led=set()
    try: _led={_curl(json.loads(l)['url']) for l in open(os.path.join(TR,"dispositions.jsonl"), encoding="utf-8")}
    except FileNotFoundError: pass
    _auto=0
    with open(os.path.join(TR,"dispositions.jsonl"),"a", encoding="utf-8") as _f:
        for x in ok:
            _hc=str(x.get('critic',''))
            # 2026-10-01 audit H2: the critic's document-wide clearance regex auto-ledgered 226 postings on boilerplate
            # (EEO/preferred text). Citizenship/clearance is decided by the SCREEN (min-quals block + hard-eligibility
            # phrases -> verdict INELIGIBLE, never in `ok`). The critic's INELIGIBLE is now ADVISORY (shown as HOLD).
            _hard_auto=("GRAD-GATE" in _hc) or ("CONTRACT-GIG" in _hc)   # CONTRACT-GIG only fires when settings.yaml exclusions.contract_work is false (critic.py)
            if _hc.startswith("HOLD") and _hard_auto and _curl(x.get('url','')) not in _led:
                _f.write(json.dumps(dict(date=datetime.date.today().isoformat(),url=_curl(x['url']),decision="SKIP",
                    reason=f"AUTO(critic): {x['critic'][:150]}"))+"\n")
                _led.add(_curl(x['url'])); _auto+=1
                x['fitclass']="AUTOSKIP"
                print(f"  AUTO-SKIP: {x.get('src','')[:16]} - {x.get('title','')[:52]} [{x['critic'][:60]}]")
    ok=[x for x in ok if x.get('fitclass')!="AUTOSKIP"]
    print(f"auto-ledgered {_auto} critic-HOLD skips (deterministic)")
    print(f"judgment gate (title-blind; {_match.gate_description()}): {_nq} screened-in -> {len(ok)} pass ({sum(1 for x in ok if x.get('gate'))} via a lane gate; rest -> NOISE)")
    json.dump(scr,open(os.path.join(TR,"minquals_screened.json"),"w", encoding="utf-8"),indent=1)
    ok.sort(key=lambda x:(order[x['fitclass']],{'FRESH':0,'RECENT':1,'OPEN':2}.get(x.get('band'),3),int(x.get('tier',3))))
    with open(qp,"w", encoding="utf-8") as f:
        f.write(f"# Judgment queue - {today}\n\nFor each: read the min-quals, the CRITIC line (critic.py already ran on the saved JD), decide, ledger it with `<jobkit python> system/engine/tools/decide.py`, build the BUILDs (build skill).\n\n")
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
    print(f"queue written: {qp} - {len(ok)} for judgment ({excl} auto-excluded)")
    print("\n"+"="*20,"STEP 5: RUBRIC PREP (blind LLM ranking pass)","="*20)
    # Benchmark 2026-09-04 (tracking/matchbench): blind rubric AUC 0.91 vs deterministic 0.58 at
    # ranking interview-producers. Deterministic code preps the batch; the agent spawns two blind
    # scoring subagents and merges — see tools/rubric.py docstring for the ritual.
    _arm("rubric prep",[PY,os.path.join(T,"rubric.py"),"prep"],check=True,cwd=ROOT)   # v0.9 (H6): a failed prep stops here with a sentence
    print("\nNEXT: run the rubric ritual above (scorer A -> rubric.py prep-b -> scorer B -> rubric.py merge), then judge the")
    print("rubric-ordered queue top-down, build CLOSE-first, log every decision via")
    print("tools/decide.py <url> SKIP|BUILT|APPLIED \"reason\". Human approves sends.")

    # ═══ JUDGMENT CHECK (v0.7; replaces the original user's "3 builds a week" tripwire). Strong matches must never sit without a
    # decision: every job that scored at or above the build line in the last 7 days (rubric/score_history.jsonl) should have a
    # BUILT, WATCH or SKIP-with-reason line in the ledger. settings.yaml run.judgment_check: false turns it off.
    _BUILD_LINE=_thresholds()['build_default_min_rubric']
    try:
        if _run_opts().get("judgment_check", True):
            _cut=(datetime.date.today()-datetime.timedelta(days=7)).isoformat(); _hi=set()
            _hp=os.path.join(TR,"rubric","score_history.jsonl")
            if os.path.exists(_hp):
                for _l in open(_hp,encoding="utf-8"):
                    try: _h=json.loads(_l)
                    except Exception: continue
                    if _h.get('date','')>=_cut and float(_h.get('rubric',0))>=_BUILD_LINE: _hi.add(_h['url'])
            _dec={}
            for _l in open(os.path.join(TR,"dispositions.jsonl"),encoding="utf-8"):
                try: _d=json.loads(_l); _dec[_curl(_d['url'])]=_d['decision']
                except Exception: pass
            _open=[u for u in _hi if _dec.get(_curl(u)) not in ("BUILT","WATCH","SKIP","APPLIED")]
            if _open:
                print("\n"+"!"*78+f"\n!! JUDGMENT CHECK: {len(_open)} job(s) scored >={_BUILD_LINE} in the last 7 days and have no decision yet.\n!! Decide each one today (build, watch, or skip with the reason).\n"+"!"*78)
            else:
                print(f"\njudgment check OK: every job >={_BUILD_LINE} in the last 7 days has a decision ({len(_hi)} such jobs)")
    except Exception as _e: print("judgment check error:",_e)

    # ═══ RUN SUMMARY (v0.5): the lines the report opens with. Also in tracking/run_summary.json. ═══
    _SUMMARY["queue"]=len(ok); _SUMMARY["candidates"]=len(cands)
    try:
        _jp=json.load(open(os.path.join(TR,"rubric","judge_plan.json"),encoding="utf-8"))
        _SUMMARY["judge"]=_jp if _jp.get("date")==datetime.date.today().isoformat() else dict(top_n=0,scored=0,deferred=0)   # v0.9 (M12): never yesterday's counts
    except Exception: pass
    _save_summary()
    print("\n"+"="*20,"RUN SUMMARY (put these facts in the report's first lines)","="*20)
    _a=_SUMMARY["arms"]
    _c=_a.get("corpus",{}); print(f"employer job boards (full text): {_c.get('count') or 0} postings from {_c.get('boards') or 0} boards"+(f"; {_c.get('boards_failed')} board(s) did not answer" if _c.get("boards_failed") else ""))
    for _k,_lab in (("sweep","Workday boards"),("feeds","listing feeds"),("hard-ATS","other employer sites (Oracle/ADP/iCIMS/...)"),("watch","watched employers")):
        _x=_a.get(_k,{})
        if not _x: continue
        _st=("failed to run" if not _x.get("ok") else (f"{_x['errors']} fetch error(s)" if _x.get("errors") else "ok"))
        print(f"{_lab}: "+(f"{_x['count']} found; " if _x.get("count") is not None else "")+_st+(f" - {_x['first_error']}" if _x.get("first_error") else ""))
    print(f"postings that could not be read (page refused or timed out): {_SUMMARY['could_not_read']}")
    print(f"for judgment: {len(ok)} posting(s)"+(f"; blind scorers: about {_SUMMARY['judge'].get('scored',0)} posting(s) scored, {_SUMMARY['judge'].get('deferred',0)} deferred below the top {_SUMMARY['judge'].get('top_n')}" if _SUMMARY.get("judge") else ""))



if __name__ == "__main__":
    main()
