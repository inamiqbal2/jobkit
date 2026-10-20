#!/usr/bin/env python3
"""APPROVED CLAIMS - the build script's view of My Job Search/profile/approved_claims.yaml (jobkit refactor 2026-10-08).

The original module was a hand-written Python file of one person's constants (experience tuples,
bullet strings, skills lines, publication line, forbidden terms). In jobkit the SAME content is DATA
the user owns: profile/approved_claims.yaml (see My Job Search/profile/approved_claims.yaml.example).

Back-compat: build scripts do `from approved_claims import <ENTRY_KEY>, <BULLET_NAME>, PUBS, ...`.
This module serves those names from the YAML so existing build-script patterns keep working:
  - experience[].key          -> <KEY> = (org, dates, role, loc)
  - experience[].bullets      -> <BULLET_NAME> = text   and  <KEY>_BULLETS = [texts]
  - skills_lines.<LABEL>      -> <LABEL> = (label, text)
  - publications.line / short -> PUBS, PUBS_SHORT
  - tenure.line / short       -> TENURE, TENURE_SHORT
  - projects.<key>            -> PROJECTS[key] = (title, bullet)
  - entry_variants.<NAME>     -> <NAME> = (org, dates, role, loc)   (same employer, different title read)
  - bullet_bank.<NAME>        -> <NAME> = text                      (approved bullets not tied to one entry)
  - constants.<NAME>          -> <NAME> = text or (label, text)     (approved phrasings)
  - never_claims.forbidden_terms -> FORBIDDEN
Everything is also reachable as CLAIMS (the raw dict). Nothing here is person-specific.

v1.0 (audit M26): importing this module reads NOTHING. The YAML is parsed on the first call of load() (cached for the
process; claims_loader holds the code) or on the first attribute access - `from approved_claims import ERMC` and
`approved_claims.EXPERIENCE` both go through the module __getattr__ below, which calls load(). The reserved-name
refusal (ReservedClaimName, v0.8 H7) therefore fires on that first use - before any document is built or audited -
and no longer on `import`, so a tool can be imported, py_compiled and self-tested on a bare checkout. Engine modules
call load() once per function and read the returned Claims; the attribute form exists for build scripts.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import APPROVED_CLAIMS_YAML
import claims_loader as _cl
from claims_loader import Claims, ReservedClaimName, load, reload, DATA_NAMES, _APPROVED_KEYS, _norm


def loaded():
    """True when a real approved_claims.yaml is present (the engine refuses to build without one)."""
    return load().loaded()


def approved_texts():
    """EVERY string the YAML approves, normalized - the audit's traceability set (audit_claims)."""
    return load().approved_texts()


def __getattr__(name):
    """PEP 562: a YAML name (entry key, bullet, constant, skills label) or an engine table (EXPERIENCE, FORBIDDEN, ...)
    is served from load() on first use. Dunder / private lookups stay plain AttributeErrors so importlib, unittest and
    hasattr() probes never trigger a file read."""
    if name.startswith("_"):
        raise AttributeError(name)
    c = load()
    if name in c.exports:
        return c.exports[name]
    if name in DATA_NAMES:
        return getattr(c, name)
    if not c.loaded():
        # ImportError, not AttributeError: `from approved_claims import ERMC` would otherwise replace this sentence with
        # Python's "cannot import name" and the person would never read WHY (the file is missing).
        raise ImportError(f"approved_claims has no name {name!r}: " + c.missing_sentence(), name="approved_claims")
    raise AttributeError(f"approved_claims has no name {name!r}: it is not an entry key, bullet name, constant or "
                         f"skills label in {c.path} (and not one of the engine's tables).")


def audit(path):
    """Fail loudly if a built resume contains a forbidden claim. Delegates to audit_claims.check
    (never/retired/operator/frozen/work-auth/banned-word checks) and returns its problem list.
    v1.0 (audit M26): audit_claims sits ABOVE this module (it imports claims_loader, never approved_claims), so this
    late import is a one-way edge up the dependency order, not a cycle."""
    try:
        import audit_claims as _strict
        return _strict.check(path)
    except Exception as _e:
        return [f"strict audit unavailable: {_e}"]


if __name__ == "__main__":
    try:
        c = load()
    except ReservedClaimName as e:
        print(str(e), file=sys.stderr); sys.exit(2)
    print("approved_claims.yaml:", APPROVED_CLAIMS_YAML, "(loaded)" if c.loaded() else "(MISSING - run onboarding)")
    print("experience keys:", list(c.ENTRY))
    print("named bullets:", len(c.BULLETS), "| frozen entries:", list(c.FROZEN))
    print("skills lines:", list(c.SKILLS_LINES))
    print("PUBS:", c.PUBS)
    print("FORBIDDEN:", c.FORBIDDEN)
    print("RETIRED patterns:", len(c.RETIRED), "| pending (unusable):", len(c.PENDING))
    if c.CV: print("cv sections:", {k: (len(v) if isinstance(v, (list, dict)) else 1) for k, v in c.CV.items()})
