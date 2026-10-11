#!/usr/bin/env python3
"""ENTRY SCORER - quantitative check on experience-entry selection.

Employer-side person-job-fit models score resume<->JD alignment with text embeddings; no published
applicant-side system selects WHICH verified experiences to present. This tool scores every candidate
entry-combination against a JD so selection is measured, reproducible, and testable against human
judgment - v1 uses TF-IDF cosine (classic IR baseline; upgrade path: sentence-transformer embeddings).

Entries come from My Job Search/profile/approved_claims.yaml -> experience[] (key, org, role, bullets,
keywords, always_include). The anchor entries (always_include: true) are in every combination.

Usage: <jobkit python> entry_scorer.py <jd.txt>     # rank the entries + best 3-5-entry combos
It never CHOOSES alone: judgment can override, but overrides get logged in the build script."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sys, itertools, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import approved_claims as _ac

# Canonical text for each entry = role + org + bullets + keywords.
ENTRIES = {}
ANCHORS = []
for _e in _ac.EXPERIENCE:
    _k = _e["key"]
    _bl = _e.get("bullets", {}) or {}
    _texts = list(_bl.values()) if isinstance(_bl, dict) else list(_bl)
    ENTRIES[_k] = " ".join([str(_e.get("role", "")), str(_e.get("org", ""))] + [str(x) for x in _texts] + [str(_e.get("keywords", ""))])
    if _e.get("always_include"):
        ANCHORS.append(_k)


def score(jd_text):
    names = list(ENTRIES)
    if not names:
        raise RuntimeError("no experience entries in profile/approved_claims.yaml")
    docs = [ENTRIES[n] for n in names] + [jd_text]
    tf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    X = tf.fit_transform(docs)
    sims = cosine_similarity(X[:-1], X[-1]).ravel()
    per = dict(zip(names, sims))
    combos = []
    others = [n for n in names if n not in ANCHORS]
    for k in range(max(1, 3 - len(ANCHORS)), min(len(others), 5 - len(ANCHORS)) + 1):
        for combo in itertools.combinations(others, k):
            sel = tuple(ANCHORS) + combo
            combos.append((sum(per[n] for n in sel) / len(sel), sel))
    combos.sort(reverse=True)
    return per, combos


if __name__ == "__main__":
    jd = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
    jd = re.sub(r"<[^>]+>", " ", jd)
    per, combos = score(jd)
    print("PER-ENTRY relevance (TF-IDF cosine vs JD):")
    for n, v in sorted(per.items(), key=lambda x: -x[1]):
        print(f"  {n:10} {v:.3f}")
    print(f"\nTOP entry-combinations (anchors always included: {', '.join(ANCHORS) or 'none'}):")
    for v, sel in combos[:5]:
        print(f"  {v:.3f}  {' + '.join(sel)}")
