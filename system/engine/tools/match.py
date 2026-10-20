#!/usr/bin/env python3
"""MATCH - score EVERY corpus posting against the user's full profile (title-blind Stage 2).
Score = 0.55*TFIDF-cosine(profile, JD) + 0.45*signature-term hits (capped).
Eligibility-only drops (not fit drops): outside the country of search, clearance/citizen-only (per the
user's work-authorization flags), intern/NCG/temp and excluded role types.
Output: tracking/matched.json (ranked), printed distribution + top preview.

EVERYTHING field-specific is workspace data: profile/signals.yaml (see My Job Search/profile/signals.yaml.example):
  lanes.<name>.role: home          -> SIG  "is this JD about my field?"        (all home lanes merged)
  lanes.<name>.role: transferable  -> SIGX "does the work run on my portable strengths?" (merged)
  lanes.<name>.role: gate          -> a per-lane second door: domain terms + a lane_ref text + minimums
  thresholds: jd_gate, sig_min, sigx_min, sig_floor
Missing/empty file: the engine runs cosine-only (sig_min 0, no transferable rescue, no lane gates) and
says so; the onboarding skill's calibration step (13) fills the file.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json,re,os,sys,glob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, signals as _signals, thresholds as _user_thresholds, path as _wspath
import geo as _geo
T=lambda p:re.sub(r'[#*`\[\]|>-]',' ',open(p,encoding='utf-8',errors='ignore').read())

def profile_doc():
    parts=[]
    for p in sorted(glob.glob(os.path.join(ROOT,"profile","evidence","*.md"))):
        if "_TEMPLATE" in p: continue
        parts.append(T(p))
    for name in ("skills-inventory.md","publications.md"):
        p=os.path.join(ROOT,"profile",name)
        if os.path.exists(p): parts.append(T(p))
    return " ".join(parts)

# ── SIGNATURE TABLES from profile/signals.yaml ────────────────────────────────────────────────────────────────
def _terms(block):
    """{pattern: weight} from a lane block's `terms` (+ optional `negatives`). Accepts [{pattern, weight}] or {pattern: weight}."""
    out={}
    for key in ("terms","negatives"):
        v=(block or {}).get(key) or []
        if isinstance(v,dict): items=list(v.items())
        else: items=[(d.get("pattern"),d.get("weight")) for d in v if isinstance(d,dict)]
        for pat,w in items:
            if not pat: continue
            try: w=float(w)
            except (TypeError,ValueError): continue
            if key=="negatives" and w>0: w=-w
            out[str(pat)]=int(w) if float(w).is_integer() else w
    return out
def _compile(table): return {k:(re.compile(k,re.I),w) for k,w in table.items()}
_SIGNALS=_signals()
_LANES={str(k):(v or {}) for k,v in (_SIGNALS.get("lanes") or {}).items()}
SIG={}; SIGX={}
for _n,_b in _LANES.items():
    _role=str(_b.get("role","home")).lower()
    if _role=="home": SIG.update(_terms(_b))
    elif _role=="transferable": SIGX.update(_terms(_b))
SIGC=_compile(SIG); SIGXC=_compile(SIGX)
# lane gates: a title-blind SECOND door for lanes whose JDs cannot reach the home-profile-anchored bar
# (the original project's finance-quant / consulting lanes). Each: domain terms + lane_ref text + minimums.
GATES=[]
for _n,_b in _LANES.items():
    if str(_b.get("role","")).lower()!="gate": continue
    _g=_b.get("gate") or {}
    _ref=_b.get("lane_ref") or ""
    if _ref and not os.path.isabs(_ref): _ref=_wspath(_ref)
    GATES.append(dict(name=_n,terms=_compile(_terms(_b)),ref=_ref,
        sigx_min=float(_g.get("sigx_min",8)),domain_min=float(_g.get("domain_min",15)),cos_min=float(_g.get("cos_min",0.05))))
_TH=_SIGNALS.get("thresholds") or {}
JD_GATE=float(_TH.get("jd_gate",_user_thresholds()["jd_gate"]))     # JD-text match bar (0.55*cosine + 0.45*signature)
JD_SIG=float(_TH.get("sig_min",4 if SIG else 0))                     # home-signature weight required with the bar
JD_SIGX=float(_TH.get("sigx_min",12)) if SIGX else float("inf")      # transferable-signature rescue (needs SIGX terms)
JD_SIG_FLOOR=float(_TH.get("sig_floor",-4))                          # a JD whose home signature is this negative is never rescued
# 2026-10-16 port: JD-GATE RESCUE. A posting just under the match bar whose home signature is strong (many of the person's own
# field words) passes, tagged '~SIG' so the queue shows how it got in. signals.yaml thresholds rescue_match / rescue_sig.
JD_GATE_RESCUE=float(_TH.get("rescue_match",0.25)); JD_RESCUE_SIG=float(_TH.get("rescue_sig",8)) if SIG else float("inf")
SIGNALS_EMPTY=not (SIG or SIGX or GATES)
if SIGNALS_EMPTY:
    print("match: profile/signals.yaml has no terms - running COSINE-ONLY (score>=jd_gate, no signature floor). "
          "Calibrate it (onboarding phase 18) before trusting the ranking.",file=sys.stderr)

def _score_table(table,t):
    """Signature score: cap 3 hits per positive term, 2 per negative term."""
    s=0
    for rx,w in table.values():
        n=len(rx.findall(t))
        if n: s+= w*min(n,3) if w>0 else w*min(n,2)
    return s
def sig_score(t): return _score_table(SIGC,t)
def sigx_score(t): return _score_table(SIGXC,t)
def gate_scores(blob,cos_by_gate):
    """{gate name: {'dom': domain-signature, 'cos': cosine to the lane_ref text}}."""
    return {g['name']:dict(dom=_score_table(g['terms'],blob),cos=round(float(cos_by_gate.get(g['name'],0.0)),4)) for g in GATES}

def lane_ref_docs():
    """Plain descriptions of the REQUIRED work of each gate lane (NOT claims about the candidate)."""
    return {g['name']:(T(g['ref']) if g['ref'] and os.path.exists(g['ref']) else "") for g in GATES}
_QUAL=re.compile(r"(qualificat|responsib|requirement|years? of experience|degree in|bachelor|master|ph\.?d|you will|what you)",re.I)
def is_stub_text(t):
    """One stub definition for every arm: funnel.stub_text."""
    import funnel; return funnel.stub_text(t)

# ── ELIGIBILITY DROPS (corpus arm). v1.0 (audit M28): the patterns, the work-authorization switch and the negation guard live
# in eligibility.py - this arm is an EARLY filter and the screener re-decides every survivor, so it fires only on GATE-FORM
# phrases (eligibility.CLEARANCE_RX, wider than the old 'active clearance' but exactly the forms the screener would have
# excluded anyway) and now applies the permanent-resident guard the screener always had (eligibility_hit). The old names stay
# as aliases for daily.py and the tests. ──
from eligibility import (ELIG as NOTJOB, non_us as NONUS_TEST, CITIZEN_ONLY, CLEARANCE, NEVER_RX as _NEVER, NEGATION_RX as _NEG_WORDS,
                         CITIZEN_ONLY_RX as _CITIZEN, CLEARANCE_RX as _CLEARANCE, eligibility_hit as _elig_hit)   # shared eligibility + geo (country-aware)
IN_COUNTRY=_geo.in_country

def judgment_gate(score,sg,sx,gates=None,stub=False):
    """The ONE title-blind judgment gate (used by the corpus arm in daily.py and by the screened arm).
    Returns 'std' (bar + home signature, or bar + transferable rescue), 'gate:<lane>' (a lane gate opened), or None.
    - std:  score>=JD_GATE and (sg>=JD_SIG or (sx>=JD_SIGX and sg>JD_SIG_FLOOR))
    - lane: not a stub JD and sx>=gate.sigx_min and dom>=gate.domain_min and cos>=gate.cos_min and sg>JD_SIG_FLOOR"""
    if score>=JD_GATE and (sg>=JD_SIG or (sx>=JD_SIGX and sg>JD_SIG_FLOOR)): return 'std'
    if score>=JD_GATE_RESCUE and sg>=JD_RESCUE_SIG: return '~SIG'
    if stub: return None
    for g in GATES:
        v=(gates or {}).get(g['name']) or {}
        if sx>=g['sigx_min'] and float(v.get('dom',0))>=g['domain_min'] and float(v.get('cos',0))>=g['cos_min'] and sg>JD_SIG_FLOOR:
            return f"gate:{g['name']}"
    return None
def gate_description():
    s=f"JD-match>={JD_GATE:g} AND [home-sig>={JD_SIG:g}"+(f" OR transferable-sig>={JD_SIGX:g}" if SIGX else "")+"]"
    if SIG: s+=f" OR [JD-match>={JD_GATE_RESCUE:g} AND home-sig>={JD_RESCUE_SIG:g}] (~SIG)"
    for g in GATES: s+=f" OR lane gate {g['name']} [sigx>={g['sigx_min']:g} & dom>={g['domain_min']:g} & cos>={g['cos_min']:g}]"
    return s

def main():
    rows=[json.loads(l) for l in open(os.path.join(ROOT,"tracking","corpus.jsonl"), encoding="utf-8")]
    kept,dropped={},{'geo':0,'inelig':0,'notjob':0,'thin':0}
    docs=[]
    for r in rows:
        if not IN_COUNTRY(r.get('loc') or 'Remote'): dropped['geo']+=1; continue
        if NONUS_TEST(r.get('loc',''), r.get('url',''), r.get('title','')): dropped['geo']+=1; continue
        if len(r['text'])<300: dropped['thin']+=1; continue
        if NOTJOB.search(r['title']): dropped['notjob']+=1; continue
        if _elig_hit(CITIZEN_ONLY, r['text']) or _elig_hit(CLEARANCE, r['text']): dropped['inelig']+=1; continue   # v0.9 (audit H4): "no clearance required" no longer drops
        docs.append(r)
    if not docs:
        json.dump([],open(os.path.join(ROOT,"tracking","matched.json"),"w", encoding="utf-8")); print(f"eligible docs scored: 0  (dropped: {dropped})"); return
    prof=profile_doc()
    vec=TfidfVectorizer(stop_words='english',max_features=60000,ngram_range=(1,2),sublinear_tf=True)
    X=vec.fit_transform([prof]+[d['text'] for d in docs])
    cos=cosine_similarity(X[0:1],X[1:]).ravel()
    refs=lane_ref_docs()
    cosg={n:(cosine_similarity(vec.transform([txt]),X[1:]).ravel() if txt else [0.0]*len(docs)) for n,txt in refs.items()}
    if len(docs)>=200: _fit_save(vec,X[0:1],{n:(vec.transform([txt]) if txt else None) for n,txt in refs.items()})   # v0.9 (M4): score_texts reuses this space
    sig=[sig_score(d['title']+' '+d['text']) for d in docs]
    out=[]
    for i,(d,c,s) in enumerate(zip(docs,cos,sig)):
        score=0.55*min(float(c)/0.14,1.0)+0.45*min(max(s,0),40)/40.0  # FIXED scales (audit: per-run max made thresholds drift)
        blob=d['title']+' '+d['text']
        out.append({**{k:d.get(k,'') for k in('src','title','loc','url','posted','updated')},'cos':round(float(c),4),'sig':s,
                    'sigx':sigx_score(blob),'score':round(score,4),
                    'gates':gate_scores(blob,{n:v[i] for n,v in cosg.items()}),'stub':is_stub_text(d['text'])})
    out.sort(key=lambda r:-r['score'])
    json.dump(out,open(os.path.join(ROOT,"tracking","matched.json"),"w", encoding="utf-8"),indent=1)
    print(f"eligible docs scored: {len(docs)}  (dropped: {dropped})")
    import statistics as st
    sc=[r['score'] for r in out]
    print(f"score dist: max={sc[0]:.3f} p99={sc[len(sc)//100]:.3f} p95={sc[len(sc)//20]:.3f} median={st.median(sc):.3f}")
    print(f"judgment gate: {gate_description()}")
    print("\nTOP 40 (title-blind):")
    for r in out[:40]:
        print(f"  {r['score']:.3f} sig={r['sig']:>3} | {r['src'][:18]:<18} | {r['title'][:62]:<62} | {r['loc'][:28]}")

def strip_aggregator(t):
    """Aggregator detail pages (Adzuna) wrap the employer's JD in ~2-10k chars of site chrome ('What? Where? Search
    Advanced', salary estimates, 'Stats for this job', 'Similar jobs', popular-search link farms) that inflated
    TF-IDF cosine and signatures. Keep only the JD body."""
    if 'Stats for this job' in t or 'back to last search' in t:
        head,_,rest=t.partition('Apply for this job')
        body=rest if rest and len(head)<2500 else t
        body=body.split('Stats for this job')[0].split('Apply for this job')[0]
        first3='\n'.join(t.split('\n')[:3])      # title / location / url lines written by the screener
        return first3+'\n'+body
    return t
_FIT=None
_FITP=os.path.join(ROOT,"tracking","tfidf_fit.pkl")
def _fit_sig():
    """v0.9 (audit M4): identity of the fitted space - the corpus file (size, mtime) and the profile text."""
    import hashlib
    cp=os.path.join(ROOT,"tracking","corpus.jsonl")
    try: st=os.stat(cp); c=(st.st_size,int(st.st_mtime))
    except OSError: c=(0,0)
    return (c,hashlib.md5(profile_doc().encode("utf-8","ignore")).hexdigest())
def _fit_save(vec,P,L):
    try:
        import pickle
        with open(_FITP,"wb") as f: pickle.dump((_fit_sig(),vec,P,L),f)
    except Exception as e: print(f"match: TF-IDF cache not written ({type(e).__name__})",file=sys.stderr)
def _fit_load():
    try:
        import pickle
        with open(_FITP,"rb") as f: sig,vec,P,L=pickle.load(f)
        return (vec,P,L) if sig==_fit_sig() else None
    except Exception: return None
def score_texts(pairs):
    """Title-blind score for arbitrary (title, text) pairs on the SAME fixed scales as the corpus arm
    ('the only thing that matters is a match with the job description').
    Fits the TF-IDF space once per process on profile + corpus, then transforms the extras.
    Returns per pair: (score, sig, sigx, gates) where gates = {lane: {'dom', 'cos'}}."""
    global _FIT
    if _FIT is None: _FIT=_fit_load()   # v0.9 (audit M4): the space match.py fitted minutes ago on the same corpus
    if _FIT is None:
        cp=os.path.join(ROOT,"tracking","corpus.jsonl")
        rows=[json.loads(l) for l in open(cp, encoding="utf-8")] if os.path.exists(cp) else []
        docs=[r['text'] for r in rows if len(r.get('text',''))>=300]
        prof=profile_doc()
        # 2026-10-09: a workspace whose packs have no Greenhouse/Lever/Ashby boards (the academic pack) has an EMPTY corpus.
        # Fitting TF-IDF on the profile alone makes every JD that shares a few profile words score cosine ~1 (the first
        # academic run gave 700 FIU postings m=0.55 flat). Below 200 corpus docs the vectorizer is fitted on the profile
        # plus the texts being scored, so the IDF has a background to weigh against.
        extra=[strip_aggregator(t or '') for _,t in pairs if len(t or '')>=300] if len(docs)<200 else []
        if extra and len(docs)<200: print(f"match.score_texts: corpus has {len(docs)} docs - TF-IDF fitted on profile + {len(extra)} screened JDs",file=sys.stderr)
        vec=TfidfVectorizer(stop_words='english',max_features=60000,ngram_range=(1,2),sublinear_tf=True)
        X=vec.fit_transform([prof]+docs+extra)
        L={n:(vec.transform([txt]) if txt else None) for n,txt in lane_ref_docs().items()}
        _FIT=(vec,X[0:1],L)
        if not extra: _fit_save(vec,X[0:1],L)
    vec,P,L=_FIT
    out=[]
    for title,text in pairs:
        text=strip_aggregator(text or '')
        if len(text)<300: out.append((0.0,0,0,{g['name']:dict(dom=0,cos=0.0) for g in GATES})); continue
        V=vec.transform([text])
        c=float(cosine_similarity(P,V).ravel()[0])
        cg={n:(float(cosine_similarity(lv,V).ravel()[0]) if lv is not None else 0.0) for n,lv in L.items()}
        blob=(title or '')+' '+text
        sg=sig_score(blob); sx=sigx_score(blob)
        out.append((round(0.55*min(c/0.14,1.0)+0.45*min(max(sg,0),40)/40.0,4), sg, sx, gate_scores(blob,cg)))
    return out
if __name__=="__main__": main()
