"""ELIGIBILITY — the ONE shared title filter (2026-09-29 audit fix #5).
Per the title-blind rule (system/engine/charters/search.md), a job title may only DROP a posting for
ELIGIBILITY - roles the user cannot or will not take regardless of fit - never for fit. Every arm imports ELIG
from here so the lists cannot drift apart again (the 9/29 audit found four inconsistent copies).
Covered: internships/co-ops/apprenticeships, new-grad/campus programs, temp and contract gigs (generic), plus
the role types the user lists in settings.yaml exclusions.role_types (e.g. buyer, procurement, recruiter, operator).
Deliberately NOT covered: technician, manager, director, specialist etc. - those are fit questions the
JD gate and rubric decide."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import work_auth as _work_auth, exclusions as _exclusions, targets as _targets   # JOBKIT
# GENERIC title-eligibility drops (every user): internships/co-ops/apprenticeships, new-grad/campus programs,
# temp and contract gigs. Role-TYPE drops the user will never take (e.g. buyer, procurement, recruiter, operator,
# vehicle driver) are WORKSPACE data: settings.yaml exclusions.role_types, a list of regexes (plain words are fine),
# each applied word-bounded and case-insensitively. Empty list = only the generic drops.
# 2026-10-09 (academic path): the pieces are switchable from settings.yaml -
#   targets.phd_positions: true  -> the new-grad / campus-hire / "(2027 Start)" piece is OFF (PhD studentships and graduate
#                                   research assistantships are the target, not a closed door)
#   targets.fixed_term_ok: true  -> the temp / temporary piece is OFF (academic research posts are routinely fixed-term)
#   exclusions.postdocs: false   -> postdoctoral titles are DROPPED (the flag existed in settings.yaml but no code consumed it)
_TG = _targets(); _EXC = _exclusions()
# v0.7: every piece below is switched by what the person said they are looking for (settings.yaml targets.position_types,
# onboarding phase 5). Nothing is dropped because the ORIGINAL user did not want it.
_ELIG_PARTS = []
if not _TG["internships_ok"]:
    _ELIG_PARTS += [r"\bintern(s|ships?)?\b|\bsummer (analyst|associate)s?\b"]   # internship titles incl. finance-style
if not _TG["coops_ok"]:
    _ELIG_PARTS += [r"\bco-?ops?\b|\bapprentice(s|ships?)?\b"]
if not _EXC["contract_work"]:
    _ELIG_PARTS += [r"\bcontract(or)?\s*\(|\(contract(or)?\)"]
if not (_TG["phd_positions"] or _TG["new_grad_ok"]):
    _ELIG_PARTS += [r"\b20\d\d start\b|\(20\d\d start\)",  # "(2027 Start)" graduate-programme titles
                    r"\bnew[- ](college[- ])?grad(uate)?s?\b|\b(university|college) (grad|graduate|hire)s?\b|\bcampus (hire|recruit\w*)\b"]
if not _TG["fixed_term_ok"]:
    # 2026-10-16 port: "High Temp Metallics" / "Low-Temp Furnace" are materials words, not a temporary job
    _ELIG_PARTS += [r"(?<!high )(?<!high-)(?<!low )(?<!low-)(?<!ultra )(?<!ultra-)\btemp\b(?![- ]?(?:metal|alloy|material|ceramic|furnace|sensor|control|superconduct))|\btemporary\b"]
if not _EXC["postdocs"]:
    _ELIG_PARTS += [r"\bpost[- ]?doc(toral|s)?\b|\bpost[- ]?doctoral\b"]   # "Postdoc", "Post-doctoral", "Post Doctoral Researcher"
_GENERIC_ELIG = "|".join(_ELIG_PARTS) or r"(?!x)x"
def _role_type_regex():
    pats = []
    for x in _exclusions()["role_types"]:
        x = str(x or "").strip()
        if not x:
            continue
        try:
            re.compile(x)
        except re.error:
            x = re.escape(x)
        pats.append(rf"\b(?:{x})\b")
    return "|".join(pats)
_RT = _role_type_regex()
ELIG = re.compile(_GENERIC_ELIG + (("|" + _RT) if _RT else ""), re.I)

# EXPORT-CONTROL TAG. By default NOT an eligibility drop: the queue marks export-controlled / U.S.-person /
# residency-gated postings "⚠ITAR" so judgment can apply a user rule (e.g. prefer untagged for a while). When
# settings.yaml work_authorization.export_controlled_open is FALSE the tag becomes a knockout (export_knockout()).
# 2026-10-01 audit: the first EXPORT regex tagged 3 of 5 queue items on NDAA country-restriction boilerplate
# ("citizens of the People's Republic of China ... who are not Lawful Permanent Residents") and on inclusive
# EEO text. Tag ONLY real gates: strong export terms, or a citizen/permanent-resident requirement in gate form.
_EXPORT_STRONG = re.compile(
    r"\bITAR\b|International Traffic in Arms|export[- ]control(?:led|s)?\b|Export Administration Regulations|\bEAR\b"
    r"|export licen[cs]e|10 CFR (?:Part )?810|U\.?S\.? persons? (?:as defined|requirement|status|only|\(as)"
    r"|must be (?:a )?U\.?S\.? persons?\b|U\.?S\.? person\b[^.\n]{0,40}\brequired", re.I)
_EXPORT_GATE = re.compile(
    r"(?:must be|limited to|only|restricted to|required to be|eligib\w+|requires?)[^.\n]{0,90}"
    r"(?:U\.?S\.? citizen|permanent residen|green[- ]card)", re.I)
_NDAA = re.compile(r"People'?s Republic|Islamic Republic|Russian Federation|Democratic People|DOE Order 142", re.I)
def export_gated(text):
    """True only for a real export-control / citizenship-or-permanent-resident gate. Returns the matched phrase or None."""
    t = text or ""
    m = _EXPORT_STRONG.search(t)
    if m: return m.group(0)
    for m in _EXPORT_GATE.finditer(t):
        ctx = t[max(0, m.start()-200): m.end()+200]
        if not _NDAA.search(ctx): return m.group(0)
    return None
# Back-compat: EXPORT.search(text) now means export_gated(text). Keep the name for daily.py/rubric.py.
class _ExportCompat:
    def search(self, text): return export_gated(text)
EXPORT = _ExportCompat()

# 2026-10-01 audit H1/H4: ONE non-US geo test for every arm. Workday "N Locations" placeholders carry the city
# in the URL path (/job/Remote-Germany/, /job/BangaloreIND/), so the URL is checked too.
NONUS_TEXT = re.compile(
    r"\b(India|China|Japan|Korea|Israel|Germany|Ireland|Netherlands|Malaysia|Singapore|Taiwan|Canada|Brazil|France"
    r"|Italy|Spain|Poland|Lithuania|Austria|Switzerland|Czech(?:ia)?|Hungary|Romania|Finland|Norway|Denmark|Portugal"
    r"|Vietnam|Thailand|Philippines|Indonesia|Australia|Iceland|Sweden|Belgium|United Kingdom|Scotland)\b|(?<!New )\bEngland\b"
    r"|(?<!New )\bMexico\b|(?<!New )\bLondon\b|\bU\.?K\.?\b(?![A-Za-z])"
    r"|Kumamoto|Tsukuba|Yokohama|Osaka|Tokyo|Kyoto|JASM|Hsinchu|Tainan|Taichung|Dresden|Munich|Nanjing|Shanghai|Beijing"
    r"|Shenzhen|Seoul|Kaohsiung|Taoyuan|Bangalore|Bengaluru|Penang|Toronto|Vancouver(?![,\s-]*(?:WA\b|Washington|USA|US\b))|Montreal|Veldhoven|Eindhoven|Reykjav"
    r"|(?<!Florida-)(?<!Florida )(?<!FL-)(?<!FL )\b(?:Berlin|Stockholm|Copenhagen|Frankfurt|Paris|Zurich|Zürich|Amsterdam|Madrid|Milan|Warsaw|Hong Kong|Dubai|Sydney|Melbourne|Brussels|Oslo|Helsinki|Prague|Luxembourg|Barcelona|Gurgaon|Gurugram|Hyderabad|Pune|Mumbai|Chennai|Noida|Budapest|Bucharest|Lisbon|Dublin|Vienna|Athens|Krakow|Kraków|Wroclaw|Wrocław|Bratislava|Sofia|Belgrade|Zagreb|Riga|Tallinn|Vilnius|Kyiv|Istanbul|Tel Aviv|Cairo|Johannesburg|Cape Town|Lagos|Nairobi|Bogota|Bogotá|Buenos Aires|Sao Paulo|São Paulo|Santiago|Lima|Manila|Jakarta|Kuala Lumpur|Ho Chi Minh|Hanoi|Bangkok|Edinburgh|Glasgow|Manchester|Belfast|Cork|Galway|Geneva|Basel|Lausanne|Hamburg|Stuttgart|Cologne|Düsseldorf|Rotterdam|The Hague|Antwerp|Lyon|Toulouse|Valencia|Porto|Gothenburg|Aarhus|Bergen|Tampere)\b(?!,\s*(?:(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b|USA|US\b|United States|Texas|Florida|Ohio|Georgia|Virginia|California|Oregon))"  # finance-board cities leaked once; US namesakes (Berlin, Paris, Melbourne as US towns) are excluded by the state lookahead
    r"|[぀-ヿ一-鿿가-힯]", re.I)
NONUS_URL = re.compile(r"(?:Remote|Hybrid)[-_ ]+(?:Germany|UK|Europe|EMEA|Canada|India|APAC|Netherlands|Ireland|Israel|Japan|Korea|Taiwan|Singapore|Mexico)\b"
    r"|(?<=[a-z])(?:IND|CHN|JPN|KOR|ISR|TWN|DEU|GBR|CAN|MEX|SGP|MYS|NLD|IRL)(?=[/_-]|$)|(?<=/)(?:IND|CHN|JPN|KOR|ISR|TWN|DEU|GBR|CAN|MEX|SGP|MYS|NLD|IRL)---|Bangalore|Bengaluru|Hsinchu|Tokyo|Shanghai|Beijing|Munich|Dresden|Toronto"
    r"|(?<![A-Za-z])(?:Germany|Netherlands|Ireland|Israel|Japan|Korea|Taiwan|Singapore|Malaysia|Canada)(?![A-Za-z])")
# 2026-10-05: country codes only glued to a city (BangaloreIND) or as a "CAN---" prefix - "Senior-ISR-Payload" (Leidos)
# was read as Israel; "New England" and "Vancouver, WA/USA" were read as non-US.
# Country awareness (system/engine/tools/geo.py): the lists above are foreign places RELATIVE TO THE UNITED STATES. For a
# user searching another country the user's own country name/code is whitelisted first and geo.FOREIGN_EXTRA
# (e.g. "United States|USA" for a Canadian user) is added. Declared assumption: one country of search per workspace.
import geo as _geo
# v0.7: other countries the person would also work in (settings.yaml location.other_countries; onboarding phase 4)
from userconfig import location as _loc_cfg
_LC = _loc_cfg()
_OTHER_ANY = any(str(c).strip().lower() in ("any", "anywhere", "all") for c in _LC["other_countries"])
def _other_regex():
    parts = []
    for c in _LC["other_countries"]:
        c = str(c).strip()
        if not c or c.lower() in ("any", "anywhere", "all"): continue
        row = _geo.COUNTRIES.get(c.upper())
        parts.append(row["in_loc"] if row else re.escape(c))
    if _LC["other_countries_regex"]: parts.append(_LC["other_countries_regex"])
    return re.compile("|".join(f"(?:{p})" for p in parts), re.I) if parts else None
_OTHER = _other_regex()
_HOME = re.compile(rf"\b{re.escape(_geo.COUNTRY_NAME)}\b|\b{re.escape(_geo.country_code())}\b", re.I) if _geo.country_code() != "US" else None
# 2026-10-16 port: a multi-site posting whose FIRST listed site is in the United States ("New York, NY; London; Bangalore",
# "Charlotte, NC, US and 2 more") is a US job with offices abroad - keep it. Only the primary (first) site decides.
_US_STATES = ("AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY")
_US_PRIMARY = re.compile(rf"^\s*(?:[^,;|/\n]+,\s*(?:{_US_STATES})\b|[^;|/\n]*\b(?:United States|USA|U\.S\.A?\.?)\b|Remote[- ,(]*(?:US|USA|United States)\b)")
def _us_primary(loc):
    first = re.split(r"\s*(?:;|\||\n| and \d+ (?:more|other)| \+\d+)\s*", loc or "", maxsplit=1)[0]
    return bool(_US_PRIMARY.search(first))
def non_us(loc="", url="", title=""):
    """Eligibility-only geo test (never fit): True if the posting is outside the user's country by location text,
    URL path or title. The function keeps its historical name; it means "not in the country of search"."""
    loc = loc or ""; url = url or ""; title = title or ""
    if _OTHER_ANY: return False                                         # v0.7: the person would work anywhere
    if _OTHER and (_OTHER.search(loc) or _OTHER.search(title)): return False   # v0.7: a country the person also accepts
    if _HOME and (_HOME.search(loc) or _HOME.search(title)): return False
    if not _HOME and _geo.country_code() == "US" and _us_primary(loc) and not NONUS_TEXT.search(title): return False
    if _geo.FOREIGN_EXTRA and (_geo.FOREIGN_EXTRA.search(loc) or _geo.FOREIGN_EXTRA.search(title)): return True
    if NONUS_TEXT.search(loc) or NONUS_TEXT.search(title): return True
    try:
        path = url.split("://",1)[-1].split("?",1)[0]
    except Exception: path = url
    if re.search(r"United[- ]States|USA|(?<![A-Za-z-])US(?:---|[-/])", path): return False   # "US---Canada" = US; NOT the Workday "/en-US/" locale segment (2026-10-05: Micron Taichung leaked)
    seg = re.search(r"/job/([^/]+)/", path)   # Workday: /job/<location>/<title>; codes count only in the location part
    if seg and re.search(r"(?<![A-Za-z])(?:IND|CHN|JPN|KOR|ISR|TWN|DEU|GBR|CAN|MEX|SGP|MYS|NLD|IRL)(?![A-Za-z])|Kaohsiung|Taoyuan", seg.group(1)):
        return True
    return bool(NONUS_URL.search(path))

# Employer-level exclusion (settings.yaml exclusions.employers: regex or plain names). Matched on the source /
# employer name and the URL only - never on JD body text (other employers mention an excluded employer as a partner).
_EXCL = [x for x in _exclusions()["employers"] if x]
EXCLUDED_EMPLOYER = re.compile("|".join(_EXCL), re.I) if _EXCL else None
def excluded_employer(src="", url="", title=""):
    return bool(EXCLUDED_EMPLOYER and EXCLUDED_EMPLOYER.search(f"{src or ''} {url or ''}"))

# Work-authorization flags (settings.yaml). The engine assumes NOTHING: every flag defaults to the restrictive reading.
AUTH = _work_auth()
def export_knockout(text):
    """True when the posting is export-gated AND the user cannot take export-controlled roles."""
    return (not AUTH["export_controlled_open"]) and bool(export_gated(text))
