#!/usr/bin/env python3
"""FUNNEL - the small rules every arm of the pipeline shares (v0.8, code audit M10).

They used to live in three to five copies across daily.py, sweep.py, screen_minquals.py, rubric.py and match.py and had
started to drift. One definition each:

    band(age_days)        -> "FRESH" (<= 7 d) | "RECENT" (<= 14 d) | "OPEN"
    BAND_ORDER            -> sort key for the bands (fresh first)
    tier(loc)             -> "1" commutable / remote | "2" nearby | "3" everywhere else   (settings.yaml location.tier1/2_regex)
    stub_text(text)       -> True when a saved posting is too thin, or reads as site navigation, to judge on
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import location as _loc_cfg

BAND_ORDER = {"FRESH": 0, "RECENT": 1, "OPEN": 2}


def band(age_days):
    try:
        a = int(age_days)
    except (TypeError, ValueError):
        return "OPEN"
    return "FRESH" if a <= 7 else ("RECENT" if a <= 14 else "OPEN")


_L = _loc_cfg()
T1 = re.compile(_L.get("tier1_regex") or r"Remote", re.I)
T2 = re.compile(_L.get("tier2_regex") or r"(?!x)x", re.I)


def tier(loc):
    loc = loc or ""
    return "1" if T1.search(loc) else ("2" if T2.search(loc) else "3")


_QUAL = re.compile(r"(qualificat|responsib|requirement|years? of experience|degree in|bachelor|master|ph\.?d|you will|what you)", re.I)


def stub_text(t):
    """A posting under ~700 characters of body, or with no qualifications / responsibilities language, cannot be judged."""
    t = t or ""
    body = t.split("==========")[-1] if "==========" in t else t
    body = re.sub(r"\s+", " ", body).strip()
    return len(body) < 700 or not _QUAL.search(body)
