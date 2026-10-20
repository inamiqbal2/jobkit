#!/usr/bin/env python3
"""FEEDS - non-ATS discovery sources.
Every board and every search term here is WORKSPACE data; this file only knows HOW to fetch each kind.
  tracking/registries/feeds_registry.json  (assembled by registries.py from the selected packs + custom.json)
      {"feeds": [{"kind": <kind>, "name": ..., "base": ..., ...}, ...]}
      kinds: getro (VC job-board __NEXT_DATA__ search)  ats_links (server-rendered page whose job links point at
             GH/Lever/Ashby)  rss (RSS 2.0 / RSS 1.0 feed, optional {kw} placeholder, optional loc_regex on the
             description)  html_links (anchor scan of a server-rendered listing: title_regex and/or href_regex select the
             job anchors; {kw} in base = one fetch per board term; relative hrefs resolved - PageUp, PeopleAdmin, ...)
             bamboo / breezy / jobvite / wprss / rippling / nodi (small ATSes, one fetch per company; nodi base = company name)
             smartrecruiters_search (open JSON search API, tenant)  custom_html (card_regex over one careers page;
             positional groups title, location[, url] OR named groups (?P<title>)(?P<loc>)(?P<url>)(?P<id>)(?P<posted>)
             with url_template "{id}" and loc_default)
             -- added 2026-10-09 (academic lanes) --
             pipermail (a Mailman archive, read-only: the current month's date.html subject index; subject_regex selects
             posting-like subjects)  neogov (governmentjobs.com / schooljobs.com agency board, JSON; descriptions cached)
             json_list (any public JSON listing: root path + field map + url_template; descriptions cached when present)
             usajobs (USAJobs search API; needs keys.json usajobs_key + usajobs_email - a free key the USER registers)
  tracking/registries/queries.yaml
      board_terms  -> keyword-searched whole boards (getro, ats_links, rss/html_links with {kw}, neogov, smartrecruiters_search)
      usajobs      -> USAJobs keyword queries (falls back to board_terms)
      adzuna / linkedin / indeed -> aggregator queries (quoted phrases allowed)
Arm switches: settings.yaml run.adzuna (needs keys.json adzuna_id/adzuna_key; the official API, default ON once the key exists),
  run.linkedin_guest and run.indeed_jobspy (both OFF by default since v0.3: unofficial scrapes of sites whose terms of service
  restrict automated access - the person opts in knowingly; see system/docs/DEVELOPER.md).
Output: tracking/feed_candidates.json in sweep-candidate format. Titles are never a fit gate (eligibility only).
A listing that already carries the full description (neogov, json_list, usajobs) is cached to tracking/jds/feed_<md5>.txt at
ingest, and screen_minquals.fetch() reads that cache first (the same trick the Indeed arm uses).
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json,urllib.request,urllib.parse,re,html,os,datetime,gzip,hashlib,concurrent.futures as cf
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, secrets as _secrets, get as _cfg, queries as _queries, location as _loc_cfg   # JOBKIT
from eligibility import ELIG as _ADROP   # one shared eligibility filter
TODAY=datetime.date.today()
UA={'User-Agent':'Mozilla/5.0'}
_Q=_queries()
BOARD_TERMS=_Q.get("board_terms") or []
_FRP=os.path.join(ROOT,"tracking","registries","feeds_registry.json")
try: FEEDS=[e for e in (json.load(open(_FRP, encoding="utf-8")).get("feeds") or []) if isinstance(e,dict) and e.get("kind")]
except Exception: FEEDS=[]
ATS=re.compile(r"(greenhouse\.io|lever\.co|ashbyhq\.com|myworkdayjobs\.com)")
_COUNTRY=(_loc_cfg().get("country") or "US").upper()
_COUNTRY_NAME={"US":"United States","CA":"Canada","UK":"United Kingdom"}.get(_COUNTRY,_COUNTRY)
def fetch(u,headers=None):
    """GET as text. Some hosts (AJO, Firebase functions) send gzip bodies regardless of Accept-Encoding: decode them."""
    h=dict(UA); h.update(headers or {})
    b=urllib.request.urlopen(urllib.request.Request(u,headers=h),timeout=25).read()
    if b[:2]==b'\x1f\x8b':
        try: b=gzip.decompress(b)
        except Exception: pass
    return b.decode('utf-8','ignore')
def _untag(x):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",x or ""))).strip()
def _join(base,u):
    return urllib.parse.urljoin(base,u) if u and not re.match(r"https?://",u) else (u or "")
def _cache_jd(url,title,loc,text):
    """A listing that came with its full description: persist it so screen_minquals never has to fetch the page
    (NEOGOV / PeopleSoft / USAJobs pages are JS-rendered or slow). Same md5 key screen_minquals.fetch() looks up."""
    if not url or len(text or "")<300: return
    try:
        d=os.path.join(ROOT,"tracking","jds"); os.makedirs(d,exist_ok=True)
        open(os.path.join(d,"feed_"+hashlib.md5(url.encode()).hexdigest()[:16]+".txt"),"w", encoding="utf-8").write(f"{title}\n{loc}\n{url}\n\n{text}")
    except Exception: pass

# ── keyword-searched whole boards ──────────────────────────────────────────────────────────────────────────────
def getro(e):
    name,base=e.get("name",""),e.get("base","").rstrip("/")
    out=[]
    for kw in BOARD_TERMS:
        try: h=fetch(f"{base}/jobs?q={urllib.parse.quote(kw)}")
        except Exception: continue
        m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',h,re.S)
        if not m: continue
        try: d=json.loads(m.group(1))
        except Exception: continue
        def walk(o):
            if isinstance(o,dict):
                if 'title' in o and ('url' in o or 'applyUrl' in o):
                    u=o.get('applyUrl') or o.get('url') or ''
                    if ATS.search(u):
                        loc=o.get('locations') or o.get('location') or ''
                        if isinstance(loc,list): loc=", ".join(str(x) for x in loc[:2])
                        ts=o.get('createdAt') or o.get('postedAt') or 0
                        try: dt=datetime.date.fromtimestamp(int(ts)/1000 if int(ts)>1e12 else int(ts)).isoformat() if ts else ''
                        except Exception: dt=''
                        out.append((f"getro:{name}",o['title'],str(loc),u.split('?')[0],dt))
                for v in o.values(): walk(v)
            elif isinstance(o,list):
                for v in o: walk(v)
        walk(d)
    return out
def ats_links(e):
    """A server-rendered listing page whose job anchors point at Greenhouse/Lever/Ashby (e.g. a VC portfolio board)."""
    name,base,qp=e.get("name",""),e.get("base",""),e.get("query_param","q")
    out=[]
    for kw in (BOARD_TERMS or [""]):
        u=f"{base}?{qp}={urllib.parse.quote(kw)}" if kw else base
        try: h=fetch(u)
        except Exception: continue
        for m in re.finditer(r'href="(https://[^"]*(?:greenhouse\.io|lever\.co|ashbyhq\.com)[^"]*)"[^>]*>([^<]{4,90})<',h):
            out.append((name,html.unescape(m.group(2)).strip(),"",m.group(1).split('?')[0],""))
    return out
_CDATA=lambda x:re.sub(r"^\s*<!\[CDATA\[(.*?)\]\]>\s*$",r"\1",x or "",flags=re.S).strip()
def _tag(item,name):
    m=re.search(rf"<{name}(?:\s[^>]*)?>(.*?)</{name}>",item,re.S|re.I)
    return _CDATA(m.group(1)) if m else ""
def _rss_date(d):
    """'Thu, 08 Oct 2026 09:32:13 EDT' / '2026-10-08T..' -> ISO date or ''."""
    d=(d or "").strip()
    m=re.search(r"(\d{4})-(\d\d)-(\d\d)",d)
    if m: return m.group(0)
    try: return datetime.datetime.strptime(re.sub(r"\s+[A-Z]{2,4}$|\s+[+-]\d{4}$","",d.replace(",","")).strip(),"%a %d %b %Y %H:%M:%S").date().isoformat()
    except Exception:
        try: return datetime.datetime.strptime(re.sub(r"\s+[A-Z]{2,4}$|\s+[+-]\d{4}$","",d.replace(",","")).strip(),"%a %d %b %Y").date().isoformat()
        except Exception: return ""
def rss(e):
    """An RSS 2.0 (<item>) or RSS 1.0 (<item rdf:about=...>) job feed; `base` may contain {kw} (one fetch per board term)
    or not (one fetch = the whole feed, which the JD gate then filters). Optional `loc_regex`: a regex with one group,
    applied to the item's description, that yields the location (e.g. HigherEdJobs "Employer (City, ST)")."""
    name,base=e.get("name",""),e.get("base","")
    lrx=re.compile(e["loc_regex"],re.I|re.S) if e.get("loc_regex") else None
    out=[]
    for kw in (BOARD_TERMS if "{kw}" in base else [""]):
        try: h=fetch(base.replace("{kw}",urllib.parse.quote(kw)),e.get("headers"))
        except Exception as ex: print(f"rss arm error ({name}):",ex); continue
        for it in re.findall(r"<item\b[^>]*>.*?</item>",h,re.S|re.I):
            t=_untag(_tag(it,"title")); u=html.unescape(_tag(it,"link").strip())   # &amp; -> & (audit v0.4 finding 21)
            if not (t and u): continue
            loc=""
            if lrx:
                m=lrx.search(_untag(_tag(it,"description")))
                if m: loc=(m.group(1) if m.lastindex else m.group(0)).strip()
            out.append((name,t,loc,u,_rss_date(_tag(it,"pubDate") or _tag(it,"dc:date"))))
    return out
def html_links(e):
    """Anchor scan of a server-rendered listing with no job API. `title_regex` (on the anchor text) and/or `href_regex`
    (on the href, e.g. "/en-us/job/\\d+" for PageUp, "/postings/\\d+" for PeopleAdmin) are LINK SELECTORS - which anchors
    are jobs - never a fit gate. `base` may carry {kw} (one fetch per board term). Relative hrefs are resolved."""
    name,base=e.get("name",""),e.get("base","")
    trx=re.compile(e["title_regex"],re.I) if e.get("title_regex") else None
    hrx=re.compile(e["href_regex"],re.I) if e.get("href_regex") else None
    if not (trx or hrx): trx=re.compile(".")
    out=[]; seen=set()
    for kw in (BOARD_TERMS if "{kw}" in base else [""]):
        u0=base.replace("{kw}",urllib.parse.quote(kw))
        try: h=fetch(u0,e.get("headers"))
        except Exception as ex: print(f"html_links arm error ({name}):",ex); continue
        for m in re.finditer(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>',h,re.I|re.S):
            href,txt=m.group(1),_untag(m.group(2))
            if hrx and not hrx.search(href): continue
            if trx and not trx.search(txt): continue
            if len(txt)<4 or len(txt)>140: continue
            u=_join(u0,html.unescape(href)).split("#")[0]
            if u in seen: continue
            seen.add(u); out.append((name,txt,"",u,""))
    return out
def smartrecruiters_search(e):
    """SmartRecruiters open public JSON search API, per board term."""
    c=e.get("tenant") or e.get("name",""); out=[]; seen=set()
    for q in BOARD_TERMS:
        try:
            d=json.load(urllib.request.urlopen(urllib.request.Request(
                f"https://api.smartrecruiters.com/v1/companies/{c}/postings?q={urllib.parse.quote(q)}&limit=50&country={_COUNTRY.lower()}",
                headers=UA),timeout=25))
        except Exception as ex: print(f"smartrec arm error ({c},{q}):",ex); continue
        for r in d.get("content",[]):
            if r.get("id") in seen: continue
            seen.add(r.get("id"))
            loc=r.get("location",{}) or {}
            out.append(dict(src="sr:"+c,title=r.get("name",""),
                loc=", ".join(x for x in (loc.get("city"),loc.get("region")) if x),
                url=f"https://jobs.smartrecruiters.com/{c}/{r.get('id')}",
                posted=(r.get("releasedDate","") or "")[:10]))
    return out
def custom_html(e):
    """One employer careers page with no ATS: `card_regex` over the page HTML. Either positional groups (title, location[, url])
    or NAMED groups: (?P<title>) required; (?P<loc>) (?P<url>) (?P<id>) (?P<posted>) optional. `url_template` ("{id}" /
    "{title}" placeholders) builds the link when the card has an id but no href; `loc_default` fills a missing location;
    `posted_format` (strptime, e.g. "%m/%d/%Y") parses the posted group. Relative URLs are resolved against `base`.
    Jobs with no link at all point at the page itself (anchor = slug of the title)."""
    name,base,rx=e.get("name",""),e.get("base",""),e.get("card_regex","")
    out=[]
    if not rx: return out
    try: h=fetch(base,e.get("headers"))
    except Exception as ex: print(f"custom arm error ({name}):",ex); return out
    seen=set()
    for m in re.finditer(rx,h,re.S|re.I):
        g=m.groupdict()
        if "title" in g:
            t=_untag(g.get("title") or ""); loc=_untag(g.get("loc") or "") or e.get("loc_default","")
            u=g.get("url") or ""
            if not u and e.get("url_template"):
                u=e["url_template"].replace("{id}",html.unescape(g.get("id") or "")).replace("{title}",urllib.parse.quote(t))
            dt=""
            if g.get("posted"):
                try: dt=datetime.datetime.strptime(g["posted"].strip(),e.get("posted_format","%Y-%m-%d")).date().isoformat()
                except Exception: dt=""
        else:
            t=_untag(m.group(1))
            loc=_untag(m.group(2)) if m.lastindex and m.lastindex>=2 else ""
            loc=loc or e.get("loc_default","")
            u=m.group(3) if m.lastindex and m.lastindex>=3 else ""
            dt=""
        if not t: continue
        u=_join(base,html.unescape(u)) if u else base.rstrip("/")+"/#"+re.sub(r"[^a-z0-9]+","-",t.lower())
        if u in seen: continue
        seen.add(u); out.append(dict(src="custom:"+name,title=t,loc=loc,url=u,posted=dt))
    return out

# ── 2026-10-09: source classes added for the academic / field-science lanes (all generic, all config-driven) ────────
def pipermail(e):
    """A Mailman (pipermail) archive, READ-ONLY: fetch this month's (and, early in the month, last month's) date.html
    subject index under `base` (the archive root, e.g. .../pipermail/<list>/). `subject_regex` selects posting-like
    subjects (a LINK SELECTOR like html_links' title_regex: most list traffic is discussion, not jobs); `strip_regex`
    removes list tags such as "[ES_JOBS_NET]". Each hit links to the archived message (the JD the screen reads).
    Never subscribes, never posts: archives only."""
    name,base=e.get("name",""),e.get("base","").rstrip("/")+"/"
    srx=re.compile(e["subject_regex"],re.I) if e.get("subject_regex") else None
    strip=re.compile(e.get("strip_regex") or r"^\s*(?:\[[^\]]+\]\s*)+|^\s*(?:Re|Fwd?):\s*",re.I)
    months=[TODAY.replace(day=1)]
    if TODAY.day<=7: months.append((TODAY.replace(day=1)-datetime.timedelta(days=1)).replace(day=1))
    out=[]
    for mo in months:
        u=f"{base}{mo.strftime('%Y-%B')}/date.html"
        try: h=fetch(u,e.get("headers"))
        except Exception as ex: print(f"pipermail arm error ({name} {mo.strftime('%Y-%B')}):",ex); continue
        for m in re.finditer(r'<LI><A HREF="(\d+\.html)">(.*?)</A>',h,re.S|re.I):
            subj=strip.sub("",_untag(m.group(2))).strip()
            if srx and not srx.search(subj): continue
            if len(subj)<4: continue
            out.append((name,subj,"",f"{base}{mo.strftime('%Y-%B')}/{m.group(1)}",""))
    return out
def neogov(e):
    """A NEOGOV agency board (governmentjobs.com / schooljobs.com): GET {host}/careers/{agency}/home/loadJobsOnMaps?keyword=
    returns JSON {jobList:[{ID, Classification, Location, PostingDate, JobTitle(slug), FullDescription,...}]}. One call per
    board term (no terms -> the whole board). Descriptions are cached for the screen (the job pages are JS-rendered)."""
    name,host,agency=e.get("name",""),e.get("host","www.governmentjobs.com"),e.get("agency","")
    out=[]; seen=set()
    for kw in (BOARD_TERMS or [""]):
        u=f"https://{host}/careers/{agency}/home/loadJobsOnMaps"+(f"?keyword={urllib.parse.quote(kw)}" if kw else "")
        try: d=json.loads(fetch(u,{"X-Requested-With":"XMLHttpRequest","Accept":"application/json"}))
        except Exception as ex: print(f"neogov arm error ({name},{kw!r}):",ex); continue
        for j in d.get("jobList") or []:
            jid=str(j.get("ID") or "")
            if not jid or jid in seen: continue
            seen.add(jid)
            t=_untag(str(j.get("Classification") or j.get("JobTitle") or ""))
            loc=_untag(str(j.get("Location") or ""))
            url=f"https://{host}/careers/{agency}/jobs/{jid}/{j.get('JobTitle') or ''}"
            dt=""
            try: dt=datetime.datetime.strptime(str(j.get("PostingDate") or ""),"%m/%d/%y").date().isoformat()
            except Exception: pass
            _cache_jd(url,t,loc,_untag(str(j.get("FullDescription") or "")))
            out.append((name,t,loc,url,dt))
    return out
def _dig(o,path):
    for k in [x for x in (path or "").split(".") if x]:
        if isinstance(o,dict): o=o.get(k)
        elif isinstance(o,list) and k.isdigit(): o=o[int(k)] if int(k)<len(o) else None
        else: return None
    return o
def json_list(e):
    """Any public JSON listing: `base` (URL, {kw} allowed), `root` (dotted path to the list, "" = the body itself),
    `fields` {title, loc, url, posted, desc, id} (dotted paths inside each item), `url_template` ("{id}") when items carry
    no link, optional `headers`. A `desc` field is cached as the JD. Example: the FIU careers cloud function."""
    name,base,f=e.get("name",""),e.get("base",""),e.get("fields") or {}
    out=[]; seen=set()
    for kw in (BOARD_TERMS if "{kw}" in base else [""]):
        try: d=json.loads(fetch(base.replace("{kw}",urllib.parse.quote(kw)),e.get("headers")))
        except Exception as ex: print(f"json_list arm error ({name}):",ex); continue
        items=_dig(d,e.get("root",""))
        if isinstance(items,dict): items=list(items.values())
        for it in items or []:
            if not isinstance(it,dict): continue
            t=_untag(str(_dig(it,f.get("title","title")) or ""))
            if not t: continue
            u=str(_dig(it,f.get("url","url")) or "") if f.get("url") else ""
            if not u and e.get("url_template"): u=e["url_template"].replace("{id}",str(_dig(it,f.get("id","id")) or ""))
            u=_join(base,u)
            if not u or u in seen: continue
            seen.add(u)
            loc=_untag(str(_dig(it,f.get("loc","")) or "")) if f.get("loc") else e.get("loc_default","")
            dt=str(_dig(it,f.get("posted","")) or "")[:10] if f.get("posted") else ""
            if f.get("desc"): _cache_jd(u,t,loc,_untag(str(_dig(it,f["desc"]) or "")))
            out.append((name,t,loc,u,dt))
    return out
def usajobs(e):
    """USAJobs search API (federal: NOAA, USGS, NPS, Smithsonian, FWS, EPA...). The key is FREE but the USER registers it
    (https://developer.usajobs.gov/ -> keys.json: {"usajobs_key": "...", "usajobs_email": "you@example.com"}); the engine
    never registers one. Queries: queries.yaml -> usajobs (else board_terms). Optional entry keys: `organization` (agency
    code filter, e.g. "NOAA"), `days` (DatePosted window, default 30). Summaries are cached as the JD text."""
    name=e.get("name","usajobs"); key=_sec.get("usajobs_key",""); mail=_sec.get("usajobs_email","")
    if not (key and mail): print("usajobs arm: off (no usajobs_key / usajobs_email in keys.json - register a free key at developer.usajobs.gov)"); return []
    out=[]; seen=set()
    for q in (_Q.get("usajobs") or BOARD_TERMS or [""]):
        u=(f"https://data.usajobs.gov/api/search?Keyword={urllib.parse.quote(q)}&ResultsPerPage=100&DatePosted={int(e.get('days',30))}"
           +(f"&Organization={urllib.parse.quote(str(e['organization']))}" if e.get("organization") else ""))
        try: d=json.loads(fetch(u,{"Host":"data.usajobs.gov","User-Agent":mail,"Authorization-Key":key}))
        except Exception as ex: print(f"usajobs arm error ({q!r}):",ex); continue
        for it in ((d.get("SearchResult") or {}).get("SearchResultItems") or []):
            md=it.get("MatchedObjectDescriptor") or {}
            url=md.get("PositionURI") or ""
            if not url or url in seen: continue
            seen.add(url)
            t=md.get("PositionTitle") or ""; loc=md.get("PositionLocationDisplay") or ""
            org=md.get("OrganizationName") or md.get("DepartmentName") or "USAJobs"
            dt=(md.get("PublicationStartDate") or "")[:10]
            summ=((md.get("UserArea") or {}).get("Details") or {}).get("JobSummary") or ""
            quals=md.get("QualificationSummary") or ""
            _cache_jd(url,t,loc,_untag(f"{org}\n{summ}\n\nQualifications: {quals}"))
            out.append((f"{name}:{org[:40]}",t,loc,url,dt))
    return out

# ── aggregators ────────────────────────────────────────────────────────────────────────────────────────────────
_sec=_secrets()
ADZUNA_ID,ADZUNA_KEY=_sec.get("adzuna_id",""),_sec.get("adzuna_key","")
def _adzuna_url(what=None,company=None,days=7):
    u=(f"https://api.adzuna.com/v1/api/jobs/{_COUNTRY.lower() if _COUNTRY!='UK' else 'gb'}/search/1?app_id={ADZUNA_ID}&app_key={ADZUNA_KEY}"
       f"&results_per_page=50&max_days_old={days}&sort_by=date")
    if what: u+=f"&what={urllib.parse.quote(what)}"
    if company: u+=f"&company={urllib.parse.quote(company)}"
    return u
def adzuna():
    # 2026-10-16 port: the API snippet travels with each record as 'desc' (screen_minquals falls back to it when the landing
    # page is bot-walled), and queries.yaml adzuna_companies: [names] runs one company-scoped query per employer - a cheap way
    # to cover an employer whose own board jobkit cannot read.
    out=[]
    jobs=[(q,None) for q in (_Q.get("adzuna") or [])]+[(None,c) for c in (_Q.get("adzuna_companies") or [])]
    for q,co in jobs:
        try:
            u=_adzuna_url(what=q,company=co)
            d=json.load(urllib.request.urlopen(u,timeout=25))
            for r in d.get("results",[]):
                t=r.get("title","")
                if _ADROP.search(t): continue
                out.append(dict(src="adzuna:"+ (r.get("company",{}).get("display_name") or "unknown"),
                    title=t, loc=(r.get("location",{}).get("display_name") or ""),
                    url=r.get("redirect_url",""), posted=(r.get("created","") or "")[:10], desc=_untag(r.get("description",""))))
        except Exception as e:
            print("adzuna arm error:",e)
    seen=set(); ded=[]
    for x in out:
        k=(x["src"],x["title"][:40])
        if k in seen: continue
        seen.add(k); ded.append(x)
    print(f"adzuna: {len(ded)} candidates (7d window)")
    return ded

def _discover(items,src_prefix):
    """Shared company-discovery: flag employers absent from every registry + swept corpus.
    Appends to tracking/registries/li_discovery.jsonl, prints NEW-COMPANY lines."""
    _canon=lambda s:re.sub(r"[^a-z0-9]","",s.lower())
    known=set()
    try:
        for r in json.load(open(os.path.join(ROOT,"tracking","registries","wd_registry.json"), encoding="utf-8")): known.add(_canon(r[1]))
        hr=json.load(open(os.path.join(ROOT,"tracking","registries","hard_registry.json"), encoding="utf-8"))
        for arm in hr.values():
            if isinstance(arm,list):
                for e in arm: known.add(_canon(str(e.get("name","") if isinstance(e,dict) else e)[:40]))
        for ln in open(os.path.join(ROOT,"tracking","corpus.jsonl"), encoding="utf-8"):
            try: known.add(_canon(json.loads(ln).get("src","")))
            except Exception: pass
    except Exception as e: print("discovery: registry load error",e)
    dpath=os.path.join(ROOT,"tracking","registries","li_discovery.jsonl")
    logged={_canon(json.loads(x)["company"]) for x in open(dpath, encoding="utf-8")} if os.path.exists(dpath) else set()
    with open(dpath,"a", encoding="utf-8") as f:
        for x in items:
            comp=x["src"].split(":",1)[-1]
            ck=_canon(comp)
            if not ck or ck in logged or any(ck in k or k in ck for k in known if len(k)>3): continue
            f.write(json.dumps(dict(date=TODAY.isoformat(),company=comp,arm=src_prefix,
                example_title=x["title"],url=x["url"]))+"\n")
            logged.add(ck)
            print(f"  {src_prefix.upper()}-NEW-COMPANY: {comp} - {x['title'][:50]}")

def linkedin():
    """LinkedIn public guest-API sweep. DISCOVERY arm: one page of PUBLIC search cards per query, no login, 48h window,
    2s pacing. Two outputs: (a) jobs into the funnel like any feed arm; (b) companies not in any registry appended to
    tracking/registries/li_discovery.jsonl for registry adds. Fragility is expected (guest API is rate-limited and
    unversioned): errors degrade to zero results, never block the run."""
    import time, urllib.error
    # 2026-10-16 port: back off on 429 (5s, 10s, 20s), stop the arm after 3 queries in a row fail, and cache each query's
    # page for 12 h in tracking/li_cache.json so a re-run the same day does not hit LinkedIn again.
    _cp=os.path.join(ROOT,"tracking","li_cache.json")
    try: cache=json.load(open(_cp,encoding="utf-8"))
    except Exception: cache={}
    out=[]; streak=0
    for q in (_Q.get("linkedin") or []):
        u=("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
           f"keywords={urllib.parse.quote(q)}&location={urllib.parse.quote(_COUNTRY_NAME)}&f_TPR=r172800&start=0")
        hit=cache.get(u)
        if hit and time.time()-hit.get("t",0)<12*3600: h=hit.get("h","")
        else:
            h=None
            for k in range(3):
                try: h=fetch(u); break
                except urllib.error.HTTPError as e:
                    if e.code!=429: break
                    time.sleep(5*2**k)
                except Exception: break
            if h is None:
                streak+=1; print(f"linkedin arm: no answer for '{q}'")
                if streak>=3: print("linkedin arm: stopping for this run (3 queries in a row failed)"); break
                time.sleep(2); continue
            streak=0; cache[u]={"t":time.time(),"h":h}
        for card in re.findall(r"<li>(.*?)</li>",h,re.S):
            l=re.search(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)',card)
            t=re.search(r'<h3[^>]*>\s*(.*?)\s*</h3>',card,re.S)
            c=re.search(r'<h4[^>]*>.*?>\s*([^<]{2,60}?)\s*</a>',card,re.S) or re.search(r'<h4[^>]*>\s*([^<]{2,60}?)\s*<',card,re.S)
            loc=re.search(r'job-search-card__location[^>]*>\s*(.*?)\s*</span>',card,re.S)
            dt=re.search(r'datetime="(\d{4}-\d\d-\d\d)"',card)
            if not (l and t): continue
            title=html.unescape(t.group(1)).strip()
            if _ADROP.search(title): continue
            out.append(dict(src="li:"+(html.unescape(c.group(1)).strip() if c else "unknown"),
                title=title, loc=html.unescape(loc.group(1)).strip() if loc else "",
                url=l.group(1), posted=dt.group(1) if dt else ""))
        time.sleep(2)
    try:
        cache={k:v for k,v in cache.items() if time.time()-v.get("t",0)<12*3600}
        json.dump(cache,open(_cp,"w",encoding="utf-8"))
    except Exception: pass
    seen=set(); ded=[]
    for x in out:
        k=re.sub(r"[^0-9]","",x["url"][-12:]) or x["url"]
        if k in seen: continue
        seen.add(k); ded.append(x)
    _discover(ded,"li")
    print(f"linkedin: {len(ded)} candidates (48h window)")
    return ded

def indeed():
    """Indeed arm via JobSpy's mobile-GraphQL route. Descriptions come free in the response, so each card's JD is CACHED
    at ingest to tracking/jds/indeed_<jk>.txt and screen_minquals reads the cache (indeed.com pages are Cloudflare-walled).
    job_url_direct is deliberately NOT used as canonical: JobSpy sometimes misattaches it."""
    try: from jobspy import scrape_jobs
    except ImportError: print("indeed arm: python-jobspy not installed - skipping"); return []
    out=[]
    os.makedirs(os.path.join(ROOT,"tracking","jds"),exist_ok=True)
    _cc={"US":"USA","CA":"Canada","UK":"UK"}.get(_COUNTRY,_COUNTRY)
    for q in (_Q.get("indeed") or []):
        try:
            df=scrape_jobs(site_name=["indeed"],search_term=q,location=_COUNTRY_NAME,
                           hours_old=72,results_wanted=25,country_indeed=_cc)
        except Exception as e: print(f"indeed arm error ({q}):",e); continue
        for _,r in df.iterrows():
            t=str(r.get('title') or '')
            if _ADROP.search(t): continue
            url=str(r.get('job_url') or '')
            jk=re.search(r"jk=([0-9a-f]+)|job/[^/]*-([0-9a-f]{10,})",url)
            jk=(jk.group(1) or jk.group(2)) if jk else str(r.get('id') or '').replace('in-','')
            desc=str(r.get('description') or '')
            if jk and len(desc)>300:
                open(os.path.join(ROOT,"tracking","jds",f"indeed_{jk}.txt"),"w", encoding="utf-8").write(
                    f"{t}\n{r.get('location')}\n{url}\n\n{desc}")
            _co=str(r.get('company') or '');_co='unknown' if _co in ('','nan','None') else _co
            out.append(dict(src="in:"+_co,title=t,
                loc=str(r.get('location') or ''),url=url,posted=str(r.get('date_posted') or '')[:10]))
    seen=set(); ded=[]
    for x in out:
        k=(x["src"],x["title"][:40])
        if k in seen: continue
        seen.add(k); ded.append(x)
    _discover(ded,"in")
    print(f"indeed: {len(ded)} candidates (72h window)")
    return ded

# ── small-ATS boards (one fetch per company) ───────────────────────────────────────────────────────────────────
def misc_one(e):
    kind,name,base=e.get("kind"),e.get("name",""),e.get("base","").rstrip("/")
    out=[]
    try:
        if kind=="bamboo":
            d=json.loads(fetch(base+"/careers/list"))
            for j in d.get("result",[]):
                out.append((name,j.get("jobOpeningName",""),(j.get("location",{}) or {}).get("city","") if isinstance(j.get("location"),dict) else str(j.get("location") or ""),f"{base}/careers/{j.get('id')}",""))
        elif kind=="breezy":
            for j in json.loads(fetch(base+"/json")):
                out.append((name,j.get("name",""),(j.get("location",{}) or {}).get("name",""),j.get("url",""),(j.get("published_date","") or "")[:10]))
        elif kind=="jobvite":
            h=fetch(base)
            for m in re.finditer(r'href="(/[^"]*?/job/[^"]+)"[^>]*>\s*([^<]{4,90})<',h):
                out.append((name,html.unescape(m.group(2)).strip(),"","https://jobs.jobvite.com"+m.group(1),""))
        elif kind=="wprss":
            h=fetch(base)
            for m in re.finditer(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>",h,re.S):
                out.append((name,html.unescape(m.group(1)).strip(),"",html.unescape(m.group(2).strip()),""))
        elif kind=="nodi":   # 2026-10-16 port: Nodi public job offers; base = the company name as Nodi spells it. Descriptions cached.
            for j in json.loads(fetch(f"https://api.nodi.global/job-offers/active/company/{urllib.parse.quote(base or name)}")):
                u=j.get("magic_link") or ""
                if not u: continue
                _cache_jd(u,j.get("title",""),j.get("location",""),_untag(j.get("description","")))
                out.append((name,j.get("title",""),j.get("location") or j.get("modality") or "",u,(j.get("updated_at") or j.get("created_at") or "")[:10]))
        elif kind=="rippling":
            h=fetch(base)
            for m in re.finditer(r'href="(/[^"]*jobs/[^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{4,90})<',h):
                out.append((name,html.unescape(m.group(2)).strip(),"","https://ats.rippling.com"+m.group(1),""))
    except Exception as ex: print(f"misc arm error ({name}):",ex)
    return out

_WHOLE={"getro":getro,"ats_links":ats_links,"rss":rss,"html_links":html_links,"pipermail":pipermail,"neogov":neogov,"json_list":json_list,"usajobs":usajobs}
_SMALL=("bamboo","breezy","jobvite","wprss","rippling","nodi")
def main():
    res=[]
    whole=[e for e in FEEDS if e.get("kind") in _WHOLE]
    if any(x.get("kind") in ("getro","ats_links") or "{kw}" in str(x.get("base","")) for x in whole) and not BOARD_TERMS:
        print("feeds: queries.yaml has no board_terms - keyword-searched boards return nothing")
    with cf.ThreadPoolExecutor(6) as ex:
        futs=[(e,ex.submit(_WHOLE[e["kind"]],e)) for e in whole]
        for e,f in futs:
            try: res+=f.result()
            except Exception as ex_: print(f"feeds error ({e.get('kind')}:{e.get('name','?')}): {type(ex_).__name__}")   # v0.8 (M12): said, not swallowed
    seen=set(); uniq=[]
    for src,title,loc,url,dt in res:
        k=url.rstrip('/')
        if k in seen or _ADROP.search(title): continue
        seen.add(k); uniq.append(dict(src=src,title=title,loc=loc,url=url,posted=dt))
    if _cfg('run.adzuna', False) and ADZUNA_KEY: uniq+=adzuna()      # settings.yaml run.adzuna + keys.json
    else: print('adzuna arm: off (settings.yaml run.adzuna false or no key)')
    if _cfg('run.linkedin_guest', False): uniq+=linkedin()      # v0.3: OFF by default (opt-in in settings.yaml; see system/docs/DEVELOPER.md on the LinkedIn/Indeed terms of service)
    else: print('linkedin arm: off (settings.yaml run.linkedin_guest false)')
    if _cfg('run.indeed_jobspy', False): uniq+=indeed()
    for e in FEEDS:
        if e.get("kind")=="smartrecruiters_search": uniq+=smartrecruiters_search(e)
        elif e.get("kind")=="custom_html": uniq+=custom_html(e)
    small=[e for e in FEEDS if e.get("kind") in _SMALL]
    out=[]
    for e in small: out+=misc_one(e)
    ded=[]; seen=set()
    for nm,t,loc,u,dt in out:
        if u in seen or _ADROP.search(t): continue
        seen.add(u); ded.append(dict(src="misc:"+nm,title=t,loc=loc,url=u,posted=dt))
    print(f"misc: {len(ded)} candidates from {len(small)} small-ATS boards")
    uniq+=ded
    json.dump(uniq,open(os.path.join(ROOT,"tracking","feed_candidates.json"),"w", encoding="utf-8"),indent=1)
    print(f"feeds: {len(res)} raw from {len(whole)} keyword boards (+aggregators, small ATS, custom) -> {len(uniq)} unique candidates -> tracking/feed_candidates.json")
    from collections import Counter
    print("by source:",dict(Counter(u['src'] for u in uniq)))
if __name__=="__main__": main()
