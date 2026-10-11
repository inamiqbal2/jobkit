#!/usr/bin/env python3
"""SWEEP — board discovery (durable port, 2026-08-28). Registries: tracking/registries/.
Usage: <jobkit python> tools/sweep.py [window_days=30]   -> writes tracking/candidates.json"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import random, time, urllib.error, json,urllib.request,re,datetime,os,sys,concurrent.futures as cf
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from eligibility import ELIG
from userconfig import WS as ROOT, location as _loc_cfg, queries as _queries   # JOBKIT: workspace = data root
REG=os.path.join(ROOT,"tracking","registries")
TODAY=datetime.date.today(); WIN=int(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].isdigit() else 30
CUT=(TODAY-datetime.timedelta(days=WIN)).isoformat()
# Geography = eligibility only (geo.py: settings.yaml location.country; loose test because Workday locations are often
# "N Locations" placeholders). Title gates are RETIRED (title-blind rule): only eligibility.ELIG acts on titles.
import geo as _geo
T1=re.compile(_loc_cfg()["tier1_regex"] or r"Remote",re.I)     # JOBKIT: settings.yaml location.tier1_regex
T2=re.compile(_loc_cfg()["tier2_regex"] or r"(?!x)x",re.I)     # JOBKIT: settings.yaml location.tier2_regex
def J(u,data=None,hdr=None):
    h={'User-Agent':'Mozilla/5.0'}; h.update(hdr or {})
    return json.load(urllib.request.urlopen(urllib.request.Request(u,data=data,headers=h),timeout=20))
def gh(s): return [(j['title'],j['location']['name'],j['absolute_url'],(j.get('first_published') or '')[:10]) for j in J(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs")['jobs']]
def lv(s): return [(j['text'],j['categories'].get('location',''),j['hostedUrl'],datetime.date.fromtimestamp(j['createdAt']/1000).isoformat() if j.get('createdAt') else '') for j in J(f"https://api.lever.co/v0/postings/{s}?mode=json")]
def ab(s): return [(j['title'],j.get('location',''),j['jobUrl'],(j.get('publishedAt') or '')[:10]) for j in J(f"https://api.ashbyhq.com/posting-api/job-board/{s}?includeCompensation=true")['jobs']]
def wk(s2):
    d=J(f"https://apply.workable.com/api/v1/widget/accounts/{s2}")
    return [(j.get('title',''),(j.get('city','') or '')+', '+(j.get('country','') or ''),j.get('url',''),(j.get('published_on') or j.get('created_at') or '')[:10]) for j in d.get('jobs',[])]
def sr(s2):
    d=J(f"https://api.smartrecruiters.com/v1/companies/{s2}/postings?limit=100")
    return [(p['name'],((p.get('location') or {}).get('city','') or '')+', '+((p.get('location') or {}).get('country','') or '').upper(),f"https://jobs.smartrecruiters.com/{s2}/{p['id']}",(p.get('releasedDate') or '')[:10]) for p in d.get('content',[])]
F={'gh':gh,'lever':lv,'ashby':ab,'workable':wk,'smartrecruiters':sr}
AGE=re.compile(r"Posted (Today|Yesterday|(\d+)\+? Days? Ago)",re.I)
def _wd_get(host,ten,site,term,off,state):
    """One CXS page. Honors Retry-After; on repeated 429 marks the tenant cooled so the
    caller stops hammering it. Returns (data|None, reason)."""
    # 2026-10-07: some tenants live on the shared host form wd1.myworkdaysite.com/recruiting/<tenant>/<site>
    # (Wells Fargo, Fidelity). Registry host "wd1.myworkdaysite.com" is used verbatim; CXS path is identical.
    url=f"https://{_wd_base(host)}/wday/cxs/{ten}/{site}/jobs"
    body=json.dumps({"appliedFacets":{},"limit":20,"offset":off,"searchText":term}).encode()
    for attempt in range(3):
        try:
            return J(url,body,{'Content-Type':'application/json'}), None
        except urllib.error.HTTPError as e:
            if e.code==429:
                state['429']=state.get('429',0)+1
                if attempt==2:
                    state['cooled']=True; return None,'RATE-LIMITED'
                ra=e.headers.get('Retry-After') if e.headers else None
                try: wait=min(float(ra),30.0) if ra else 0
                except ValueError: wait=0
                if not wait: wait=(2**attempt)*4          # 4s, 8s
                time.sleep(wait+random.uniform(0,1.5))    # jitter: avoid synchronized retries
                continue
            return None,f'HTTP {e.code}'
        except Exception as e:
            return None,type(e).__name__
    return None,'RATE-LIMITED'

def _wd_base(host):
    return host if host.endswith('.myworkdaysite.com') else f"{host}.myworkdayjobs.com"
def _wd_joburl(host,ten,site,path):
    return (f"https://{host}/en-US/recruiting/{ten}/{site}{path}" if host.endswith('.myworkdaysite.com')
            else f"https://{host}.myworkdayjobs.com/en-US/{site}{path}")
def wds(spec):
    """2026-09-14: ONE TASK PER TENANT, terms serialized inside it.
    The old shape was [(tenant,term) for tenant for term] fed to a 20-thread pool — because the
    list is tenant-major, the pool put ~10 concurrent requests on the SAME host, and Workday
    rate-limits per tenant. That, not total volume, was what produced the 429 storms. Now each
    host sees a single paced stream while different tenants still run in parallel."""
    host,ten,site=spec.split('|'); host=host.replace('.myworkdayjobs.com','')
    out=[]; state={}
    for term in TERMS:
        if state.get('cooled'):
            print(f"  RATE-LIMITED (skipping remaining terms, retry next run): {host}/{ten} after {state.get('429',0)} 429s")
            break
        postings=[]
        for off in range(0,200,20):
            d,why=_wd_get(host,ten,site,term,off,state)
            if d is None:
                if off==0 and why!='RATE-LIMITED':
                    print(f"  TENANT DEAD? (registry action) {host}/{ten}/{site} term={term!r}: {why}")
                break
            page=d.get('jobPostings',[])
            postings+=page
            if len(page)<20: break
            time.sleep(0.25+random.uniform(0,0.25))   # paced + jittered between pages
        for p in postings:
            m=AGE.search(p.get('postedOn','') or '')
            if not m: continue
            days=0 if m.group(1).lower() in ('today','yesterday') else int(m.group(2) or 999)
            out.append((p.get('title',''),p.get('locationsText',''),_wd_joburl(host,ten,site,p.get('externalPath','')),(TODAY-datetime.timedelta(days=days)).isoformat()))   # 2026-10-07: myworkdaysite-aware
        time.sleep(0.4+random.uniform(0,0.4))          # pause between terms on the same host
    return out

# Workday search terms are LANE data: tracking/registries/queries.yaml -> workday_terms (breadth only; fit = JD gate + rubric).
TERMS=_queries().get("workday_terms") or []
if not TERMS: print("sweep: queries.yaml has no workday_terms - the Workday arm is idle", file=sys.stderr)

def main():
    jobs=[]
    wd_only="--wd-only" in sys.argv  # boards arm now covered by corpus.py+match.py full-text matching
    if not wd_only:
        reg=json.load(open(os.path.join(REG,"registry.json"), encoding="utf-8"))
        def r1(v):
            k,s,_=v
            try: return (s,F[k](s))
            except Exception: return (s,[])
        with cf.ThreadPoolExecutor(20) as ex:
            for s,rows in ex.map(r1,[v for v in reg if v[0] in F]): jobs+=[(s,)+r for r in rows]
    wd=[f"{h}|{t}|{s}" for h,t,s,n in json.load(open(os.path.join(REG,"wd_registry.json"), encoding="utf-8"))]
    wd+=[r[1] for r in json.load(open(os.path.join(REG,"registry2.json"), encoding="utf-8")) if r[0]=="workday"]
    with cf.ThreadPoolExecutor(min(20,max(4,len(wd)))) as ex:   # one worker per TENANT, never several per host
        for sp,rows in zip(wd,ex.map(wds,wd)): jobs+=[(sp.split('|')[1],)+r for r in rows]
    _WD_SRC={sp.split('|')[1] for sp in wd}
    seen=set(); hits=[]
    for src,title,loc,url,dt in jobs:
        k=(src,title,loc)
        if k in seen or not dt: continue
        seen.add(k)
        try: age=(TODAY-datetime.date.fromisoformat(dt)).days
        except Exception: continue
        if not (0<=age<=WIN): continue
        # 2026-09-29 audit fix #6: the KEEP/DROP TITLE gate is RETIRED. Whole-board kinds (gh/lever/ashby/workable/
        # smartrecruiters) are covered TITLE-BLIND, from full JD text, by the corpus arm (corpus.py + match.py), so
        # the sweep no longer re-emits them; Workday tenants (keyword-searched, not in the corpus) keep flowing
        # with the shared eligibility filter only. Fit = JD gate + rubric.
        if src not in _WD_SRC: continue
        if ELIG.search(title): continue
        if not _geo.in_country_loose(loc or ''): continue   # non_us() (URL/title aware) runs once more in daily.py for every arm
        tier="1" if T1.search(loc or '') else ("2" if T2.search(loc or '') else "3")
        band="FRESH" if age<=7 else ("RECENT" if age<=14 else "OPEN")
        hits.append(dict(band=band,tier=tier,age=age,src=src,title=title,loc=loc,url=url))
    hits.sort(key=lambda h:({'FRESH':0,'RECENT':1,'OPEN':2}[h['band']],int(h['tier']),h['age']))
    out=os.path.join(ROOT,"tracking","candidates.json")
    json.dump(hits,open(out,"w", encoding="utf-8"),indent=1)
    print(f"sweep: {len(seen)} unique reqs | {len(hits)} candidates ({WIN}d window) -> tracking/candidates.json")
if __name__=="__main__": main()
