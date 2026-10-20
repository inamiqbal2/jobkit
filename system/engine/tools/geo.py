#!/usr/bin/env python3
"""GEO - the one place the engine knows what "inside the user's country" looks like.

Every discovery arm assumes ONE country of search (settings.yaml location.country). The original project
hard-coded the United States in four places with four slightly different regexes; those four are now
rows of the COUNTRIES table below plus the shared foreign-place list in eligibility.py.

Per country the table holds:
  in_loc        strict test on a LOCATION STRING: "City, ST" / country name / Remote (but not Remote-<elsewhere>)
                -> used by match.py on the corpus (where every posting has a location field)
  in_loc_loose  the same plus ATS placeholders ("3 Locations") and any ", XX" code
                -> used by sweep.py (Workday) and daily.py (hard-ATS arm), whose locations are often placeholders
  foreign_extra country-specific foreign-place cues appended to eligibility.NONUS_TEXT (cities, scripts)

A user can override any row from settings.yaml:
  location.in_country_regex, location.in_country_regex_loose, location.foreign_regex_extra
Unknown country code -> permissive defaults (everything is "inside") plus a printed warning, so the
engine still runs; the onboarding skill then asks for the regexes.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import location as _loc_cfg

# v1.0 (audit M28): the ONE US state/territory code list - eligibility.py (US-primary site test, foreign-city state lookahead)
# imports it; its own copy lacked D.C. and the territories, so "San Juan, PR" / "Washington, D.C." read as non-US there.
US_STATES = (r"AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|"
             r"RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|D\.?C\.?"
             # 2026-10-09: U.S. territories and freely-associated locations count as inside the United States
             r"|PR|GU|VI|AS|MP")
_US_STATES = US_STATES   # historical private name
_US_TERRITORIES = r"Puerto Rico|\bGuam\b|Saipan|Northern Mariana|American Samoa|Pago Pago|U\.?S\.? Virgin Islands|St\.? (?:Thomas|Croix|John)\b|Tutuila|Rota\b|Tinian"
_REMOTE_NOT_ELSEWHERE = r"Remote(?!\s*[-–(,]?\s*(?:Germany|UK|U\.K\.|Europe|EMEA|Canada|India|APAC|Netherlands|Ireland|Israel|Japan|Korea))"

COUNTRIES = {
    "US": {
        "name": "United States",
        # match.py (2026-10-01 audit H4): state codes only after a comma; Remote-<non-US> excluded
        "in_loc": rf",\s*({_US_STATES})\b|United States|\bUSA?\b|{_US_TERRITORIES}|{_REMOTE_NOT_ELSEWHERE}",
        # sweep.py / daily.py hard-ATS arm: Workday "N Locations" placeholders count as inside; any ", XX" code too
        "in_loc_loose": rf"United States|USA|\bUS\b|,\s*({_US_STATES})\b|{_US_TERRITORIES}|,\s*[A-Z]{{2}}\b|Remote|Locations",
        "foreign_extra": "",
    },
    "CA": {
        "name": "Canada",
        "in_loc": r",\s*(AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)\b|\bCanada\b|Remote(?!\s*[-–(,]?\s*(?:US|USA|UK|Europe|EMEA|India|APAC))",
        "in_loc_loose": r"\bCanada\b|,\s*(AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)\b|,\s*[A-Z]{2}\b|Remote|Locations",
        "foreign_extra": r"United States|\bUSA?\b",
    },
    "UK": {
        "name": "United Kingdom",
        "in_loc": r"\bUnited Kingdom\b|\bU\.?K\.?\b|\bEngland\b|\bScotland\b|\bWales\b|Northern Ireland|London|Manchester|Cambridge|Oxford|Edinburgh|Bristol|Leeds|Glasgow|Remote(?!\s*[-–(,]?\s*(?:US|USA|Germany|Europe|EMEA|India|APAC|Canada))",
        "in_loc_loose": r"\bUnited Kingdom\b|\bU\.?K\.?\b|\bEngland\b|\bScotland\b|\bWales\b|Remote|Locations",
        "foreign_extra": r"United States|\bUSA?\b|,\s*(" + _US_STATES + r")\b",
    },
}


def country_code():
    return (str(_loc_cfg().get("country") or "US")).strip().upper()


def _row():
    cc = country_code()
    row = COUNTRIES.get(cc)
    if row is None:
        print(f"geo: no built-in geography table for country '{cc}'. Set location.in_country_regex / "
              f"in_country_regex_loose / foreign_regex_extra in settings.yaml; until then every location counts as inside.",
              file=sys.stderr)
        row = {"name": cc, "in_loc": r".", "in_loc_loose": r".", "foreign_extra": ""}
    loc = _loc_cfg()
    return {
        "name": row["name"],
        "in_loc": loc.get("in_country_regex") or row["in_loc"],
        "in_loc_loose": loc.get("in_country_regex_loose") or row["in_loc_loose"],
        "foreign_extra": loc.get("foreign_regex_extra") or row["foreign_extra"],
    }


_R = _row()
IN_COUNTRY = re.compile(_R["in_loc"], re.I)
IN_COUNTRY_LOOSE = re.compile(_R["in_loc_loose"], re.I)
FOREIGN_EXTRA = re.compile(_R["foreign_extra"], re.I) if _R["foreign_extra"] else None
COUNTRY_NAME = _R["name"]


def in_country(loc):
    """Strict: True when a location string reads as inside the user's country (corpus arm)."""
    return bool(IN_COUNTRY.search(loc or "Remote"))


def in_country_loose(loc):
    """Loose: placeholders and bare ", XX" codes count as inside (Workday / hard-ATS arms)."""
    return bool(IN_COUNTRY_LOOSE.search(loc or ""))


if __name__ == "__main__":
    print("country:", country_code(), COUNTRY_NAME)
    for t in ("Austin, TX", "3 Locations", "Remote", "Remote - Germany", "Toronto, ON", "Bangalore, India", "Mayaguez, PR", "Mangilao, Guam", "Honolulu, HI"):
        print(f"  {t!r:22} strict={in_country(t)!s:5} loose={in_country_loose(t)}")
