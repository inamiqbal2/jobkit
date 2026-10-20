#!/usr/bin/env python3
"""MIN-QUALS SCREENER (built 2026-08-26 to make the 20/day target real).

Why it exists: title-level + regex screening passed roles that fail on their actual core
requirements ("Materials Scientist" that is really 5+ yrs ALD; "Research Engineer" that is really
petroleum engineering at NETL). Survival after reading min-quals was ~13% of auto-passed roles.

What it does: fetches each posting, extracts ONLY the Basic/Minimum Qualifications block (and,
separately, Preferred), and auto-flags knockouts. A blocker in MINIMUM quals is fatal; the same
blocker in PREFERRED is not. Output is a compact digest a human can triage 150 roles from.

Usage:  <jobkit python> screen_minquals.py <candidates.json> [max] > digest.md
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json,urllib.request,re,html,sys,os,concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as _WS, work_auth as _work_auth, thresholds as _thresholds, critic_rules as _critic_rules   # JOBKIT: workspace = data root
_WA=_work_auth(); _LBT=_thresholds()['low_band_top']
# JOBKIT: 'no sponsorship' phrases are a knockout only when settings.yaml work_authorization.sponsorship_needed is true
_NO_SPONSOR=r"(?:not|unable to|will not|cannot|do(?:es)? not)\s+(?:offer|provide|consider|sponsor)[^.\n]{0,40}(?:sponsorship|visa)|without (?:the need for )?(?:visa )?sponsorship|must (?:be )?(?:currently )?authorized to work[^.\n]{0,60}without[^.\n]{0,30}sponsor"


# ── 2026-09-29: POLITE FETCHING. With the screen cap lifted, thousands of Workday/Adzuna pages are fetched per
# run; 14 unthrottled threads got tenants to 429 us and ~5,300 fetches failed in one run. Every network call in
# this module now goes through _open(): at most _PER_HOST concurrent requests per host, and retry with
# exponential backoff + jitter on 429/5xx/timeouts (honoring Retry-After).
import threading as _th, time as _time, random as _rnd, urllib.error as _ue
_PER_HOST=3; _HOST_SEM={}; _SEM_LOCK=_th.Lock()
def _host_sem(url):
    h=re.sub(r'^https?://([^/]+).*',r'\1',url if isinstance(url,str) else url.full_url)
    with _SEM_LOCK:
        if h not in _HOST_SEM: _HOST_SEM[h]=_th.BoundedSemaphore(_PER_HOST)
        return _HOST_SEM[h]
from urlcanon import safe_http as _safe_http
def _open(req,timeout=25,tries=4):
    url=req if isinstance(req,str) else req.full_url
    _safe_http(url)   # v0.9 (audit H1): http(s) only
    last=None
    for k in range(tries):
        with _host_sem(url):
            try:
                return urllib.request.urlopen(req,timeout=timeout)
            except _ue.HTTPError as e:
                last=e
                if e.code not in (429,500,502,503,504): raise
                ra=e.headers.get('Retry-After') if e.headers else None
                wait=float(ra) if ra and str(ra).isdigit() else 2**(k+1)
            except (_ue.URLError,TimeoutError,ConnectionError) as e:
                last=e; wait=2**(k+1)
        _time.sleep(min(wait,30)+_rnd.random())
    raise last

def _strip(h):
    h=re.sub(r'<(script|style)[^>]*>.*?</\1>','',h,flags=re.S)
    h=re.sub(r'<li[^>]*>','\n- ',h); h=re.sub(r'</(p|div|h\d|li|ul|tr)>','\n',h)
    return re.sub(r'\n{3,}','\n\n',html.unescape(re.sub(r'<[^>]+>','',h))).strip()

def _generic_fetch(url):
    # GENERIC FALLBACK: plain GET + tag-strip for hard-ATS/feed URLs (oracle/adp/eightfold/
    # phenom/sap/icims/acers/...) which previously died as FETCHFAIL and wasted screen slots.
    import urllib.request as _u, re as _re, html as _h
    try:
        _safe_http(url)
        raw=_open(_u.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read().decode('utf-8','ignore')
        txt=_re.sub(r'<script.*?</script>|<style.*?</style>',' ',raw,flags=_re.S)
        txt=_re.sub(r'\s{2,}',' ',_re.sub(r'<[^>]+>',' ',_h.unescape(txt)))
        return txt if len(txt)>400 else "__THIN__"
    except Exception as e:
        return f"__FETCHFAIL {e}"

# 2026-10-16 port: a posting already in tracking/corpus.jsonl (full text from the board's own API) is never fetched again.
_CORPUS=None; _CORPUS_LOCK=_th.Lock()
def _corpus_text(url):
    global _CORPUS
    with _CORPUS_LOCK:
        if _CORPUS is None:
            _CORPUS={}
            p=os.path.join(_WS,"tracking","corpus.jsonl")
            if os.path.exists(p):
                for line in open(p,encoding="utf-8",errors="ignore"):
                    try: r=json.loads(line)
                    except Exception: continue
                    if r.get("url") and len(r.get("text") or "")>300: _CORPUS[r["url"]]=r["text"]
    return _CORPUS.get(url)

# 2026-10-16 port: Adzuna's landing pages sit behind a bot wall that answers bursts with blocks. Throttle to one page
# every 3.5 s, and after 5 failures stop trying for the rest of the run (screen() then falls back to the API snippet).
_ADZ_LOCK=_th.Lock(); _ADZ_LAST=[0.0]; _ADZ_FAILS=[0]; _ADZ_MAX_FAILS=5; _ADZ_GAP=3.5
def _adzuna_blocked(): return _ADZ_FAILS[0]>=_ADZ_MAX_FAILS
def _adzuna_fetch(url):
    m=re.search(r"adzuna\.[a-z.]+/(?:land/ad|details)/(\d+)",url)
    if not m or _adzuna_blocked(): return None
    with _ADZ_LOCK:
        wait=_ADZ_LAST[0]+_ADZ_GAP-_time.time()
        if wait>0: _time.sleep(wait)
        _ADZ_LAST[0]=_time.time()
    try:
        h=_open(urllib.request.Request(f"https://www.adzuna.com/details/{m.group(1)}",
            headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36',
                     'Accept':'text/html','Accept-Language':'en-US,en;q=0.9'}),timeout=25,tries=2).read().decode('utf-8','ignore')
        d=re.search(r'<section[^>]*class="[^"]*adp-body[^"]*"[^>]*>(.*?)</section>',h,re.S)
        t=_strip(d.group(1)) if d else _strip(h)
        if len(t)>400: return t
    except Exception:
        pass
    _ADZ_FAILS[0]+=1
    return None

def fetch(url):
    try: _safe_http(url)
    except Exception as e: return f"__FETCHFAIL {e}"
    _ct=_corpus_text(url)
    if _ct: return _ct
    # 2026-10-09: a listing that came with its description (feeds.py neogov / json_list / usajobs) was cached at ingest
    import hashlib as _hl
    _fc=os.path.join(_WS,"tracking","jds","feed_"+_hl.md5(url.encode()).hexdigest()[:16]+".txt")
    if os.path.exists(_fc):
        try:
            _t=open(_fc,encoding='utf-8',errors='ignore').read().split("\n\n",1)[-1]
            if len(_t)>300: return _t
        except Exception: pass
    try:
        if "greenhouse.io" in url:
            m=re.search(r"(?:jobs/|gh_jid=)(\d+)",url); s=re.search(r"greenhouse\.io/([a-z0-9_-]+)/jobs",url)
            if s and m:
                d=json.load(_open(urllib.request.Request(
                    f"https://boards-api.greenhouse.io/v1/boards/{s.group(1)}/jobs/{m.group(1)}",
                    headers={'User-Agent':'Mozilla/5.0'}),timeout=20))
                return _strip(d['content'])
        if "lever.co" in url:
            m=re.search(r"lever\.co/([^/]+)/([0-9a-f-]+)",url)
            d=json.load(_open(urllib.request.Request(
                f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}?mode=json",
                headers={'User-Agent':'Mozilla/5.0'}),timeout=20))
            return _strip(d['description']+''.join(l.get('text','')+'\n'+_strip(l.get('content','')) for l in d.get('lists',[])))
        if "ashbyhq.com" in url:
            m=re.search(r"ashbyhq\.com/([^/]+)/([0-9a-f-]+)",url)
            for j in json.load(_open(urllib.request.Request(
                f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}",headers={'User-Agent':'Mozilla/5.0'}),timeout=20))['jobs']:
                if m.group(2) in j['jobUrl']: return _strip(j['descriptionHtml'])
        if ".myworkdaysite.com/" in url:   # 2026-10-16 port: shared Workday host (wdN.myworkdaysite.com/<lang>/recruiting/<tenant>/<site>/job/...)
            m=re.search(r"https://(wd\d+\.myworkdaysite\.com)/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/([^/]+)/([^/]+)(/job/[^?#]*)",url)
            if m:
                host,ten,site,path=m.groups()
                d=json.load(_open(urllib.request.Request(f"https://{host}/wday/cxs/{ten}/{site}{path}",
                    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=20))
                return _strip(d['jobPostingInfo']['jobDescription'])
        if "myworkdayjobs.com" in url:
            m=re.search(r"https://([^.]+)\.([^.]+)\.myworkdayjobs\.com/en-US/([^/]+)(/job/.*)",url)
            if m:
                h,wd,site,path=m.groups()
                d=json.load(_open(urllib.request.Request(
                    f"https://{h}.{wd}.myworkdayjobs.com/wday/cxs/{h}/{site}{path}",
                    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=20))
                return _strip(d['jobPostingInfo']['jobDescription'])
        if "oraclecloud.com" in url:
            m=re.search(r"https://([^/]+)/hcmUI/CandidateExperience/en/sites/([^/]+)/job/(\d+)",url)
            if m:
                h,site,jid=m.groups()
                d=json.load(_open(urllib.request.Request(
                    f'https://{h}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;siteNumber={site},Id="{jid}"',
                    headers={'User-Agent':'Mozilla/5.0'}),timeout=25))
                it=d.get('items',[{}])[0]
                return _strip((it.get('ExternalDescriptionStr') or '')+' '+(it.get('ExternalQualificationsStr') or '')+' '+(it.get('ExternalResponsibilitiesStr') or ''))
        if ".eightfold.ai/" in url:   # 2026-10-16 port: the careers page is an app shell (CSS/JSON config, no job text); the PCSX API has the posting
            m=re.search(r"https://([a-z0-9.-]+\.eightfold\.ai)/[^?#]*\?(?:[^#]*&)?pid=(\d+)",url); dm=re.search(r"[?&]domain=([a-z0-9.-]+)",url)
            if m:
                q=f"position_id={m.group(2)}"+(f"&domain={dm.group(1)}" if dm else "")
                d=json.load(_open(urllib.request.Request(f"https://{m.group(1)}/api/pcsx/position_details?{q}",
                    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=25))
                dd=d.get('data') or {}
                t=_strip(dd.get('jobDescription') or '')
                if len(t)>200: return f"{dd.get('name','')}\n{dd.get('location','')}\n\n{t}"
            return "__FETCHFAIL eightfold position not found"
        if "workforcenow.adp.com" in url:
            m=re.search(r"cid=([0-9a-f-]+).*?ccId=([0-9_]+)",url); j=re.search(r"jobId=(\d+)",url)
            if m and j:
                d=json.load(_open(urllib.request.Request(
                    f"https://workforcenow.adp.com/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions/{j.group(1)}?cid={m.group(1)}&ccId={m.group(2)}&lang=en_US",
                    headers={'User-Agent':'Mozilla/5.0'}),timeout=25))
                return _strip(str(d.get('requisitionDescription','') or d))
        if "jobs.smartrecruiters.com" in url:
            m=re.search(r"smartrecruiters\.com/([^/]+)/([0-9a-zA-Z]+)",url)
            if m:
                d=json.load(_open(urllib.request.Request(
                    f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}",
                    headers={'User-Agent':'Mozilla/5.0'}),timeout=25))
                sec=(d.get("jobAd",{}) or {}).get("sections",{}) or {}
                return _strip(" ".join(str(s.get("text","")) for s in sec.values() if isinstance(s,dict)))
        if "indeed.com" in url:
            m=re.search(r"jk=([0-9a-f]+)|job/[^/]*-([0-9a-f]{10,})",url)
            if m:
                jk=m.group(1) or m.group(2)
                p=os.path.join(_WS,"tracking","jds",f"indeed_{jk}.txt")
                if os.path.exists(p): return open(p,encoding='utf-8',errors='ignore').read()
        # 2026-10-05 fetch-fail audit: 270 of 1,580 screened items (17%) were never read - Adzuna /land/ad/ redirects
        # 403, iCIMS renders the JD inside an iframe, BambooHR loads it from a JSON endpoint.
        if "adzuna." in url and ("/land/ad/" in url or "/details/" in url):
            t=_adzuna_fetch(url)
            if t: return t
            return "__FETCHFAIL adzuna page blocked"
        if ".icims.com/jobs/" in url and "in_iframe" not in url:
            r=_generic_fetch(url.split("?")[0]+"?in_iframe=1")
            if not r.startswith("__"): return r
        if ".bamboohr.com/careers/" in url:
            m=re.search(r"https://([a-z0-9-]+)\.bamboohr\.com/careers/(\d+)",url)
            if m:
                d=json.load(_open(urllib.request.Request(f"https://{m.group(1)}.bamboohr.com/careers/{m.group(2)}/detail",
                    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=25))
                jo=(d.get("result") or {}).get("jobOpening") or {}
                t=_strip(str(jo.get("description") or ""))
                if len(t)>200: return f"{jo.get('jobOpeningName','')}\n{t}"
        if "linkedin.com/jobs/view" in url:
            m=re.search(r"jobs/view/(?:[^/]*-)?(\d{8,})",url)
            if m:
                h=_open(urllib.request.Request(
                    f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}",
                    headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read().decode('utf-8','ignore')
                d=re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>',h,re.S)
                if d: return _strip(d.group(1))
    except Exception as e:
        return f"__FAIL__{type(e).__name__}"
    return _generic_fetch(url)

_BAND=re.compile(r"\$\s?(\d{2,3})(?:[,.]?(\d{3})|\s?([Kk]))\s*(?:/\s?(?:year|yr|annum)|per year|annually)?\s*(?:-|–|—|to)\s*\$?\s?(\d{2,3})(?:[,.]?(\d{3})|\s?([Kk]))")
def _band(t):
    for m in _BAND.finditer(t or ""):
        lo=int(m.group(1)+(m.group(2) or "000")); hi=int(m.group(4)+(m.group(5) or "000"))
        if 60000<=lo<=hi<=500000: return lo,hi
    return None
_EXPIRED=re.compile(r"\b(posting|position|job|opening)[^.]{0,40}\b(expired|no longer (available|accepting)|has been (filled|closed))|>\s*Expired\s*<|- Hybrid Expired",re.I)
MINHDR=re.compile(r"(BASIC QUALIFICATIONS|MINIMUM QUALIFICATIONS|Basic Qualifications|Minimum Qualifications|Required Qualifications|REQUIREMENTS|Requirements:|Qualifications:|What [Ww]e['’]re [Ll]ooking [Ff]or|What [Yy]ou['’]ll [Nn]eed|You [Ww]ill [Nn]eed|Required Skills|REQUIRED QUALIFICATIONS|MINIMUM REQUIREMENTS|WHAT YOU BRING|WHAT YOU'?LL NEED|QUALIFICATIONS)",re.M|re.I)
PREFHDR=re.compile(r"(PREFERRED|Preferred Qualifications|Preferred Skills|Nice to Have|Bonus|Strong Candidates|Ideal Experience|PREFERRED QUALIFICATIONS|NICE TO HAVE|DESIRED QUALIFICATIONS)",re.M|re.I)
def blocks(t):
    m=MINHDR.search(t)
    if not m: return "",""
    rest=t[m.end():]
    p=PREFHDR.search(rest)
    return (rest[:p.start()] if p else rest[:1400]).strip()[:1400], (rest[p.end():p.end()+900].strip() if p else "")

# --- KNOCKOUT CLASSES. In MIN quals => fatal (BLOCKED -> routed to judgment as a flagged STRETCH); in PREFERRED => soft flag.
# Built-in (every user, switched by the work-authorization flags): clearance, citizen-only, no-sponsorship.
# Everything the user genuinely does NOT have is WORKSPACE data: profile/critic_rules.yaml -> screen_block {key: regex}.
# Empty = no field-specific knockouts (only years bars and eligibility act).
# v1.0 (audit M28): the two built-in classes are eligibility.py's switched patterns (a never-matching regex when the person's
# work-authorization flag opens the class), so the switch is applied once, here, and not again after the fact. Consequence:
# a person with clearance_possible=true no longer gets a "clearance" SOFT flag from the preferred block (it is not a miss for them).
from eligibility import (CITIZEN_ONLY as _CITIZEN_ONLY, CLEARANCE as _CLEARANCE, CLEARANCE_MENTION as _CLEARANCE_MENTION, NEVER_RX as _NEVER,
                         NEGATION_RX as _NEG, PR_INCL_RX as _PR_INCL, PR_EXCL_RX as _PR_EXCL, negated_matches as _negated_matches, eligibility_hit)
_BUILTIN_BLOCK={
 "clearance":_CLEARANCE_MENTION,   # inside the min-quals block ANY mention is the requirement
 "citizen-only":_CITIZEN_ONLY,
}
_USER_BLOCK={str(k):str(v) for k,v in ((_critic_rules().get("screen_block") or {}).items()) if v and str(k) not in _BUILTIN_BLOCK}
BLOCK={**_BUILTIN_BLOCK,**_USER_BLOCK}
# soft-flag keys that auto-exclude a posting from the judgment queue (daily.py), e.g. a domain the user has never once
# applied to. critic_rules.yaml -> screen_auto_exclude_soft: [key, ...]; default none.
AUTO_EXCLUDE_SOFT=[str(x) for x in (_critic_rules().get("screen_auto_exclude_soft") or [])]
YRS=re.compile(r"(\d+)\s*(?:-|–|to)\s*\d+\s*(?:\+\s*)?years|(\d+)\+?\s*(?:or more\s*)?years",re.I)   # v0.9 (M19): "3-5 years" -> 3, never 5
def years_mentioned(scope):
    """Experience bars in a text: the lower bound of a range; numbers over 25 ignored (company-age blurbs)."""
    out=set()
    for a,b in YRS.findall(scope or ""):
        v=int(a or b)
        if v<=25: out.add(v)
    return sorted(out)
# 2026-09-09 comp analysis: the market credits a PhD against years ("PhD and 1 year" = Senior at
# TerraPower L11; "PhD with 0-3 years" at Pfizer; Lila titles PhD+1-5yr postdoc Senior). These
# ladder clauses waive the >=5-yr STRETCH/YEARS knockout so Senior-titled roles reach judgment.
PHD_WAIVER=re.compile(r"Ph\.?D\.?.{0,80}(in lieu of|may substitute|counts? (for|as)|equivalent to)|advanced degree.{0,40}in lieu|higher level degree as a substitute"
    r"|Ph\.?D\.?\s*(?:degree)?\s*(?:and|with|\+|plus)\s*(?:0|1|2|zero|one|two)(?:\s*(?:-|–|to)\s*\d)?\s*(?:\+\s*)?(?:years?|yrs)"
    r"|Ph\.?D\.?[^.]{0,40}\b0\s*(?:-|–|to)\s*[1-3]\s*(?:years?|yrs)"
    r"|(?:doctora(?:te|l)|Ph\.?D\.?)[^.]{0,60}(?:or equivalent (?:practical )?experience|or equivalent combination)",re.I|re.S)

# 2026-09-10: BLOCK patterns fired on NEGATED statements — "Security Clearance: None required"
# and "No security clearance is required" both matched, and because clearance auto-ledgers as
# INELIGIBLE those jobs died unseen (caught when LLNL scored 68 blind while the critic killed it).
# v1.0 (audit M28): the negation guard itself (clause window, negation words) is eligibility.negated_matches, shared with
# match.py and critic.py; only the alternatives-list test, a screener-specific reading of user knockouts, stays here.
_ALT=re.compile(r"(one or more of|such as|e\.g\.|for example|including|and/or|familiarity with)[^.]{0,80}$",re.I)
def _hit(pat,text,win=22):
    """True only for a NON-negated match that is not inside an alternatives list ("familiarity with X, Y or Z")."""
    t=text or ""
    return any(not _ALT.search(t[max(0,m.start()-90):m.start()]) for m in _negated_matches(pat,t,win))
_elig_hit=eligibility_hit   # a gate the person actually fails (negation, Public Trust and permanent-resident wording): eligibility.py

_GC_ELIGIBLE=re.compile(r"(?:green[- ]card holders?|(?:lawful )?permanent residents?)[^.;]{0,90}\b(?:are|is)\s+eligible(?:\s+to\s+apply)?",re.I)
def screen(rec):
    txt=fetch(rec['url'])
    if txt.startswith("__") and len(str(rec.get('desc') or ''))>150:   # 2026-10-16 port: page unreadable -> the listing's own snippet
        txt=str(rec['desc']); rec=dict(rec,snippet_only=True)
    if txt.startswith("__"): return dict(rec,verdict="FETCHFAIL",minq="",pref="",flags=[txt])
    # persist the full JD so downstream steps (critic, build) run on the same text deterministically
    import hashlib
    _jdir=os.path.join(_WS,"tracking","jds")
    os.makedirs(_jdir,exist_ok=True)
    _jp=os.path.join(_jdir,hashlib.md5(rec['url'].encode()).hexdigest()[:16]+".txt")
    open(_jp,"w", encoding="utf-8").write(f"{rec.get('title','')}\n{rec.get('loc','')}\n{rec['url']}\n\n{txt}")
    rec=dict(rec,jd=_jp)
    _b=_band(txt)
    if _b: rec["band_lo"],rec["band_hi"]=_b; rec["lowband"]=bool(_LBT and _b[1]<int(_LBT))   # JOBKIT: settings.yaml thresholds.low_band_top
    if _EXPIRED.search(txt or ""):   # v0.8 (code audit H3): return at once - the earlier mark was overwritten by the final return
        return dict(rec,verdict="EXPIRED",fitclass="EXCLUDED",minq="EXPIRED posting",pref="",flags=["expired"],soft=[],yrs=[],waiver=False)
    mn,pf=blocks(txt)
    scope = mn if mn else txt[:1500]
    flags=[k for k,p in BLOCK.items() if (_elig_hit(p,scope) if k in ("clearance","citizen-only") else _hit(p,scope))]
    # Hard eligibility phrases are frequently OUTSIDE the min-quals block (EEO/footer sections), so the GATE-FORM patterns are
    # checked against the WHOLE posting (2026-09-10). v1.0 (audit M28): each under its OWN class - before, a whole-posting
    # clearance gate was filed as "citizen-only", so a person with citizenship open but clearance closed never saw that knockout
    # and the reverse person was excluded from a job open to them. The switched patterns never match for an open class
    # (settings.yaml work_authorization flags), so no filter is needed afterwards.
    for k,p in (("citizen-only",_CITIZEN_ONLY),("clearance",_CLEARANCE)):
        if k not in flags and _elig_hit(p,txt): flags.append(k)
    if _WA["sponsorship_needed"] and _hit(_NO_SPONSOR,txt): flags.append("no-sponsorship")
    softflags=[k for k,p in BLOCK.items() if pf and _hit(p,pf) and k not in flags]
    yrs=years_mentioned(scope)
    waiver=bool(PHD_WAIVER.search(txt))
    # employer EXPLICITLY lists permanent residents as eligible next to a clearance line ("Only U.S. Citizens, Green
    # Card holders ... are eligible to apply. Security Clearance eligibility is required.") -> the clearance line is the
    # employer's own contradiction; route to judgment with a soft flag, never auto-exclude.
    if "citizen-only" not in flags and "clearance" in flags and _GC_ELIGIBLE.search(txt or ""):
        flags=[f for f in flags if f!="clearance"]; softflags=softflags+["clearance-vs-GC-eligible"]
    verdict="PASS"
    if any(f in flags for f in ("clearance","citizen-only","no-sponsorship")): verdict="INELIGIBLE"
    elif flags: verdict="BLOCKED"   # 2026-09-11: BLOCKED now routes to judgment as a flagged STRETCH (see fitclass)
    elif yrs and min(yrs)>=7 and not waiver: verdict="YEARS"
    elif yrs and min(yrs)>=5 and not waiver: verdict="STRETCH"

    # --- FIT CLASS drives the daily processing order (the original user's rule 2026-08-26):
    # work CLOSE matches first so fresh, genuinely-good roles are never lost to volume.
    misses = len(softflags) + (1 if verdict in ("STRETCH","YEARS") else 0)
    if verdict in ("INELIGIBLE","FETCHFAIL"): fitclass="EXCLUDED"
    elif verdict=="BLOCKED": fitclass="STRETCH"   # 2026-09-11: never-claim flags are advisory — reach the rubric + critic + human
    elif misses==0: fitclass="CLOSE"      # meets the stated minimums
    elif misses==1: fitclass="STRETCH"    # one clear miss (years bar, or one adjacent-domain gap)
    else:           fitclass="LOOSE"      # two or more misses - genuine long shot
    return dict(rec,verdict=verdict,fitclass=fitclass,minq=mn[:900],pref=pf[:400],
                flags=flags,soft=softflags,yrs=yrs,waiver=waiver)

if __name__=="__main__":
    cands=json.load(open(sys.argv[1], encoding="utf-8"))
    lim=int(sys.argv[2]) if len(sys.argv)>2 else 150
    recs=[]
    for c in cands[:lim]:
        if isinstance(c,list):
            if len(c)==9: ns,bi,tier,age,src,title,loc,url,band=c
            else: bi,tier,age,src,title,loc,url,band=c
            recs.append(dict(tier=str(tier),age=age,src=src,title=title,loc=loc,url=url,band=band))
        else: recs.append(c)
    with cf.ThreadPoolExecutor(14) as ex: out=list(ex.map(screen,recs))
    json.dump(out,open(os.path.join(_WS,"tracking","minquals_screened.json"),"w", encoding="utf-8"),indent=1)
    from collections import Counter
    # DAILY PROCESSING ORDER: fit class first, then freshness, then tier. Build in this order so
    # that if a run is cut short, the close/fresh/local roles are the ones that got done.
    FIT={"CLOSE":0,"STRETCH":1,"LOOSE":2,"EXCLUDED":3}
    BAND={"FRESH":0,"RECENT":1,"OPEN":2}
    out.sort(key=lambda o:(FIT.get(o.get('fitclass'),3),BAND.get(o.get('band'),3),int(o.get('tier',3)),o.get('age',99)))
    json.dump(out,open(os.path.join(_WS,"tracking","minquals_screened.json"),"w", encoding="utf-8"),indent=1)
    print("## MIN-QUALS SCREEN - "+str(len(out))+" roles\n")
    print("verdicts:",dict(Counter(o['verdict'] for o in out)))
    print("FIT CLASS:",dict(Counter(o.get('fitclass') for o in out)))
    print("block reasons:",dict(Counter(f for o in out for f in o['flags'])),"\n")
    for o in out:
        if o.get('fitclass') in ("CLOSE","STRETCH","LOOSE"):
            print(f"\n### [{o['fitclass']}] [{o['band']} T{o['tier']} {o['age']}d] {o['src']} - {o['title']}")
            print(f"{o['loc']} | yrs{o['yrs']} | phd-waiver={o['waiver']} | soft-flags={o.get('soft',[])}")
            print(f"{o['url']}")
            print("MIN-QUALS:\n"+"\n".join("  "+l for l in o['minq'].split("\n")[:14] if l.strip()))
