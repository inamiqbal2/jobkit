"""PRIORITY LANE - the user's declared target job type (never silently discarded before a human sees it).

WHAT THE FLAG DOES (daily.py, rubric.py, critic.py): a priority-lane posting always passes the judgment gate,
is exempt from the sub-40 rubric auto-ledger, and has its never-claim critic flags downgraded to advisory.
Eligibility knockouts are UNAFFECTED. It never auto-applies and never relaxes the honesty gate.

WHERE THE DATA LIVES (nothing field-specific in this file):
  settings.yaml       lanes[].priority: true            -> at least one lane must be flagged for the detector to run
  signals.yaml    priority_patterns:                -> four regex tiers (lists of regex strings, OR-ed)
                    exclude: [...]   domains that are emphatically NOT the lane, whatever else the title says
                    strong:  [...]   unambiguous lane terms (title alone suffices)
                    weak:    [...]   generic title words that count only with an anchor in the text
                    anchor:  [...]   domain words that make a weak title count
Rule (v0.5, audit bug 11): excluded -> False; strong in title -> True; strong in text AND an anchor within 200 characters
of it -> True; weak in title AND an anchor within the first 200 characters of the text, or within 200 characters of a weak
term in the text -> True; else False. (The old "anchor anywhere in 4,000 characters" rule marked 49 of 78 teaching
postings as priority for a chemistry teacher: every school posting mentions "high school" somewhere.)
No priority lane / empty patterns -> is_priority() is always False.
  <jobkit python> lanes.py --test [n]      dry test on up to n saved postings (tracking/jds, default 200): prints "N of M
                                           would be marked priority" with examples, so the person can judge the patterns
                                           before they are kept (onboarding phase 17).
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import signals as _signals, priority_lane_names as _prio

_PP = (_signals().get("priority_patterns") or {}) if _prio() else {}
_NEVER = re.compile(r"(?!x)x")


def _rx(key):
    pats = [str(p) for p in (_PP.get(key) or []) if p]
    return re.compile("(" + "|".join(f"(?:{p})" for p in pats) + ")", re.I) if pats else _NEVER


_EXCLUDE, _STRONG, _WEAK, _ANCHOR = (_rx(k) for k in ("exclude", "strong", "weak", "anchor"))
ENABLED = bool(_prio()) and (_STRONG is not _NEVER or _WEAK is not _NEVER)


NEAR = 200   # characters: an anchor must sit this close to the strong / weak term it is meant to qualify


def _near(rx_term, rx_anchor, text):
    """True when some match of rx_term has an rx_anchor match within NEAR characters of it."""
    for m in rx_term.finditer(text):
        win = text[max(0, m.start() - NEAR): m.end() + NEAR]
        if rx_anchor.search(win):
            return True
    return False


def is_priority(title="", text=""):
    """True when a posting is in the user's declared priority lane (see the module docstring for the rule)."""
    if not ENABLED:
        return False
    t = title or ""
    body = (text or "")[:4000]
    blob = f"{t}\n{body}"
    if _EXCLUDE.search(t) or _EXCLUDE.search(blob[:1500]):
        return False
    if _STRONG.search(t):
        return True
    if _STRONG is not _NEVER and _ANCHOR is not _NEVER and _near(_STRONG, _ANCHOR, blob):
        return True
    if _WEAK.search(t) and _ANCHOR is not _NEVER:
        if _ANCHOR.search(blob[:len(t) + NEAR]) or _near(_WEAK, _ANCHOR, body):
            return True
    return False


def dry_test(n=200):
    """(hits, total, examples_yes, examples_no) over up to n saved postings in tracking/jds (title = first line)."""
    import glob
    from userconfig import JDS
    files = sorted(glob.glob(os.path.join(JDS, "*.txt")), key=os.path.getmtime, reverse=True)[:n]
    hits, yes, no = 0, [], []
    for p in files:
        try:
            raw = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        lines = raw.split("\n", 4)
        title = lines[0].strip() if lines else ""
        body = lines[4] if len(lines) > 4 else raw
        if is_priority(title, body):
            hits += 1; yes.append(title)
        else:
            no.append(title)
    return hits, len(files), yes, no


if __name__ == "__main__":
    if "--test" in sys.argv:
        _n = int(sys.argv[sys.argv.index("--test") + 1]) if len(sys.argv) > sys.argv.index("--test") + 1 and sys.argv[-1].isdigit() else 200
        if not ENABLED:
            print("no priority lane: settings.yaml has no lane with priority: true, or profile/signals.yaml priority_patterns is empty"); sys.exit(0)
        h, m, yes, no = dry_test(_n)
        print(f"priority-lane dry test: {h} of {m} saved postings would be marked priority (never auto-skipped, always hand-judged)")
        for t in yes[:8]: print(f"  YES  {t[:90]}")
        for t in no[:5]: print(f"  no   {t[:90]}")
        if m and h / m > 0.5:
            print("  -> more than half: the patterns are too broad. Move generic words out of `strong`, make `anchor` words specific to the lane.")
    else:
        print(__doc__)


def tag(title="", text=""):
    return "★LANE " if is_priority(title, text) else ""
