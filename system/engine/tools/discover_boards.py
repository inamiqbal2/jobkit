#!/usr/bin/env python3
"""DISCOVER BOARDS - find an employer's job board automatically and register it (jobkit v0.3).

  system/.venv/bin/python system/engine/tools/discover_boards.py "Mayo Clinic" "Acme Robotics"   # these employers
  system/.venv/bin/python system/engine/tools/discover_boards.py                                 # settings.yaml targets.employers
      --dry-run     probe and report, write nothing
      --assemble    run registries.py assemble afterwards (the active lists pick the new entries up)
      --no-search   API probes only (no web search; use when the network blocks search engines)
      --watch "Name=https://..."   add a MANUAL watch entry for an employer whose careers page you already know (no probing)
      --workspace   (env JOBKIT_WORKSPACE wins) where custom.json lives

For every employer name it:
  1. probes the public job-board APIs under token variants of the name (lowercase, no-space, hyphen, common suffixes):
       Greenhouse   boards-api.greenhouse.io/v1/boards/<token>/jobs
       Lever        api.lever.co/v0/postings/<token>
       Ashby        api.ashbyhq.com/posting-api/job-board/<token>
       SmartRecruiters api.smartrecruiters.com/v1/companies/<token>/postings
       Workable     apply.workable.com/api/v1/widget/accounts/<token>
       iCIMS        careers-<token>.icims.com/jobs/search
       NEOGOV       governmentjobs.com/careers/<token>  (and schooljobs.com)
  2. web-searches "<employer>" careers (Bing first - it answers automated queries; DuckDuckGo as the fallback - it
     challenges bots after a few queries), fetches the employer's careers pages and scans them for an embedded ATS:
       Workday (<tenant>.wdN.myworkdayjobs.com/<site>, verified with the CXS POST), Oracle CX, ADP WorkforceNow, Eightfold,
       Phenom, Greenhouse/Lever/Ashby/SmartRecruiters/Workable embeds, NEOGOV, Radancy/TalentBrew and PageUp/PeopleAdmin
       server-rendered search pages (registered as html_links feeds)
  3. VERIFIES every candidate with a live call (an entry is registered only when the API answered with a job list) and
     appends it to My Job Search/tracking/registries/custom.json in the pack shape (kind, token/host, live count, date)
  4. falls back to a MANUAL watch entry with the careers-page URL when nothing verifiable was found - ONLY when that page is
     clearly the employer's (host label = the name, or the page title carries the full name; watch_url_ok) - else it says
     "I could not find <employer>'s careers page; tell me the web address if you know it" and registers nothing.
Output: one plain-language line per employer, e.g.
  Mayo Clinic: found their Oracle job site (Mayo-US), 3,114 openings; registered.
  Acme Robotics: no readable job board found; I will watch https://acme.example.com/careers by hand each run.
Nothing is ever registered unverified; existing custom.json entries are never removed (CONSTITUTION I.7).
LIMIT: a board found through the web search is verified as a live board, not as THAT employer's board - a namesake
(UCHealth Colorado vs UC Health Cincinnati) can be picked up. The output names the host; read it back to the person.
Every network call has a timeout (15-25 s) and the whole employer is capped at ~40 requests.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, sys, re, json, html, time, base64, datetime, urllib.parse, urllib.request, urllib.error, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import REGISTRIES, get as _cfg, queries as _queries
from feeds import fetch as _fetch           # the engine's GET helper (gzip-aware, UA + per-call headers)

TODAY = datetime.date.today().isoformat()
CUSTOM = os.path.join(REGISTRIES, "custom.json")
BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
JSONH = {"Accept": "application/json"}
TIMEOUT = 20
_BUDGET = {}   # employer -> requests spent


def _get(u, headers=None, data=None, timeout=TIMEOUT):
    """GET/POST as text through the engine's fetch (GET) or urllib (POST). Raises on HTTP errors."""
    from urlcanon import safe_http as _safe_http; _safe_http(u)   # v0.9 (audit H1)
    if data is None:
        return _fetch(u, headers={**BROWSER, **(headers or {})})      # feeds.fetch: 25 s timeout, gzip-aware
    h = dict(BROWSER); h.update(headers or {})
    r = urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=timeout)
    return r.read().decode("utf-8", "ignore")


def _json(u, headers=None, data=None):
    return json.loads(_get(u, headers={**JSONH, **(headers or {})}, data=data))


def _spend(emp, n=1):
    """Request budget per employer (the token probes are counted once per token; the search phase per call)."""
    _BUDGET[emp] = _BUDGET.get(emp, 0) + n
    return _BUDGET[emp] <= 60


# ---- name -> token variants ------------------------------------------------------------------------------------------
_SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|llc|ltd|plc|group|holdings|the|of|and|&|health|healthcare|"
                     r"health system|hospital|hospitals|medical center|medicine|foundation|university|college|institute|international|"
                     r"usa|us|global|technologies|technology|labs|laboratories|systems)\b", re.I)


def tokens(name):
    """Candidate board tokens for a name, most likely first. Short list: every token costs several requests."""
    base = re.sub(r"[^a-z0-9 ]+", " ", name.lower()).strip()
    words = base.split()
    stripped = _SUFFIX.sub(" ", base).split()
    cands = []
    def add(x):
        x = x.strip("-")
        if x and x not in cands and len(x) >= 2:
            cands.append(x)
    add("".join(words)); add("-".join(words)); add("".join(stripped)); add("-".join(stripped))
    if stripped: add(stripped[0])
    if words: add(words[0])
    for w in stripped:
        if len(w) >= 5: add(w)                     # "State of Washington" -> "washington"
    for s in ("careers", "jobs", "inc", "usa"):
        add("".join(stripped) + s)
    # CamelCase (SmartRecruiters style: CityofPhiladelphia) and the acronym
    add("".join(w.capitalize() if w not in ("of", "and", "the") else w for w in words))
    if len(words) >= 2: add("".join(w[0] for w in words))
    return cands[:12]


# ---- company-name check: a token like "denver" can hit a different company's board ("Animal Health Care Denver") ----
_NOISE = re.compile(r"\b(jobs?|careers?|job board|openings|hiring|at)\b", re.I)
def _sig_words(name):
    return {w for w in re.sub(r"[^a-z0-9 ]+", " ", _NOISE.sub(" ", _SUFFIX.sub(" ", str(name or "").lower()))).split() if len(w) >= 3}
def name_matches(found_name, emp):
    """True when the board's company name is the employer (same significant words, or one is the other plus at most one word)."""
    a, b = _sig_words(found_name), _sig_words(emp)
    if not a or not b: return False
    if a == b: return True
    if a < b and len(b - a) <= 1: return True
    if b < a and len(a - b) <= 1: return True
    # single-word employer vs a single compound word ("UCHealth" vs "uchealthcolorado"); never a multi-word found name
    return len(a) == 1 and len(b) == 1 and next(iter(a)).startswith(next(iter(b)))

def title_matches(title, emp):
    """Page titles come as 'A | B' / 'A - B' segments ('Working at X', 'X Job Opportunities | Work that Matters'); any segment may match."""
    for seg in re.split(r"\s[|\-\u2013\u2014:]\s", str(title or "")):
        seg = re.sub(r"^\s*(working at|jobs at|careers at|welcome to)\s+", "", seg, flags=re.I)
        if name_matches(seg, emp): return True
    return False

class NameMismatch(ValueError):
    pass

def _check_name(found_name, emp, what):
    if emp and found_name and not name_matches(found_name, emp):
        raise NameMismatch(f"{what} board belongs to '{found_name}', not '{emp}'")


# ---- verifiers: each returns (entry, count, label) or raises -------------------------------------------------------------
def v_greenhouse(tok, emp=None):
    d = _json(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs")
    n = len(d.get("jobs", []))
    if emp:
        if n == 0: raise ValueError("greenhouse: empty board under a guessed token - not evidence")
        _check_name((_json(f"https://boards-api.greenhouse.io/v1/boards/{tok}") or {}).get("name", ""), emp, "Greenhouse")
    return (["gh", tok, f"added {TODAY} by discover_boards: {n} openings"], n, "Greenhouse")

def _title_of(url):
    m = re.search(r"<title>(.*?)</title>", _get(url), re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else ""

def v_lever(tok, emp=None):
    d = _json(f"https://api.lever.co/v0/postings/{tok}?mode=json")
    if not isinstance(d, list): raise ValueError("not a lever list")
    if emp:
        if not d: raise ValueError("lever: empty board under a guessed token - not evidence")
        _check_name(_title_of(f"https://jobs.lever.co/{tok}"), emp, "Lever")
    return (["lever", tok, f"added {TODAY} by discover_boards: {len(d)} openings"], len(d), "Lever")

def v_ashby(tok, emp=None):
    d = _json(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
    n = len(d.get("jobs", []))
    if n == 0: raise ValueError("ashby: empty board (unknown slugs answer with an empty list)")
    if emp: _check_name(_title_of(f"https://jobs.ashbyhq.com/{tok}"), emp, "Ashby")
    return (["ashby", tok, f"added {TODAY} by discover_boards: {n} openings"], n, "Ashby")

def v_smartrecruiters(tok, emp=None):
    d = _json(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=1")
    n = int(d.get("totalFound") or 0)
    if n == 0: raise ValueError("smartrecruiters: no postings")
    if emp:
        c = ((d.get("content") or [{}])[0].get("company") or {}).get("name", "")
        _check_name(c, emp, "SmartRecruiters")
    return (["smartrecruiters", tok, f"added {TODAY} by discover_boards: {n} openings"], n, "SmartRecruiters")

def v_workable(tok, emp=None):
    d = _json(f"https://apply.workable.com/api/v1/widget/accounts/{tok}")
    n = len(d.get("jobs", []))
    if n == 0: raise ValueError("workable: unknown account or no openings (the widget answers 200 for any token)")
    if emp: _check_name(d.get("name", ""), emp, "Workable")
    return (["workable", tok, f"added {TODAY} by discover_boards: {n} openings"], n, "Workable")

def v_icims(tok, emp=None):
    h = _get(f"https://careers-{tok}.icims.com/jobs/search?ss=1&in_iframe=1&pr=0")
    n = len(set(re.findall(r"/jobs/(\d+)/", h)))
    if n == 0: raise ValueError("icims: no job links")
    if emp:
        m = re.search(r"<title>(.*?)</title>", h, re.S | re.I)
        t = html.unescape(m.group(1)) if m else _title_of(f"https://careers-{tok}.icims.com/jobs/intro")
        if t and not title_matches(t, emp): raise NameMismatch(f"iCIMS site belongs to '{t.strip()[:60]}', not '{emp}'")
    return ({"name": tok, "tenant": tok, "note": f"added {TODAY} by discover_boards: {n} job links on the first search page"}, n, "iCIMS")

def v_neogov(tok, host="www.governmentjobs.com", emp=None):
    d = _json(f"https://{host}/careers/{tok}/home/loadJobsOnMaps", headers={"X-Requested-With": "XMLHttpRequest"})
    n = len(d.get("jobList") or [])
    if n == 0: raise ValueError("neogov: empty")
    if emp:
        t = _title_of(f"https://{host}/careers/{tok}")
        if t and not title_matches(t, emp): raise NameMismatch(f"NEOGOV board belongs to '{t.strip()[:60]}', not '{emp}'")
    return ({"kind": "neogov", "name": tok, "host": host, "agency": tok, "note": f"added {TODAY} by discover_boards: {n} postings on the board"}, n, "NEOGOV")

def v_workday(host, tenant, site):
    """host like 'ccf.wd1' (or a myworkdaysite.com host). Verified ONLY on HTTP 200 + a jobPostings list."""
    base = host if host.endswith(".myworkdaysite.com") else f"{host}.myworkdayjobs.com"
    body = json.dumps({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}).encode()
    d = _json(f"https://{base}/wday/cxs/{tenant}/{site}/jobs", headers={"Content-Type": "application/json"}, data=body)
    if "jobPostings" not in d: raise ValueError("workday: no jobPostings")
    n = int(d.get("total") or 0)
    return ([host, tenant, site, f"added {TODAY} by discover_boards: {n} openings"], n, "Workday")

def v_oracle(host, site):
    d = _json(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&finder=findReqs;siteNumber={site},limit=1,offset=0,sortBy=POSTING_DATES_DESC")
    it = (d.get("items") or [{}])[0]
    if "TotalJobsCount" not in it: raise ValueError("oracle: not a requisition search response")
    n = int(it.get("TotalJobsCount") or 0)
    return ({"name": "", "host": host, "site": site, "note": f"added {TODAY} by discover_boards: {n} openings"}, n, "Oracle CX")

def v_adp(cid, ccid):
    d = _json(f"https://workforcenow.adp.com/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions?cid={cid}&ccId={ccid}&lang=en_US&locale=en_US&$top=50&$skip=0")
    n = len(d.get("jobRequisitions") or [])
    if n == 0: raise ValueError("adp: empty")
    return ({"name": "", "cid": cid, "ccId": ccid, "note": f"added {TODAY} by discover_boards: {n} openings (first page)"}, n, "ADP WorkforceNow")

def v_eightfold(base, domain):
    d = _json(f"{base}/api/pcsx/search?domain={domain}&query=&location=&start=0")
    n = int(((d.get("data") or {}).get("count")) or len((d.get("data") or {}).get("positions") or []))
    if n == 0: raise ValueError("eightfold: empty")
    return ({"name": "", "base": base, "domain": domain, "note": f"added {TODAY} by discover_boards: {n} openings"}, n, "Eightfold")

def v_phenom(base, locale="us/en"):
    body = json.dumps({"lang": "en_us", "deviceType": "desktop", "country": "us", "ddoKey": "refineSearch", "from": 0, "size": 1,
                       "jobs": True, "counts": True, "keywords": "", "global": True, "selected_fields": {}}).encode()
    d = _json(f"{base}/widgets", headers={"Content-Type": "application/json"}, data=body)
    n = int(((d.get("refineSearch") or {}).get("totalHits")) or 0)
    if n == 0: raise ValueError("phenom: empty")
    return ({"name": "", "base": base, "locale": locale, "note": f"added {TODAY} by discover_boards: {n} openings"}, n, "Phenom")

_RADANCY_JOB = re.compile(r'href="(/job/[a-z0-9-]+/[a-z0-9-]+/\d+/\d+)"', re.I)
def v_radancy(origin):
    """Radancy / TalentBrew career sites: server-rendered /search-jobs/<keyword> pages with /job/<city>/<title>/<n>/<n> links."""
    h = _get(f"{origin}/search-jobs")
    n = len(set(_RADANCY_JOB.findall(h)))
    if n == 0: raise ValueError("radancy: no job links")
    return ({"kind": "html_links", "name": "", "base": f"{origin}/search-jobs/{{kw}}", "href_regex": r"^/job/[a-z0-9-]+/[a-z0-9-]+/\d+/\d+", "headers": BROWSER,
             "note": f"added {TODAY} by discover_boards: Radancy search page, {n} job links on the unfiltered first page; one fetch per board term"}, n, "Radancy careers site")

_PAGE_PATTERNS = [   # (label, href regex that marks a job anchor, keyword-search URL template or None)
    ("PageUp", r"/en-us/job/\d+", "{origin}/en-us/search/?search-keyword={kw}"),
    ("PeopleAdmin", r"^/postings/\d+$", "{origin}/postings/search?query={kw}"),
]
def v_server_rendered(url):
    """A careers page whose anchors already point at job detail pages (PageUp / PeopleAdmin and a generic '-<id>/' slug)."""
    h = _get(url)
    origin = re.match(r"https?://[^/]+", url).group(0)
    for label, rx, tmpl in _PAGE_PATTERNS:
        n = len(set(re.findall(rx, h)))
        if n >= 3:
            return ({"kind": "html_links", "name": "", "base": tmpl.format(origin=origin, kw="{kw}"), "href_regex": rx, "headers": BROWSER,
                     "note": f"added {TODAY} by discover_boards: {label} listing, {n} job links on {url}"}, n, label)
    # generic: the page itself lists jobs as /<path>/<slug>-<id>/ anchors with a readable title
    m = re.findall(r'href="((?:https?://[^/"]+)?(/[a-z0-9/_-]*?)/[a-z0-9-]+-\d{3,}/?)"', h, re.I)
    if m and re.search(r"career|job|employment|opening|position", url, re.I):
        from collections import Counter
        prefix, cnt = Counter(p for _, p in m).most_common(1)[0]
        if cnt >= 5 and prefix:
            rx = re.escape(prefix) + r"/[a-z0-9-]+-\d{3,}/?$"
            sep = "&" if "?" in url else "?"
            return ({"kind": "html_links", "name": "", "base": f"{url}{sep}keyword={{kw}}", "href_regex": rx, "headers": BROWSER,
                     "note": f"added {TODAY} by discover_boards: server-rendered listing, {cnt} job links under {prefix}/ on {url}; keyword param assumed"}, cnt, "careers page listing")
    raise ValueError("no job anchors")


# ---- web search ------------------------------------------------------------------------------------------------------
def _bing(q):
    """Bing answers automated queries. The form that works is q='"<employer>" careers' - appending 'jobs' or other words makes
    Bing drop the quoted phrase and answer about the city instead (tested 2026-10-11)."""
    h = _get("https://www.bing.com/search?q=" + urllib.parse.quote_plus(q))
    out = []
    for m in re.findall(r'<h2[^>]*><a[^>]+href="([^"]+)"', h):
        mm = re.search(r"u=a1([A-Za-z0-9_-]+)", m)
        if mm:
            s = mm.group(1); s += "=" * (-len(s) % 4)
            try: out.append(base64.urlsafe_b64decode(s).decode("utf-8", "ignore"))
            except Exception: pass
        elif m.startswith("http") and "bing.com" not in m:
            out.append(html.unescape(m))
    for c in re.findall(r"<cite>([^<]+)</cite>", h):      # the breadcrumb form carries the real host + first path segments
        u = re.sub(r"\s*›\s*", "/", html.unescape(c)).replace("/...", "")
        if u.startswith("http") and u not in out: out.append(u)
    return out

def _ddg(q):
    h = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q))
    if "bots use DuckDuckGo too" in h or "challenge" in h[:3000].lower():
        raise RuntimeError("duckduckgo is showing a bot challenge")
    out = []
    for m in re.findall(r'uddg=([^&"]+)', h):
        u = urllib.parse.unquote(m)
        if u not in out: out.append(u)
    return out

def web_search(q):
    """Result URLs for q, Bing first (the employer name should be quoted), then DuckDuckGo; [] when both fail."""
    for fn in (_bing, _ddg):
        try:
            r = fn(q)
            if r: return r
        except Exception as e:
            print(f"    web search ({fn.__name__[1:]}) failed: {type(e).__name__}", file=sys.stderr)
    return []


# ---- ATS URL recognition in a page or a search result ------------------------------------------------------------------
ATS_URL = re.compile(r"https?://[A-Za-z0-9.-]*(?:myworkdayjobs\.com|myworkdaysite\.com|greenhouse\.io|lever\.co|ashbyhq\.com|icims\.com|"
                     r"oraclecloud\.com|eightfold\.ai|smartrecruiters\.com|governmentjobs\.com|schooljobs\.com|workforcenow\.adp\.com|"
                     r"apply\.workable\.com)[^\"'\s<>\\]*", re.I)
_WD_SITES = ["External", "Careers", "careers", "External_Careers", "ExternalCareers", "Jobs", "jobs"]


def _candidates_from_urls(urls, emp):
    """Turn ATS-looking URLs into verifier calls. Returns [(label, callable)] without running them."""
    out, seen = [], set()
    for u in urls:
        u = html.unescape(u).split("#")[0]
        m = re.search(r"https?://([a-z0-9-]+\.wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)", u)
        if m:
            host, site = m.group(1), m.group(2); tenant = host.split(".")[0]
            if site.lower() in ("wday", "login", "en-us", "job", "details"): site = None
            key = ("wd", host, site)
            if key in seen: continue
            seen.add(key)
            if site: out.append((f"Workday {host}/{site}", lambda h=host, t=tenant, s=site: v_workday(h, t, s)))
            else:
                for s in _WD_SITES: out.append((f"Workday {host}/{s}", lambda h=host, t=tenant, s=s: v_workday(h, t, s)))
            continue
        m = re.search(r"https?://(wd\d+\.myworkdaysite\.com)/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)", u)
        if m and ("wds", m.group(2), m.group(3)) not in seen:
            seen.add(("wds", m.group(2), m.group(3)))
            out.append((f"Workday {m.group(1)}/{m.group(2)}/{m.group(3)}", lambda h=m.group(1), t=m.group(2), s=m.group(3): v_workday(h, t, s)))
            continue
        m = re.search(r"https?://([a-z0-9.-]+oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}/sites/([A-Za-z0-9_-]+)", u)
        if m and ("ora", m.group(1), m.group(2)) not in seen:
            seen.add(("ora", m.group(1), m.group(2)))
            out.append((f"Oracle CX {m.group(1)}/{m.group(2)}", lambda h=m.group(1), s=m.group(2): v_oracle(h, s))); continue
        m = re.search(r"greenhouse\.io/([a-z0-9_-]+)", u)
        if m and ("gh", m.group(1)) not in seen and m.group(1) not in ("v1", "embed", "boards"):
            seen.add(("gh", m.group(1))); out.append((f"Greenhouse {m.group(1)}", lambda t=m.group(1): v_greenhouse(t))); continue
        m = re.search(r"lever\.co/([a-z0-9_-]+)", u)
        if m and ("lv", m.group(1)) not in seen and m.group(1) != "v0":
            seen.add(("lv", m.group(1))); out.append((f"Lever {m.group(1)}", lambda t=m.group(1): v_lever(t))); continue
        m = re.search(r"ashbyhq\.com/([A-Za-z0-9_.-]+)", u)
        if m and ("ab", m.group(1)) not in seen and m.group(1) not in ("posting-api",):
            seen.add(("ab", m.group(1))); out.append((f"Ashby {m.group(1)}", lambda t=m.group(1): v_ashby(t))); continue
        m = re.search(r"careers-([a-z0-9-]+)\.icims\.com", u)
        if m and ("ic", m.group(1)) not in seen:
            seen.add(("ic", m.group(1))); out.append((f"iCIMS {m.group(1)}", lambda t=m.group(1): v_icims(t))); continue
        m = re.search(r"smartrecruiters\.com/(?:v1/companies/)?([A-Za-z0-9_-]+)", u)
        if m and ("sr", m.group(1)) not in seen and m.group(1) not in ("api", "jobs"):
            seen.add(("sr", m.group(1))); out.append((f"SmartRecruiters {m.group(1)}", lambda t=m.group(1): v_smartrecruiters(t))); continue
        m = re.search(r"(governmentjobs\.com|schooljobs\.com)/careers/([a-z0-9]+)", u)
        if m and ("ng", m.group(2)) not in seen:
            seen.add(("ng", m.group(2))); out.append((f"NEOGOV {m.group(2)}", lambda t=m.group(2), h="www." + m.group(1): v_neogov(t, h))); continue
        m = re.search(r"workforcenow\.adp\.com[^\s]*?cid=([0-9a-f-]+)[^\s]*?ccId=([0-9_]+)", u)
        if m and ("adp", m.group(1)) not in seen:
            seen.add(("adp", m.group(1))); out.append((f"ADP {m.group(1)[:8]}", lambda c=m.group(1), cc=m.group(2): v_adp(c, cc))); continue
        m = re.search(r"(https?://[a-z0-9.-]*eightfold\.ai)[^\s]*?domain=([a-z0-9.-]+)", u)
        if m and ("ef", m.group(2)) not in seen:
            seen.add(("ef", m.group(2))); out.append((f"Eightfold {m.group(2)}", lambda b=m.group(1), d=m.group(2): v_eightfold(b, d))); continue
        m = re.search(r"apply\.workable\.com/([a-z0-9-]+)", u)
        if m and ("wk", m.group(1)) not in seen and m.group(1) != "api":
            seen.add(("wk", m.group(1))); out.append((f"Workable {m.group(1)}", lambda t=m.group(1): v_workable(t))); continue
    return out


_PLACE = re.compile(r"^(city|county|state|town|village|district|department|dept|office|school|schools|public)$", re.I)
def _same_org(url, emp):
    """Does a search-result URL belong to the employer? Every significant name word must appear in the host (no hyphens), or
    the URL must be a careers/jobs page that carries the employer's first significant word somewhere in it."""
    m = re.match(r"https?://([^/]+)", url)
    if not m: return False
    host = m.group(1).lower().replace("-", "")
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", emp.lower()).split() if len(w) > 2 and w not in ("the", "and", "for") and not _PLACE.match(w)]
    if not words: words = [w for w in re.sub(r"[^a-z0-9 ]", " ", emp.lower()).split() if len(w) > 2]
    missing = [w for w in words if w not in host]
    if words and (not missing or (len(words) >= 3 and len(missing) == 1)): return True
    low = url.lower().replace("-", "")
    return bool(words) and any(k in low for k in ("career", "jobs", "employment")) and words[0] in low


def _host_label(url):
    """'https://www.columbusstate.edu/careers' -> 'columbusstate' (the registrable label, hyphens removed)."""
    m = re.match(r"https?://([^/:]+)", url or "")
    if not m: return ""
    parts = [x for x in m.group(1).lower().split(".") if x and x != "www"]
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "ac", "edu", "gov", "net", "k12"): parts = parts[:-2]   # example.co.uk / x.k12.oh.us
    elif len(parts) >= 2: parts = parts[:-1]
    return (parts[-1] if parts else "").replace("-", "")

def watch_url_ok(url, emp, title=""):
    """May a careers page be registered as the employer's MANUAL watch page? (audit v0.4 bug 7: 'Columbus City Schools'
    -> columbusstate.edu, 'Dublin City Schools' -> visitdublin.com were registered as the schools' pages.)
    YES when the host's registrable label equals a significant word of the name or contains the whole name run together
    (with or without its generic suffixes), or when the page TITLE contains the full employer name. Otherwise NO."""
    words = re.sub(r"[^a-z0-9 ]+", " ", str(emp or "").lower()).split()
    if not words: return False
    stripped = _SUFFIX.sub(" ", " ".join(words)).split()
    label = _host_label(url)
    if label:
        whole = {"".join(words)} | ({"".join(stripped)} if len(stripped) >= 2 else set())
        if any(w in label for w in whole if w): return True
        if len(words) == 1 and label == words[0]: return True   # a one-word employer ("Battelle" -> battelle.org); a word of a
                                                                 # longer name ("denver" of Denver Health, "columbus" of Columbus
                                                                 # City Schools) never suffices on its own
    t = re.sub(r"\s+", " ", html.unescape(str(title or ""))).lower()
    return bool(t) and " ".join(words) in re.sub(r"[^a-z0-9 ]+", " ", t)


# ---- the per-employer routine ------------------------------------------------------------------------------------------
def discover(emp, do_search=True):
    """Returns dict(employer, found=[(label, entry, count, kind)], watch=url|None, lines=[...])."""
    found, notes = [], []
    toks = tokens(emp)
    print(f"  {emp}: probing {len(toks)} name variants on 7 ATS APIs ...", flush=True)
    # 1. direct token probes, in parallel (cheap JSON calls; an unknown token answers 404 at once)
    jobs = []
    for t in toks:
        jobs += [("gh", t, lambda t=t: v_greenhouse(t, emp)), ("lever", t, lambda t=t: v_lever(t, emp)), ("ashby", t, lambda t=t: v_ashby(t, emp)),
                 ("sr", t, lambda t=t: v_smartrecruiters(t, emp)), ("workable", t, lambda t=t: v_workable(t, emp))]
        if len(t) >= 5 and "-" not in t:   # tenant-style tokens only (a short token like "denver" would hit someone else's agency)
            jobs += [("icims", t, lambda t=t: v_icims(t, emp)), ("neogov", t, lambda t=t: v_neogov(t, emp=emp)), ("neogov-school", t, lambda t=t: v_neogov(t, "www.schooljobs.com", emp))]
    def run(j):
        k, t, fn = j
        try: return k, t, fn()
        except NameMismatch as e: return k, t, str(e)
        except Exception: return k, t, None
    with cf.ThreadPoolExecutor(8) as ex:
        for k, t, r in ex.map(run, jobs):
            if isinstance(r, str): notes.append(r)
            elif r:
                entry, n, label = r
                found.append((label, entry, n, k))
    _spend(emp, len(toks))
    # one board per ATS kind: the most populated token wins (e.g. "stripe" over "stripecareers")
    best = {}
    for label, entry, n, k in found:
        if label not in best or n > best[label][2]: best[label] = (label, entry, n, k)
    found = list(best.values())
    # 2. web search -> careers pages -> embedded ATS
    watch_url = None
    if do_search and not any(l in ("Greenhouse", "Lever", "Ashby", "Workday") and n > 0 for l, e, n, k in found):
        urls = [u for u in web_search(f'"{emp}" careers') if _same_org(u, emp)]
        if not urls:   # Bing sometimes drops the quoted phrase; try the plain form once
            urls = [u for u in web_search(f"{emp} careers") if _same_org(u, emp)]
        urls = urls[:6]
        # their own careers address: <origin>/careers for every host of theirs the search returned, then www.<token>.org|com/careers
        guessed = set()
        if not any(re.search(r"career|jobs|employment", u, re.I) for u in urls):
            for o in list(dict.fromkeys(re.match(r"https?://[^/]+", u).group(0) for u in urls if re.match(r"https?://[^/]+", u)))[:2]:
                urls.append(f"{o}/careers"); guessed.add(f"{o}/careers")
            for t in toks[:2]:
                if "-" in t: continue
                for tld in ("org", "com"):
                    urls.append(f"https://www.{t}.{tld}/careers"); guessed.add(f"https://www.{t}.{tld}/careers")
            notes.append("web search gave no careers page of theirs; trying the usual careers addresses")
        cands = _candidates_from_urls(urls, emp)
        pages = [u for u in urls if not ATS_URL.search(u) and not re.search(r"indeed|glassdoor|linkedin|wikipedia|ziprecruiter", u)]
        pages = sorted(dict.fromkeys(pages), key=lambda u: 0 if re.search(r"career|jobs|employment", u, re.I) else 1)[:5]   # careers pages first
        reached = []; titles = {}
        for u in pages:
            if not _spend(emp): break
            try:
                h = _get(u)
            except Exception as e:
                notes.append(f"{u.split('?')[0][:70]} did not answer ({type(e).__name__}: {str(e)[:40]})"); continue
            reached.append(u)
            _tm = re.search(r"<title>(.*?)</title>", h, re.S | re.I); titles[u] = html.unescape(_tm.group(1)).strip() if _tm else ""
            cands += _candidates_from_urls(ATS_URL.findall(h), emp)
            origin = re.match(r"https?://[^/]+", u).group(0)
            if "talentbrew" in h or "radancy" in h or _RADANCY_JOB.search(h):
                cands.append((f"Radancy {origin}", lambda o=origin: v_radancy(o)))
            if re.search(r"phenom|/widgets\b|phapp", h, re.I):
                cands.append((f"Phenom {origin}", lambda o=origin: v_phenom(o)))
            cands.append((f"careers page {u}", lambda u=u: v_server_rendered(u)))
        # dedupe candidate labels, verify (sequential: these are heavier calls)
        seen = set()
        for label, fn in cands:
            if label in seen or not _spend(emp): continue
            seen.add(label)
            try:
                entry, n, kind = fn()
                if isinstance(entry, dict) and not entry.get("name"): entry["name"] = emp
                found.append((kind, entry, n, label))
            except Exception as e:
                notes.append(f"{label}: {type(e).__name__}")
        # the page to watch by hand: a careers/jobs URL of THEIRS (host label = their name, or the page title carries the full
        # name) - even one that refused automated reading; a namesake's page is never registered (watch_url_ok).
        careers_like = [u for u in pages if re.search(r"career|jobs|employment", u, re.I)]
        rejected = []
        for u in (careers_like + [x for x in reached if x not in careers_like] + [x for x in pages if x not in reached]):
            if u in guessed and u not in reached: continue        # a guessed address that never answered is not a page to watch
            if watch_url_ok(u, emp, titles.get(u, "")): watch_url = u; break
            rejected.append(u)
        if watch_url is None and rejected:
            notes.append("pages found but none is clearly theirs (namesake guard): " + ", ".join(re.sub(r"^https?://", "", r)[:40] for r in rejected[:3]))
        if not urls and not found:
            notes.append("web search returned nothing (both engines)")
    # one employer, one best source: a full-text board API beats a keyword API beats a scraped listing (mirrors would double-count)
    rank = {"Greenhouse": 0, "Lever": 0, "Ashby": 0, "SmartRecruiters": 0, "Workable": 0, "Workday": 1, "Oracle CX": 2, "Eightfold": 3,
            "Phenom": 3, "iCIMS": 4, "ADP WorkforceNow": 4, "NEOGOV": 4}
    if found:
        best = min(rank.get(k, 9) for k, *_ in found)
        found = [f for f in found if rank.get(f[0], 9) == best]
        if any(n > 0 for k, e, n, l in found): found = [f for f in found if f[2] > 0]
        uniq, seen_e = [], set()
        for k, e, n, l in found:
            key = json.dumps(e, sort_keys=True) if isinstance(e, dict) else tuple(e[:3])
            host = (e.get("host") or e.get("base") or "") if isinstance(e, dict) else (e[0] if k == "Workday" else "")
            key2 = (k, host, n) if host else None     # one API host answering the same count under several site names = one board
            if key in seen_e or (key2 and key2 in seen_e): continue
            seen_e.add(key); seen_e.add(key2) if key2 else None
            uniq.append((k, e, n, l))
        found = uniq
    return dict(employer=emp, found=found, watch=watch_url, notes=notes)


# ---- custom.json merge --------------------------------------------------------------------------------------------------
EMPTY = {"pack": "custom", "description": "Your own target employers (filled during onboarding / discover_boards.py). Same shape as system/engine/registries/packs/*.json.",
         "boards": [], "workday": [], "hard": {}, "misc": [], "feeds": [], "watch": []}
_HARD_ARM = {"Oracle CX": "oracle", "ADP WorkforceNow": "adp", "Eightfold": "eightfold", "Phenom": "phenom", "iCIMS": "icims_html"}


def register(res, custom):
    """Append the verified entries of one employer to the custom dict. Returns the plain-language line."""
    emp = res["employer"]; added = []
    for kind, entry, n, label in res["found"]:
        if kind in ("Greenhouse", "Lever", "Ashby", "SmartRecruiters", "Workable"):
            if not any(b[0] == entry[0] and b[1] == entry[1] for b in custom["boards"]):
                custom["boards"].append(entry); added.append(f"{kind} board '{entry[1]}', {n:,} openings")
        elif kind == "Workday":
            if not any(w[:3] == entry[:3] for w in custom["workday"]):
                custom["workday"].append(entry); added.append(f"Workday site {entry[0]}.myworkdayjobs.com/{entry[2]}, {n:,} openings")
        elif kind in _HARD_ARM:
            arm = _HARD_ARM[kind]; entry = dict(entry); entry["name"] = entry.get("name") or emp
            lst = custom["hard"].setdefault(arm, [])
            if not any((e.get("host"), e.get("site"), e.get("tenant"), e.get("base"), e.get("cid")) == (entry.get("host"), entry.get("site"), entry.get("tenant"), entry.get("base"), entry.get("cid")) for e in lst):
                lst.append(entry); added.append(f"{kind} job site at {entry.get('host') or entry.get('base') or entry.get('tenant') or 'workforcenow.adp.com'}, {n:,} openings")
        elif kind == "NEOGOV":
            entry = dict(entry); entry["name"] = emp
            if not any(f.get("kind") == "neogov" and f.get("agency") == entry["agency"] for f in custom.setdefault("feeds", [])):
                custom["feeds"].append(entry); added.append(f"NEOGOV board '{entry['agency']}', {n:,} postings")
        else:   # html_links feeds (Radancy / PageUp / PeopleAdmin / generic listing)
            entry = dict(entry); entry["name"] = entry.get("name") or emp
            if not any(f.get("base") == entry["base"] for f in custom.setdefault("feeds", [])):
                custom["feeds"].append(entry); added.append(f"{kind} ({n} job links seen)")
    if added:
        return f"{emp}: found their " + "; ".join(added) + "; registered."
    if res["watch"]:
        if not any(str(w.get("name", "")).lower() == emp.lower() for w in custom["watch"]):
            custom["watch"].append({"name": emp, "ats": "MANUAL", "slug": res["watch"], "watch_for": [t for t in (_queries().get("board_terms") or [])[:4]],
                                    "note": f"added {TODAY} by discover_boards: no verifiable job-board API found ({'; '.join(res['notes'][:3])})"})
        return f"{emp}: no readable job board found; I will watch their careers page by hand each run ({res['watch']})."
    return f"{emp}: I could not find {emp}'s careers page; tell me the web address if you know it ({'; '.join(res['notes'][:2]) or 'no job-board API answered and the web search gave nothing of theirs'})."


def load_custom():
    if os.path.exists(CUSTOM):
        try:
            c = json.load(open(CUSTOM, encoding="utf-8"))
            for k, v in EMPTY.items():
                c.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
            return c
        except Exception as e:
            print(f"custom.json unreadable ({e}); refusing to overwrite it", file=sys.stderr); sys.exit(2)
    return json.loads(json.dumps(EMPTY))


def save_custom(c):
    os.makedirs(REGISTRIES, exist_ok=True)
    if os.path.exists(CUSTOM):
        b = f"{CUSTOM}.bak-{TODAY}"
        if not os.path.exists(b):
            os.replace(CUSTOM, b)
    with open(CUSTOM, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1, ensure_ascii=False); f.write("\n")


def main(argv):
    dry = "--dry-run" in argv; assemble = "--assemble" in argv; no_search = "--no-search" in argv
    manual = []
    while "--watch" in argv:
        i = argv.index("--watch"); spec = argv[i + 1] if i + 1 < len(argv) else ""
        if "=" in spec: manual.append(tuple(spec.split("=", 1)))
        argv = argv[:i] + argv[i + 2:]
    names = [a for a in argv if not a.startswith("--")]
    if manual and not names:
        custom = load_custom()
        for nm, url in manual:
            if not any(str(w.get("name", "")).lower() == nm.lower() for w in custom["watch"]):
                custom["watch"].append({"name": nm, "ats": "MANUAL", "slug": url, "watch_for": [t for t in (_queries().get("board_terms") or [])[:4]], "note": f"added {TODAY} (careers page given by the person)"})
            print(f"  {nm}: I will watch {url} by hand each run.")
        if not dry: save_custom(custom)
        return 0
    if not names:
        names = [str(x) for x in (_cfg("targets.employers", []) or []) if str(x).strip()]
    if not names:
        print("discover_boards: no employer names (pass them as arguments or fill settings.yaml targets.employers)"); return 1
    custom = load_custom()
    lines = []
    for emp in names:
        res = discover(emp, do_search=not no_search)
        line = register(res, custom) if not dry else (f"{emp}: " + ("; ".join(f"{k} ({n:,}) via {l}" for k, e, n, l in res["found"]) if res["found"] else f"nothing verifiable (watch {res['watch']})"))
        for nt in res["notes"]:
            print(f"      note: {nt}")
        print("  " + line, flush=True); lines.append(line)
        time.sleep(1.0)   # be polite to the search engines between employers
    if not dry:
        save_custom(custom)
        print(f"\nwrote {CUSTOM} ({len(custom['boards'])} boards, {len(custom['workday'])} Workday, "
              f"{sum(len(v) for v in custom['hard'].values())} hard-ATS, {len(custom.get('feeds', []))} feeds, {len(custom['watch'])} watch)")
        if assemble:
            import subprocess
            subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "registries.py"), "assemble"])
        else:
            print("next: system/.venv/bin/python system/engine/tools/registries.py assemble   (puts the new entries into the active lists)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
