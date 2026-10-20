#!/usr/bin/env python3
"""USERCONFIG - the one place the engine learns who it is working for.

Every person-specific fact (name, contact, work authorization, geography, lanes, thresholds,
exclusions, module switches) lives in the WORKSPACE (the person's `My Job Search/` folder), never in
engine code. This module resolves the workspace path and parses settings.yaml. Engine tools import
from here instead of hard-coding.

Layout (v0.4):
  <jobkit>/My Job Search/        the person's area = the workspace (settings.yaml, keys.json, my-rules.md,
                                 profile/, intake/, applications/, reports/, tracking/, tracker.csv)
  <jobkit>/system/engine/        this code (locked after install; see setup.py --lock)
  <jobkit>/system/.venv/         the Python environment setup.py creates

Workspace resolution (first match wins):
  1. $JOBKIT_WORKSPACE            (absolute path to the workspace folder)
  2. <jobkit>/My Job Search       (the default: ../My Job Search relative to system/engine)

settings.yaml may also be supplied as settings.json (same keys) when PyYAML is not installed. Folders made
by v0.3 (user.yaml / secrets.json / charters/user-rules.md) are still read when the new names are absent.

Usage:
  from userconfig import WS, load, get, path
  cfg = load()                       # dict (cached)
  get("identity.name", "")           # dotted lookup with default
  path("tracking", "state.db")       # absolute path inside the workspace
  MODULES["inbox_sweep"]             # False by default
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, sys, json, functools

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # <jobkit>/system/engine
SYSTEM = os.path.dirname(ENGINE)                                                # <jobkit>/system
JOBKIT = os.path.dirname(SYSTEM)                                                # <jobkit>
TOOLS = os.path.join(ENGINE, "tools")
WORKSPACE_NAME = "My Job Search"
WS = os.environ.get("JOBKIT_WORKSPACE") or os.path.join(JOBKIT, WORKSPACE_NAME)
WS = os.path.abspath(WS)
VENV = os.path.join(SYSTEM, ".venv")
VENV_PYTHON = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")

# Canonical workspace sub-paths. Tools build every data path from these, never from ROOT/tracking.
TRACKING = os.path.join(WS, "tracking")
PROFILE = os.path.join(WS, "profile")
EVIDENCE = os.path.join(PROFILE, "evidence")
APPLICATIONS = os.path.join(WS, "applications")
REPORTS = os.path.join(WS, "reports")
INTAKE = os.path.join(WS, "intake")                      # v0.4: the person's own documents (read-only for the engine)
INTAKE_EXTRACTED = os.path.join(INTAKE, "_extracted")    # intake.py writes the extracted text here
REGISTRIES = os.path.join(TRACKING, "registries")
JDS = os.path.join(TRACKING, "jds")
RUBRIC_DIR = os.path.join(TRACKING, "rubric")
TRACKER_CSV = os.path.join(WS, "tracker.csv")            # v0.4: the plain-English application tracker (state.py tracker)
APPROVED_CLAIMS_YAML = os.path.join(PROFILE, "approved_claims.yaml")


def _first_existing(*cands):
    """The first path that exists, else the first candidate (the v0.4 name) so new files get the new name."""
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[0]


SECRETS = _first_existing(os.path.join(WS, "keys.json"), os.path.join(WS, "secrets.json"))
USER_YAML = _first_existing(os.path.join(WS, "settings.yaml"), os.path.join(WS, "user.yaml"))
USER_JSON = _first_existing(os.path.join(WS, "settings.json"), os.path.join(WS, "user.json"))
USER_RULES = _first_existing(os.path.join(WS, "my-rules.md"), os.path.join(WS, "charters", "user-rules.md"))


def path(*parts):
    """Absolute path inside the workspace."""
    return os.path.join(WS, *parts)


def _read_yaml(p):
    try:
        import yaml  # PyYAML (requirements.txt)
    except ImportError as e:
        raise RuntimeError(
            f"PyYAML is not installed but {p} is YAML. Either `pip install pyyaml` or provide the same "
            f"content as {USER_JSON} (JSON)."
        ) from e
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@functools.lru_cache(maxsize=None)
def load():
    """Parsed settings.yaml (or user.json). Missing file -> {} so the engine can still be imported and
    py_compiled on a bare checkout; tools that NEED a field should call require()."""
    if os.path.exists(USER_YAML):
        return _read_yaml(USER_YAML)
    if os.path.exists(USER_JSON):
        with open(USER_JSON, encoding="utf-8") as f:
            return json.load(f) or {}
    return {}


def load_yaml(p, default=None):
    """Parse any workspace YAML/JSON data file (approved_claims.yaml, lexicon.yaml, ...)."""
    if not os.path.exists(p):
        return {} if default is None else default
    if p.endswith(".json"):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return _read_yaml(p)


def get(dotted, default=None):
    """get('identity.email') -> value or default."""
    cur = load()
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def require(dotted):
    v = get(dotted, None)
    if v in (None, ""):
        raise RuntimeError(f"settings.yaml is missing required field '{dotted}' (workspace: {WS}). "
                           f"Run the onboarding skill (system/engine/skills/onboarding/SKILL.md).")
    return v


def secrets():
    if not os.path.exists(SECRETS):
        return {}
    with open(SECRETS, encoding="utf-8") as f:
        return json.load(f)


# ---- Convenience views used by several tools ------------------------------------------------
def modules():
    m = get("modules", {}) or {}
    return {"inbox_sweep": bool(m.get("inbox_sweep", False)),
            "outreach": bool(m.get("outreach", False))}


MODULES = modules()


def work_auth():
    """Flags with safe defaults = the MOST restrictive reading (nothing is assumed open)."""
    w = get("work_authorization", {}) or {}
    return {
        "resume_line": w.get("resume_line", ""),
        "citizenship_only_roles_open": bool(w.get("citizenship_only_roles_open", False)),
        "clearance_possible": bool(w.get("clearance_possible", False)),
        "export_controlled_open": bool(w.get("export_controlled_open", False)),
        "sponsorship_needed": bool(w.get("sponsorship_needed", False)),
        # optional: true when the user is a permanent resident, so gates that explicitly ADMIT permanent
        # residents ("citizens and green-card holders are eligible") are open even though citizenship_only is not
        "permanent_resident": bool(w.get("permanent_resident", False)),
    }


def lanes():
    return get("lanes", []) or []


def lane_names():
    return tuple(l.get("name") for l in lanes() if l.get("name"))


def priority_lane_names():
    """Lanes flagged `priority: true` in settings.yaml (never auto-skipped; patterns in profile/signals.yaml)."""
    return tuple(l.get("name") for l in lanes() if l.get("name") and l.get("priority"))


def selected_packs():
    """Union of lanes[].packs (registry packs enabled for this workspace), in first-seen order."""
    out = []
    for l in lanes():
        for p in (l.get("packs") or []):
            if p and p not in out:
                out.append(p)
    return out


def _num(v, default, kind=int, key=""):
    """Coerce a settings value; a wrong type falls back to the default with one stderr line instead of a traceback
    (validate() is the place that tells the person; this keeps every tool running meanwhile)."""
    if v is None or v == "":
        return default
    try:
        return kind(v)
    except (TypeError, ValueError):
        print(f"settings.yaml: {key or 'a value'} is {v!r}, expected a number - using {default}", file=sys.stderr)
        return default


def thresholds():
    t = get("thresholds", {}) or {}
    return {
        "build_default_min_rubric": _num(t.get("build_default_min_rubric", 60), 60, int, "thresholds.build_default_min_rubric"),
        "commutable_min_rubric": _num(t.get("commutable_min_rubric", 45), 45, int, "thresholds.commutable_min_rubric"),
        "auto_skip_below_rubric": _num(t.get("auto_skip_below_rubric", 40), 40, int, "thresholds.auto_skip_below_rubric"),
        "jd_gate": _num(t.get("jd_gate", 0.28), 0.28, float, "thresholds.jd_gate"),
        "band_midpoint_ceiling": t.get("band_midpoint_ceiling", None),   # None = no advisory
        "low_band_top": t.get("low_band_top", None),                     # None = no LOWBAND tag
    }


def exclusions():
    e = get("exclusions", {}) or {}
    return {
        "employers": list(e.get("employers", []) or []),
        "role_types": list(e.get("role_types", []) or []),
        "contract_work": bool(e.get("contract_work", False)),   # v0.8 (M13): absent = OUT, as the template says
        "postdocs": bool(e.get("postdocs", True)),
    }


def location():
    loc = get("location", {}) or {}
    return {
        "home": loc.get("home", ""),
        "country": loc.get("country", "US"),
        "commute_radius_miles": loc.get("commute_radius_miles", 0),
        "commutable_metros": list(loc.get("commutable_metros", []) or []),
        "relocation": loc.get("relocation", "case-by-case"),
        # v0.7 (onboarding phase 4): how location shapes the search - see location_mode()
        "away_bar": _num(loc.get("away_bar", 70), 70, int, "location.away_bar"),
        "never_places": list(loc.get("never_places", []) or []),
        "remote": str(loc.get("remote", "ok") or "ok").lower(),            # ok | preferred | no
        # v0.7: other countries the person would work in (names or codes); ["any"] = anywhere. Place words for them
        # (cities, regions) can be given in other_countries_regex; US / CA / UK use the built-in geography tables.
        "other_countries": [str(x) for x in (loc.get("other_countries", []) or [])],
        "other_countries_regex": loc.get("other_countries_regex", "") or "",
        "tier1_regex": loc.get("tier1_regex", r"Remote"),
        "tier2_regex": loc.get("tier2_regex", r"(?!x)x"),   # never matches by default
        # optional overrides of the engine's per-country geography table (system/engine/tools/geo.py)
        "in_country_regex": loc.get("in_country_regex", "") or "",
        "in_country_regex_loose": loc.get("in_country_regex_loose", "") or "",
        "foreign_regex_extra": loc.get("foreign_regex_extra", "") or "",
    }


# ---- Workspace data files added by the 2026-10-08 refactor (REFACTOR_PLAN items 1-7) -------------
SIGNALS_YAML = os.path.join(PROFILE, "signals.yaml")          # match.py signature terms, gate thresholds, lane gates, priority patterns
CRITIC_RULES_YAML = os.path.join(PROFILE, "critic_rules.yaml")  # critic.py / screen_minquals.py / daily.py knockout + annotation rules
LEXICON_YAML = os.path.join(PROFILE, "lexicon.yaml")           # keywords.py claim-class lexicon
QUERIES_YAML = os.path.join(REGISTRIES, "queries.yaml")        # feeds.py / sweep.py / hard_ats.py search terms


@functools.lru_cache(maxsize=None)
def signals():
    """profile/signals.yaml (missing -> {}: the engine then runs cosine-only with a loud warning)."""
    return load_yaml(SIGNALS_YAML, default={}) or {}


@functools.lru_cache(maxsize=None)
def critic_rules():
    """profile/critic_rules.yaml (missing -> {}: only the generic engine knockouts apply)."""
    return load_yaml(CRITIC_RULES_YAML, default={}) or {}


@functools.lru_cache(maxsize=None)
def queries():
    """tracking/registries/queries.yaml (missing -> every keyword-searched arm is idle)."""
    q = load_yaml(QUERIES_YAML, default={}) or {}
    return {k: [str(x) for x in (v or [])] for k, v in q.items() if isinstance(v, (list, tuple))}


def build():
    b = get("build", {}) or {}
    fmt = str(b.get("format", "resume") or "resume").strip().lower()
    if fmt not in ("resume", "academic_cv"):
        print(f"userconfig: build.format '{fmt}' unknown (resume | academic_cv) - using 'resume'", file=sys.stderr)
        fmt = "resume"
    return {
        "resume_filename": b.get("resume_filename", "Resume.docx"),
        "min_experience_entries": _num(b.get("min_experience_entries", 3), 3, int, "build.min_experience_entries"),
        "location_line_default": b.get("location_line_default", "Open to relocation"),
        # 2026-10-09 academic path: "resume" = the one-page industry resume (default); "academic_cv" = the multi-page CV
        # (resume_builder.AcademicCV, page range enforced by verify_resume, every line traceable by audit_claims)
        "format": fmt,
        "cv_max_pages": _num(b.get("cv_max_pages", 3), 3, int, "build.cv_max_pages"),
        "cv_min_pages": _num(b.get("cv_min_pages", 2), 2, int, "build.cv_min_pages"),
        "cv_filename": b.get("cv_filename", "CV.docx"),
    }


def run_options():
    """settings.yaml run: discovery arms + the cost knobs (v0.5)."""
    r = get("run", {}) or {}
    return {
        "adzuna": bool(r.get("adzuna", False)),
        "linkedin_guest": bool(r.get("linkedin_guest", False)),
        "indeed_jobspy": bool(r.get("indeed_jobspy", False)),
        "window_days": _num(r.get("window_days", 30), 30, int, "run.window_days"),
        # only the top N postings (by the deterministic match score) go to the two blind scorers each run; the rest are
        # ledgered "not scored - below the top N" and come back next run if still open. 0 = score everything.
        "judge_top_n": _num(r.get("judge_top_n", 40), 40, int, "run.judge_top_n"),
        # the scorers read at most this many characters of each posting (the requirements block is kept whole)
        "jd_text_cap_chars": _num(r.get("jd_text_cap_chars", 6000), 6000, int, "run.jd_text_cap_chars"),
        # v0.7: warn when a job at or above the build line has gone 7 days without a decision (daily.py); false = off
        "judgment_check": bool(r.get("judgment_check", True)),
        # v0.7 light mode (Pro plans): fewer postings judged per run, the judge model the person picked at setup
        "judge_model": str(r.get("judge_model", "") or ""),
    }


# ---- validation (v0.5, audit bug 3): plain-language problems, never a traceback ---------------------------------------
PACKS_DIR = os.path.join(ENGINE, "registries", "packs")
_PLACEHOLDER = __import__("re").compile(r"^\s*<[^>]*>\s*$")


def is_placeholder(v):
    """True for template values such as "<your name>"."""
    return isinstance(v, str) and bool(_PLACEHOLDER.match(v))


def validate(cfg=None):
    """Check settings.yaml and return a list of (level, message): level "missing" = a required value is not filled in
    yet (normal while the interview is running), "error" = a value is the wrong kind, out of range, or names something
    that does not exist (always a mistake). Messages are plain English and name the field. [] means fine."""
    import re as _re
    cfg = load() if cfg is None else cfg
    out = []
    err = lambda m: out.append(("error", m))
    miss = lambda m: out.append(("missing", m))
    if not isinstance(cfg, dict) or not cfg:
        return [("missing", f"settings.yaml is empty or not a list of fields ({USER_YAML})")]

    def sect(name, required=False):
        v = cfg.get(name)
        if v is None:
            if required: miss(f"the '{name}' section is missing")
            return {}
        if not isinstance(v, dict):
            err(f"'{name}' should be a section with fields under it, not {type(v).__name__}"); return {}
        return v

    def want_bool(sec, d, key):
        v = d.get(key)
        if v is not None and not isinstance(v, bool):
            err(f"{sec}.{key} should be true or false, not {v!r}")

    def want_int(sec, d, key, lo=None, hi=None, allow_none=False):
        v = d.get(key)
        if v is None:
            if not allow_none and key in d: err(f"{sec}.{key} is empty; give a whole number")
            return
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            err(f"{sec}.{key} should be a number, not {v!r} (write it without quotes, e.g. 60)"); return
        if lo is not None and v < lo or hi is not None and v > hi:
            err(f"{sec}.{key} is {v}; it must be between {lo} and {hi}")

    def want_regex(sec, key, v):
        if v in (None, ""):
            return
        if not isinstance(v, str):
            err(f"{sec}.{key} should be a text pattern in quotes, not {v!r}"); return
        try:
            _re.compile(v)
        except _re.error as e:
            err(f"{sec}.{key} is not a valid pattern ({e}): {v!r}")

    ident = sect("identity", required=True)
    for k in ("name", "email"):
        v = ident.get(k)
        if v in (None, "") or is_placeholder(v):
            miss(f"identity.{k} is not filled in yet")
    if ident.get("links") is not None and not isinstance(ident.get("links"), list):
        err("identity.links should be a list of links (one per line starting with '- '), or []")

    wa = sect("work_authorization", required=True)
    if wa:
        if wa.get("resume_line") is None or is_placeholder(wa.get("resume_line")):
            miss("work_authorization.resume_line is not filled in yet (the exact words to print, or \"\" to print nothing)")
        for k in ("citizenship_only_roles_open", "clearance_possible", "export_controlled_open", "sponsorship_needed", "permanent_resident"):
            if k not in wa: miss(f"work_authorization.{k} is not set (true or false)")
            else: want_bool("work_authorization", wa, k)

    loc = sect("location", required=True)
    if loc:
        c = loc.get("country")
        if c in (None, "") or is_placeholder(c):
            miss("location.country is not filled in yet (US, CA, UK, or another two-letter code)")
        elif not isinstance(c, str) or not _re.fullmatch(r"[A-Za-z]{2}", c):
            err(f"location.country should be a two-letter country code such as US, not {c!r}")
        elif c.upper() not in ("US", "CA", "UK") and not loc.get("in_country_regex"):
            err(f"location.country is {c}: for a country other than US / CA / UK the three location patterns "
                "(in_country_regex, in_country_regex_loose, foreign_regex_extra) must be filled in, or every posting counts as inside the country")
        r = loc.get("relocation")
        if r is not None and not is_placeholder(r) and str(r).lower() not in ("yes", "no", "case-by-case"):
            err(f"location.relocation should be yes, no or case-by-case, not {r!r}")
        _m = loc.get("mode")
        if _m not in (None, "") and not is_placeholder(_m) and str(_m).lower().replace("-", "_") not in ("local_only", "local_first", "fit_first", "unsure"):
            err(f"location.mode should be local_only, local_first, fit_first or unsure, not {_m!r}")
        want_int("location", loc, "away_bar", 0, 100)
        _rm = loc.get("remote")
        if _rm not in (None, "") and str(_rm).lower() not in ("ok", "preferred", "no"):
            err(f"location.remote should be ok, preferred or no, not {_rm!r}")
        want_regex("location", "other_countries_regex", loc.get("other_countries_regex"))
        _sc = get("scoring", {}) or {}
        for _k, _ok in (("location", ("yes", "a little", "no", "true", "false")), ("career_fit", ("yes", "no", "true", "false")),
                        ("pay", ("yes", "no", "true", "false")), ("remote", ("yes", "no", "true", "false"))):
            if _k in _sc and str(_sc[_k]).lower() not in _ok:
                err(f"scoring.{_k} should be one of {', '.join(_ok[:3] if _k == 'location' else _ok[:2])}, not {_sc[_k]!r}")
        want_int("location", loc, "commute_radius_miles", 0, 1000)
        if loc.get("commutable_metros") is not None and not isinstance(loc.get("commutable_metros"), list):
            err("location.commutable_metros should be a list of places, or []")
        for k in ("tier1_regex", "tier2_regex", "in_country_regex", "in_country_regex_loose", "foreign_regex_extra"):
            want_regex("location", k, loc.get(k))

    lanes_v = cfg.get("lanes")
    packs = {os.path.basename(p)[:-5] for p in __import__("glob").glob(os.path.join(PACKS_DIR, "*.json"))}
    if lanes_v is None or lanes_v == []:
        miss("no lanes yet (the kinds of job you want; the interview writes them in phase 5)")
    elif not isinstance(lanes_v, list):
        err("lanes should be a list (each lane starts with '- name:')")
    else:
        for i, l in enumerate(lanes_v, 1):
            if not isinstance(l, dict):
                err(f"lane {i} should be a block with name / description / packs under it"); continue
            if not l.get("name") or is_placeholder(l.get("name")):
                miss(f"lane {i} has no name")
            for k in ("example_titles", "never_claims", "packs"):
                if l.get(k) is not None and not isinstance(l.get(k), list):
                    err(f"lane {i} ({l.get('name', '?')}): {k} should be a list, or []")
            if l.get("priority") is not None: want_bool(f"lane {i}", l, "priority")
            for pk in (l.get("packs") or []) if isinstance(l.get("packs"), list) else []:
                if pk not in packs:
                    err(f"lane {i} ({l.get('name', '?')}) names a job-board pack that does not exist: {pk!r}. Available: {', '.join(sorted(packs))}")

    tg = sect("targets")
    if tg:
        tr = tg.get("track")
        if tr not in (None, "") and not is_placeholder(tr) and str(tr).lower() not in ("industry", "academic", "government", "nonprofit", "mix"):
            err(f"targets.track should be industry, academic, government, nonprofit or mix, not {tr!r}")
        for k in ("phd_positions", "fixed_term_ok", "hourly_ok"): want_bool("targets", tg, k)
        if tg.get("employers") is not None and not isinstance(tg.get("employers"), list):
            err("targets.employers should be a list of employer names, or []")

    th = sect("thresholds")
    if th:
        for k in ("build_default_min_rubric", "commutable_min_rubric", "auto_skip_below_rubric"):
            want_int("thresholds", th, k, 0, 100)
        v = th.get("jd_gate")
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1):
            err(f"thresholds.jd_gate should be a number between 0 and 1, not {v!r}")
        for k in ("band_midpoint_ceiling", "low_band_top"):
            want_int("thresholds", th, k, 0, None, allow_none=True)
        a, b_, c_ = th.get("auto_skip_below_rubric"), th.get("commutable_min_rubric"), th.get("build_default_min_rubric")
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b_, c_)) and not (a <= b_ <= c_):
            err(f"thresholds should go up: auto_skip_below_rubric ({a}) <= commutable_min_rubric ({b_}) <= build_default_min_rubric ({c_})")

    ex = sect("exclusions")
    if ex:
        for k in ("employers", "role_types"):
            v = ex.get(k)
            if v is not None and not isinstance(v, list):
                err(f"exclusions.{k} should be a list, or []")
            elif isinstance(v, list):
                for pat in v: want_regex("exclusions", k, pat)
        for k in ("contract_work", "postdocs"): want_bool("exclusions", ex, k)

    sal = sect("salary")
    if sal:
        for k in ("floor", "target"): want_int("salary", sal, k, 0, None, allow_none=True)
        f, t = sal.get("floor"), sal.get("target")
        if isinstance(f, (int, float)) and isinstance(t, (int, float)) and not isinstance(f, bool) and f > t:
            err(f"salary.floor ({f}) is above salary.target ({t})")

    mo = sect("modules")
    for k in ("inbox_sweep", "outreach"): want_bool("modules", mo, k)
    rn = sect("run")
    for k in ("adzuna", "linkedin_guest", "indeed_jobspy"): want_bool("run", rn, k)
    want_int("run", rn, "window_days", 1, 365)
    want_int("run", rn, "judge_top_n", 0, 500)
    want_int("run", rn, "jd_text_cap_chars", 500, 100000)

    bd = sect("build")
    if bd:
        fmt = bd.get("format")
        if fmt is not None and not is_placeholder(fmt) and str(fmt).strip().lower() not in ("resume", "academic_cv"):
            err(f"build.format should be resume or academic_cv, not {fmt!r}")
        want_int("build", bd, "min_experience_entries", 0, 10)
        want_int("build", bd, "cv_min_pages", 1, 20); want_int("build", bd, "cv_max_pages", 1, 20)
        for k in ("resume_filename", "cv_filename"):
            v = bd.get(k)
            if v is not None and not is_placeholder(v) and not str(v).lower().endswith(".docx"):
                err(f"build.{k} should end in .docx, not {v!r}")

    ed = cfg.get("education")
    if ed is not None:
        if not isinstance(ed, list):
            err("education should be a list of entries (each starting with '- institution:')")
        else:
            for i, e in enumerate(ed, 1):
                if not isinstance(e, dict) or not e.get("institution"):
                    err(f"education entry {i} needs institution, dates and line")
    return out


def validate_or_exit(context="this run"):
    """For daily.py and friends: print every problem in plain words and exit 2 when any exists."""
    probs = validate()
    if not probs:
        return
    print(f"settings.yaml has problems; {context} stops here until they are fixed:")
    for lvl, m in probs:
        print(f"  - {m}")
    print(f"(file: {USER_YAML})")
    sys.exit(2)


def targets():
    """settings.yaml targets: what KINDS of positions are in scope beyond ordinary staff roles (2026-10-09, academic path).
    phd_positions  true -> funded PhD positions / studentships / graduate research assistantships are IN scope: the generic
                           new-grad / campus-hire title drop and the critic's GRAD-GATE are switched off
    fixed_term_ok  true -> "temporary" / "fixed-term" titles are NOT an eligibility drop (academic posts are usually fixed-term)
    hourly_ok      true -> the critic's "BELOW LEVEL: technician/HS tier" advisory is OFF (technician roles are the target)
    Defaults are the industry reading (both false)."""
    # v0.7: targets.position_types is the list the person ticked at setup (onboarding phase 5). Each type switches off the
    # matching title drop / critic gate. The older boolean flags still work and are OR-ed in, so v0.6 workspaces keep working.
    t = get("targets", {}) or {}
    pt = {str(x).strip().lower().replace(" ", "_").replace("-", "_") for x in (t.get("position_types") or [])}
    return {
        "position_types": sorted(pt),
        "phd_positions": bool(t.get("phd_positions", False)) or "phd_positions" in pt,
        "fixed_term_ok": bool(t.get("fixed_term_ok", False)) or bool(pt & {"temporary", "seasonal", "fixed_term"}),
        # hourly_ok true -> hourly-paid / high-school-minimum postings are NOT flagged "BELOW LEVEL" by the critic
        "hourly_ok": bool(t.get("hourly_ok", False)) or "hourly" in pt,
        "internships_ok": bool(t.get("internships_ok", False)) or bool(pt & {"internships", "internship"}),
        "coops_ok": bool(t.get("coops_ok", False)) or bool(pt & {"co_ops", "coops", "apprenticeships", "co_op"}),
        "new_grad_ok": bool(t.get("new_grad_ok", False)) or bool(pt & {"new_grad", "early_career", "graduate_programs"}),
        "unpaid_ok": bool(t.get("unpaid_ok", False)) or bool(pt & {"unpaid", "volunteer", "unpaid_research"}),
        "part_time_ok": bool(t.get("part_time_ok", True)) or "part_time" in pt,
    }


def location_mode():
    """v0.7: how location shapes the search, chosen by the person at setup (onboarding phase 4).
    local_only  - stay local: jobs outside the commuting area (and not remote) are not judged
    local_first - local first, would move for a strong fit: away jobs need `away_bar` to get a resume
    fit_first   - location barely matters: not scored by the judges, no location bar
    unsure      - like local_first, but every strong away job is put to the person as a question
    Missing -> derived from the older location.relocation (no -> local_only, yes -> fit_first, else local_first)."""
    loc = get("location", {}) or {}
    m = str(loc.get("mode", "") or "").strip().lower().replace("-", "_")
    if m not in ("local_only", "local_first", "fit_first", "unsure"):
        r = str(loc.get("relocation", "case-by-case") or "").strip().lower()
        m = {"no": "local_only", "yes": "fit_first"}.get(r, "local_first")
    return m


def scoring():
    """v0.7: what the blind judges score besides skills and experience (always scored). Chosen at setup (phase 14).
    location: "yes" | "a little" | "no"   career_fit: "yes" | "no"   pay: "yes" | "no"   remote: "yes" | "no"
    Defaults follow the location mode (fit_first -> location "no") and keep career fit on."""
    sc = get("scoring", {}) or {}
    def _v(k, d):
        raw = sc.get(k)
        v = (str(raw).strip().lower() if raw not in (None, "") else d)   # empty / missing -> the default
        return {"true": "yes", "false": "no", "little": "a little"}.get(v, v)
    return {
        "location": _v("location", "no" if location_mode() == "fit_first" else "yes"),
        "career_fit": _v("career_fit", "yes"),
        "pay": _v("pay", "no"),
        "remote": _v("remote", "no"),
    }


if __name__ == "__main__":
    if "--validate" in sys.argv:
        _p = validate()
        for _l, _m in _p: print(f"{_l}: {_m}")
        print("settings.yaml: " + ("OK" if not _p else f"{sum(1 for l, _ in _p if l == 'error')} error(s), {sum(1 for l, _ in _p if l == 'missing')} not filled in"))
        sys.exit(1 if any(l == "error" for l, _ in _p) else 0)
    print("workspace:", WS, "(exists)" if os.path.isdir(WS) else "(MISSING)")
    print("settings.yaml:", ("found: " + os.path.basename(USER_YAML)) if os.path.exists(USER_YAML) else (("found: " + os.path.basename(USER_JSON)) if os.path.exists(USER_JSON) else "MISSING"))
    print("modules:", MODULES)
    print("identity.name:", get("identity.name", "<unset>"))
    print("lanes:", lane_names())
    print("build.format:", build()["format"], "| targets:", targets())
