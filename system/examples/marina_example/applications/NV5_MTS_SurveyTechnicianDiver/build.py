#!/usr/bin/env python3
"""jobkit build (daily ritual 2026-10-09) - NV5_MTS_SurveyTechnicianDiver. Every line imported from approved_claims.yaml; nothing typed here that
the YAML does not approve. CRITIC: CLEAR. ENTRY SCORER: ERI + THESIS + KEYS (the only 3-entry combination; anchor ERI).
# ANGLE: scientific-diving survey technician (marine field surveys, lab sample processing, data management) -> the home-lane
# summary leads (AAUS diver, benthic surveys). HONEST GAPS (card only): altitude / cold-water diving, own full dive kit, consulting
# deliverables; no commercial diving.
Run: JOBKIT_WORKSPACE=<workspace> system/.venv/bin/python <this file>"""
import sys, os
JOBKIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))   # <jobkit>
sys.path.insert(0, os.path.join(JOBKIT, "engine", "tools"))
from resume_builder import AcademicCV
from approved_claims import SUMMARIES, audit
from userconfig import get as _cfg
APP = os.path.dirname(os.path.abspath(__file__))
cv = AcademicCV(location_line=_cfg("build.location_line_default", "Open to relocation"))
cv.standard(summary='Survey technician candidate: ' + SUMMARIES['coral-reef-research'])
p = cv.save(os.path.join(APP, _cfg("build.cv_filename", "CV.docx")))
hits = audit(p); print(("AUDIT CLEAN " if not hits else f"AUDIT FAIL {hits} ") + p)
