#!/usr/bin/env python3
"""CRITIC - adversarial review of a fit decision BEFORE build effort is spent.
Deterministic decision-linter. GENERIC knockouts live here (eligibility per the user's work-authorization flags,
new-grad gates, contract gigs per exclusions.contract_work, hourly/HS-tier reqs). EVERYTHING field-specific
comes from My Job Search/profile/critic_rules.yaml (see My Job Search/profile/critic_rules.yaml.example):
  hard_checks        [{name, regex}]  never-claim cores, wrong domains, closed lanes -> HOLD
  soft_flags         [{name, regex}]  warn only
  instrument_owner   {verbs, instruments[], min_named}  "N un-operated instruments with method-development verbs"
  lane_rules         [{lane, regex}]  JD text -> the state.db Lane label, for the per-lane track record
  closed_lanes       {rule: {min_applied, max_positive}, action: advisory|hold}  computed from state.db outcomes
  priority_advisory  [substrings]     hard-check names that become advisory inside the priority lane (lanes.py)
Usage: <jobkit python> tools/critic.py <JobDescription.txt path | folder>   -> verdict + reasons
The agent MUST run this before building; overrides are allowed but logged in the build script."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sys, os, re, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, work_auth as _work_auth, exclusions as _exclusions, thresholds as _thresholds, critic_rules as _rules, targets as _targets   # JOBKIT
_R=_rules()

# ── GENERIC checks (every user; switched by settings.yaml flags) ───────────────────────────────────────────────────
_GENERIC=[
 ("INELIGIBLE: citizenship/clearance (per settings.yaml work_authorization flags; ITAR/export-control is a TAG, not this)",
  r"security clearance|secret clearance|TS/SCI|Top Secret|polygraph[^.\n]{0,40}(?:required|clearance)|(?:clearance|TS/SCI)[^.\n]{0,40}polygraph|active clearance|must be a U\.?S\.? citizen(?![^\n;]{0,100}(?:permanent resident|green card|u\.?s\.? person|lawful))|U\.?S\.? citizenship (is )?required(?![^\n;]{0,50}(?:or|/)\s*(?:a\s+)?(?:u\.?s\.?\s*)?(?:lawful\s+)?(?:permanent|green))|Only U\.S\. Citizens|(?:all )?(?:candidates|applicants|employees) must be u\.?s\.? citizens(?![^\n;]{0,100}(?:permanent resident|green card|u\.?s\.? person|lawful))|must be u\.?s\.? citizens\b(?![^\n;]{0,100}(?:permanent resident|green card|u\.?s\.? person|lawful))"),
 ("GRAD-GATE: New College Grad / campus req (closed to an experienced candidate)", r"new college grad|university grad|campus hire|class of 20\d\d"),
 ("CONTRACT-GIG: contract / 1099 / freelance / AI-training gig (settings.yaml exclusions.contract_work: false)",
  # 2026-10-16 port: a bare "1099" was a location/requisition code ("Remote (1099)", "US-NY-1099") as often as a tax form; it
  # counts only outside parentheses and with employment words next to it ("1099 contractor", "on a 1099 basis", "W2 or 1099")
  r"(?<![(\w-])1099(?![)\w-])(?=[^.\n]{0,30}\b(?:contract\w*|basis|position|role|worker|employ\w*|engagement)\b)|\b(?:W-?2|contract\w*|basis|as an?)\b[^.\n]{0,20}(?<![(\w-])1099(?![)\w-])|independent contractor|\bfreelance (?:role|position|contract|basis|opportunit\w+|engagement)|\bcontract (?:role|position|basis|opportunity|assignment|engagement)\b|contract-to-hire|\bAI (?:trainer|tutor)s?\b|expert (?:contributor|annotator)s?\b|paid per (?:task|hour)\b|this is a contract\b"),
 ("BELOW LEVEL: technician/HS tier", r"high school (degree|diploma)|(?<![a-zA-Z])GED(?![a-zA-Z])|\$\s?\d[\d.,]*\s*(?:/|per)\s*h(?:ou)?r\b|\bhourly (?:pay|wage|rate for this)|\bthis is an hourly\b|non-?exempt hourly"),
]
_WA=_work_auth(); _EX=_exclusions()
if _WA["citizenship_only_roles_open"] and _WA["clearance_possible"]: _GENERIC=[c for c in _GENERIC if not c[0].startswith("INELIGIBLE")]
if _EX["contract_work"]: _GENERIC=[c for c in _GENERIC if not c[0].startswith("CONTRACT-GIG")]
if _targets()["phd_positions"] or _targets()["new_grad_ok"]: _GENERIC=[c for c in _GENERIC if not c[0].startswith("GRAD-GATE")]   # v0.7: a new graduate's own target is never a gate
if _targets()["hourly_ok"]: _GENERIC=[c for c in _GENERIC if not c[0].startswith("BELOW LEVEL")]   # v0.2: technician / hourly posts are the target (settings.yaml targets.hourly_ok)   # 2026-10-09: graduate positions are the target (settings.yaml targets.phd_positions)
def _pairs(key):
    out=[]
    for d in (_R.get(key) or []):
        if isinstance(d,dict) and d.get("regex"): out.append((str(d.get("name") or d.get("key") or "RULE"),str(d["regex"])))
    return out
# user's hard checks FIRST (they are the field-specific ones), then the generic eligibility/level classes
CHECKS=_pairs("hard_checks")+_GENERIC
SOFT=_pairs("soft_flags")
_IO=_R.get("instrument_owner") or {}
INSTRUMENT_OWNER=(str(_IO.get("verbs") or r"(develop|validate|optimize|maintain|calibrat)\w*[^.]{0,80}(methods? for|techniques? for)?[^.]{0,80}"),
                  [str(x) for x in (_IO.get("instruments") or [])], int(_IO.get("min_named",4) or 4))
LANE_RULES=[(str(d.get("lane")),re.compile(str(d.get("regex")),re.I)) for d in (_R.get("lane_rules") or []) if isinstance(d,dict) and d.get("lane") and d.get("regex")]
_CL=_R.get("closed_lanes") or {}
_CL_RULE=_CL.get("rule") or {}
CLOSED_MIN_APPLIED=int(_CL_RULE.get("min_applied",5) or 5); CLOSED_MAX_POSITIVE=int(_CL_RULE.get("max_positive",0) or 0)
CLOSED_ACTION=str(_CL.get("action","advisory")).lower()
PRIORITY_ADVISORY=[str(x) for x in (_R.get("priority_advisory") or [])]

# ═══ LEVEL / BAND ADVISORY ═══ Prints an advisory (never a knockout) when the posted midpoint exceeds
# settings.yaml thresholds.band_midpoint_ceiling (null = off) or the title is senior-and-above. Whether that matters is
# a per-user, outcome-driven finding; see system/docs/EXAMPLES_FROM_ORIGINAL.md for how the original user derived his ceiling.
_CEIL=_thresholds()['band_midpoint_ceiling']
_BAND=re.compile(r"\$?\s?(\d{2,3})(?:,(\d{3})(?:\.\d\d)?|k)\s*(?:USD)?\s*(?:-|to|–|—)\s*\$?\s?(\d{2,3})(?:,(\d{3})(?:\.\d\d)?|k)(?![\d,])",re.I)
_SENIOR=re.compile(r"\b(senior|sr\.?|staff|principal|lead|distinguished|iii|iv|expert)\b",re.I)
def level_band(txt,title=""):
    """Advisory, never a knockout. Phone numbers do not parse as bands (tested)."""
    out=[]
    m=_BAND.search(txt or "")
    if m:
        lo=int(m.group(1)+(m.group(2) or "000")) if m.group(2) else int(m.group(1))*1000
        hi=int(m.group(3)+(m.group(4) or "000")) if m.group(4) else int(m.group(3))*1000
        if 40000<lo<hi<900000:
            mid=(lo+hi)//2
            if _CEIL and mid>int(_CEIL):
                out.append(f"LEVEL/BAND: posted midpoint ${mid:,} is above the user's ceiling ${int(_CEIL):,}. Apply only as a deliberate stretch.")
            elif _CEIL:
                out.append(f"LEVEL/BAND OK: posted midpoint ${mid:,} is at or below the user's ceiling ${int(_CEIL):,}.")
    if _SENIOR.search(title or ""):
        out.append("LEVEL/BAND: senior/staff/principal-titled req - check the years bar is answerable from the user's tenure line before building.")
    return out

def lane_of(txt):
    """The state.db Lane label this JD belongs to, by critic_rules.yaml lane_rules (first match wins; None if none)."""
    for lane,rx in LANE_RULES:
        if rx.search(txt): return lane
    return None
def lane_stats(lane):
    db=os.path.join(ROOT,"tracking","state.db")
    if not os.path.exists(db) or not lane: return None
    c=sqlite3.connect(db)
    try:
        n,pos,neg=c.execute("""SELECT COUNT(*),SUM(Status IN ('interviewing','advanced','closed')),
            SUM(Status='rejected') FROM applications WHERE Lane=?""",(lane,)).fetchone()
    except sqlite3.Error: return None
    return (n or 0,pos or 0,neg or 0)
def closed_lanes():
    """Lanes the outcomes say are CLOSED: >= min_applied applications with <= max_positive positive responses.
    Computed from state.db every time; never hard-coded."""
    db=os.path.join(ROOT,"tracking","state.db")
    if not os.path.exists(db): return {}
    c=sqlite3.connect(db); out={}
    try:
        for lane,n,pos,neg in c.execute("""SELECT Lane,COUNT(*),SUM(Status IN ('interviewing','advanced','closed')),
                SUM(Status='rejected') FROM applications WHERE Lane<>'' GROUP BY Lane"""):
            if (n or 0)>=CLOSED_MIN_APPLIED and (pos or 0)<=CLOSED_MAX_POSITIVE: out[lane]=(n or 0,pos or 0,neg or 0)
    except sqlite3.Error: pass
    return out
def lane_history(txt):
    lane=lane_of(txt)
    st=lane_stats(lane)
    if not st: return None
    n,pos,neg=st
    return f"lane '{lane}' track record: {n} applied, +{pos}/-{neg}"
def review(path):
    if os.path.isdir(path):
        for cand in ("JobDescription.txt","JobDescription_FULL.txt","job-description.md","JD.txt"):
            fp=os.path.join(path,cand)
            if os.path.exists(fp): path=fp; break
        else:
            print(f"CRITIC: no JD file found in {path}"); return 99
    t=open(path,encoding='utf-8',errors='ignore').read()
    # the critic must read the POSTING, not aggregator page chrome (Adzuna footers trip CONTRACT-GIG)
    try:
        from match import strip_aggregator as _strip
        t=_strip(t)
    except Exception:
        pass
    flags=[]
    # Some JDs carry a clearance sentence AND an explicit "Green Card holders ... are eligible to apply" line. The
    # employer's own eligibility statement is the stronger signal: the citizenship/clearance flag is DOWNGRADED to
    # advisory so a human decides.
    _PR_OK=re.compile(r"(green[- ]card holders?[^.\n]{0,60}(are )?eligible|permanent residents?[^.\n]{0,40}(are )?eligible to apply|U\.?S\.? persons?\s*\(i\.e\.[^)]*permanent resident)",re.I)
    _pr_welcomed=bool(_PR_OK.search(t))
    # conditional boilerplate ("may be contingent upon your ability to obtain ... clearance") is not a requirement
    _NEG=re.compile(r"\b(no|none|not|never|without|n/?a|may be contingent|contingent upon|if and when|may require|could require|some (roles|positions)|certain (roles|positions))\b",re.I)
    for name,pat in CHECKS:
        # skip NEGATED matches ("Security Clearance: None required", "no clearance is required") - but only a negation in
        # the SAME sentence within 60 characters before / 40 after counts (audit v0.4 bug 12: a 130-character window let
        # "No security clearance required." cancel "$22/hour" two sentences later)
        m=None
        for _m in re.finditer(pat,t,re.I):
            _pre=t[max(0,_m.start()-60):_m.start()]; _pre=re.split(r"[.;\n]",_pre)[-1]
            _post=t[_m.end():_m.end()+40]; _post=re.split(r"[.;\n]",_post)[0]
            if not _NEG.search(_pre+" | "+_post): m=_m; break
        if m:
            if _pr_welcomed and name.startswith("INELIGIBLE"):
                flags.append(("ELIGIBILITY-CONFLICT (advisory, NOT a knockout): JD names a clearance BUT also states permanent residents may apply - human call",m.group(0)[:70]))
            else:
                flags.append((name,m.group(0)[:70]))
    verb,instr,min_named=INSTRUMENT_OWNER
    named=[i for i in instr if re.search(rf"\b{re.escape(i)}\b",t)]
    if instr and len(named)>=min_named and re.search(verb+r"("+"|".join(re.escape(x) for x in named[:6])+")",t,re.I):
        flags.append((f"INSTRUMENT-OWNER PROFILE: {len(named)} un-operated instruments with method-development verbs",", ".join(named[:6])))
    # closed lanes computed from outcomes (critic_rules.yaml closed_lanes.rule); action advisory (default) or hold
    _lane=lane_of(t); _closed=closed_lanes(); _closed_note=None
    if _lane and _lane in _closed:
        n,pos,neg=_closed[_lane]
        _msg=f"CLOSED-LANE (computed from state.db): lane '{_lane}' has {n} applied, +{pos}/-{neg} - rule >= {CLOSED_MIN_APPLIED} applied with <= {CLOSED_MAX_POSITIVE} positive"
        if CLOSED_ACTION=="hold": flags.append((_msg,_lane))
        else: _closed_note=_msg
    softs=[(n,re.search(p2,t,re.I).group(0)[:50]) for n,p2 in SOFT if re.search(p2,t,re.I) and not any(n2==n for n2,_ in flags)]
    hist=lane_history(t)
    _title=t.split("\n")[0][:120] if t else ""
    _lb=level_band(t,_title)
    print(f"CRITIC REVIEW: {os.path.basename(os.path.dirname(os.path.abspath(path)))}")
    for _m in _lb:
        print(("  [WARN] " if _m.startswith("LEVEL/BAND:") else "  [OK] ")+_m)
    if not flags:
        print("  [OK] NO RED FLAGS - proceed to build. (Critic checks knockouts, not fit quality.)")
    else:
        try:
            from lanes import is_priority as _LANE
            _lane_hit = _LANE(_title, t)
        except Exception:
            _lane_hit = False
        if _lane_hit and PRIORITY_ADVISORY:
            _soft = [f for f in flags if any(s in f[0] for s in PRIORITY_ADVISORY)]
            if _soft and len(_soft) == len(flags):
                print("  [LANE] PRIORITY LANE (user-declared target lane; tools/lanes.py).")
                print("    The flags below are ADVISORY in this lane (critic_rules.yaml priority_advisory).")
                print("    Verdict: PROCEED, claiming only what approved_claims.yaml allows. Flags:")
                for n, m in flags:
                    print(f"      - {n}: {m}")
                if _closed_note: print(f"  [WARN] {_closed_note}")
                return flags
            if _soft:
                print("  [LANE] PRIORITY LANE: the advisory-class flags below weigh less; weigh the others.")
        print(f"  [HOLD] {len(flags)} FLAG(S) - verdict: HOLD unless explicitly overridden (log the override):")
        for n,ev in flags: print(f"   - {n}\n       evidence: \"{ev}\"")
    for n,ev in softs: print(f"  [WARN] {n} - \"{ev}\"")
    if _closed_note: print(f"  [WARN] {_closed_note}")
    if hist: print(f"  [STATS] {hist}")
    return len(flags)
if __name__=="__main__":
    sys.exit(0 if review(sys.argv[1])==0 else 1)
