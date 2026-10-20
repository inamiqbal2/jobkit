#!/usr/bin/env python3
"""RUBRIC — blind LLM ranking pass over the screened judgment queue (2026-09-04).
Benchmark evidence (tracking/matchbench/, 27 labeled JDs, 5 real interview-producers):
  deterministic matcher AUC 0.58 · matcher+critic 0.54 · blind LLM rubric 0.89/0.90 · A+B avg 0.91.
  Rank correlation between independent runs 0.973; single scores wobble up to 20pts on borderline
  cases, so TWO independent runs are averaged and large disagreements are flagged, never trusted.
Division of labor: this file is deterministic (batch prep, prompt generation, merge, ordering).
The ONLY agentic step is two independent scoring subagents that see profile+JD and nothing else —
no match scores, no critic verdicts, no outcomes, no knowledge of each other.

Usage:
  <jobkit python> tools/rubric.py prep                      # after daily.py; writes batch+prompt, prints next steps
  <jobkit python> tools/rubric.py prep-b <runA.json>         # scorer B's prompt: only ids scorer A put in 30-69
  <jobkit python> tools/rubric.py merge <runA.json> <runB.json>   # averages runs (A-only where B did not read), re-orders queue_<date>.md
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sys, os, json, datetime, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urlcanon import canon as _curl
import funnel as _funnel
from userconfig import WS as ROOT, get as _cfg, run_options as _run_opts   # JOBKIT: workspace = data root
TR=os.path.join(ROOT,"tracking")
RB=os.path.join(TR,"rubric")
PROFILE=os.path.join(ROOT,"profile","profile_blind.md")   # JOBKIT: the blind profile lives in My Job Search/profile/
TODAY=datetime.date.today().isoformat()

# JOBKIT: a workspace may override the scorer instructions with profile/rubric_prompt_header.txt (same contract: output JSON only).
_PH=os.path.join(ROOT,"profile","rubric_prompt_header.txt")
# v0.7: the judges' criteria come from the person's own answers (settings.yaml scoring, onboarding phase 14). Skills and
# experience are always scored; location, career fit, pay and remote only when the person said they should count.
from userconfig import scoring as _scoring, location_mode as _location_mode, location as _loc_cfg
def prompt_header():
    sc=_scoring()
    crit=[("skills","skills (required-vs-preferred match: weigh the posting's REQUIRED block heavily, forgive gaps in preferred)"),
          ("experience","experience (level / seniority fit: read the profile's LEVEL line and judge against it)")]
    if sc["location"]!="no":
        crit.append(("location","location (read the profile's LOCATION line: commuting area, moving stance, remote)"+
                     (" - count it only LIGHTLY in overall" if sc["location"]=="a little" else "")))
    if sc["career_fit"]=="yes":
        crit.append(("career","career (would this role use and grow the candidate's core strengths, or park them in an unrelated lane)"))
    if sc["pay"]=="yes":
        crit.append(("pay","pay (the posted pay against the profile's PAY line; no posted pay = 5)"))
    if sc["remote"]=="yes":
        crit.append(("remote","remote (the posting's remote / hybrid / on-site terms against the profile's REMOTE line)"))
    ignore=[]
    if sc["location"]=="no": ignore.append("where the job is")
    if sc["career_fit"]!="yes": ignore.append("whether the job matches the candidate's long-term career direction (any job they can realistically do and get counts)")
    if sc["pay"]!="yes": ignore.append("pay")
    keys=", ".join(f'"{k}": n' for k,_ in crit)
    return ("You are scoring job fit BLIND. Read the candidate profile below, then each job\n"
            "description file IN FULL. You know NOTHING else: no application outcomes, no other scores, no company\n"
            "reputation beyond what the posting says. Score each job for THIS candidate on 0-100 overall plus\n"
            "sub-scores (each 0-10): " + "; ".join(t for _,t in crit) + ".\n"
            "The overall score reflects ONLY these criteria." + (" Do NOT let these count: " + "; ".join(ignore) + "." if ignore else "") + "\n"
            "Honor the profile's DOES-NOT-HAVE list absolutely: a job whose core duty requires a listed\n"
            "never-claim is scored low on skills no matter how attractive it looks.\n"
            # v0.7 (light-vs-Fable test 2026-10-19): fixed anchors keep every model on the same scale, and a verbatim quote per
            # posting proves the judge read it (merge checks each quote against the posting text).
            "Use this scale for overall, the same for every posting:\n"
            "  90 = meets every REQUIRED item at the right level; the kind of job this person is aiming for.\n"
            "  70 = meets the REQUIRED items; gaps only in preferred items or one minor required item.\n"
            "  50 = meets most REQUIRED items but has one material gap (a missing core skill, or one level off).\n"
            "  30 = misses a core REQUIRED item, or is the right field but a different specialty.\n"
            "  10 = a different field or kind of work.\n"
            "Read every posting in full before scoring it. For each id also give \"req\": the posting's own words (under 15 words,\n"
            "copied exactly) for the requirement that most decided your score.\n"
            'Output ONLY valid JSON, no prose: {"<id>": {' + keys + ', "overall": n, "req": "<quote>"}, ...} covering every id listed.\n')
PROMPT_HEADER=prompt_header()

if os.path.exists(_PH): PROMPT_HEADER=open(_PH,encoding="utf-8").read()

_REQ=re.compile(r"(minimum|basic|required|preferred)\s+qualifications|requirements|qualifications|what you(?:'ll)? (?:bring|need)|who you are|about you|skills and experience",re.I)
def cap_text(t,n):
    """At most n characters of a posting for the scorers (settings.yaml run.jd_text_cap_chars): the opening of the posting
    plus the requirements block kept whole, joined by a [...] marker. Short postings are returned untouched."""
    t=t or ""
    if n<=0 or len(t)<=n: return t
    head_n=int(n*0.55)
    head=t[:head_n]
    m=_REQ.search(t,head_n)
    if m:
        start=max(head_n,t.rfind("\n",0,m.start())+1)
        tail=t[start:start+(n-head_n)]
    else:
        tail=t[-(n-head_n):]
    return head+"\n[... trimmed to "+str(n)+" characters; the requirements block follows ...]\n"+tail
def prep():
    scr=json.load(open(os.path.join(TR,"minquals_screened.json"), encoding="utf-8"))
    items=[x for x in scr if x.get('fitclass') in ("CLOSE","STRETCH","LOOSE")
           and x.get('jd') and os.path.exists(x['jd'])]
    if not items:
        print("rubric prep: judgment queue is empty - nothing to score."); return
    os.makedirs(RB,exist_ok=True)
    # ── v0.5 COST KNOBS (settings.yaml run.judge_top_n / run.jd_text_cap_chars; audit section 5) ──
    # Only the top N by the deterministic match score (priority-lane postings first) go to the two blind scorers; the rest
    # are ledgered DEFER ("not scored - below the top N") and re-surface next run if still open (daily.py does not treat
    # DEFER as judged). Each posting is trimmed to the cap with its requirements block kept whole.
    _ro=_run_opts(); top_n=int(_ro["judge_top_n"] or 0); cap=int(_ro["jd_text_cap_chars"] or 0)
    from lanes import is_priority as _LANE
    def _jdtext(p):
        try: return open(p,encoding='utf-8',errors='ignore').read()
        except Exception: return ''
    def _score(x): return float(x.get('score') or x.get('jdmatch') or 0)
    # v0.7 LOCATION MODE (settings.yaml location.mode, chosen at setup). "Local" = the commuting-area pattern (location.tier1_regex,
    # which includes Remote) matches the posting's location or the first part of its text (multi-site postings list cities there).
    _mode=_location_mode(); _T1=re.compile(_loc_cfg()["tier1_regex"] or r"Remote",re.I)
    _LOCLINE=re.compile(r"location|,\s*[A-Z]{2}\b|\bremote\b|\bhybrid\b|\$\s?\d",re.I); _LEGAL=re.compile(r"fair chance|ordinance|\blaw\b|act of|regulation",re.I)
    def _local(x):
        """Inside the commuting area: the posting's location string, or a location-like line of its text (multi-site postings
        list cities with their pay); legal boilerplate ("New York City's Fair Chance Act") never counts."""
        if _T1.search(str(x.get('loc','') or '')): return True
        for ln in _jdtext(x['jd'])[:8000].splitlines():
            if len(ln)<200 and _LOCLINE.search(ln) and not _LEGAL.search(ln) and _T1.search(ln): return True
        return False
    if _mode=="local_only":
        _away=[x for x in items if not _local(x)]
        if _away:
            dp0=os.path.join(TR,"dispositions.jsonl")
            _seen=set()   # v0.8 (M6): a same-day re-run must not append the same AUTO(location) line again
            if os.path.exists(dp0):
                for l in open(dp0,encoding="utf-8"):
                    try: _seen.add(_curl(json.loads(l)['url']))
                    except Exception: pass
            with open(dp0,"a",encoding="utf-8") as f:
                for x in _away:
                    if _curl(x['url']) in _seen: continue
                    f.write(json.dumps(dict(date=TODAY,url=_curl(x['url']),decision="SKIP",
                        reason=f"AUTO(location): outside your commuting area - you chose to stay local (settings.yaml location.mode) - {x.get('src','')[:20]} {x.get('title','')[:50]}"))+"\n")
            print(f"rubric prep: {len(_away)} posting(s) outside your commuting area set aside (you chose to stay local)")
            items=[x for x in items if _local(x)]
    _locrank=(lambda x: 0 if _local(x) else 1) if _mode in ("local_first","unsure") else (lambda x: 0)
    items.sort(key=lambda x:(0 if _LANE(x.get('title','') or '',_jdtext(x['jd'])) else 1,_locrank(x),-_score(x)))
    deferred=items[top_n:] if top_n and len(items)>top_n else []
    items=items[:top_n] if top_n else items
    if deferred:
        _led=set()
        dp=os.path.join(TR,"dispositions.jsonl")
        if os.path.exists(dp):
            for l in open(dp,encoding="utf-8"):
                try:
                    _d=json.loads(l)
                    if _d.get('decision')!="DEFER" or _d.get('date')==TODAY: _led.add(_curl(_d['url']))   # v0.8 (M6): one DEFER line per day
                except Exception: pass
        with open(dp,"a",encoding="utf-8") as f:
            for x in deferred:
                if _curl(x['url']) in _led: continue
                f.write(json.dumps(dict(date=TODAY,url=_curl(x['url']),decision="DEFER",
                    reason=f"not scored - below the top {top_n} by match score (run.judge_top_n); re-surfaces next run if still open - {x.get('src','')[:20]} {x.get('title','')[:50]}"))+"\n")
        print(f"rubric prep: {len(deferred)} posting(s) deferred (below the top {top_n} by match score; settings.yaml run.judge_top_n) - they come back next run")
    man={}; total_chars=0
    for i,x in enumerate(items):
        jd=x['jd']
        if cap:
            t=_jdtext(jd)
            if len(t)>cap:
                jd=os.path.join(RB,f"jd_{i:02d}_{TODAY}.txt")
                open(jd,"w",encoding="utf-8").write(cap_text(t,cap))
            total_chars+=min(len(t),cap+120)
        else: total_chars+=len(_jdtext(jd))
        man[f"{i:02d}"]=dict(title=x.get('title',''),src=x.get('src',''),url=x.get('url',''),jd=jd,jd_full=x['jd'])
    json.dump(dict(top_n=top_n,scored=len(man),deferred=len(deferred),cap_chars=cap,chars_per_scorer=total_chars,
                   est_input_tokens_per_scorer=int(total_chars/4)+3000),open(os.path.join(RB,"judge_plan.json"),"w",encoding="utf-8"),indent=1)
    mp=os.path.join(RB,f"batch_{TODAY}.json")
    # 2026-09-12 HIGH-1: if blind runs already exist for today and the batch changed, park them aside
    for _r in ("A","B"):
        _rp=os.path.join(RB,f"run_{_r}_{TODAY}.json")
        if os.path.exists(_rp) and os.path.exists(mp):
            try:
                if set(json.load(open(_rp, encoding="utf-8")))!=set(man): os.replace(_rp,_rp+".stale"); print(f"rubric prep: parked stale run_{_r} (id set changed)")
            except Exception: pass
    json.dump(man,open(mp,"w", encoding="utf-8"),indent=1)
    pp=os.path.join(RB,f"prompt_{TODAY}.txt")
    with open(pp,"w", encoding="utf-8") as f:
        f.write(PROMPT_HEADER)
        f.write(f"\n== CANDIDATE PROFILE (read this file): {PROFILE}\n")
        f.write("\n== JOBS TO SCORE (id -> JD file to read):\n")
        for k,v in man.items(): f.write(f"  {k}: {v['jd']}\n")
        f.write(f"\nWrite your JSON to: {RB}/run_<A|B>_{TODAY}.json\n")
    print(f"rubric prep: {len(man)} queue items -> {mp}  (about {len(man)} postings scored, ~{total_chars//1000}k characters of postings per scorer, ~{(total_chars//4+3000)//1000}k input tokens each)")
    print(f"agent prompt -> {pp}")
    print("NEXT (agent ritual): spawn blind scorer A on the prompt file above, verbatim (run A writes run_A_"+TODAY+".json),")
    print(f"then: <jobkit python> tools/rubric.py prep-b {RB}/run_A_{TODAY}.json  (writes prompt_B with A's borderline ids),")
    print(f"then a second, independent blind scorer B on prompt_B_{TODAY}.txt (writes run_B_{TODAY}.json),")
    print(f"then: <jobkit python> tools/rubric.py merge {RB}/run_A_{TODAY}.json {RB}/run_B_{TODAY}.json")

# ── 2026-10-16 port: CONDITIONAL SCORER B (prep-b) ─────────────────────────────────────────────────────────────────────
# Scorer A reads every posting. Scorer B is only needed where one score could decide wrongly: A's 30-69 band (rubric.b_band
# in settings.yaml to change it). Below 30 A alone is a clear reject; at 70+ A alone is a clear build. This roughly halves
# the second scorer's cost. The merge treats an id A scored and B did not as a single-judge score (delta 0, tagged A-only).
def _b_band():
    try: lo,hi=_cfg("rubric.b_band",[30,70]); return float(lo),float(hi)
    except Exception: return 30.0,70.0
def prep_b(pa):
    man=json.load(open(os.path.join(RB,f"batch_{TODAY}.json"), encoding="utf-8"))
    A=json.load(open(pa, encoding="utf-8"))
    if set(A)!=set(man): sys.exit(f"prep-b ABORTED: run A covers {len(A)} ids, the batch has {len(man)} - finish run A first")
    lo,hi=_b_band()
    ids=[k for k in man if lo<=float(A[k].get('overall',0))<hi]
    json.dump(ids,open(os.path.join(RB,f"b_ids_{TODAY}.json"),"w",encoding="utf-8"))
    pp=os.path.join(RB,f"prompt_B_{TODAY}.txt")
    with open(pp,"w",encoding="utf-8") as f:
        f.write(PROMPT_HEADER)
        f.write(f"\n== CANDIDATE PROFILE (read this file): {PROFILE}\n")
        f.write("\n== JOBS TO SCORE (id -> JD file to read):\n")
        for k in ids: f.write(f"  {k}: {man[k]['jd']}\n")
        f.write(f"\nWrite your JSON to: {RB}/run_B_{TODAY}.json\n")
    print(f"prep-b: scorer B reads {len(ids)} of {len(man)} postings (scorer A's {lo:g}-{hi:g} band) -> {pp}")

# ── 2026-10-16 port: 14-DAY BEST-SCORE HISTORY ──────────────────────────────────────────────────────────────────────────
# Every merged score is appended to tracking/rubric/score_history.jsonl. A posting that scored at or above the build line
# in the last 14 days is never auto-skipped on a lower re-score (blind scorers wobble), and decide.py SKIP checks it too.
HIST=os.path.join(RB,"score_history.jsonl")
def best_recent(url,days=14):
    cu=_curl(url); cut=(datetime.date.today()-datetime.timedelta(days=days)).isoformat(); best=None
    if os.path.exists(HIST):
        for l in open(HIST,encoding="utf-8"):
            try: h=json.loads(l)
            except Exception: continue
            if h.get('url')==cu and h.get('date','')>=cut: best=max(best or 0,float(h.get('rubric',0)))
    return best

def merge(pa,pb):
    man=json.load(open(os.path.join(RB,f"batch_{TODAY}.json"), encoding="utf-8"))
    A=json.load(open(pa, encoding="utf-8")); B=json.load(open(pb, encoding="utf-8"))
    # 2026-09-12 code audit HIGH-1: ids are positional; refuse to merge runs whose id sets differ from the batch.
    # 2026-10-16: B may cover only the prep-b subset (b_ids_<today>.json), exactly.
    _bp=os.path.join(RB,f"b_ids_{TODAY}.json")
    _bset=set(json.load(open(_bp,encoding="utf-8"))) if os.path.exists(_bp) and set(B)!=set(man) else set(man)
    if set(A)!=set(man) or set(B)!=_bset:
        sys.exit(f"rubric merge ABORTED: id sets differ (batch {len(man)}, A {len(A)}, B {len(B)}, B expected {len(_bset)}) - re-run the blind agents on the current prompt")
    # v0.7 READING CHECK: each judge quotes the deciding requirement per posting; a quote that is not in the posting means the
    # judge did not read it. Reported per judge; more than 20% unverifiable quotes = re-run that judge.
    def _norm(t): return re.sub(r"[^a-z0-9]+"," ",str(t or "").lower()).strip()
    for _tag,_run in (("A",A),("B",B)):
        _bad=[]; _n=0
        for k,v in _run.items():
            q=_norm(v.get('req',''))
            if not q: _bad.append(k); continue
            _n+=1
            try: _t=_norm(open(man[k]['jd_full'] if os.path.exists(man[k].get('jd_full','')) else man[k]['jd'],encoding='utf-8',errors='ignore').read())
            except Exception: _t=""
            if q not in _t: _bad.append(k)
        if _run:
            share=len(_bad)/len(_run)
            print(f"reading check, judge {_tag}: {len(_run)-len(_bad)}/{len(_run)} quotes found in the postings"+(f" - WARNING: judge {_tag} may not have read {len(_bad)} posting(s) ({', '.join(_bad[:8])}); re-run it" if share>0.2 else ""))
    scr=json.load(open(os.path.join(TR,"minquals_screened.json"), encoding="utf-8"))
    by_url={v['url']:k for k,v in man.items()}
    rows=[]
    for x in scr:
        k=by_url.get(x.get('url'))
        if k is None or k not in A: continue
        a=A[k].get('overall',0)
        if k in B:
            b=B[k].get('overall',0); x['rubric']=round((a+b)/2,1); x['rubric_delta']=abs(a-b); x.pop('single_judge',None)
        else:
            x['rubric']=float(a); x['rubric_delta']=0; x['single_judge']=True
        x['best14']=best_recent(x['url'])
        rows.append(x)
    with open(HIST,"a",encoding="utf-8") as f:
        for x in rows: f.write(json.dumps(dict(date=TODAY,url=_curl(x['url']),rubric=x['rubric'],single=bool(x.get('single_judge'))))+"\n")
    json.dump(scr,open(os.path.join(TR,"minquals_screened.json"),"w", encoding="utf-8"),indent=1)
    # AUTO-LEDGER of clear rubric rejects (2026-09-09, after audit found 23/45 queue items were
    # recurring sub-50 re-scores). THREE GUARDS, all evidence-bounded by tracking/matchbench:
    #   avg<40  — 86% of benchmark negatives sit below 40; lowest non-archetype interview-producer
    #             (Thea) averaged 45.
    #   Δ<15    — both blind runs must agree (Thea's own runs split 55/35 — she would be exempt).
    #   archetype exemption — Bruker (a REAL interview) averaged 23.5: the instruments/applications-
    #             scientist lane is a rubric blind spot and never auto-skips.
    # STUB-JD GUARD. An auto-skip is PERMANENT, so it must never be made on text nobody read. ASML was skipped 3x on a 5-line stub before the audit re-opened it -> interview.
    # On this run five JD files held only site navigation (4x CoreWeave, 1x Steel Dynamics metallurgist)
    # and four were auto-skipped. A thin or boilerplate-only JD now goes to the human instead.
    _QUAL=re.compile(r"(qualificat|responsib|requirement|years? of experience|degree in|bachelor|master|ph\.?d|you will|what you)",re.I)
    def _stub(x):
        """True when the saved JD is too thin, or reads as navigation chrome, to judge on (funnel.stub_text)."""
        jd=x.get('jd')
        if not jd or not os.path.exists(jd): return True
        try: return _funnel.stub_text(open(jd,encoding='utf-8',errors='ignore').read())
        except Exception: return True
    from userconfig import thresholds as _th
    _AUTO_SKIP=float(_th()["auto_skip_below_rubric"])   # v0.8 (code audit H4): the documented setting now decides; it was hard-coded 40
    _PROTECT=re.compile(_cfg("rubric.protect_title_regex", r"(?!x)x") or r"(?!x)x",re.I)   # JOBKIT: archetype the rubric is known to under-score for THIS user (settings.yaml rubric.protect_title_regex); default none
    # PRIORITY LANE: the user's declared target job type never auto-skips on rubric score. See tools/lanes.py.
    from lanes import is_priority as _LANE
    def _jdtext(p):   # 2026-09-29 audit fix #2: the lane check must read the JD TEXT, not the file path
        try: return open(p,encoding='utf-8',errors='ignore').read()
        except Exception: return ''
    _led=set()
    dp=os.path.join(TR,"dispositions.jsonl")
    if os.path.exists(dp):
        for l in open(dp, encoding="utf-8"):
            try: _led.add(_curl(json.loads(l)['url']))
            except Exception: pass
    _auto=0
    with open(dp,"a", encoding="utf-8") as f:
        for x in rows:
            if x['rubric']<_AUTO_SKIP and x['rubric_delta']<15 and not _PROTECT.search(x.get('title','')) \
                    and not _LANE(x.get('title','') or '', _jdtext(x.get('jd','') or '')) \
                    and not _stub(x) and _curl(x['url']) not in _led \
                    and not (x.get('best14') and x['best14']>=_cfg("thresholds.build_default_min_rubric",60)):
                f.write(json.dumps(dict(date=TODAY,url=_curl(x['url']),decision="SKIP",
                    reason=f"AUTO(rubric): dual-blind avg {x['rubric']:.0f} (Δ{x['rubric_delta']}) below {_AUTO_SKIP:.0f} — {x.get('src','')[:20]} {x.get('title','')[:50]}"))+"\n")
                x['fitclass']="AUTOSKIP"; _auto+=1
                print(f"  AUTO-SKIP(rubric {x['rubric']:.0f}): {x.get('src','')[:18]} - {x.get('title','')[:55]}")
    _stubs=[x for x in rows if x.get('fitclass')!="AUTOSKIP" and _stub(x)]
    for x in _stubs: x['stub_jd']=True
    print(f"auto-ledgered {_auto} clear rubric rejects (avg<{_AUTO_SKIP:.0f}, delta<15, non-archetype, non-PRIORITY-LANE, non-stub)")
    if _stubs:
        print(f"  WARN: {len(_stubs)} item(s) had a THIN/BOILERPLATE JD - auto-skip withheld, sent to judgment:")
        for x in _stubs: print(f"      {x.get('src','')[:16]} - {x.get('title','')[:60]} (rubric {x.get('rubric')})")
    rows=[x for x in rows if x.get('fitclass')!="AUTOSKIP"]
    # rewrite the judgment queue ordered by rubric average (benchmark: this ordering put 4/5
    # interview-producers in the top 5; fitclass ordering put 1-2).
    qp=os.path.join(TR,f"queue_{TODAY}.md")
    rows.sort(key=lambda x:-x['rubric'])
    # Export-control TAG (export_gated): informational; a user rule may prefer untagged postings. Rubric order unchanged.
    from eligibility import EXPORT as _EXPORT
    for x in rows: x['itar']=bool(_EXPORT.search(_jdtext(x.get('jd','') or '')))
    with open(qp,"w", encoding="utf-8") as f:
        f.write(f"# Judgment queue — {TODAY} — RUBRIC-ORDERED (dual blind runs, averaged)\n\n")
        f.write("Judge top-down. ⚠Δ = the two blind runs disagreed by >=15pts: borderline case, read closely.\n\n")
        for x in rows:
            warn=(" ⚠Δ%d"%x['rubric_delta'] if x['rubric_delta']>=15 else "")+(" A-only" if x.get('single_judge') else "")+(f" best14d {x['best14']:.0f}" if x.get('best14') and x['best14']>x['rubric'] else "")
            _c=(f" · ${x['band_lo']/1000:.0f}-{x['band_hi']/1000:.0f}K" + (" LOWBAND" if x.get('lowband') else "")) if x.get('band_hi') else " · $?"
            _it=" · ⚠ITAR" if x.get('itar') else " · noITAR"
            f.write(f"## [RUBRIC {x['rubric']:.0f}{warn}{_c}{_it} · {x['fitclass']} · {x.get('band')} T{x.get('tier')} "
                    f"{x.get('age')}d · det {float(x.get('score') or 0):.2f}] {x['src']} — {x['title']}\n")
            f.write(f"{x.get('loc','')} | CRITIC: {x.get('critic','?')}\n{x['url']}\nJD: {x.get('jd','')}\n\n")
    print(f"merged: {len(rows)} items rubric-ordered -> {qp}  ({sum(1 for x in rows if not x.get('itar'))} noITAR / {sum(1 for x in rows if x.get('itar'))} ITAR)")
    for x in rows[:10]:
        w=" ⚠Δ%d"%x['rubric_delta'] if x['rubric_delta']>=15 else ""
        _c=f"${x['band_hi']/1000:.0f}K" if x.get('band_hi') else "$?"
        print(f"  {x['rubric']:5.1f}{w:6s} {_c:>6s} {x['src'][:18]:18s} {x['title'][:50]}")

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="prep": prep()
    elif len(sys.argv)>2 and sys.argv[1]=="prep-b": prep_b(sys.argv[2])
    elif len(sys.argv)>3 and sys.argv[1]=="merge": merge(sys.argv[2],sys.argv[3])
    else: print(__doc__)
