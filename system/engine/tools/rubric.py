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
  <jobkit python> tools/rubric.py merge <runA.json> <runB.json>   # averages runs, re-orders queue_<date>.md
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sys, os, json, datetime, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urlcanon import canon as _curl
from userconfig import WS as ROOT, get as _cfg, run_options as _run_opts   # JOBKIT: workspace = data root
TR=os.path.join(ROOT,"tracking")
RB=os.path.join(TR,"rubric")
PROFILE=os.path.join(ROOT,"profile","profile_blind.md")   # JOBKIT: the blind profile lives in My Job Search/profile/
TODAY=datetime.date.today().isoformat()

# JOBKIT: a workspace may override the scorer instructions with profile/rubric_prompt_header.txt (same contract: output JSON only).
_PH=os.path.join(ROOT,"profile","rubric_prompt_header.txt")
PROMPT_HEADER="""You are scoring job fit BLIND. Read the candidate profile below, then each job
description file. You know NOTHING else: no application outcomes, no other scores, no company
reputation beyond what the JD says. Score each job for THIS candidate on 0-100 overall plus
sub-scores (each 0-10): skills (required-vs-preferred technical match — weigh the JD's REQUIRED
block heavily, forgive gaps in preferred), experience (level/seniority fit - read the profile's LEVEL line and judge against it), location
(0-10; read the profile's LOCATION line: commutable, relocation stance), career (would this role use and grow the
candidate's core strengths, or park them in an unrelated lane).
Honor the profile's DOES-NOT-HAVE list absolutely: a job whose core duty requires a listed
never-claim is scored low on skills no matter how attractive it looks.
Output ONLY valid JSON, no prose: {"<id>": {"skills": n, "experience": n, "location": n,
"career": n, "overall": n}, ...} covering every id listed.
"""

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
    items.sort(key=lambda x:(0 if _LANE(x.get('title','') or '',_jdtext(x['jd'])) else 1,-_score(x)))
    deferred=items[top_n:] if top_n and len(items)>top_n else []
    items=items[:top_n] if top_n else items
    if deferred:
        _led=set()
        dp=os.path.join(TR,"dispositions.jsonl")
        if os.path.exists(dp):
            for l in open(dp,encoding="utf-8"):
                try: _d=json.loads(l); _led.add(_curl(_d['url'])) if _d.get('decision')!="DEFER" else None
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
    print("NEXT (agent ritual): spawn TWO independent blind subagents, each given ONLY the")
    print(f"prompt file above - the SAME file, verbatim, for both (an identical prompt is cached once) -")
    print(f"(run A writes run_A_{TODAY}.json, run B writes run_B_{TODAY}.json),")
    print(f"then: <jobkit python> tools/rubric.py merge {RB}/run_A_{TODAY}.json {RB}/run_B_{TODAY}.json")

def merge(pa,pb):
    man=json.load(open(os.path.join(RB,f"batch_{TODAY}.json"), encoding="utf-8"))
    A=json.load(open(pa, encoding="utf-8")); B=json.load(open(pb, encoding="utf-8"))
    # 2026-09-12 code audit HIGH-1: ids are positional; refuse to merge runs whose id sets differ from the batch
    if set(A)!=set(man) or set(B)!=set(man):
        sys.exit(f"rubric merge ABORTED: id sets differ (batch {len(man)}, A {len(A)}, B {len(B)}) - re-run the blind agents on the current prompt")
    scr=json.load(open(os.path.join(TR,"minquals_screened.json"), encoding="utf-8"))
    by_url={v['url']:k for k,v in man.items()}
    rows=[]
    for x in scr:
        k=by_url.get(x.get('url'))
        if k is None or k not in A or k not in B: continue
        a,b=A[k].get('overall',0),B[k].get('overall',0)
        x['rubric']=round((a+b)/2,1); x['rubric_delta']=abs(a-b)
        rows.append(x)
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
        """True when the saved JD is too thin, or reads as navigation chrome, to judge on."""
        jd=x.get('jd')
        if not jd or not os.path.exists(jd): return True
        try: t=open(jd,encoding='utf-8',errors='ignore').read()
        except Exception: return True
        body=t.split('==========')[-1] if '==========' in t else t
        body=re.sub(r"\s+"," ",body).strip()
        return len(body) < 700 or not _QUAL.search(body)
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
            if x['rubric']<40 and x['rubric_delta']<15 and not _PROTECT.search(x.get('title','')) \
                    and not _LANE(x.get('title','') or '', _jdtext(x.get('jd','') or '')) \
                    and not _stub(x) and _curl(x['url']) not in _led:
                f.write(json.dumps(dict(date=TODAY,url=x['url'],decision="SKIP",
                    reason=f"AUTO(rubric): dual-blind avg {x['rubric']:.0f} (Δ{x['rubric_delta']}) below 40 — {x.get('src','')[:20]} {x.get('title','')[:50]}"))+"\n")
                x['fitclass']="AUTOSKIP"; _auto+=1
                print(f"  AUTO-SKIP(rubric {x['rubric']:.0f}): {x.get('src','')[:18]} - {x.get('title','')[:55]}")
    _stubs=[x for x in rows if x.get('fitclass')!="AUTOSKIP" and _stub(x)]
    for x in _stubs: x['stub_jd']=True
    print(f"auto-ledgered {_auto} clear rubric rejects (avg<40, delta<15, non-archetype, non-PRIORITY-LANE, non-stub)")
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
            warn=" ⚠Δ%d"%x['rubric_delta'] if x['rubric_delta']>=15 else ""
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
    elif len(sys.argv)>3 and sys.argv[1]=="merge": merge(sys.argv[2],sys.argv[3])
    else: print(__doc__)
