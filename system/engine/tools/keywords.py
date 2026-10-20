#!/usr/bin/env python3
"""KEYWORDS — JD-vs-resume keyword coverage with claim-boundary awareness (2026-09-03).
Fixes the naive n-gram extractor problem: uses the user's curated LEXICON (profile/lexicon.yaml), expands
synonyms, and classifies every JD term as PRESENT / MISSING-CLAIMABLE (add it verbatim, it's
true) / MISSING-NEVER (honest gap — report, never add).
Usage: <jobkit python> tools/keywords.py <resume.docx> <jd.txt>"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import PROFILE as _PROFILE, load_yaml as _load_yaml

# ── LEXICON: term -> (synonyms that count as present, claim status) ─────────────────────────────────────────
# claim: 'YES' = claimable verbatim; 'NEVER' = never-claim (Article II); 'UTIL' = claimable only with the hedged
# phrasing from approved_claims.yaml -> hedged_phrases; 'ASK' = pending the user's confirmation.
# The user's lexicon is WORKSPACE data: profile/lexicon.yaml {term: {syn: [..], claim: YES|NEVER|UTIL|ASK}}, seeded
# by the onboarding skill from the skills inventory (CORE/WORKING -> YES, used-not-operated -> UTIL, NEVER CLAIM ->
# NEVER). Without it the engine falls back to this SMALL GENERIC list of terms any professional can claim; every
# field term a JD uses is then simply not classified (reported as "not in lexicon"), never guessed.
GENERIC_LEX = {
 "written communication":   (["communication skills", "communicate", "writing skills"], "YES"),
 "technical documentation": (["documentation", "technical writing", "technical reports", "write reports"], "YES"),
 "presentations":           (["presentation", "present findings", "present results"], "YES"),
 "cross-functional":        (["cross functional", "cross-functional collaboration", "cross-functional teams"], "YES"),
 "collaboration":           (["collaborate", "collaborative", "team player", "teamwork"], "YES"),
 "problem solving":         (["problem-solving", "troubleshoot"], "YES"),
 "attention to detail":     (["detail-oriented", "detail oriented"], "YES"),
 "time management":         (["prioritiz", "manage multiple", "deadlines"], "YES"),
 "continuous improvement":  (["process improvement"], "ASK"),
 "project management":      (["manage projects", "project plans", "project schedule"], "ASK"),
 "stakeholder management":  (["stakeholders"], "ASK"),
 "mentoring":               (["mentor", "coach", "train junior"], "ASK"),
 "data analysis":           (["analyze data", "data-driven", "data driven"], "ASK"),
 "Microsoft Office":        (["Excel", "PowerPoint", "Word"], "ASK"),
 "Python":                  ([], "ASK"),
 "SQL":                     ([], "ASK"),
 "Git":                     (["version control"], "ASK"),
}
LEX = dict(GENERIC_LEX)
_lexp = os.path.join(_PROFILE, "lexicon.yaml")
LEX_SOURCE = "generic fallback (profile/lexicon.yaml missing)"
if os.path.exists(_lexp):
    _user = _load_yaml(_lexp) or {}
    if _user:
        LEX = {str(t): (list((v or {}).get("syn", []) or []), str((v or {}).get("claim", "ASK"))) for t, v in _user.items()}
        LEX_SOURCE = _lexp
def _hedged():
    """approved_claims.yaml hedged_phrases, read at call time (v1.0, audit M26: importing this module reads no file)."""
    try:
        import claims_loader as _cl
        return list(_cl.load().HEDGED_PHRASES or [])
    except Exception:
        return []

import re as _re
# 2026-09-12 red-team defect 6: hyphen/space and singular/plural are normalized when matching, so
# "irradiation-effects" == "irradiation effects" and "test plan" == "test plans". Acronyms (all-caps
# words) and words under 4 letters are matched literally.
def _word_pat(w):
    if w.isupper() or len(w) < 4:
        return _re.escape(w.lower())
    lw = w.lower()
    if lw.endswith("ies") and len(lw) > 4:
        return _re.escape(lw[:-3]) + r"(?:y|ies)"
    if lw.endswith("sis"):
        return _re.escape(lw[:-3]) + r"s[ie]s"
    if lw.endswith("es") and lw[:-2].endswith(("s", "x", "z", "ch", "sh")):
        base = lw[:-2]
    elif lw.endswith("s") and not lw.endswith("ss"):
        base = lw[:-1]
    else:
        base = lw
    return _re.escape(base) + r"(?:e?s)?"
def _norm_pat(needle):
    words = [w for w in _re.split(r"[\s\-]+", needle.strip()) if w]
    return r"[\s-]+".join(_word_pat(w) for w in words)
def _kw_hit(needle, text_lower):
    # word-boundary-aware: 'TEM' must not match 'system'; hyphen/space and plural normalized
    pat = _norm_pat(needle)
    if _re.search(r'(?<![a-z0-9])' + pat + r'(?![a-z0-9])', text_lower): return True
    # 2026-09-12: lexicon stems ('microscop', 'calibrat', 'nanoindent') never matched under the strict
    # boundary; allow a trailing word continuation for lowercase single-word needles >= 6 chars.
    if ' ' not in needle and '-' not in needle and len(needle) >= 6 and needle.islower():
        return _re.search(r'(?<![a-z0-9])' + pat + r'[a-z]*(?![a-z0-9])', text_lower) is not None
    return False
def _found(term, syns, text):
    tl = text.lower()
    if _kw_hit(term, tl): return True
    return any(_kw_hit(s, tl) for s in syns)

_SKIP_LINE = _re.compile(r"^\s*(#|SOURCE:|APPLY:|URL:|FIT:|Verified|Posted|=+|-+\s*$)", re.I)
_LEVEL = _re.compile(r"\b(?:Senior|Sr|Staff|Principal|Lead|Junior|Jr|Associate|I{1,3}|IV|V|\d)\b\.?", re.I)   # 2026-10-16: "Sr." / "Jr." swallow their dot
def jd_title(jtext):
    """The JD's job title: first non-empty line after the '# FIT' header (or other header lines);
    'Title | Company | ...' lines are cut at the first '|'."""
    for line in jtext.splitlines():
        if not line.strip() or _SKIP_LINE.match(line):
            continue
        return line.split("|")[0].strip()
    return ""
# 2026-09-14 (Relativity build): two defects in title_present, both MATCHER bugs \u2014 no claim boundary
# and no lexicon class is touched by this fix.
#  (a) the core split required WHITESPACE BEFORE the delimiter, so a comma-qualified title
#      ("... Engineer, Powder Bed Fusion") \u2014 the common Greenhouse form \u2014 never split and the 'near'
#      path could never fire. Comma/colon/paren now split with or without a preceding space; the
#      DASH still requires one, so "Non-Destructive Evaluation Engineer" is not cut at its hyphen.
#  (b) "&" and "and" were not equivalent, so a JD's "Materials & Processes Engineer" missed a resume
#      that says "materials and process engineer" \u2014 the exact form charters/build.md audit rule 1
#      mandates for the summary opener.
_AMP = _re.compile(r"\s*&\s*")
def _deamp(s):
    return _AMP.sub(" and ", s)
def title_present(title, rtext):
    """'exact' if the normalized title is in the resume, 'near' if it matches after stripping level
    words / trailing ' - qualifier' / parentheses, else None. '&' == 'and'."""
    if not title: return None
    tl = rtext.lower()
    tl_amp = _deamp(tl)
    def _hit(needle):
        return _kw_hit(needle, tl) or _kw_hit(_deamp(needle), tl_amp)
    if _hit(title): return "exact"
    core = _re.split(r"(?:\s+[-\u2013\u2014]|\s*[:,(])\s*", title)[0]
    core = _LEVEL.sub(" ", core)
    core = _re.sub(r"\s+", " ", core).strip(" -,.")
    if core and core.lower() != title.lower() and _hit(core): return f"near: {core}"
    return None

def check(resume_path, jd_path):
    import docxtext; rtext = " ".join(p.text for p, _ in docxtext.paragraphs(resume_path))   # v0.8: all text channels
    jtext = open(jd_path, encoding="utf-8", errors="ignore").read()
    if "==========" in jtext: jtext = jtext.split("==========", 1)[1]   # v0.2: the job-card header (SOURCE/APPLY/FIT) is not JD text
    in_jd = {t: (s, c) for t, (s, c) in LEX.items() if _found(t, s, jtext)}
    present, add, never, ask = [], [], [], []
    for t, (s, c) in sorted(in_jd.items()):
        if _found(t, s, rtext):
            # synonym-only presence still risks failing a verbatim recruiter search
            verbatim = _kw_hit(t, rtext.lower())
            present.append((t, "verbatim" if verbatim else "SYNONYM ONLY — consider adding exact term"))
        elif c == "YES":   add.append(t)
        elif c == "NEVER": never.append(t)
        elif c in ("UTIL", "ASK"): ask.append((t, c))
    title = jd_title(jtext)
    tp = title_present(title, rtext)
    print(f"TITLE PRESENT: {'yes' if tp else 'no'} ({tp or 'missing'}) -- JD title: {title!r}")
    print(f"JD lexicon terms found: {len(in_jd)}   (lexicon: {LEX_SOURCE})")
    print("\n-- PRESENT:")
    for t, note in present: print(f"  + {t}  ({note})")
    print("\n-- MISSING but CLAIMABLE - the person HAS these; use an approved line that carries the term, a confirmed lexicon equivalent, or confirm a new sentence:")
    for t in add: print(f"  + {t}")
    HEDGED = _hedged()
    print("\n-- MISSING, classification UTIL/ASK - add with correct phrasing or confirm with the user:")
    for t, c in ask: print(f"  ? {t} [{c}]" + (f"  (UTIL = only with a hedged phrase: {' / '.join(HEDGED)})" if c == "UTIL" and HEDGED else ""))
    print("\n-- MISSING and NEVER-CLAIM - honest gaps, do NOT add:")
    for t in never: print(f"  x {t}")
    return add, ask, never

def lexicon_swaps(resume_path, jd_path, category=None):
    """2026-10-16: confirmed equivalence-lexicon swaps worth making for this posting - the resume uses the approved wording,
    the posting uses a confirmed equivalent. Advisory: the build may use the posting's wording; the audit accepts it."""
    from claim_lexicon import for_category, _pat
    try:
        import docxtext; rt = docxtext.text(resume_path)
    except Exception:
        rt = open(resume_path, encoding="utf-8", errors="ignore").read() if os.path.exists(resume_path) else ""
    jt = open(jd_path, encoding="utf-8", errors="ignore").read()
    es = for_category(category)
    print(f"\n-- EQUIVALENCE LEXICON ({len(es)} confirmed entr{'y' if len(es)==1 else 'ies'}" + (f", category {category}" if category else "") + "):")
    n = 0
    for e in es:
        if not _pat(e["approved"]).search(rt):
            continue
        for q in e["equivalents"]:
            if _pat(q).search(jt) and not _pat(e["approved"]).search(jt):
                print(f"  ~ the posting says {q!r}; the resume says {e['approved']!r} - the confirmed equivalent may be used"); n += 1
    if not n:
        print("  (no swaps apply)")

if __name__ == "__main__":
    _args = [a for a in sys.argv[1:] if not a.startswith("--category")]
    _cat = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--category=")), None)
    if "--category" in sys.argv and sys.argv.index("--category") + 1 < len(sys.argv):
        _cat = sys.argv[sys.argv.index("--category") + 1]; _args = [a for a in _args if a != _cat]
    check(_args[0], _args[1])
    lexicon_swaps(_args[0], _args[1], _cat)
