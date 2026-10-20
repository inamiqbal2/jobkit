#!/usr/bin/env python3
"""CORPUS — fetch FULL JD text for every job on every registry board (2026-08-31 restructure).
GH: one ?content=true call per board. Lever/Ashby: text already in the list call.
Output: tracking/corpus.jsonl — one JSON per line: {src,title,loc,url,posted,text}.
Workday/hard-ATS arms stay keyword-search-based (their APIs don't bulk-return text)."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json,urllib.request,re,html,os,datetime,concurrent.futures as cf,sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urlcanon import safe_http as _safe_http
from userconfig import WS as ROOT   # JOBKIT: workspace = data root
def strip(h):
    h=re.sub(r'<[^>]+>',' ',html.unescape(h or ''))
    return re.sub(r'\s{2,}',' ',h).strip()
def J(u):
    _safe_http(u)   # v0.9 (audit H1): http(s) only
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))
def gh(s):
    d=J(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true")
    return [dict(src=s,title=j['title'],loc=j['location']['name'],url=j['absolute_url'],
                 posted=(j.get('first_published') or '')[:10],updated=(j.get('updated_at') or '')[:10],text=strip(j.get('content',''))[:7000]) for j in d.get('jobs',[])]
def lv(s):
    d=J(f"https://api.lever.co/v0/postings/{s}?mode=json")
    out=[]
    for j in d:
        txt=strip(j.get('description',''))+' '+' '.join(strip(l.get('content','')) for l in j.get('lists',[]))
        out.append(dict(src=s,title=j['text'],loc=j['categories'].get('location',''),url=j['hostedUrl'],
            posted=datetime.date.fromtimestamp(j['createdAt']/1000).isoformat() if j.get('createdAt') else '',updated=datetime.date.fromtimestamp(j['updatedAt']/1000).isoformat() if j.get('updatedAt') else '',text=txt[:7000]))
    return out
def ab(s):
    d=J(f"https://api.ashbyhq.com/posting-api/job-board/{s}")
    return [dict(src=s,title=j['title'],loc=j.get('location',''),url=j['jobUrl'],
                 posted=(j.get('publishedAt') or '')[:10],updated=(j.get('updatedAt') or '')[:10],text=strip(j.get('descriptionHtml',''))[:7000]) for j in d.get('jobs',[])]
# 2026-09-11 code audit: 8 registered boards (workable x4, smartrecruiters x4, ~200 postings) were
# fetched by NOTHING — corpus.py knew only gh/lever/ashby and daily runs sweep --wd-only.
def wk(s):
    d=J(f"https://apply.workable.com/api/v1/widget/accounts/{s}")
    out=[]
    for j in d.get('jobs',[]):
        out.append(dict(src=s,title=j.get('title',''),loc=(j.get('city','') or '')+', '+(j.get('country','') or ''),
            url=j.get('url',''),posted=(j.get('published_on') or j.get('created_at') or '')[:10],
            updated=(j.get('updated_at') or '')[:10],text=((strip(j.get('description',''))+' '+strip(j.get('requirements',''))).strip() or j.get('title',''))[:7000]))
    return out
def sr(s):
    d=J(f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=100")
    out=[]
    for p in d.get('content',[])[:100]:
        txt=p.get('name','')
        try:
            det=J(f"https://api.smartrecruiters.com/v1/companies/{s}/postings/{p['id']}")
            sec=(det.get('jobAd',{}) or {}).get('sections',{}) or {}
            txt=' '.join(strip(str(x.get('text',''))) for x in sec.values() if isinstance(x,dict))
        except Exception as ex: print(f"corpus error (smartrecruiters {s} posting {p.get('id')}): {type(ex).__name__}"); continue   # v0.8 (M12): a posting without text is a failure, not a thin JD
        loc=p.get('location') or {}
        out.append(dict(src=s,title=p.get('name',''),loc=(loc.get('city','') or '')+', '+(loc.get('country','') or '').upper(),
            url=f"https://jobs.smartrecruiters.com/{s}/{p['id']}",posted=(p.get('releasedDate') or '')[:10],updated='',text=txt[:7000]))
    return out
F={'gh':gh,'lever':lv,'ashby':ab,'workable':wk,'smartrecruiters':sr}
def main():
    reg=[(k,s) for k,s,_ in json.load(open(os.path.join(ROOT,"tracking","registries","registry.json"), encoding="utf-8")) if k in F]
    n=0; failed=[]
    with open(os.path.join(ROOT,"tracking","corpus.jsonl"),"w", encoding="utf-8") as f, cf.ThreadPoolExecutor(20) as ex:
        def run(t):
            try: return F[t[0]](t[1])
            except Exception as e: return ("__ERR__",f"{t[0]}:{t[1]} ({type(e).__name__})")
        for rows in ex.map(run,reg):
            if isinstance(rows,tuple): failed.append(rows[1]); continue
            for r in rows:
                f.write(json.dumps(r)+"\n"); n+=1
    # v0.5: failures are counted and said (audit bug 6: an offline run used to report "0 postings from 52 boards" and move on)
    print(f"corpus: {n} full-text postings from {len(reg)} boards -> tracking/corpus.jsonl"+(f" ({len(failed)} of {len(reg)} boards did not answer: {', '.join(failed[:5])}{'...' if len(failed)>5 else ''})" if failed else ""))
    if reg and len(failed)==len(reg): print("corpus: EVERY board failed to answer - no internet connection, or the job-board hosts are blocked")
if __name__=="__main__": main()
