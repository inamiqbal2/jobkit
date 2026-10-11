#!/usr/bin/env python3
"""Onboarding phase 19 test build for the FABRICATED Taylor Example workspace (jobkit smoke test, 2026-10-08).
Posting: Redwood Materials - Power Systems Engineer, Energy Storage (a real public posting; the JD text is not
committed). Every tuple / bullet / skills line is imported from approved_claims.yaml; nothing is typed in here that the
YAML does not already say. Run: JOBKIT_WORKSPACE=system/examples/taylor_example system/.venv/bin/python system/examples/taylor_example/build_test_example.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "engine", "tools"))
from resume_builder import Resume
from approved_claims import (FRU, FRU_BULLETS, GRIDSENSE, GRIDSENSE_BULLETS, THESIS, THESIS_BULLETS,
                             SUMMARIES, TENURE_SHORT, POWER, TOOLS, DATA, PUBS_SHORT, PROJECTS, audit)
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applications", "RedwoodMaterials_PowerSystemsEngineer_EnergyStorage")
# CRITIC: CLEAR. ENTRY SCORER: FRU + GRIDSENSE + THESIS (the only 3-entry combination; min 3 honored).
# ANGLE (approved claims only): power-system modeling in PSS/E (operated) with PSCAD vendor models USED (hedged, never
# "built"); interconnection screens against IEEE 1547; the validation harness (GridSense) as the "validates models" ask.
# HONEST GAPS kept off the page: no PSCAD model authorship, no BESS controls design, no transmission-level studies.
r = Resume(location_line="Open to relocation")
r.summary("Power Systems Engineer candidate: " + SUMMARIES["power-systems"])
r.job(*FRU, bullets=FRU_BULLETS)
r.job(*GRIDSENSE, bullets=GRIDSENSE_BULLETS)          # frozen entry: bullets verbatim from the YAML
r.job(*THESIS, bullets=THESIS_BULLETS)
r.projects_heading("Selected Projects")
r.project(*PROJECTS["scada_import"])
r.education()
r.skills([POWER, TOOLS, DATA, PUBS_SHORT])
p = r.save(os.path.join(APP, "Resume_Taylor_Example.docx"))
hits = audit(p); print(("AUDIT CLEAN " if not hits else f"AUDIT FAIL {hits} ") + p)
