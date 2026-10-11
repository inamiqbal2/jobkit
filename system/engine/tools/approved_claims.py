#!/usr/bin/env python3
"""APPROVED CLAIMS - loader for My Job Search/profile/approved_claims.yaml (jobkit refactor 2026-10-08).

The original module was a hand-written Python file of one person's constants (experience tuples,
bullet strings, skills lines, publication line, forbidden terms). In jobkit the SAME content is DATA
the user owns: profile/approved_claims.yaml (see My Job Search/profile/approved_claims.yaml.example).

Back-compat: build scripts do `from approved_claims import <ENTRY_KEY>, <BULLET_NAME>, PUBS, ...`.
This module re-creates those names from the YAML so existing build-script patterns keep working:
  - experience[].key          -> module global <KEY> = (org, dates, role, loc)
  - experience[].bullets      -> module global <BULLET_NAME> = text   and  <KEY>_BULLETS = [texts]
  - skills_lines.<LABEL>      -> module global <LABEL> = (label, text)
  - publications.line / short -> PUBS, PUBS_SHORT
  - tenure.line / short       -> TENURE, TENURE_SHORT
  - projects.<key>            -> PROJECTS[key] = (title, bullet)
  - entry_variants.<NAME>     -> <NAME> = (org, dates, role, loc)   (same employer, different title read)
  - bullet_bank.<NAME>        -> <NAME> = text                      (approved bullets not tied to one entry)
  - constants.<NAME>          -> <NAME> = text or (label, text)     (approved phrasings)
  - never_claims.forbidden_terms -> FORBIDDEN
Everything is also reachable as CLAIMS (the raw dict). Nothing here is person-specific.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import APPROVED_CLAIMS_YAML, load_yaml, work_auth

CLAIMS = load_yaml(APPROVED_CLAIMS_YAML, default={}) or {}

# ---- experience entries --------------------------------------------------------------------
EXPERIENCE = []            # list of dicts as in the YAML (key, org, dates, role, loc, bullets, ...)
ENTRY = {}                 # key -> (org, dates, role, loc)
BULLETS = {}               # bullet name -> text   (global namespace of named bullets)
FROZEN = {}                # org heading -> [approved bullet texts]  (audit: every bullet under that heading must match)
for _e in CLAIMS.get("experience", []) or []:
    _k = str(_e.get("key", "")).strip()
    if not _k:
        continue
    EXPERIENCE.append(_e)
    ENTRY[_k] = (_e.get("org", ""), _e.get("dates", ""), _e.get("role", ""), _e.get("loc", ""))
    globals()[_k] = ENTRY[_k]
    _bl = _e.get("bullets", {}) or {}
    if isinstance(_bl, dict):
        _texts = []
        for _bn, _bt in _bl.items():
            BULLETS[str(_bn)] = str(_bt)
            globals()[str(_bn)] = str(_bt)
            _texts.append(str(_bt))
    else:
        _texts = [str(x) for x in _bl]
    globals()[f"{_k}_BULLETS"] = _texts
    if _e.get("frozen"):
        FROZEN[_e.get("org", "")] = list(_texts)

# ---- optional extras: entry variants, a free bullet bank, named text constants ----------------
# entry_variants: {NAME: {base: KEY, role: "...", org/dates/loc overrides}} -> module global NAME = (org, dates, role, loc)
#   (e.g. the same employer with a different title read on engineer reqs; same facts, same dates)
ENTRY_VARIANTS = {}
for _vn, _vv in (CLAIMS.get("entry_variants", {}) or {}).items():
    _vv = _vv or {}
    _base = ENTRY.get(str(_vv.get("base", "")), ("", "", "", ""))
    ENTRY_VARIANTS[str(_vn)] = (str(_vv.get("org", _base[0])), str(_vv.get("dates", _base[1])), str(_vv.get("role", _base[2])), str(_vv.get("loc", _base[3])))
    globals()[str(_vn)] = ENTRY_VARIANTS[str(_vn)]
# bullet_bank: {NAME: text} -> approved bullets not tied to one entry (dissertation / publication bullets)
for _bn, _bt in (CLAIMS.get("bullet_bank", {}) or {}).items():
    BULLETS[str(_bn)] = str(_bt)
    globals()[str(_bn)] = str(_bt)
# constants: {NAME: text | [label, text]} -> approved text snippets (coursework/teaching phrasings, instrument models)
CONSTANTS = {}
for _cn, _cv in (CLAIMS.get("constants", {}) or {}).items():
    CONSTANTS[str(_cn)] = tuple(str(x) for x in _cv) if isinstance(_cv, (list, tuple)) else str(_cv)
    globals()[str(_cn)] = CONSTANTS[str(_cn)]

# ---- skills lines, publications, tenure, projects --------------------------------------------
SKILLS_LINES = {}
for _lab, _val in (CLAIMS.get("skills_lines", {}) or {}).items():
    if isinstance(_val, (list, tuple)) and len(_val) == 2:
        SKILLS_LINES[_lab] = (str(_val[0]), str(_val[1]))
    else:
        SKILLS_LINES[_lab] = (str(_lab), str(_val))
    globals()[str(_lab)] = SKILLS_LINES[_lab]

_pubs = CLAIMS.get("publications", {}) or {}
PUBS = ("Publications", str(_pubs.get("line", ""))) if _pubs.get("line") else None
PUBS_SHORT = ("Publications", str(_pubs.get("short", _pubs.get("line", "")))) if _pubs.get("line") or _pubs.get("short") else None
PUB_COUNTS = _pubs.get("counts", {}) or {}

_ten = CLAIMS.get("tenure", {}) or {}
TENURE = str(_ten.get("line", "")) if _ten.get("line") else None
TENURE_SHORT = str(_ten.get("short", _ten.get("line", ""))) if _ten.get("short") or _ten.get("line") else None
TENURE_YEARS = _ten.get("years")

PROJECTS = {}
for _pk, _pv in (CLAIMS.get("projects", {}) or {}).items():
    if isinstance(_pv, dict):
        PROJECTS[_pk] = (str(_pv.get("title", _pk)), str(_pv.get("bullet", "")))
    elif isinstance(_pv, (list, tuple)) and len(_pv) == 2:
        PROJECTS[_pk] = (str(_pv[0]), str(_pv[1]))

SUMMARIES = CLAIMS.get("summaries", {}) or {}

# ---- academic CV sections (2026-10-09; optional `cv:` block, see approved_claims.yaml.example) ----------------
# Every item is confirmed text the CV may print verbatim. Items may be strings or dicts; dict items carry `evidence`.
#   cv.education[]        {institution, dates, degree, loc, details[]}   (the CV's own education block; settings.yaml
#                                                                        education is the one-page resume's)
#   cv.publications[]     str | {citation, status, evidence}             printed as given (numbered, newest first)
#   cv.presentations[]    str | {text, evidence}
#   cv.field_experience[] {title, org, dates, loc, bullets[], evidence}  expeditions, cruises, field seasons
#   cv.certifications[]   str | {text, evidence}                         diving / boat / first-aid / permits
#   cv.technical_skills   {LABEL: text}                                  (skills_lines is used when absent)
#   cv.teaching[]         str | {org, dates, role, loc, bullets[]}
#   cv.grants_awards[]    str | {text, evidence}
#   cv.service[]          str | {text, evidence}
#   cv.references         str (e.g. "Available upon request") | [str]
# experience[].section   optional: research | professional | field | teaching -> AcademicCV groups entries by it
def _cv_text(x, *keys):
    if isinstance(x, dict):
        for k in keys:
            if x.get(k): return str(x[k])
        return ""
    return str(x) if x is not None else ""
CV = CLAIMS.get("cv", {}) or {}
CV_EDUCATION = [e for e in (CV.get("education", []) or []) if isinstance(e, dict)]
CV_PUBLICATIONS = [_cv_text(x, "citation", "text") for x in (CV.get("publications", []) or [])]
CV_PRESENTATIONS = [_cv_text(x, "text", "citation") for x in (CV.get("presentations", []) or [])]
CV_FIELD = [e for e in (CV.get("field_experience", []) or []) if isinstance(e, dict)]
CV_CERTIFICATIONS = [_cv_text(x, "text") for x in (CV.get("certifications", []) or [])]
CV_SKILLS = {str(k): (tuple(str(x) for x in v) if isinstance(v, (list, tuple)) else (str(k), str(v)))
             for k, v in (CV.get("technical_skills", {}) or {}).items()} or dict(SKILLS_LINES)
CV_TEACHING = list(CV.get("teaching", []) or [])
CV_GRANTS = [_cv_text(x, "text") for x in (CV.get("grants_awards", []) or [])]
CV_SERVICE = [_cv_text(x, "text") for x in (CV.get("service", []) or [])]
CV_REFERENCES = CV.get("references", "Available upon request")
EXPERIENCE_BY_SECTION = {}
for _e in EXPERIENCE:
    EXPERIENCE_BY_SECTION.setdefault(str(_e.get("section", "research")).lower(), []).append(_e)


def approved_texts():
    """EVERY string the YAML approves, normalized - the audit's traceability set for CV mode (audit_claims)."""
    out = set()
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("evidence", "nda", "keywords", "question", "pending", "retired_claims", "never_claims",
                         "hedged_phrases", "banned_words", "consistency_items", "status", "key", "base", "kind", "match"):
                    continue
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o: walk(v)
        elif isinstance(o, str):
            out.add(o)
    walk({k: v for k, v in CLAIMS.items() if k not in ("pending", "retired_claims", "never_claims", "consistency_items")})
    for lab, (l, t) in {**SKILLS_LINES, **CV_SKILLS}.items():
        out.add(f"{l} : {t}"); out.add(f"{l}: {t}")
    return {_norm(x) for x in out if x}


def _norm(t):
    import re as _re
    return _re.sub(r"\s+", " ", str(t or "").replace("\u2022", " ").replace("\t", " ")).strip().lower()


# ---- claim boundaries ----------------------------------------------------------------------
_nc = CLAIMS.get("never_claims", {}) or {}
FORBIDDEN = [str(x) for x in (_nc.get("forbidden_terms", []) or [])]
OPERATOR_PATTERNS = [str(x) for x in (_nc.get("operator_patterns", []) or [])]
RETIRED = [str(x) for x in (CLAIMS.get("retired_claims", []) or [])]
BANNED_WORDS = [str(x) for x in (CLAIMS.get("banned_words", ["local"]) or [])]
HEDGED_PHRASES = [str(x) for x in (CLAIMS.get("hedged_phrases", []) or [])]
CONSISTENCY_ITEMS = CLAIMS.get("consistency_items", []) or []
PENDING = CLAIMS.get("pending", []) or []
WORK_AUTH_LINE = work_auth()["resume_line"]


def loaded():
    """True when a real approved_claims.yaml is present (the engine refuses to build without one)."""
    return bool(CLAIMS)


def audit(path):
    """Fail loudly if a built resume contains a forbidden claim. Delegates to audit_claims.check
    (never/retired/operator/frozen/work-auth/banned-word checks) and returns its problem list."""
    try:
        import audit_claims as _strict
        return _strict.check(path)
    except Exception as _e:
        return [f"strict audit unavailable: {_e}"]


if __name__ == "__main__":
    print("approved_claims.yaml:", APPROVED_CLAIMS_YAML, "(loaded)" if loaded() else "(MISSING - run onboarding)")
    print("experience keys:", list(ENTRY))
    print("named bullets:", len(BULLETS), "| frozen entries:", list(FROZEN))
    print("skills lines:", list(SKILLS_LINES))
    print("PUBS:", PUBS)
    print("FORBIDDEN:", FORBIDDEN)
    print("RETIRED patterns:", len(RETIRED), "| pending (unusable):", len(PENDING))
    if CV: print("cv sections:", {k: (len(v) if isinstance(v, (list, dict)) else 1) for k, v in CV.items()})
