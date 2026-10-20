#!/usr/bin/env python3
"""CLAIMS LOADER - reads and validates My Job Search/profile/approved_claims.yaml on demand (v1.0, audit M26).

Until v0.9 this code lived at the top level of approved_claims.py and ran AT IMPORT: importing the module read the
YAML, built every derived table and ran the reserved-name check, so a build script, the audit, the consistency check
and the keyword tool all paid for (and could crash on) a file read the moment they were imported, and
approved_claims.audit() -> audit_claims -> approved_claims closed an import cycle. Now:

  load()        parses the YAML ONCE (module-level cache) and returns a Claims object; a missing file gives an EMPTY
                Claims whose loaded() is False and whose missing_sentence() says what to do - never a traceback.
  reload()      drops the cache (tests; onboarding after it writes the file).
  Claims        every derived table the engine used to find as a module global (EXPERIENCE, ENTRY, BULLETS, FROZEN,
                SKILLS_LINES, PUBS, TENURE*, PROJECTS, SUMMARIES, CV_*, FORBIDDEN, ... WORK_AUTH_LINE) plus
                .exports (the person's own names: entry keys, bullet names, constants, skills labels).

Dependency order: userconfig < claims_loader < approved_claims (back-compat facade) < audit_claims. This module imports
nothing above userconfig, so audit_claims can import it directly and no cycle remains. Nothing here is person-specific.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import APPROVED_CLAIMS_YAML, load_yaml, work_auth


class ReservedClaimName(ValueError):
    """A bullet / entry / constant in approved_claims.yaml uses a name the engine needs for itself."""


# v0.8 (code audit M8): the whitelist is built from the keys that HOLD approved wording, never from "everything in the file".
_APPROVED_KEYS = ("summaries", "tenure", "experience", "entry_variants", "bullet_bank", "constants", "skills_lines",
                  "publications", "projects", "cv")
_TEXT_FIELDS = ("org", "dates", "role", "loc", "bullets", "line", "short", "title", "bullet", "text", "citation",
                "institution", "degree", "section_titles", "education", "publications", "presentations", "field_experience",
                "certifications", "skills", "teaching", "grants_awards", "service", "references")

# The engine's own attribute names on a Claims object. A YAML name may not shadow any of these (v0.8 H7), and the
# approved_claims facade resolves exactly these (plus .exports) through its module __getattr__.
DATA_NAMES = ("CLAIMS", "EXPERIENCE", "ENTRY", "BULLETS", "FROZEN", "ENTRY_VARIANTS", "CONSTANTS", "SKILLS_LINES",
              "PUBS", "PUBS_SHORT", "PUB_COUNTS", "TENURE", "TENURE_SHORT", "TENURE_YEARS", "PROJECTS", "SUMMARIES",
              "CV", "CV_EDUCATION", "CV_PUBLICATIONS", "CV_PRESENTATIONS", "CV_FIELD", "CV_CERTIFICATIONS", "CV_SKILLS",
              "CV_TEACHING", "CV_GRANTS", "CV_SERVICE", "CV_REFERENCES", "EXPERIENCE_BY_SECTION",
              "FORBIDDEN", "OPERATOR_PATTERNS", "RETIRED", "BANNED_WORDS", "HEDGED_PHRASES", "CONSISTENCY_ITEMS",
              "PENDING", "WORK_AUTH_LINE")

# Names a YAML key may never take: the engine's data names, the facade's own public names, builtins and keywords.
# v1.0 (audit M26): this set is fixed here instead of being read off approved_claims' globals() at the end of loading, so the
# check gives the same answer whichever module triggers the load.
_ENGINE_NAMES = frozenset(DATA_NAMES) | {
    "ReservedClaimName", "Claims", "load", "reload", "loaded", "audit", "approved_texts", "DATA_NAMES",
    "APPROVED_CLAIMS_YAML", "load_yaml", "work_auth", "os", "re", "sys", "_sys0", "_cl", "_norm", "_cv_text",
    "_APPROVED_KEYS", "_TEXT_FIELDS", "_ENGINE_NAMES", "_CACHE"}


def _norm(t):
    return re.sub(r"\s+", " ", str(t or "").replace("•", " ").replace("\t", " ")).strip().lower()


def _cv_text(x, *keys):
    if isinstance(x, dict):
        for k in keys:
            if x.get(k): return str(x[k])
        return ""
    return str(x) if x is not None else ""


class Claims:
    """Everything approved_claims.yaml says, as the engine's tables. Built by load(); never construct one by hand
    except in tests (Claims({}) is the 'file missing' state)."""

    def __init__(self, raw, path=APPROVED_CLAIMS_YAML):
        self.path = path
        self.CLAIMS = raw or {}
        c = self.CLAIMS
        # v0.8 (code audit H7): the person's own names (entry keys, bullet names, constants, skills labels) are collected here
        # and handed out only after a check that none collides with the engine's names.
        self.exports = {}

        # ---- experience entries ----------------------------------------------------------------
        self.EXPERIENCE = []            # list of dicts as in the YAML (key, org, dates, role, loc, bullets, ...)
        self.ENTRY = {}                 # key -> (org, dates, role, loc)
        self.BULLETS = {}               # bullet name -> text   (global namespace of named bullets)
        self.FROZEN = {}                # org heading -> [approved bullet texts]  (audit: every bullet under that heading must match)
        for e in c.get("experience", []) or []:
            k = str(e.get("key", "")).strip()
            if not k:
                continue
            self.EXPERIENCE.append(e)
            self.ENTRY[k] = (e.get("org", ""), e.get("dates", ""), e.get("role", ""), e.get("loc", ""))
            self.exports[k] = self.ENTRY[k]
            bl = e.get("bullets", {}) or {}
            if isinstance(bl, dict):
                texts = []
                for bn, bt in bl.items():
                    self.BULLETS[str(bn)] = str(bt)
                    self.exports[str(bn)] = str(bt)
                    texts.append(str(bt))
            else:
                texts = [str(x) for x in bl]
            self.exports[f"{k}_BULLETS"] = texts
            if e.get("frozen"):
                self.FROZEN[e.get("org", "")] = list(texts)

        # ---- optional extras: entry variants, a free bullet bank, named text constants ------------
        # entry_variants: {NAME: {base: KEY, role: "...", org/dates/loc overrides}} -> NAME = (org, dates, role, loc)
        #   (e.g. the same employer with a different title read on engineer reqs; same facts, same dates)
        self.ENTRY_VARIANTS = {}
        for vn, vv in (c.get("entry_variants", {}) or {}).items():
            vv = vv or {}
            base = self.ENTRY.get(str(vv.get("base", "")), ("", "", "", ""))
            self.ENTRY_VARIANTS[str(vn)] = (str(vv.get("org", base[0])), str(vv.get("dates", base[1])), str(vv.get("role", base[2])), str(vv.get("loc", base[3])))
            self.exports[str(vn)] = self.ENTRY_VARIANTS[str(vn)]
        # bullet_bank: {NAME: text} -> approved bullets not tied to one entry (dissertation / publication bullets)
        for bn, bt in (c.get("bullet_bank", {}) or {}).items():
            self.BULLETS[str(bn)] = str(bt)
            self.exports[str(bn)] = str(bt)
        # constants: {NAME: text | [label, text]} -> approved text snippets (coursework/teaching phrasings, instrument models)
        self.CONSTANTS = {}
        for cn, cv in (c.get("constants", {}) or {}).items():
            self.CONSTANTS[str(cn)] = tuple(str(x) for x in cv) if isinstance(cv, (list, tuple)) else str(cv)
            self.exports[str(cn)] = self.CONSTANTS[str(cn)]

        # ---- skills lines, publications, tenure, projects ----------------------------------------
        self.SKILLS_LINES = {}
        for lab, val in (c.get("skills_lines", {}) or {}).items():
            if isinstance(val, (list, tuple)) and len(val) == 2:
                self.SKILLS_LINES[lab] = (str(val[0]), str(val[1]))
            else:
                self.SKILLS_LINES[lab] = (str(lab), str(val))
            self.exports[str(lab)] = self.SKILLS_LINES[lab]

        pubs = c.get("publications", {}) or {}
        self.PUBS = ("Publications", str(pubs.get("line", ""))) if pubs.get("line") else None
        self.PUBS_SHORT = ("Publications", str(pubs.get("short", pubs.get("line", "")))) if pubs.get("line") or pubs.get("short") else None
        self.PUB_COUNTS = pubs.get("counts", {}) or {}

        ten = c.get("tenure", {}) or {}
        self.TENURE = str(ten.get("line", "")) if ten.get("line") else None
        self.TENURE_SHORT = str(ten.get("short", ten.get("line", ""))) if ten.get("short") or ten.get("line") else None
        self.TENURE_YEARS = ten.get("years")

        self.PROJECTS = {}
        for pk, pv in (c.get("projects", {}) or {}).items():
            if isinstance(pv, dict):
                self.PROJECTS[pk] = (str(pv.get("title", pk)), str(pv.get("bullet", "")))
            elif isinstance(pv, (list, tuple)) and len(pv) == 2:
                self.PROJECTS[pk] = (str(pv[0]), str(pv[1]))

        self.SUMMARIES = c.get("summaries", {}) or {}

        # ---- academic CV sections (2026-10-09; optional `cv:` block, see approved_claims.yaml.example) ----------
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
        cv = c.get("cv", {}) or {}
        self.CV = cv
        self.CV_EDUCATION = [e for e in (cv.get("education", []) or []) if isinstance(e, dict)]
        self.CV_PUBLICATIONS = [_cv_text(x, "citation", "text") for x in (cv.get("publications", []) or [])]
        self.CV_PRESENTATIONS = [_cv_text(x, "text", "citation") for x in (cv.get("presentations", []) or [])]
        self.CV_FIELD = [e for e in (cv.get("field_experience", []) or []) if isinstance(e, dict)]
        self.CV_CERTIFICATIONS = [_cv_text(x, "text") for x in (cv.get("certifications", []) or [])]
        self.CV_SKILLS = {str(k): (tuple(str(x) for x in v) if isinstance(v, (list, tuple)) else (str(k), str(v)))
                          for k, v in (cv.get("technical_skills", {}) or {}).items()} or dict(self.SKILLS_LINES)
        self.CV_TEACHING = list(cv.get("teaching", []) or [])
        self.CV_GRANTS = [_cv_text(x, "text") for x in (cv.get("grants_awards", []) or [])]
        self.CV_SERVICE = [_cv_text(x, "text") for x in (cv.get("service", []) or [])]
        self.CV_REFERENCES = cv.get("references", "Available upon request")
        self.EXPERIENCE_BY_SECTION = {}
        for e in self.EXPERIENCE:
            self.EXPERIENCE_BY_SECTION.setdefault(str(e.get("section", "research")).lower(), []).append(e)

        # ---- claim boundaries --------------------------------------------------------------------
        nc = c.get("never_claims", {}) or {}
        self.FORBIDDEN = [str(x) for x in (nc.get("forbidden_terms", []) or [])]
        self.OPERATOR_PATTERNS = [str(x) for x in (nc.get("operator_patterns", []) or [])]
        self.RETIRED = [str(x) for x in (c.get("retired_claims", []) or [])]
        self.BANNED_WORDS = [str(x) for x in (c.get("banned_words", ["local"]) or [])]
        self.HEDGED_PHRASES = [str(x) for x in (c.get("hedged_phrases", []) or [])]
        self.CONSISTENCY_ITEMS = c.get("consistency_items", []) or []
        self.PENDING = c.get("pending", []) or []
        self.WORK_AUTH_LINE = work_auth()["resume_line"]

        self._check_names()

    def _check_names(self):
        """v0.8 (code audit H7): a YAML name that collides with an engine name, a builtin or a keyword is refused with a
        clear error, never a crash or a silent swap. Same wording as before v1.0; now raised from load(), not from import."""
        import builtins, keyword
        taken = _ENGINE_NAMES | set(dir(builtins)) | set(keyword.kwlist)
        bad = sorted(k for k in self.exports if k in taken or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k))
        if bad:
            raise ReservedClaimName(f"profile/approved_claims.yaml uses reserved or invalid names: {bad}. Rename these bullets / keys "
                                    "(e.g. B_ERMC_CARE, ERMC); names like EXPERIENCE, SUMMARIES, FORBIDDEN, PUBS belong to the engine.")

    def loaded(self):
        """True when a real approved_claims.yaml is present (the engine refuses to build without one)."""
        return bool(self.CLAIMS)

    def missing_sentence(self):
        """The plain sentence a tool prints when loaded() is False."""
        return (f"profile/approved_claims.yaml is missing (looked at {self.path}) - nothing can be built or audited; "
                "run onboarding first, or point JOBKIT_WORKSPACE at your 'My Job Search' folder.")

    def approved_texts(self):
        """EVERY string the YAML approves, normalized - the audit's traceability set (audit_claims)."""
        out = set()
        def walk(o, allow_all=False):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("evidence", "nda", "keywords", "question", "status", "key", "base", "kind", "match", "counts", "years"):
                        continue
                    if allow_all or k in _TEXT_FIELDS or k in _APPROVED_KEYS:
                        walk(v, allow_all=True)
            elif isinstance(o, (list, tuple)):
                for v in o: walk(v, allow_all)
            elif isinstance(o, str):
                out.add(o)
        walk({k: v for k, v in self.CLAIMS.items() if k in _APPROVED_KEYS})
        for lab, (l, t) in {**self.SKILLS_LINES, **self.CV_SKILLS}.items():
            out.add(f"{l} : {t}"); out.add(f"{l}: {t}")
        return {_norm(x) for x in out if x}


_CACHE = {}   # {"claims": Claims} once load() has run; a dict so reload() can empty it without `global`


def load():
    """The parsed, validated approved_claims.yaml (read once per process). Raises ReservedClaimName (and nothing else of
    the engine's own) when a YAML name collides with an engine name; a MISSING file is not an error here - the returned
    Claims has loaded() False and consumers decide (the audit prints a FAIL sentence, the builders refuse)."""
    c = _CACHE.get("claims")
    if c is None:
        c = Claims(load_yaml(APPROVED_CLAIMS_YAML, default={}) or {})
        _CACHE["claims"] = c
    return c


def reload():
    """Forget the cached Claims so the next load() re-reads the file (tests; onboarding right after writing the YAML)."""
    _CACHE.clear()
    return load()
