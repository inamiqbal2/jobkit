#!/usr/bin/env python3
"""SETUP - the one script Claude runs to get a computer ready for jobkit . Safe to run any number of times.

  <launcher> setup            # full: venv, packages, templates, folders, database, checks, lock, status table
  <launcher> setup --quick    # before a daily run: no installs unless something is missing, no network
  <launcher> setup --unlock   # make system/engine writable (the "modify:" command does this, then re-locks)
  <launcher> setup --lock     # make system/engine read-only again
  <launcher> setup --no-lock  # full setup without locking (development checkouts)

What it does (every step is skipped when already done):
  1. detect the operating system and the Python version (3.11+ required) - plain report if missing
  2. create system/.venv and install system/requirements.txt; requirements-optional.txt only when settings.yaml asks
     (run.indeed_jobspy: true). A .pth file makes system/engine/tools importable by every script run with that Python.
  3. copy every template in the shipped "My Job Search" folder to its live name if absent (settings.yaml, keys.json,
     profile/*.yaml|.md, my-rules.md, tracking/registries/queries.yaml; custom.json starts EMPTY, not from the example)
  4. create intake/, profile/, tracking/, applications/, reports/ and ONBOARDING_STATUS.md (all phases pending)
  5. initialise tracking/state.db through state.conn() and write tracker.csv (the plain-English application tracker)
  6. detect LibreOffice (soffice) and poppler (pdftoppm) for the page checks; say so plainly if absent
  7. run the engine self-checks (userconfig, approved_claims, registries list)
  8. check system/engine against its shipped MANIFEST.sha256 (original vs modified), then lock the engine read-only
  9. print a short status table

Exit code 0 = ready (possibly with optional things missing), 1 = blocked (Python too old / venv could not be made).
Workspace = $JOBKIT_WORKSPACE or <jobkit>/My Job Search. Nothing personal is ever written into system/engine/.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, sys, subprocess, shutil, platform, datetime, json, re
os.environ.setdefault("PYTHONUTF8", "1")   # every child tool prints and writes utf-8, on Windows too

HERE = os.path.dirname(os.path.abspath(__file__))        # <jobkit>/system/engine/tools
ENGINE = os.path.dirname(HERE)                            # <jobkit>/system/engine
SYSTEM = os.path.dirname(ENGINE)                          # <jobkit>/system
JOBKIT = os.path.dirname(SYSTEM)                          # <jobkit>
WORKSPACE_NAME = "My Job Search"
WS = os.path.abspath(os.environ.get("JOBKIT_WORKSPACE") or os.path.join(JOBKIT, WORKSPACE_NAME))
TEMPLATE_WS = os.path.join(JOBKIT, WORKSPACE_NAME)        # where the *.example / *.TEMPLATE files ship
VENV = os.path.join(SYSTEM, ".venv")
WIN = os.name == "nt"
VPY = os.path.join(VENV, "Scripts", "python.exe") if WIN else os.path.join(VENV, "bin", "python")
QUICK = "--quick" in sys.argv
NO_LOCK = "--no-lock" in sys.argv
TODAY = datetime.date.today().isoformat()
sys.path.insert(0, HERE)
import manifest as _manifest                               # engine source lock (MANIFEST.sha256, lock/unlock)
VERSION = _manifest.JOBKIT_VERSION

ROWS = []          # (item, state, note) for the final table
BLOCKED = False
OK, WARN, MISSING, DONE = "ok", "warn", "missing", "done"


def row(item, state, note=""):
    ROWS.append((item, state, note))


def say(msg):
    print(msg, flush=True)


def run(cmd, timeout=900, env=None):
    """Run a command, return (code, stdout+stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


# ---- 1. OS + Python ------------------------------------------------------------------------------
def check_python():
    global BLOCKED
    osname = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(platform.system(), platform.system())
    row("Operating system", OK, f"{osname} {platform.release()}")
    v = sys.version_info
    if v < (3, 11):
        BLOCKED = True
        hint = ("brew install python@3.12   (or the installer at https://www.python.org/downloads/)" if osname == "macOS"
                else "https://www.python.org/downloads/  (Windows: tick 'Add python.exe to PATH')" if osname == "Windows"
                else "sudo apt install python3.12 python3.12-venv   (Debian/Ubuntu)")
        row("Python", MISSING, f"found {v.major}.{v.minor}; need 3.11 or newer. Claude should propose: {hint}")
        say(f"Python {v.major}.{v.minor} is too old (need 3.11+). Proposed install step: {hint}")
        return False
    row("Python", OK, f"{v.major}.{v.minor}.{v.micro} ({sys.executable})")
    return True


# ---- 2. venv + packages --------------------------------------------------------------------------
def venv_healthy():
    if not os.path.exists(VPY):
        return False
    code, _ = run([VPY, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"], timeout=60)
    return code == 0


def ensure_venv():
    global BLOCKED
    if venv_healthy():
        row("Virtual environment (system/.venv)", OK, VPY)
        return True
    if os.path.exists(VENV):
        # a venv that no longer runs (folder moved, Python upgraded): set it aside, never delete it
        aside = f"{VENV}.broken-{TODAY}"
        n = 1
        while os.path.exists(aside):
            n += 1; aside = f"{VENV}.broken-{TODAY}-{n}"
        os.rename(VENV, aside)
        say(f"The old .venv no longer runs; moved it to {os.path.basename(aside)} (you may delete that folder later).")
    say("Creating the Python virtual environment (system/.venv), about a minute...")
    code, out = run([sys.executable, "-m", "venv", VENV], timeout=600)
    if code != 0 or not venv_healthy():
        BLOCKED = True
        row("Virtual environment (system/.venv)", MISSING, f"could not be created: {out.strip()[:200]}")
        return False
    row("Virtual environment (system/.venv)", DONE, VPY)
    return True


BASE_IMPORTS = ["yaml", "docx", "sklearn", "numpy", "scipy", "pypdf", "PIL"]


def packages_present(mods):
    code, out = run([VPY, "-c", "import " + ", ".join(mods)], timeout=120)
    return code == 0, out


def ensure_packages():
    present, _ = packages_present(BASE_IMPORTS)
    if present:
        row("Python packages (requirements.txt)", OK, "all importable")
    else:
        say("Installing the Python packages into system/.venv (this needs the internet, 1-5 minutes)...")
        run([VPY, "-m", "pip", "install", "--quiet", "--upgrade", "pip"], timeout=600)
        code, out = run([VPY, "-m", "pip", "install", "--quiet", "-r", os.path.join(SYSTEM, "requirements.txt")], timeout=1800)
        present, err = packages_present(BASE_IMPORTS)
        if present:
            row("Python packages (requirements.txt)", DONE, "installed")
        else:
            row("Python packages (requirements.txt)", MISSING, f"pip install failed: {(out or err).strip()[-300:]}")
    # optional extras only when the workspace asks for them
    wants_indeed = False
    try:
        if os.path.exists(os.path.join(WS, "settings.yaml")):
            txt = open(os.path.join(WS, "settings.yaml"), encoding="utf-8").read()
            m = re.search(r"^\s*indeed_jobspy:\s*(true|yes)\b", txt, re.M | re.I)
            wants_indeed = bool(m)
    except Exception:
        pass
    if wants_indeed:
        ok, _ = packages_present(["jobspy"])
        if ok:
            row("Optional: Indeed arm (python-jobspy)", OK, "installed (settings.yaml run.indeed_jobspy is on)")
        else:
            say("settings.yaml turns the Indeed arm on; installing python-jobspy (optional, may take a few minutes)...")
            run([VPY, "-m", "pip", "install", "--quiet", "-r", os.path.join(SYSTEM, "requirements-optional.txt")], timeout=1800)
            ok, _ = packages_present(["jobspy"])
            row("Optional: Indeed arm (python-jobspy)", DONE if ok else WARN,
                "installed" if ok else "install failed on this computer; the Indeed arm will be skipped (everything else runs)")
    else:
        row("Optional: Indeed arm (python-jobspy)", OK, "not requested (settings.yaml run.indeed_jobspy is off)")


# ---- 3. templates + folders -------------------------------------------------------------------------
TEMPLATES = [   # (template relative to the shipped My Job Search/, live name relative to the user's workspace)
    ("settings.yaml.example", "settings.yaml"),
    ("keys.json.example", "keys.json"),
    ("profile/signals.yaml.example", "profile/signals.yaml"),
    ("profile/critic_rules.yaml.example", "profile/critic_rules.yaml"),
    ("profile/lexicon.yaml.example", "profile/lexicon.yaml"),
    ("profile/claim_lexicon.yaml.example", "profile/claim_lexicon.yaml"),   # 2026-10-16: equivalence lexicon (starts empty)
    ("profile/approved_claims.yaml.example", "profile/approved_claims.yaml"),
    ("profile/profile_blind.TEMPLATE.md", "profile/profile_blind.md"),
    ("profile/publications.TEMPLATE.md", "profile/publications.md"),
    ("profile/skills-inventory.TEMPLATE.md", "profile/skills-inventory.md"),
    ("my-rules.TEMPLATE.md", "my-rules.md"),
    ("tracking/registries/queries.yaml.example", "tracking/registries/queries.yaml"),
]
# three worked examples of queries.yaml for other lives ship next to the template (not copied; the interview writes the live file):
#   tracking/registries/queries.nurse.yaml.example, queries.software.yaml.example, queries.biologist.yaml.example
EMPTY_CUSTOM = {
    "pack": "custom",
    "description": "Your own target employers (filled during onboarding). Same shape as system/engine/registries/packs/*.json.",
    "boards": [], "workday": [], "hard": {}, "misc": [], "watch": []
}
FOLDERS = ["intake", "intake/_extracted", "profile/evidence", "profile/templates", "tracking/registries", "tracking/jds",
           "tracking/rubric", "applications", "reports"]

PHASES = [
    "0 environment setup (setup.py)",
    "1 welcome and what to expect (and the intake folder: 'read my documents')",
    "2 identity and contact",
    "3 work authorization",
    "4 location, commuting, relocation",
    "5 your field and track, what you are looking for (lanes, targets, exclusions)",
    "6 salary floor and target",
    "7 evidence: one file per job / degree / project",
    "8 skills inventory (hands-on / used / never)",
    "9 publications and presentations (academic / research track only)",
    "10 licenses and certifications",
    "11 teaching and mentoring (academic / research track only)",
    "12 references (academic / research track only)",
    "13 approved claims and never-claims",
    "14 your own rules",
    "15 job boards and target employers",
    "16 optional keys (USAJobs if government jobs interest you; Adzuna)",
    "17 field words for the matcher (signals) and the search terms (queries)",
    "18 first dry run and calibration (20 postings)",
    "19 first live run",
    "20 the daily ritual explained",
]


def ensure_workspace():
    made = []
    for f in FOLDERS:
        p = os.path.join(WS, f)
        if not os.path.isdir(p):
            os.makedirs(p, exist_ok=True); made.append(f)
    copied = []
    for src_rel, dst_rel in TEMPLATES:
        src = os.path.join(TEMPLATE_WS, src_rel); dst = os.path.join(WS, dst_rel)
        if os.path.exists(dst):
            continue
        if not os.path.exists(src):
            row(f"Template {src_rel}", WARN, "shipped template missing; skipped")
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst); copied.append(dst_rel)
    custom = os.path.join(WS, "tracking", "registries", "custom.json")
    if not os.path.exists(custom):
        with open(custom, "w", encoding="utf-8") as f:
            json.dump(EMPTY_CUSTOM, f, indent=1); f.write("\n")
        copied.append("tracking/registries/custom.json (empty)")
    # document templates (statement of purpose etc.) travel with the workspace; copy if the user's folder lacks them
    tdir_src = os.path.join(TEMPLATE_WS, "profile", "templates"); tdir_dst = os.path.join(WS, "profile", "templates")
    if os.path.isdir(tdir_src) and os.path.abspath(tdir_src) != os.path.abspath(tdir_dst):
        for name in os.listdir(tdir_src):
            d = os.path.join(tdir_dst, name)
            if not os.path.exists(d):
                shutil.copyfile(os.path.join(tdir_src, name), d)
    ev_t_src = os.path.join(TEMPLATE_WS, "profile", "evidence", "_TEMPLATE.md"); ev_t_dst = os.path.join(WS, "profile", "evidence", "_TEMPLATE.md")
    if os.path.exists(ev_t_src) and not os.path.exists(ev_t_dst):
        shutil.copyfile(ev_t_src, ev_t_dst)
    in_src = os.path.join(TEMPLATE_WS, "intake", "README.md"); in_dst = os.path.join(WS, "intake", "README.md")
    if os.path.exists(in_src) and not os.path.exists(in_dst):
        shutil.copyfile(in_src, in_dst)
    status = os.path.join(WS, "ONBOARDING_STATUS.md")
    if not os.path.exists(status):
        with open(status, "w", encoding="utf-8") as f:
            f.write(f"# ONBOARDING STATUS (created {TODAY} by setup.py; Claude updates it after every phase)\n\n")
            f.write("Resume rule: the first phase that is not `done` is where the interview continues.\n\n")
            f.write("| phase | status | notes |\n|---|---|---|\n")
            for ph in PHASES:
                st = "done" if ph.startswith("0 ") else "pending"
                f.write(f"| {ph} | {st} | {'setup.py ran ' + TODAY if st == 'done' else ''} |\n")
            f.write("\n## Open questions\n(none yet)\n")
        copied.append("ONBOARDING_STATUS.md")
    row("Workspace folders", DONE if made else OK, WS + (f" (+{len(made)} created)" if made else ""))
    row("Workspace files from templates", DONE if copied else OK,
        ("copied: " + ", ".join(copied)) if copied else "all present (nothing overwritten)")
    # is settings.yaml still the untouched template (placeholders such as <your name>)?
    try:
        uy = open(os.path.join(WS, "settings.yaml"), encoding="utf-8").read()
        m = re.search(r'^\s*name:\s*"?([^"\n]+?)"?\s*(?:#.*)?$', uy, re.M)
        nm = (m.group(1).strip() if m else "")
        if not nm or re.fullmatch(r"<[^>]*>", nm):
            row("settings.yaml", WARN, "still the empty template (no name yet) - the onboarding interview fills it; nothing is searched until then")
        else:
            row("settings.yaml", OK, f"filled for {nm}")
    except Exception as e:
        row("settings.yaml", MISSING, str(e)[:120])


def ensure_pth():
    """system/.venv/.../site-packages/jobkit_engine.pth -> system/engine/tools, so a build script run with the venv
    Python can `from resume_builder import Resume` without computing the engine path (and spaces in the jobkit path
    never matter)."""
    code, out = run([VPY, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], timeout=60)
    if code != 0:
        row("Engine import path (.pth)", WARN, out.strip()[-120:]); return
    site = out.strip().splitlines()[-1]
    pth = os.path.join(site, "jobkit_engine.pth")
    want = HERE + "\n"
    try:
        if os.path.exists(pth) and open(pth, encoding="utf-8").read() == want:
            row("Engine import path (.pth)", OK, pth); return
        with open(pth, "w", encoding="utf-8") as f:
            f.write(want)
        row("Engine import path (.pth)", DONE, pth)
    except OSError as e:
        row("Engine import path (.pth)", WARN, str(e)[:120])


# ---- 5. state.db --------------------------------------------------------------------------------------
def ensure_state_db():
    code, out = run([VPY, "-c", "import sys; sys.path.insert(0, %r); import state; state.conn().close(); print(state.DB)" % HERE],
                    timeout=120, env=dict(os.environ, JOBKIT_WORKSPACE=WS))
    if code == 0:
        row("Application ledger (tracking/state.db)", OK, out.strip().splitlines()[-1] if out.strip() else "ready")
    else:
        row("Application ledger (tracking/state.db)", MISSING, out.strip()[-200:])
    # v0.4: the plain-English tracker the person reads (regenerated after every state change)
    code, out = run([VPY, os.path.join(HERE, "state.py"), "tracker"], timeout=120, env=dict(os.environ, JOBKIT_WORKSPACE=WS))
    if code == 0:
        row("Application tracker (tracker.csv)", OK, out.strip().splitlines()[-1][:100] if out.strip() else "written")
    else:
        row("Application tracker (tracker.csv)", WARN, out.strip()[-160:])


# ---- 5b. active job-board registries (assembled from the selected packs; missing on a fresh folder) ---------------
def ensure_registries():
    env = dict(os.environ, JOBKIT_WORKSPACE=WS)
    reg = os.path.join(WS, "tracking", "registries", "registry.json")
    code, out = run([VPY, os.path.join(HERE, "registries.py"), "list"], timeout=120, env=env)
    selected = [l for l in out.splitlines() if l.startswith("*") and "= selected" not in l] if code == 0 else []
    custom_has = False
    try:
        c = json.load(open(os.path.join(WS, "tracking", "registries", "custom.json"), encoding="utf-8"))
        custom_has = any(c.get(k) for k in ("boards", "workday", "misc", "watch")) or bool(c.get("hard"))
    except Exception:
        pass
    if not selected and not custom_has:
        row("Active job-board lists", WARN, "no packs chosen yet (onboarding phase 15 assembles them; nothing is fetched until then)")
        return
    # never assemble or snapshot boards while the person has not even given a name (the template placeholders)
    try:
        uy = open(os.path.join(WS, "settings.yaml"), encoding="utf-8").read()
        m = re.search(r'^\s*name:\s*"?([^"\n]+?)"?\s*(?:#.*)?$', uy, re.M)
        if not m or re.fullmatch(r"<[^>]*>", m.group(1).strip()):
            row("Active job-board lists", WARN, "settings.yaml is still the empty template - packs are assembled after the interview names them")
            return
    except Exception:
        pass
    if os.path.exists(reg):
        row("Active job-board lists", OK, "assembled (re-run registries.py assemble after changing packs or custom.json)")
        return
    say("Assembling the job-board lists from the selected packs...")
    code, out = run([VPY, os.path.join(HERE, "registries.py"), "assemble"], timeout=300, env=env)
    if code == 0 and os.path.exists(reg):
        run([VPY, os.path.join(HERE, "watch.py"), "--init"], timeout=900, env=env)
        row("Active job-board lists", DONE, "assembled from the selected packs; watch list snapshot taken")
    else:
        row("Active job-board lists", MISSING, out.strip()[-200:])


# ---- 6. LibreOffice + poppler ----------------------------------------------------------------------------
def find_soffice():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
              os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
              r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
              "/usr/lib/libreoffice/program/soffice", "/snap/bin/libreoffice"):
        if os.path.exists(p):
            return p
    return None


def check_page_tools():
    osname = platform.system()
    so = find_soffice(); pt = shutil.which("pdftoppm")
    hint = {"Darwin": "brew install --cask libreoffice && brew install poppler",
            "Windows": "install LibreOffice from https://www.libreoffice.org/download/ (poppler: https://github.com/oschwartz10612/poppler-windows/releases, add its bin folder to PATH)",
            }.get(osname, "sudo apt install libreoffice-writer poppler-utils")
    if so and pt:
        row("Page-count check (LibreOffice + poppler)", OK, f"{so}; {pt}")
    else:
        miss = " and ".join(x for x, p in (("LibreOffice", so), ("poppler", pt)) if not p)
        row("Page-count check (LibreOffice + poppler)", WARN,
            f"{miss} not found: the page-count check will be skipped (documents still build). Claude may propose: {hint}")


# ---- 7. self-checks ---------------------------------------------------------------------------------------
def check_settings():
    """userconfig.validate() in plain words. Wrong values block every mode; values not filled in yet block only --quick
    (a daily run on a half-filled settings.yaml would judge on placeholders) and are a note during the interview."""
    global BLOCKED
    env = dict(os.environ, JOBKIT_WORKSPACE=WS)
    code, out = run([VPY, os.path.join(HERE, "userconfig.py"), "--validate"], timeout=120, env=env)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    errors = [l[len("error: "):] for l in lines if l.startswith("error: ")]
    missing = [l[len("missing: "):] for l in lines if l.startswith("missing: ")]
    if code not in (0, 1):
        row("settings.yaml check", MISSING, "could not be read: " + out.strip()[-160:]); BLOCKED = True; return
    if errors:
        BLOCKED = True
        row("settings.yaml check", MISSING, f"{len(errors)} value(s) wrong - " + errors[0][:110] + (" (+ more below)" if len(errors) > 1 else ""))
        say("settings.yaml has values that cannot be right; fix these (plain words, one per line):")
        for e in errors: say(f"  - {e}")
    elif missing:
        if QUICK:
            BLOCKED = True
            row("settings.yaml check", MISSING, f"{len(missing)} value(s) not filled in yet - the interview must finish first: " + missing[0][:80])
        else:
            row("settings.yaml check", WARN, f"{len(missing)} value(s) not filled in yet (the interview fills them): " + "; ".join(missing)[:120])
    else:
        row("settings.yaml check", OK, "every value is the right kind and in range")


def self_checks():
    env = dict(os.environ, JOBKIT_WORKSPACE=WS)
    code, out = run([VPY, os.path.join(HERE, "userconfig.py")], timeout=120, env=env)
    if code == 0:
        lanes = re.search(r"lanes:\s*(.*)", out)
        row("Engine reads settings.yaml", OK, (lanes.group(0).strip()[:90] if lanes else out.strip().splitlines()[-1][:90]))
    else:
        row("Engine reads settings.yaml", MISSING, out.strip()[-200:])
    check_settings()
    code, out = run([VPY, os.path.join(HERE, "approved_claims.py")], timeout=120, env=env)
    if code == 0:
        bul = re.search(r"named bullets:\s*(\d+)", out); pend = re.search(r"pending \(unusable\):\s*(\d+)", out)
        row("Approved claims load", OK, f"{bul.group(1) if bul else '?'} approved bullets, {pend.group(1) if pend else '?'} pending")
    else:
        row("Approved claims load", MISSING, out.strip()[-200:])
    code, out = run([VPY, os.path.join(HERE, "registries.py"), "list"], timeout=120, env=env)
    if code == 0:
        sel = [l.strip() for l in out.splitlines() if l.startswith("*") and "= selected" not in l]
        row("Job-board packs", OK if sel else WARN, (f"{len(sel)} selected: " + ", ".join(s.split()[1] for s in sel)) if sel else "none selected yet (onboarding phase 15)")
    else:
        row("Job-board packs", MISSING, out.strip()[-200:])
    # secrets: report presence, never values
    try:
        sec = json.load(open(os.path.join(WS, "keys.json"), encoding="utf-8"))
        usa = bool(sec.get("usajobs_key")) and bool(sec.get("usajobs_email"))
        adz = bool(sec.get("adzuna_id")) and bool(sec.get("adzuna_key"))
        row("USAJobs key (optional)", OK if usa else OK, "present" if usa else "not set (federal postings idle; phase 16 offers it when government jobs interest the person)")
        row("Adzuna key (optional)", OK if adz else OK, "present" if adz else "not set (optional; arm stays off)")
    except Exception as e:
        row("USAJobs key", WARN, f"keys.json unreadable: {str(e)[:80]}")
    # onboarding progress
    st = os.path.join(WS, "ONBOARDING_STATUS.md")
    try:
        txt = open(st, encoding="utf-8").read()
        done = len(re.findall(r"^\|\s*\d+ [^|]*\|\s*done\b", txt, re.M)); total = len(re.findall(r"^\|\s*\d+ [^|]*\|", txt, re.M))
        nxt = re.search(r"^\|\s*(\d+ [^|]*?)\s*\|\s*(?!done)[a-z]", txt, re.M)
        row("Onboarding progress", OK if done >= total and total else WARN,
            f"{done}/{total} phases done" + (f"; next: {nxt.group(1).strip()}" if nxt else " - complete"))
    except Exception:
        row("Onboarding progress", WARN, "ONBOARDING_STATUS.md not readable")


# ---- 7b. engine source lock -----------------------------------------------------------------------------------
def git(*args):
    code, out = run(["git", "-C", JOBKIT] + list(args), timeout=60)
    return (out.strip() if code == 0 else None)


def engine_status():
    """MANIFEST.sha256 check (original vs modified) + the git view, then lock the engine read-only."""
    c = _manifest.check()
    line = _manifest.status_line()
    if not c["has_manifest"]:
        row("Engine", WARN, line)
    elif c["ok"]:
        row("Engine", OK, line)
    else:
        ex = (c["changed"] + c["added"] + c["missing"])[:3]
        row("Engine", WARN, line + " - e.g. " + ", ".join(ex))
    tag = git("tag", "--list", f"original-{VERSION}")
    if git("rev-parse", "--is-inside-work-tree") == "true":
        branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
        mods = git("rev-list", "--count", f"original-{VERSION}..modified") if tag and git("rev-parse", "--verify", "-q", "modified") else None
        note = f"branch {branch}; tag original-{VERSION} " + ("present" if tag else "MISSING (development checkout)")
        if mods and mods != "0":
            note += f"; {mods} commit(s) on branch 'modified' (modifications and reverts)"
        row("Program history (git)", OK if tag else WARN, note)
    else:
        import shutil as _sh   # v0.9 (audit M22): say which of the two it is
        if not _sh.which("git"):
            row("Program history (git)", WARN, "git is not installed: 'modify:' and 'revert to original' need it (https://git-scm.com/downloads)")
        else:
            row("Program history (git)", WARN, "not a git repository: 'modify:' and 'revert to original' need the shipped .git folder")
    if NO_LOCK:
        row("Engine lock", WARN, "--no-lock: system/engine left writable")
    else:
        n = _manifest.lock()
        row("Engine lock", OK, f"system/engine is read-only ({n} entries); 'modify: <what>' unlocks it for an approved change")


# ---- 8. table ------------------------------------------------------------------------------------------------
def table():
    w = max(len(r[0]) for r in ROWS) + 1
    say("\n" + "=" * 100)
    say(f"jobkit setup {'(quick check) ' if QUICK else ''}- {TODAY} (program {VERSION})")
    say("=" * 100)
    for item, state, note in ROWS:
        mark = {OK: "[ok]     ", DONE: "[done]   ", WARN: "[note]   ", MISSING: "[MISSING]"}[state]
        say(f"{mark} {item.ljust(w)} {note}")
    say("=" * 100)
    if BLOCKED:
        say("BLOCKED: fix the [MISSING] line(s) above, then run setup again.")
    else:
        bad = [r for r in ROWS if r[1] == MISSING]
        say("Python to use from now on: " + VPY)
        say("Ready." if not bad else "Ready with problems: " + "; ".join(r[0] for r in bad))


def main():
    if "--unlock" in sys.argv:
        n = _manifest.unlock(); say(f"system/engine unlocked ({n} entries writable). Re-lock with --lock or by running setup.py."); sys.exit(0)
    if "--lock" in sys.argv:
        n = _manifest.lock(); say(f"system/engine locked ({n} entries read-only). " + _manifest.status_line()); sys.exit(0)
    say(f"jobkit setup (program {VERSION}): workspace = {WS}")
    if not check_python():
        table(); sys.exit(1)
    if not ensure_venv():
        table(); sys.exit(1)
    ensure_packages()
    ensure_pth()
    ensure_workspace()
    ensure_state_db()
    ensure_registries()
    check_page_tools()
    self_checks()
    engine_status()
    table()
    sys.exit(0 if not BLOCKED else 1)


if __name__ == "__main__":
    main()
