#!/usr/bin/env python3
"""HARD-ATS fetcher — Oracle CX / ADP / Eightfold / Phenom / SAP-HTML / iCIMS-HTML (2026-08-31).
Recipes from coverage/hard_ats_census.md, all live-tested by the census agent.
Output: tracking/hard_candidates.json. Taleo deferred (session-cookie dance; census has recipe)."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json,urllib.request,re,html,os,datetime,concurrent.futures as cf
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, queries as _queries   # JOBKIT: workspace = data root
_REGP=os.path.join(ROOT,"tracking","registries","hard_registry.json")
REG=json.load(open(_REGP, encoding="utf-8")) if os.path.exists(_REGP) else {}   # JOBKIT: assembled from registry packs; empty = arm idle
UA={'User-Agent':'Mozilla/5.0'}
# Search keywords are LANE data: tracking/registries/queries.yaml -> hard_ats_terms (the first three are used per employer;
# these APIs are keyword-searched, so terms are breadth, never fit).
KW=_queries().get("hard_ats_terms") or []
if REG and not KW: print("hard_ats: queries.yaml has no hard_ats_terms - the hard-ATS arm is idle", file=sys.stderr)
def get(u,data=None,hdr=None):
    h=dict(UA); h.update(hdr or {})
    return urllib.request.urlopen(urllib.request.Request(u,data=data,headers=h),timeout=25).read().decode('utf-8','ignore')
def oracle(e):
    out=[]
    for kw in KW[:3]:
        try:
            d=json.loads(get(f"https://{e['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={e['site']},limit=50,offset=0,sortBy=POSTING_DATES_DESC,keyword={urllib.parse.quote(kw)}"))
            for it in d.get('items',[]):
                for r in it.get('requisitionList',[]):
                    out.append((e['name'],r.get('Title',''),r.get('PrimaryLocation',''),
                        f"https://{e['host']}/hcmUI/CandidateExperience/en/sites/{e['site']}/job/{r.get('Id','')}",
                        (r.get('PostedDate') or '')[:10]))
        except Exception as ex: print(f"hard-ATS error ({e.get('name','?')}): {type(ex).__name__}")
    return out
def adp(e):
    out=[]
    try:
        d=json.loads(get(f"https://workforcenow.adp.com/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions?cid={e['cid']}&ccId={e['ccId']}&lang=en_US&locale=en_US&$top=50&$skip=0"))
        for j in d.get('jobRequisitions',[]):
            loc=(j.get('requisitionLocations') or [{}])[0].get('nameCode',{}).get('shortName','')
            out.append((e['name'],j.get('requisitionTitle',''),loc,
                f"https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid={e['cid']}&ccId={e['ccId']}&jobId={j.get('itemID','')}",
                (j.get('postDate') or '')[:10]))
    except Exception as ex: print(f"hard-ATS error ({e.get('name','?')}): {type(ex).__name__}")
    return out
def eightfold(e):
    out=[]
    for kw in KW[:3]:
        try:
            d=json.loads(get(f"{e['base']}/api/pcsx/search?domain={e['domain']}&query={urllib.parse.quote(kw)}&location=&start=0"))
            for p in (d.get('data',{}).get('positions') or []):
                dt=str(datetime.date.fromtimestamp(p['postedTs'])) if p.get('postedTs') else ''
                out.append((e['name'],p.get('name',''),"; ".join(p.get('standardizedLocations',[])[:1]),
                    f"{e['base']}/careers?pid={p.get('id','')}&domain={e['domain']}",dt))
        except Exception as ex: print(f"hard-ATS error ({e.get('name','?')}): {type(ex).__name__}")
    return out
def phenom(e):
    out=[]
    for kw in KW[:3]:
        try:
            body=json.dumps({"lang":"en_us","deviceType":"desktop","country":"us","ddoKey":"refineSearch","from":0,"size":30,"jobs":True,"counts":True,"keywords":kw,"global":True,"selected_fields":{}}).encode()
            d=json.loads(get(f"{e['base']}/widgets",data=body,hdr={'Content-Type':'application/json'}))
            for j in (d.get('refineSearch',{}).get('data',{}).get('jobs') or []):
                out.append((e['name'],j.get('title',''),f"{j.get('city','')}, {j.get('state','')}",
                    f"{e['base']}/{e.get('locale','us/en')}/job/{j.get('jobId','')}",(j.get('postedDate') or '')[:10]))
        except Exception as ex: print(f"hard-ATS error ({e.get('name','?')}): {type(ex).__name__}")
    return out
def sap(e):
    out=[]
    for kw in KW[:3]:
        try:
            h=""
            for path in (f"/search/?q={urllib.parse.quote(kw)}&startrow=0", f"/go/search/?q={urllib.parse.quote(kw)}"):
                try:
                    h=get(e['base']+path)
                    if '/job/' in h: break
                except Exception: continue
            for m in re.finditer(r'href="(/job/[^"]+)"[^>]*>\s*([^<]{4,90})\s*<',h):
                out.append((e['name'],html.unescape(m.group(2)).strip(),"",e['base']+m.group(1),""))
        except Exception as ex: print(f"hard-ATS error ({e.get('name','?')}): {type(ex).__name__}")
    return out
def icims(e):
    # 2026-10-16 port: iCIMS sites are not always careers-<tenant>.icims.com (uscareers-, jobs-, external-...). A registry entry
    # may give the full "host"; job links are matched on any *.icims.com host.
    out=[]; host=e.get('host') or f"careers-{e['tenant']}.icims.com"
    for kw in KW[:3]:
        try:
            h=get(f"https://{host}/jobs/search?ss=1&searchKeyword={urllib.parse.quote(kw)}&in_iframe=1&pr=0")
            for m in re.finditer(r'href="(https://[a-z0-9-]+\.icims\.com/jobs/\d+/[^"]+/job)[^"]*"[^>]*>\s*<h\d[^>]*>([^<]+)<',h) or []:
                out.append((e['name'],html.unescape(m.group(2)).strip(),"",m.group(1),""))
            if not out:
                for m in re.finditer(r'<a[^>]+href="(https://[a-z0-9-]+\.icims\.com/jobs/\d+/[^"]+/job)[^"]*"[^>]*(?:title="([^"]+)")?',h):
                    out.append((e['name'],html.unescape(m.group(2) or m.group(1).split('/')[-2].replace('-',' ')).strip(),"",m.group(1),""))
        except Exception as ex: print(f"hard-ATS error ({e.get('name','?')}): {type(ex).__name__}")
    return out
import urllib.parse
def main():
    tasks=[(oracle,e) for e in REG.get('oracle',[])]+[(adp,e) for e in REG.get('adp',[])]+\
          [(eightfold,e) for e in REG.get('eightfold',[])]+[(phenom,e) for e in REG.get('phenom',[])]+\
          [(sap,e) for e in REG.get('sap_html',[])]+[(icims,e) for e in REG.get('icims_html',[])]
    res=[]
    with cf.ThreadPoolExecutor(10) as ex:
        for r in ex.map(lambda t:t[0](t[1]),tasks): res+=r
    seen=set(); uniq=[]
    from eligibility import ELIG as DROP   # 2026-09-29: one shared eligibility filter (audit fix #5)
    for co,title,loc,url,dt in res:
        k=(co,title[:40])
        if k in seen or not title or DROP.search(title): continue
        seen.add(k); uniq.append(dict(company=co,title=title,loc=loc,url=url,posted=dt))
    json.dump(uniq,open(os.path.join(ROOT,"tracking","hard_candidates.json"),"w", encoding="utf-8"),indent=1)
    from collections import Counter
    print(f"hard-ATS: {len(res)} raw -> {len(uniq)} unique -> tracking/hard_candidates.json")
    print("by employer:",dict(Counter(u['company'] for u in uniq)))
if __name__=="__main__": main()
