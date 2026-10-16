#!/usr/bin/env python3
"""EQUIVALENCE LEXICON (2026-10-16). Wordings the PERSON confirmed mean the same thing for them.

Why: the audit accepts a resume line only when it equals an approved claim word for word. That keeps every line true, but it
also means a resume cannot say "benchmark models" when the person's approved claim says "challenger models" and the posting
uses the first. The lexicon is the honest bridge: the person confirms, once, that a posting's wording is equally true of
their own work; from then on a build may use either wording, and the audit maps the equivalent back to the approved wording
before it compares.

Workspace file: profile/claim_lexicon.yaml (shape: My Job Search/profile/claim_lexicon.yaml.example)
    entries:
      - approved: "challenger models"          # wording that appears inside an approved claim
        equivalents: ["benchmark models"]      # wordings the person confirmed are equally true of their work
        categories: []                         # optional: lanes / job categories where the swap reads naturally ([] = any)
        confirmed: "2026-10-16"                # REQUIRED - the date the person said yes; entries without it are ignored
Rules: an equivalent is a substitution of WORDS, never a new claim; never-claims are checked on the raw resume text by
audit_claims.py, so a swap can never smuggle in a forbidden term; an empty or missing file changes nothing.

Usage: <jobkit python> claim_lexicon.py            list the confirmed entries
       <jobkit python> claim_lexicon.py "<line>"   show the line after mapping equivalents back to approved wording
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as _WS

PATH = os.path.join(_WS, "profile", "claim_lexicon.yaml")
_CACHE = None


def load():
    """Confirmed entries only: [{approved, equivalents, categories, confirmed}]."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _CACHE = []
    if not os.path.exists(PATH):
        return _CACHE
    try:
        import yaml
        d = yaml.safe_load(open(PATH, encoding="utf-8")) or {}
    except Exception as e:
        print(f"claim_lexicon: could not read {PATH}: {e}", file=sys.stderr)
        return _CACHE
    for e in d.get("entries") or []:
        if not isinstance(e, dict):
            continue
        ap = str(e.get("approved") or "").strip()
        eq = [str(x).strip() for x in (e.get("equivalents") or []) if str(x or "").strip()]
        if ap and eq and str(e.get("confirmed") or "").strip():
            _CACHE.append(dict(approved=ap, equivalents=eq, categories=[str(c) for c in (e.get("categories") or [])],
                               confirmed=str(e["confirmed"])))
    return _CACHE


def _pat(w):
    return re.compile(r"(?<![\w-])" + re.escape(w).replace(r"\ ", r"\s+") + r"(?![\w-])", re.I)


def canonical(text):
    """The text with every confirmed equivalent replaced by its approved wording (longest equivalents first)."""
    out = text or ""
    pairs = sorted(((q, e["approved"]) for e in load() for q in e["equivalents"]), key=lambda p: -len(p[0]))
    for q, ap in pairs:
        out = _pat(q).sub(ap, out)
    return out


def for_category(category=None):
    """Entries usable for a lane / category (an entry with no categories is usable everywhere)."""
    return [e for e in load() if not category or not e["categories"] or category in e["categories"]]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(canonical(sys.argv[1]))
    else:
        es = load()
        if not es:
            print(f"claim_lexicon: no confirmed entries ({PATH})")
        for e in es:
            print(f"{e['approved']!r} == {', '.join(repr(q) for q in e['equivalents'])}"
                  + (f"  [{', '.join(e['categories'])}]" if e["categories"] else "") + f"  confirmed {e['confirmed']}")
