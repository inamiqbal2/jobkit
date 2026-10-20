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
  cfg = load()                       # dict (cached; read on first use, never at import)
  get("identity.name", "")           # dotted lookup with default
  get("thresholds.jd_gate")          # no default given -> the SCHEMA default (0.28)
  path("tracking", "state.db")       # absolute path inside the workspace
  MODULES["inbox_sweep"]             # False by default
  SCHEMA["run.window_days"].default  # v1.0: the one declarative list of every settings.yaml key
  configure("/abs/path/to/ws")       # v1.0: re-point WS + every derived path (see the function's docstring)

Command line:
  userconfig.py              summary of the active workspace
  userconfig.py --validate   plain-language problems in settings.yaml (exit 1 on an error)
  userconfig.py --schema     every settings.yaml key as a Markdown table (ARCHITECTURE.md is generated from it)
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
if os.environ.get("JOBKIT_WORKSPACE") and not os.path.isdir(WS):   # v0.9 (audit M21): a relative or wrong JOBKIT_WORKSPACE must never create a second workspace
    print(f"JOBKIT_WORKSPACE points at {WS}, which is not a folder. Unset it, or set it to the absolute path of your 'My Job Search' folder.", file=sys.stderr)
    sys.exit(2)
os.environ["JOBKIT_WORKSPACE"] = WS   # children inherit the absolute path
VENV = os.path.join(SYSTEM, ".venv")
VENV_PYTHON = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")


def _first_existing(*cands):
    """The first path that exists, else the first candidate (the v0.4 name) so new files get the new name."""
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[0]


# Canonical workspace sub-paths. Tools build every data path from these, never from ROOT/tracking.
# v1.0 (audit M26): every WS-derived name is assigned in ONE function so configure() can re-point all of them at once;
# the names themselves are unchanged (38 modules import them).
TRACKING = PROFILE = EVIDENCE = APPLICATIONS = REPORTS = INTAKE = INTAKE_EXTRACTED = REGISTRIES = JDS = RUBRIC_DIR = None
TRACKER_CSV = APPROVED_CLAIMS_YAML = SECRETS = USER_YAML = USER_JSON = USER_RULES = None
SIGNALS_YAML = CRITIC_RULES_YAML = LEXICON_YAML = QUERIES_YAML = None


def _apply_workspace(ws):
    """Set WS and every path constant derived from it (import time, and again from configure())."""
    global WS, TRACKING, PROFILE, EVIDENCE, APPLICATIONS, REPORTS, INTAKE, INTAKE_EXTRACTED, REGISTRIES, JDS, RUBRIC_DIR
    global TRACKER_CSV, APPROVED_CLAIMS_YAML, SECRETS, USER_YAML, USER_JSON, USER_RULES
    global SIGNALS_YAML, CRITIC_RULES_YAML, LEXICON_YAML, QUERIES_YAML
    WS = ws
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
    SECRETS = _first_existing(os.path.join(WS, "keys.json"), os.path.join(WS, "secrets.json"))
    USER_YAML = _first_existing(os.path.join(WS, "settings.yaml"), os.path.join(WS, "user.yaml"))
    USER_JSON = _first_existing(os.path.join(WS, "settings.json"), os.path.join(WS, "user.json"))
    USER_RULES = _first_existing(os.path.join(WS, "my-rules.md"), os.path.join(WS, "charters", "user-rules.md"))
    # Workspace data files added by the 2026-10-08 refactor (REFACTOR_PLAN items 1-7)
    SIGNALS_YAML = os.path.join(PROFILE, "signals.yaml")          # match.py signature terms, gate thresholds, lane gates, priority patterns
    CRITIC_RULES_YAML = os.path.join(PROFILE, "critic_rules.yaml")  # critic.py / screen_minquals.py / daily.py knockout + annotation rules
    LEXICON_YAML = os.path.join(PROFILE, "lexicon.yaml")           # keywords.py claim-class lexicon
    QUERIES_YAML = os.path.join(REGISTRIES, "queries.yaml")        # feeds.py / sweep.py / hard_ats.py search terms


_apply_workspace(WS)


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
    py_compiled on a bare checkout; tools that NEED a field should call require().
    v1.0 (audit M26): nothing in this module calls load() at import any more (MODULES is filled on first use), so
    importing userconfig never reads settings.yaml; the first get()/load() does, and configure() forgets it again."""
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


# ---- the settings.yaml schema (v1.0, audit M27) ----------------------------------------------------------------------
# One declarative list of every key the engine reads from settings.yaml. Before v1.0 the accessor defaults below, the
# 182-line validate(), the template's comments and the ARCHITECTURE.md table were four hand-kept copies that had drifted
# (targets.*_ok read but undocumented, salary.currency documented but never read, scoring validated inside the location
# block). Now: the accessors take their defaults from here, validate() iterates this, `userconfig.py --schema` prints it,
# ARCHITECTURE.md's table is generated from it and tests/test_settings_schema.py fails when a tool reads a key that is
# not here or the docs fall behind. Cross-field rules (thresholds order, the v0.9 stay-local guard, pack names, the
# signals.yaml patterns) stay as explicit checks in validate() because they cannot be said per key.
#
# Field types ("type" column):
#   str · bool · int (rng = allowed range) · int|null · float · regex · enum (choices; show = how they are listed in
#   the error) · list (list_of = what it lists, for the error sentence) · list[str] · list[regex] · list[int] ·
#   docx (a .docx filename) · section (a mapping) · list[section] (a list of mappings; item keys are "name[].key")
# required: a "missing" note (the exact sentence in `missing`) while the value is absent / "" / a <placeholder>;
# empty_ok: "" counts as filled (work_authorization.resume_line prints nothing on purpose).
# phase: the onboarding phase (skills/onboarding/SKILL.md) that writes the key; None = not asked, set by hand.
# consumers: who reads it - the "consumed by" column of ARCHITECTURE.md (prose, kept from the hand-written table).
# reserved: documented and accepted but read by nothing yet (kept so a filled file stays valid; never deleted here).
class Field(object):
    __slots__ = ("key", "type", "default", "doc", "phase", "required", "missing", "empty_ok", "choices", "show", "rng",
                 "list_of", "hint", "item_label", "consumers", "reserved")

    def __init__(self, key, type, default=None, doc="", phase=None, required=False, missing=None, empty_ok=False,
                 choices=None, show=None, rng=None, list_of="", hint="", item_label="", consumers="", reserved=False):
        self.key, self.type, self.default, self.doc, self.phase = key, type, default, doc, phase
        self.required, self.missing, self.empty_ok = required, missing, empty_ok
        self.choices, self.show, self.rng, self.list_of, self.hint, self.item_label = choices, show, rng, list_of, hint, item_label
        self.consumers, self.reserved = consumers, reserved

    @property
    def section(self):
        """'identity.name' -> 'identity'; 'lanes[].name' -> 'lanes'; 'identity' -> ''."""
        return self.key.split(".")[0].replace("[]", "") if "." in self.key else ""

    @property
    def leaf(self):
        return self.key.split(".")[-1]


_NEVER = r"(?!x)x"   # a pattern that never matches: the engine's "" for regex defaults
_YN = ("yes", "no", "true", "false")   # PyYAML reads an unquoted yes/no as a boolean; both spellings are accepted

SCHEMA = {f.key: f for f in [
    # -- identity (phase 2) --
    Field("identity", "section", {}, "who the resume is for", 2, required=True, missing="the 'identity' section is missing",
          consumers="resume_builder (contact line, core properties), verify_resume (parse test), audit_claims (person pool)"),
    Field("identity.name", "str", "", "full name as it prints at the top of the resume", 2, required=True,
          missing="identity.name is not filled in yet", consumers="resume_builder, audit_claims, verify_resume"),
    Field("identity.first_name", "str", "", "used by the resume parse test (must survive docx -> pdf -> text)", 2, consumers="verify_resume"),
    Field("identity.email", "str", "", "contact line", 2, required=True, missing="identity.email is not filled in yet",
          consumers="resume_builder, verify_resume, audit_claims"),
    Field("identity.phone", "str", "", "printed verbatim; the parse test looks for this exact string", 2, consumers="resume_builder, verify_resume, audit_claims"),
    Field("identity.city_state", "str", "", "ATS location prefill; OFF the contact line by default (see build.location_line_default)", 2, consumers="resume_builder"),
    Field("identity.links", "list", [], "printed in this order on the contact line; [] for none", 2,
          list_of="links (one per line starting with '- ')", consumers="resume_builder, audit_claims"),
    # -- work authorization (phase 3) --
    Field("work_authorization", "section", {}, "Article I.2: the engine never assumes a status", 3, required=True,
          missing="the 'work_authorization' section is missing",
          consumers="eligibility.AUTH, screen_minquals (knockout classes), critic (INELIGIBLE), match (INELIG corpus drop), resume_builder, audit_claims"),
    Field("work_authorization.resume_line", "str", "", "the exact words printed on the resume contact line (\"\" prints nothing); audit_claims requires it verbatim", 3,
          required=True, empty_ok=True, missing="work_authorization.resume_line is not filled in yet (the exact words to print, or \"\" to print nothing)",
          consumers="resume_builder contact line; audit_claims"),
    Field("work_authorization.citizenship_only_roles_open", "bool", False, "true if \"must be a U.S. citizen\" roles are open to you", 3,
          required=True, missing="work_authorization.citizenship_only_roles_open is not set (true or false)", consumers="eligibility, screen_minquals, critic, match"),
    Field("work_authorization.clearance_possible", "bool", False, "true if you can obtain or hold a security clearance", 3,
          required=True, missing="work_authorization.clearance_possible is not set (true or false)", consumers="eligibility, screen_minquals, critic, match"),
    Field("work_authorization.export_controlled_open", "bool", False, "true if ITAR / \"U.S. person\" / export-controlled roles are open", 3,
          required=True, missing="work_authorization.export_controlled_open is not set (true or false)", consumers="eligibility, screen_minquals, critic, match"),
    Field("work_authorization.sponsorship_needed", "bool", False, "true if you need visa sponsorship (adds a knockout for \"no sponsorship\")", 3,
          required=True, missing="work_authorization.sponsorship_needed is not set (true or false)", consumers="eligibility, screen_minquals, critic, match"),
    Field("work_authorization.permanent_resident", "bool", False, "true if you hold permanent residency: postings that explicitly admit permanent residents are then open even when citizenship_only_roles_open is false", 3,
          required=True, missing="work_authorization.permanent_resident is not set (true or false)", consumers="eligibility, screen_minquals, critic, match"),
    # -- location (phase 4) --
    Field("location", "section", {}, "where the search happens and how much location matters", 4, required=True,
          missing="the 'location' section is missing", consumers="geo, eligibility, daily, sweep, decide, rubric, funnel, feeds; judgment agent + profile_blind"),
    Field("location.home", "str", "", "home city and state, in plain words", 4, consumers="judgment agent + profile_blind (not read by the engine)"),
    Field("location.country", "str", "US", "ONE two-letter country of search; US / CA / UK have built-in geography tables (geo.py), any other code needs the three regex overrides", 4,
          required=True, missing="location.country is not filled in yet (US, CA, UK, or another two-letter code)", consumers="geo.py table selection used by match/sweep/daily/eligibility"),
    Field("location.in_country_regex", "regex", "", "override: a location string that reads as INSIDE the country (strict; corpus arm); required for a country without a geo table", 4, consumers="geo.py"),
    Field("location.in_country_regex_loose", "regex", "", "override: same, loose (Workday / hard-ATS placeholders like \"3 Locations\")", 4, consumers="geo.py"),
    Field("location.foreign_regex_extra", "regex", "", "override: extra foreign-place cues to drop (e.g. \"United States|USA\" for a non-US user)", 4, consumers="geo.py"),
    Field("location.commute_radius_miles", "int", 0, "commuting radius in miles", 4, rng=(0, 1000), consumers="judgment agent + profile_blind (not read by the engine)"),
    Field("location.commutable_metros", "list", [], "plain words for the judgment agent and the rubric profile, e.g. [\"Denver CO\", \"Boulder CO\"]; must be filled for a local_only / local_first / unsure search", 4,
          list_of="places", consumers="validate() stay-local guard; judgment agent + profile_blind"),
    Field("location.relocation", "enum", "case-by-case", "kept for older workspaces; location.mode is what the engine follows (missing mode: no -> local_only, yes -> fit_first, else local_first)", 4,
          choices=("yes", "no", "case-by-case"), consumers="location_mode() fallback"),
    Field("location.mode", "enum", "", "local_only = stay local, jobs elsewhere are set aside before judging | local_first = jobs elsewhere need away_bar | fit_first = location barely matters | unsure = like local_first, but every strong job elsewhere is put to you as a question", 4,
          choices=("local_only", "local_first", "fit_first", "unsure"), consumers="location_mode(): decide.skip_guard, rubric prompt, scoring() default"),
    Field("location.away_bar", "int", 70, "local_first / unsure: the score a job elsewhere needs before a resume is built for it", 4, rng=(0, 100), consumers="decide.skip_guard"),
    Field("location.never_places", "list[str]", [], "places you would never move to, in plain words", 4, consumers="rubric / decide (never_places), judgment agent"),
    Field("location.remote", "enum", "ok", "how remote work is treated", 4, choices=("ok", "preferred", "no"), consumers="rubric prompt, judgment agent"),
    Field("location.other_countries", "list[str]", [], "other countries you would work in (names or codes); [\"any\"] = anywhere", 4, consumers="eligibility.non_us"),
    Field("location.other_countries_regex", "regex", "", "place words for those countries when they are not US / CA / UK (drafted at setup)", 4, consumers="eligibility.non_us"),
    Field("location.tier1_regex", "regex", "Remote", "commutable places + remote as a pattern, e.g. \"Denver|Boulder|Colorado|\\\\bCO\\\\b|Remote\" (T1 = commutable + remote)", 4, consumers="daily.py / sweep.py geography tiers"),
    Field("location.tier2_regex", "regex", _NEVER, "nearby places you would consider (T2); \"\" = none (the engine's default never matches)", 4, consumers="daily.py / sweep.py geography tiers"),
    # -- lanes (phase 5) --
    Field("lanes", "list[section]", [], "1-6 target lanes in plain words; packs pick the job boards. Signature terms live in profile/signals.yaml, search terms in tracking/registries/queries.yaml", 5,
          required=True, missing="no lanes yet (the kinds of job you want; the interview writes them in phase 5)", hint="each lane starts with '- name:'", item_label="lane",
          consumers="state.py canonical lanes; lanes.py (priority); registries.py assemble (packs)"),
    Field("lanes[].name", "str", "", "short canonical label (state.db Lane column warns on anything else)", 5, required=True, consumers="state.py, lanes.py"),
    Field("lanes[].description", "str", "", "the work in one or two sentences", 5, consumers="onboarding / judgment agent (not read by the engine)"),
    Field("lanes[].example_titles", "list", [], "titles that belong to the lane", 5, consumers="onboarding / judgment agent (not read by the engine)"),
    Field("lanes[].never_claims", "list", [], "things people in this lane claim that you must never claim", 5, consumers="onboarding (approved_claims never_claims)"),
    Field("lanes[].priority", "bool", False, "true = the lane is screened FOR and never auto-skipped (patterns: profile/signals.yaml priority_patterns)", 5, consumers="lanes.py via priority_lane_names()"),
    Field("lanes[].packs", "list", [], "job-board packs from system/engine/registries/packs/ ([] = none); every name must exist", 5, consumers="registries.py assemble via selected_packs()"),
    # -- targets (phase 5) --
    Field("targets", "section", {}, "what KINDS of positions are in scope, and who you would love to work for", 5,
          consumers="eligibility.ELIG, critic, discover_boards"),
    Field("targets.track", "enum", "", "onboarding only: which phases are asked (publications / teaching / references for academic; the USAJobs key step for government) and the resume-vs-CV default", 5,
          choices=("industry", "academic", "government", "nonprofit", "mix"), consumers="onboarding (not read by the engine)"),
    Field("targets.position_types", "list[str]", [], "what you are looking for: full_time, part_time, internships, co_ops, new_grad, fellowships, unpaid_research, phd_positions, postdocs, contract, temporary, hourly; anything NOT listed is set aside", 5,
          consumers="targets(): each type switches off the matching title drop / critic gate"),
    Field("targets.phd_positions", "bool", False, "legacy flag (v0.6): funded PhD positions / studentships are targets - the new-grad / campus title drop and the critic's GRAD-GATE are off", 5, consumers="eligibility.ELIG, critic GRAD-GATE"),
    Field("targets.fixed_term_ok", "bool", False, "legacy flag: \"temporary\" / fixed-term titles are not an eligibility drop", 5, consumers="eligibility.ELIG"),
    Field("targets.hourly_ok", "bool", False, "legacy flag: hourly-paid / high-school-minimum postings are NOT flagged \"BELOW LEVEL\" by the critic", 5, consumers="critic"),
    Field("targets.internships_ok", "bool", False, "legacy flag: internship titles are kept (same as position_types: [internships])", 5, consumers="eligibility.ELIG"),
    Field("targets.coops_ok", "bool", False, "legacy flag: co-op / apprenticeship titles are kept (same as position_types: [co_ops])", 5, consumers="eligibility.ELIG"),
    Field("targets.new_grad_ok", "bool", False, "legacy flag: new-grad / early-career / graduate-program titles are kept (same as position_types: [new_grad])", 5, consumers="eligibility.ELIG, critic GRAD-GATE"),
    Field("targets.unpaid_ok", "bool", False, "legacy flag: unpaid / volunteer postings are kept (same as position_types: [unpaid_research])", 5, consumers="eligibility.ELIG"),
    Field("targets.part_time_ok", "bool", True, "legacy flag: part-time titles are kept (absent = kept; position_types: [part_time] says the same)", 5, consumers="eligibility.ELIG"),
    Field("targets.employers", "list", [], "up to ~10 employers you would be glad to work for, by name", 5, list_of="employer names",
          consumers="discover_boards.py: finds and verifies each employer's board, writes custom.json (or a watch entry)"),
    # -- scoring (phase 14) --
    Field("scoring", "section", {}, "what the blind judges score BESIDES skills and experience (always scored)", 14, consumers="rubric.py prompt header"),
    Field("scoring.location", "enum", "", "yes | a little | no; missing = yes, or no when location.mode is fit_first", 14,
          choices=("yes", "a little", "no") + ("true", "false"), show="one of yes, a little, no", consumers="rubric.py"),
    Field("scoring.career_fit", "enum", "yes", "yes = a job that does not use / grow your strengths scores lower; no = any job you can get", 14, choices=_YN, show="one of yes, no", consumers="rubric.py"),
    Field("scoring.pay", "enum", "no", "yes = posted pay against the profile's PAY line counts", 14, choices=_YN, show="one of yes, no", consumers="rubric.py"),
    Field("scoring.remote", "enum", "no", "yes = remote / hybrid terms count", 14, choices=_YN, show="one of yes, no", consumers="rubric.py"),
    # -- thresholds (phase 14) --
    Field("thresholds", "section", {}, "the score lines; auto_skip_below_rubric <= commutable_min_rubric <= build_default_min_rubric", 14,
          consumers="critic (band advisory), screen (LOWBAND), daily tripwire, decide, rubric, match"),
    Field("thresholds.build_default_min_rubric", "int", 60, "dual-blind average at / above this = build by default", 14, rng=(0, 100), consumers="decide, rubric, daily, critic"),
    Field("thresholds.commutable_min_rubric", "int", 45, "inside commutable_metros, build from this line", 14, rng=(0, 100), consumers="decide"),
    Field("thresholds.auto_skip_below_rubric", "int", 40, "below this, both scorers agreeing, non-stub JD -> auto-ledger SKIP", 14, rng=(0, 100), consumers="decide, rubric"),
    Field("thresholds.jd_gate", "float", 0.28, "FALLBACK only: profile/signals.yaml thresholds.jd_gate wins when present", 14, rng=(0, 1), consumers="match (fallback)"),
    Field("thresholds.band_midpoint_ceiling", "int|null", None, "e.g. 140000 -> critic prints an ADVISORY above it; null = off", 14, rng=(0, None), consumers="critic"),
    Field("thresholds.low_band_top", "int|null", None, "e.g. 90000 -> queue tags LOWBAND below it; null = off", 14, rng=(0, None), consumers="screen_minquals"),
    # -- exclusions (phase 5) --
    Field("exclusions", "section", {}, "what is never shown", 5, consumers="eligibility, critic"),
    Field("exclusions.employers", "list[regex]", [], "regex or plain names, matched on SOURCE / URL only, never JD text", 5, consumers="eligibility.excluded_employer"),
    Field("exclusions.role_types", "list[regex]", [], "title-level eligibility drops (regexes, word-bounded, case-insensitive); only what YOU name", 5, consumers="eligibility (appended to the title filter)"),
    Field("exclusions.contract_work", "bool", False, "false = contract / 1099 / freelance / contract-to-hire postings are OUT (absent = OUT)", 5, consumers="critic CONTRACT-GIG"),
    Field("exclusions.postdocs", "bool", True, "false = postdoctoral TITLES are dropped; the template ships false, an ABSENT key keeps them (the v0.2 reading)", 5, consumers="eligibility.ELIG"),
    # -- salary (phase 6) --
    Field("salary", "section", {}, "pay expectations; judgment notes only, never a silent filter", 6, consumers="onboarding -> profile_blind PAY line; judgment agent"),
    Field("salary.floor", "int|null", None, "lowest yearly pay you would accept (a number, e.g. 85000)", 6, rng=(0, None), consumers="onboarding / judgment agent (not read by the engine)"),
    Field("salary.target", "int|null", None, "the pay you are aiming for", 6, rng=(0, None), consumers="onboarding / judgment agent (not read by the engine)"),
    Field("salary.currency", "str", "USD", "currency of floor and target (reserved: accepted, read by nothing yet)", 6, reserved=True, consumers="none yet"),
    # -- modules (phase 14) --
    Field("modules", "section", {}, "optional engine modules, OFF by default", 14, consumers="daily.py STEP 0b, inbox_sweep.py, outreach charter"),
    Field("modules.inbox_sweep", "bool", False, "Gmail read-only sweep; requires the agent's Gmail tool", 14, consumers="daily.py STEP 0b, inbox_sweep.py"),
    Field("modules.outreach", "bool", False, "outreach drafting charter", 14, consumers="outreach charter"),
    # -- run (phases 14 and 16) --
    Field("run", "section", {}, "discovery arms (employer boards always run; these are extras) and the cost knobs", 14, consumers="feeds.py, daily.py, rubric.py, setup.py"),
    Field("run.adzuna", "bool", False, "OFFICIAL free API (developer.adzuna.com); true needs adzuna_id / adzuna_key in keys.json", 16, consumers="feeds.py"),
    Field("run.linkedin_guest", "bool", False, "OPT-IN: public guest cards scraped from linkedin.com (terms of service; unversioned, rate-limited)", 16, consumers="feeds.py"),
    Field("run.indeed_jobspy", "bool", False, "OPT-IN, same caveat (Indeed's terms); needs python-jobspy (requirements-optional.txt)", 16, consumers="feeds.py, setup.py (installs jobspy)"),
    Field("run.window_days", "int", 30, "recency window on UPDATED date (charters/search.md)", 14, rng=(1, 365), consumers="daily.py"),
    Field("run.judge_top_n", "int", 40, "only the top N postings by the deterministic match score go to the two blind scorers each run; the rest are deferred (0 = score everything)", 14, rng=(0, 500), consumers="rubric.py prep"),
    Field("run.jd_text_cap_chars", "int", 6000, "the scorers read at most this many characters of each posting (the requirements block is always kept whole)", 14, rng=(500, 100000), consumers="rubric.cap_text"),
    Field("run.judgment_check", "bool", True, "warn when a job at or above the build line goes 7 days without a decision", 14, consumers="daily.py"),
    Field("run.judge_model", "str", "", "light mode: model for the two judges, e.g. \"sonnet\"; \"\" = the strongest available", 14, consumers="daily skill (scorer spawn)"),
    # -- rubric (optional) --
    Field("rubric", "section", {}, "the blind judges", None, consumers="rubric.py"),
    Field("rubric.b_band", "list[int]", [30, 70], "scorer B re-reads only postings scorer A put in this band (rubric.py prep-b)", None, consumers="rubric.py prep-b / merge"),
    Field("rubric.protect_title_regex", "regex", _NEVER, "titles the judges are known to under-score for YOU; never auto-skipped (\"\" = none)", None, consumers="rubric.py auto-skip guard"),
    # -- build (phase 5) --
    Field("build", "section", {}, "how the documents are built", 5, consumers="resume_builder, verify_resume, audit_claims, consistency"),
    Field("build.format", "enum", "resume", "resume = one-page industry resume (verify = 1 page, 90-93% fill) | academic_cv = multi-page CV (resume_builder.AcademicCV; verify = cv_min_pages..cv_max_pages; audit_claims checks EVERY line)", 5,
          choices=("resume", "academic_cv"), consumers="resume_builder, verify_resume, audit_claims, consistency"),
    Field("build.resume_filename", "docx", "Resume.docx", "every built resume uses this exact filename (phase 5 sets \"Resume_<First>_<Last>.docx\")", 5, consumers="consistency, audit_claims"),
    Field("build.cv_filename", "docx", "CV.docx", "academic_cv only: the CV filename (must start with \"CV\" for the audit's CV mode)", 5, consumers="consistency, audit_claims"),
    Field("build.cv_min_pages", "int", 2, "academic_cv: the page range verify_resume enforces (lower bound)", 5, rng=(1, 20), consumers="verify_resume"),
    Field("build.cv_max_pages", "int", 3, "academic_cv: the page range verify_resume enforces (upper bound)", 5, rng=(1, 20), consumers="verify_resume"),
    Field("build.min_experience_entries", "int", 3, "resume_builder warns below this many experience entries", 5, rng=(0, 10), consumers="resume_builder"),
    Field("build.location_line_default", "str", "Open to relocation", "contact-line text for roles outside commutable_metros", 5, consumers="resume_builder"),
    Field("build.no_pdf_copies", "bool", False, "true = verify_resume fails when a Resume_ / CV_ / CoverLetter_ PDF sits in the folder (send .docx only)", None, consumers="verify_resume"),
    # -- education (phase 7) --
    Field("education", "list[section]", [], "printed by resume_builder.education(); newest first", 7, list_of="entries", hint="each starting with '- institution:'", item_label="education entry",
          consumers="resume_builder.education(), audit_claims (person pool)"),
    Field("education[].institution", "str", "", "the school", 7, required=True, consumers="resume_builder, audit_claims"),
    Field("education[].dates", "str", "", "e.g. \"Sep 2018 - May 2022\"", 7, consumers="resume_builder, audit_claims"),
    Field("education[].line", "str", "", "\"<degree> in <field>, <city, state>  |  Thesis: <title>\"", 7, consumers="resume_builder, audit_claims"),
    # -- verification (phase 13) --
    Field("verification", "section", {}, "verify_resume.py parse test", 13, consumers="verify_resume"),
    Field("verification.employer_tokens", "list[str]", [], "the employer names on your resume; checked only when the resume mentions them", 13, consumers="verify_resume parse test"),
]}


def _d(key):
    """The SCHEMA default of a dotted key (accessors read their defaults here, never from a second literal)."""
    return SCHEMA[key].default


_MISSING = object()


def get(dotted, default=_MISSING):
    """get('identity.email') -> value or default. v1.0 (audit M27): with no default given, the SCHEMA default of that
    key (None for a key outside the schema); an explicit default, including None, is returned unchanged."""
    if default is _MISSING:
        default = SCHEMA[dotted].default if dotted in SCHEMA else None
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
    return {"inbox_sweep": bool(m.get("inbox_sweep", _d("modules.inbox_sweep"))),
            "outreach": bool(m.get("outreach", _d("modules.outreach")))}


class _LazyModules(dict):
    """v1.0 (audit M26): MODULES was computed at import, the one import-time read of settings.yaml. It is now a dict
    that fills itself on first use and is emptied by configure(), so `from userconfig import MODULES` keeps working
    (daily.py, inbox_sweep.py index it) and even follows a later configure() because the object is shared."""
    def __init__(self):
        dict.__init__(self); self._filled = False

    def _fill(self):
        if not self._filled:
            dict.update(self, modules()); self._filled = True

    def reset(self):
        dict.clear(self); self._filled = False

    def __getitem__(self, k): self._fill(); return dict.__getitem__(self, k)
    def __contains__(self, k): self._fill(); return dict.__contains__(self, k)
    def __iter__(self): self._fill(); return dict.__iter__(self)
    def __len__(self): self._fill(); return dict.__len__(self)
    def __bool__(self): self._fill(); return dict.__len__(self) > 0
    def __repr__(self): self._fill(); return dict.__repr__(self)
    def __eq__(self, other): self._fill(); return dict.__eq__(self, other)
    __hash__ = None
    def get(self, k, d=None): self._fill(); return dict.get(self, k, d)
    def keys(self): self._fill(); return dict.keys(self)
    def values(self): self._fill(); return dict.values(self)
    def items(self): self._fill(); return dict.items(self)
    def copy(self): self._fill(); return dict(self)


MODULES = _LazyModules()


def work_auth():
    """Flags with safe defaults = the MOST restrictive reading (nothing is assumed open)."""
    w = get("work_authorization", {}) or {}
    return {
        "resume_line": w.get("resume_line", _d("work_authorization.resume_line")),
        "citizenship_only_roles_open": bool(w.get("citizenship_only_roles_open", _d("work_authorization.citizenship_only_roles_open"))),
        "clearance_possible": bool(w.get("clearance_possible", _d("work_authorization.clearance_possible"))),
        "export_controlled_open": bool(w.get("export_controlled_open", _d("work_authorization.export_controlled_open"))),
        "sponsorship_needed": bool(w.get("sponsorship_needed", _d("work_authorization.sponsorship_needed"))),
        # optional: true when the user is a permanent resident, so gates that explicitly ADMIT permanent
        # residents ("citizens and green-card holders are eligible") are open even though citizenship_only is not
        "permanent_resident": bool(w.get("permanent_resident", _d("work_authorization.permanent_resident"))),
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


def _snum(d, key, kind=int):
    """A numeric settings value from section dict `d` for dotted `key`, SCHEMA default when absent or not a number."""
    return _num(d.get(SCHEMA[key].leaf, _d(key)), _d(key), kind, key)


def thresholds():
    t = get("thresholds", {}) or {}
    return {
        "build_default_min_rubric": _snum(t, "thresholds.build_default_min_rubric"),
        "commutable_min_rubric": _snum(t, "thresholds.commutable_min_rubric"),
        "auto_skip_below_rubric": _snum(t, "thresholds.auto_skip_below_rubric"),
        "jd_gate": _snum(t, "thresholds.jd_gate", float),
        "band_midpoint_ceiling": t.get("band_midpoint_ceiling", _d("thresholds.band_midpoint_ceiling")),   # None = no advisory
        "low_band_top": t.get("low_band_top", _d("thresholds.low_band_top")),                               # None = no LOWBAND tag
    }


def exclusions():
    e = get("exclusions", {}) or {}
    return {
        "employers": list(e.get("employers", []) or []),
        "role_types": list(e.get("role_types", []) or []),
        "contract_work": bool(e.get("contract_work", _d("exclusions.contract_work"))),   # v0.8 (M13): absent = OUT, as the template says
        "postdocs": bool(e.get("postdocs", _d("exclusions.postdocs"))),
    }


def location():
    loc = get("location", {}) or {}
    return {
        "home": loc.get("home", _d("location.home")),
        "country": loc.get("country", _d("location.country")),
        "commute_radius_miles": loc.get("commute_radius_miles", _d("location.commute_radius_miles")),
        "commutable_metros": list(loc.get("commutable_metros", []) or []),
        "relocation": loc.get("relocation", _d("location.relocation")),
        # v0.7 (onboarding phase 4): how location shapes the search - see location_mode()
        "away_bar": _snum(loc, "location.away_bar"),
        "never_places": list(loc.get("never_places", []) or []),
        "remote": str(loc.get("remote", _d("location.remote")) or _d("location.remote")).lower(),            # ok | preferred | no
        # v0.7: other countries the person would work in (names or codes); ["any"] = anywhere. Place words for them
        # (cities, regions) can be given in other_countries_regex; US / CA / UK use the built-in geography tables.
        "other_countries": [str(x) for x in (loc.get("other_countries", []) or [])],
        "other_countries_regex": loc.get("other_countries_regex", "") or "",
        "tier1_regex": loc.get("tier1_regex", _d("location.tier1_regex")),
        "tier2_regex": loc.get("tier2_regex", _d("location.tier2_regex")),   # never matches by default
        # optional overrides of the engine's per-country geography table (system/engine/tools/geo.py)
        "in_country_regex": loc.get("in_country_regex", "") or "",
        "in_country_regex_loose": loc.get("in_country_regex_loose", "") or "",
        "foreign_regex_extra": loc.get("foreign_regex_extra", "") or "",
    }


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
    fmt = str(b.get("format", _d("build.format")) or _d("build.format")).strip().lower()
    if fmt not in SCHEMA["build.format"].choices:
        print(f"userconfig: build.format '{fmt}' unknown (resume | academic_cv) - using 'resume'", file=sys.stderr)
        fmt = _d("build.format")
    return {
        "resume_filename": b.get("resume_filename", _d("build.resume_filename")),
        "min_experience_entries": _snum(b, "build.min_experience_entries"),
        "location_line_default": b.get("location_line_default", _d("build.location_line_default")),
        # 2026-10-09 academic path: "resume" = the one-page industry resume (default); "academic_cv" = the multi-page CV
        # (resume_builder.AcademicCV, page range enforced by verify_resume, every line traceable by audit_claims)
        "format": fmt,
        "cv_max_pages": _snum(b, "build.cv_max_pages"),
        "cv_min_pages": _snum(b, "build.cv_min_pages"),
        "cv_filename": b.get("cv_filename", _d("build.cv_filename")),
    }


def run_options():
    """settings.yaml run: discovery arms + the cost knobs (v0.5)."""
    r = get("run", {}) or {}
    return {
        "adzuna": bool(r.get("adzuna", _d("run.adzuna"))),
        "linkedin_guest": bool(r.get("linkedin_guest", _d("run.linkedin_guest"))),
        "indeed_jobspy": bool(r.get("indeed_jobspy", _d("run.indeed_jobspy"))),
        "window_days": _snum(r, "run.window_days"),
        # only the top N postings (by the deterministic match score) go to the two blind scorers each run; the rest are
        # ledgered "not scored - below the top N" and come back next run if still open. 0 = score everything.
        "judge_top_n": _snum(r, "run.judge_top_n"),
        # the scorers read at most this many characters of each posting (the requirements block is kept whole)
        "jd_text_cap_chars": _snum(r, "run.jd_text_cap_chars"),
        # v0.7: warn when a job at or above the build line has gone 7 days without a decision (daily.py); false = off
        "judgment_check": bool(r.get("judgment_check", _d("run.judgment_check"))),
        # v0.7 light mode (Pro plans): fewer postings judged per run, the judge model the person picked at setup
        "judge_model": str(r.get("judge_model", _d("run.judge_model")) or ""),
    }


# ---- validation (v0.5, audit bug 3): plain-language problems, never a traceback ---------------------------------------
PACKS_DIR = os.path.join(ENGINE, "registries", "packs")
_PLACEHOLDER = __import__("re").compile(r"^\s*<[^>]*>\s*$")


def is_placeholder(v):
    """True for template values such as "<your name>"."""
    return isinstance(v, str) and bool(_PLACEHOLDER.match(v))


def _or_join(choices):
    """('yes', 'no', 'case-by-case') -> 'yes, no or case-by-case' (how the error sentences list the choices)."""
    choices = list(choices)
    return choices[0] if len(choices) == 1 else ", ".join(choices[:-1]) + " or " + choices[-1]


def _norm_enum(v):
    """How a free-text choice is compared: lower-case, and '-' reads as '_' (location.mode accepts local-only)."""
    return str(v).strip().lower().replace("-", "_")


def validate(cfg=None):
    """Check settings.yaml and return a list of (level, message): level "missing" = a required value is not filled in
    yet (normal while the interview is running), "error" = a value is the wrong kind, out of range, or names something
    that does not exist (always a mistake). Messages are plain English and name the field. [] means fine.
    v1.0 (audit M27): the per-key checks come from SCHEMA (type, range, choices, required); every sentence is the one
    the v0.5-v0.9 code printed, because the skills and the person quote them. The checks that span fields (country vs
    the geo overrides, the thresholds order, salary floor vs target, the v0.9 stay-local guard, pack names, lane and
    education entries, the signals.yaml patterns) are explicit below."""
    import re as _re
    cfg = load() if cfg is None else cfg
    out = []
    err = lambda m: out.append(("error", m))
    miss = lambda m: out.append(("missing", m))
    if not isinstance(cfg, dict) or not cfg:
        return [("missing", f"settings.yaml is empty or not a list of fields ({USER_YAML})")]

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

    def want_list(sec, key, v, list_of=""):
        """True when v is a list; the sentence names what the list holds when the schema says so."""
        if v is not None and not isinstance(v, list):
            err(f"{sec}.{key} should be a list{(' of ' + list_of) if list_of else ''}, or []"); return False
        return isinstance(v, list)

    def check_field(f, d):
        """One SCHEMA field inside section dict d: the "missing" note when required, then the type / range / choices."""
        sec, key = f.section, f.leaf
        v = d.get(key)
        if f.required:
            if v is None or is_placeholder(v) or (v == "" and not f.empty_ok) or v == []:
                miss(f.missing); return
        if f.type == "bool":
            want_bool(sec, d, key)
        elif f.type in ("int", "int|null"):
            lo, hi = f.rng or (None, None)
            want_int(sec, d, key, lo, hi, allow_none=(f.type == "int|null"))
        elif f.type == "float":
            lo, hi = f.rng
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi):
                err(f"{sec}.{key} should be a number between {lo} and {hi}, not {v!r}")
        elif f.type == "regex":
            want_regex(sec, key, v)
        elif f.type in ("list", "list[str]"):
            want_list(sec, key, v, f.list_of)
        elif f.type == "list[regex]":
            if want_list(sec, key, v, f.list_of):
                for pat in v: want_regex(sec, key, pat)
        elif f.type == "list[int]":
            if want_list(sec, key, v, f.list_of):
                for x in v:
                    if isinstance(x, bool) or not isinstance(x, (int, float)):
                        err(f"{sec}.{key} should be a list of numbers, not {v!r}"); break
        elif f.type == "enum":
            if v not in (None, "") and not is_placeholder(v) and _norm_enum(v) not in {_norm_enum(c) for c in f.choices}:
                err(f"{sec}.{key} should be {f.show or _or_join(f.choices)}, not {v!r}")
        elif f.type == "docx":
            if v is not None and not is_placeholder(v) and not str(v).lower().endswith(".docx"):
                err(f"{sec}.{key} should end in .docx, not {v!r}")
        # "str": nothing beyond the missing note (free text)

    def section_fields(name):
        return [f for f in SCHEMA.values() if f.key.startswith(name + ".")]

    def item_fields(name):
        return [f for f in SCHEMA.values() if f.key.startswith(name + "[].")]

    # ---- cross-field checks, one per section, run right after that section's per-key loop ----
    def extra_location(loc):
        c = loc.get("country")
        if c in (None, "") or is_placeholder(c):
            pass   # the "missing" note came from the schema
        elif not isinstance(c, str) or not _re.fullmatch(r"[A-Za-z]{2}", c):
            err(f"location.country should be a two-letter country code such as US, not {c!r}")
        elif c.upper() not in ("US", "CA", "UK") and not loc.get("in_country_regex"):
            err(f"location.country is {c}: for a country other than US / CA / UK the three location patterns "
                "(in_country_regex, in_country_regex_loose, foreign_regex_extra) must be filled in, or every posting counts as inside the country")
        # v0.9 (audit H3): a local-first / stay-local search with the shipped commuting pattern would set aside every
        # non-remote posting forever; refuse until the commuting area is really filled in
        _mode = str(loc.get("mode") or "").lower().replace("-", "_")
        _t1 = str(loc.get("tier1_regex") or "").strip()
        if _mode in ("local_only", "local_first", "unsure") and (_t1 in ("", "Remote") or not loc.get("commutable_metros")):
            err(f"location.mode is {_mode} but the commuting area is not filled in (location.tier1_regex is still the default "
                f"and/or commutable_metros is empty): every job outside 'Remote' would be set aside. Finish setup phase 4.")

    def extra_lanes(lanes_v):
        packs = {os.path.basename(p)[:-5] for p in __import__("glob").glob(os.path.join(PACKS_DIR, "*.json"))}
        list_keys = [f.leaf for f in item_fields("lanes") if f.type == "list"]
        for i, l in enumerate(lanes_v, 1):
            if not isinstance(l, dict):
                err(f"lane {i} should be a block with name / description / packs under it"); continue
            if not l.get("name") or is_placeholder(l.get("name")):
                miss(f"lane {i} has no name")
            for k in list_keys:
                if l.get(k) is not None and not isinstance(l.get(k), list):
                    err(f"lane {i} ({l.get('name', '?')}): {k} should be a list, or []")
            if l.get("priority") is not None: want_bool(f"lane {i}", l, "priority")
            for pk in (l.get("packs") or []) if isinstance(l.get("packs"), list) else []:
                if pk not in packs:
                    err(f"lane {i} ({l.get('name', '?')}) names a job-board pack that does not exist: {pk!r}. Available: {', '.join(sorted(packs))}")

    def extra_thresholds(th):
        a, b_, c_ = th.get("auto_skip_below_rubric"), th.get("commutable_min_rubric"), th.get("build_default_min_rubric")
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b_, c_)) and not (a <= b_ <= c_):
            err(f"thresholds should go up: auto_skip_below_rubric ({a}) <= commutable_min_rubric ({b_}) <= build_default_min_rubric ({c_})")

    def extra_salary(sal):
        f, t = sal.get("floor"), sal.get("target")
        if isinstance(f, (int, float)) and isinstance(t, (int, float)) and not isinstance(f, bool) and f > t:
            err(f"salary.floor ({f}) is above salary.target ({t})")

    def extra_rubric(rb):
        bb = rb.get("b_band")
        if isinstance(bb, list) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in bb) and (len(bb) != 2 or not 0 <= bb[0] <= bb[1] <= 100):
            err(f"rubric.b_band should be two numbers from 0 to 100, low then high (e.g. [30, 70]), not {bb!r}")

    def extra_education(ed):
        for i, e in enumerate(ed, 1):
            if not isinstance(e, dict) or not e.get("institution"):
                err(f"education entry {i} needs institution, dates and line")

    extras = {"location": extra_location, "lanes": extra_lanes, "thresholds": extra_thresholds, "salary": extra_salary,
              "rubric": extra_rubric, "education": extra_education}

    for top in [f for f in SCHEMA.values() if not f.section]:   # the sections, in file order
        v = cfg.get(top.key)
        if top.type == "section":
            if v is None:
                if top.required: miss(top.missing)
                continue
            if not isinstance(v, dict):
                err(f"'{top.key}' should be a section with fields under it, not {type(v).__name__}"); continue
            for f in section_fields(top.key):
                check_field(f, v)
        elif top.type == "list[section]":
            if v is None or v == []:
                if top.required: miss(top.missing)
                continue
            if not isinstance(v, list):
                err(f"{top.key} should be a list{(' of ' + top.list_of) if top.list_of else ''} ({top.hint})"); continue
        if top.key in extras:
            extras[top.key](v)

    # v0.9 (audit M25): a bad pattern in profile/signals.yaml would crash the run at import; say it here instead
    try:
        _sig = signals()
        for _ln, _lv in (_sig.get("lanes") or {}).items():
            for _sec in ("terms", "negatives"):
                for _t in ((_lv or {}).get(_sec) or []):
                    want_regex(f"profile/signals.yaml lanes.{_ln}.{_sec}", "pattern", (_t or {}).get("pattern") if isinstance(_t, dict) else _t)
        for _k, _lst in (_sig.get("priority_patterns") or {}).items():
            for _p in (_lst or []):
                want_regex(f"profile/signals.yaml priority_patterns.{_k}", "pattern", _p)
    except Exception as _e:
        err(f"profile/signals.yaml could not be read: {_e}")
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


def _type_label(f):
    """The "type" column of the schema table."""
    if f.type == "enum":
        return " \\| ".join(c for c in f.choices if c not in ("true", "false"))
    if f.type in ("int", "int|null") and f.rng:
        lo, hi = f.rng
        base = "int or null" if f.type == "int|null" else "int"
        return f"{base} {lo}-{hi}" if hi is not None else f"{base} >= {lo}"
    if f.type == "float" and f.rng:
        return f"number {f.rng[0]}-{f.rng[1]}"
    return {"list[section]": "list of blocks", "section": "section", "list[regex]": "list of regex", "list[int]": "list of int",
            "list[str]": "list of str", "docx": ".docx filename"}.get(f.type, f.type)


def _default_label(f):
    if f.type in ("section", "list[section]"):
        return ""
    if f.default is None:
        return "`null`"
    if f.default == _NEVER:
        return '`""`'
    return "`" + json.dumps(f.default) + "`"


def schema_markdown():
    """Every SCHEMA key as one Markdown table (the `--schema` output; ARCHITECTURE.md embeds it verbatim)."""
    esc = lambda s: str(s).replace("|", "\\|")
    rows = ["| key | type | default | filled in | consumed by | what it does |", "|---|---|---|---|---|---|"]
    for f in SCHEMA.values():
        if f.reserved:
            when = "reserved"
        elif f.required:
            when = f"required (phase {f.phase})" if f.phase else "required"
        else:
            when = f"phase {f.phase}" if f.phase else "optional"
        rows.append(f"| `{f.key}` | {_type_label(f)} | {_default_label(f)} | {when} | {esc(f.consumers)} | {esc(f.doc)} |")
    return "\n".join(rows)


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
    flag = lambda k: bool(t.get(k, _d("targets." + k)))
    return {
        "position_types": sorted(pt),
        "phd_positions": flag("phd_positions") or "phd_positions" in pt,
        "fixed_term_ok": flag("fixed_term_ok") or bool(pt & {"temporary", "seasonal", "fixed_term"}),
        # hourly_ok true -> hourly-paid / high-school-minimum postings are NOT flagged "BELOW LEVEL" by the critic
        "hourly_ok": flag("hourly_ok") or "hourly" in pt,
        "internships_ok": flag("internships_ok") or bool(pt & {"internships", "internship"}),
        "coops_ok": flag("coops_ok") or bool(pt & {"co_ops", "coops", "apprenticeships", "co_op"}),
        "new_grad_ok": flag("new_grad_ok") or bool(pt & {"new_grad", "early_career", "graduate_programs"}),
        "unpaid_ok": flag("unpaid_ok") or bool(pt & {"unpaid", "volunteer", "unpaid_research"}),
        "part_time_ok": flag("part_time_ok") or "part_time" in pt,
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
    if m not in SCHEMA["location.mode"].choices:
        r = str(loc.get("relocation", _d("location.relocation")) or "").strip().lower()
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
        "career_fit": _v("career_fit", _d("scoring.career_fit")),
        "pay": _v("pay", _d("scoring.pay")),
        "remote": _v("remote", _d("scoring.remote")),
    }


# ---- re-pointing the workspace at run time (v1.0, audit M26) ---------------------------------------------------------
def _clear_caches():
    """Forget everything read from the workspace: the next get()/signals()/MODULES[...] reads the current one."""
    load.cache_clear(); signals.cache_clear(); critic_rules.cache_clear(); queries.cache_clear()
    MODULES.reset()


def configure(ws):
    """Point this module at another workspace at run time (tests, the examples, a tool that serves several people).
    Re-points WS and every WS-derived path constant (TRACKING, PROFILE, EVIDENCE, APPLICATIONS, REPORTS, INTAKE, ...,
    SECRETS, USER_YAML, USER_JSON, USER_RULES, SIGNALS_YAML, CRITIC_RULES_YAML, LEXICON_YAML, QUERIES_YAML), exports
    JOBKIT_WORKSPACE for child processes and clears every cache (load(), signals(), critic_rules(), queries(), MODULES).

    Call it BEFORE importing the engine modules. A module that already ran `from userconfig import WS as ROOT` (most of
    them do) keeps its old path: Python copied the value at import, and this function cannot reach into that module.
    Only names looked up through userconfig at call time (get(), path(), thresholds(), location(), MODULES[...]) and
    the module-level constants read as `userconfig.TRACKING` follow the new workspace. Import-time env handling is
    unchanged: $JOBKIT_WORKSPACE still decides the initial WS and a wrong value still exits 2 (v0.9, audit M21)."""
    ws = os.path.abspath(str(ws))
    if not os.path.isdir(ws):
        raise NotADirectoryError(f"configure({ws!r}): not a folder; give the absolute path of a 'My Job Search' folder")
    _apply_workspace(ws)
    os.environ["JOBKIT_WORKSPACE"] = ws   # children inherit the absolute path, as at import
    _clear_caches()
    return ws


if __name__ == "__main__":
    if "--schema" in sys.argv:
        print(schema_markdown()); sys.exit(0)
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
