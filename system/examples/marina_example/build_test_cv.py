#!/usr/bin/env python3
"""Onboarding phase 19 test build for the FABRICATED Marina Example workspace (academic CV mode, 2026-10-09).
Posting: University of Georgia Marine Institute - GCE-LTER Field Research Technician in Coastal Ecosystems (a REAL public
posting found by the ES_JOBS_NET archive feed; JD text is saved next to this script's output and is git-ignored).
Every line of the CV and every sentence of the statement is imported from approved_claims.yaml; nothing is typed here
that the YAML does not already say. Run:
  JOBKIT_WORKSPACE=system/examples/marina_example system/.venv/bin/python system/examples/marina_example/build_test_cv.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "engine", "tools"))
from resume_builder import AcademicCV
from approved_claims import (SUMMARIES, TENURE, B_ERI_WQ, B_ERI_SURVEYS, B_ERI_SFM, B_ERI_TRAINING, B_ERI_BLEACH,
                             B_THESIS_STATS, B_THESIS_PUB, B_KEYS_BOAT, CV_SKILLS, CV_CERTIFICATIONS, PROJECTS, audit)
from userconfig import get as _cfg, work_auth as _work_auth
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applications", "UGA_MarineInstitute_FieldResearchTechnician_GCE-LTER")
# CRITIC: CLEAR. ENTRY SCORER: ERI + THESIS + KEYS (the only 3-entry combination; anchor ERI).
# ANGLE (approved claims only): the posting's daily work is water quality, soils and wetland field sampling, small-boat
# work, GIS and data analysis at a marine institute field station -> lead with the transferable field-biology summary,
# keep the coral-specific depth in the research section. HONEST GAPS kept off the page: no USCG captain's license, no
# drone licence, no soils/wetland-plant experience (the job card says so).
cv = AcademicCV(location_line="Open to relocation")
cv.standard(summary="Research technician candidate: " + SUMMARIES["field-biology-transferable"])
p = cv.save(os.path.join(APP, _cfg("build.cv_filename", "CV.docx")))
hits = audit(p); print(("AUDIT CLEAN " if not hits else f"AUDIT FAIL {hits} ") + p)

# ---- research statement (profile/templates/research_statement.TEMPLATE.md), composed ONLY of approved sentences ----
from docx import Document
from docx.shared import Pt
d = Document(); d.styles["Normal"].font.name = "Calibri"; d.styles["Normal"].font.size = Pt(11)
name = _cfg("identity.name"); d.add_heading(f"{name} - Research Statement", level=1)
d.add_paragraph("Research technician candidate, GCE-LTER Field Research Technician in Coastal Ecosystems, University of Georgia Marine Institute.")
d.add_heading("Summary", level=2)
d.add_paragraph(SUMMARIES["field-biology-transferable"]); d.add_paragraph("Experience: " + TENURE + ".")
d.add_heading("Past and current research", level=2)
d.add_paragraph("Coral-reef monitoring and restoration program, Example Reef Institute (2023 - present):")
for b in (B_ERI_SURVEYS, B_ERI_WQ, B_ERI_SFM, B_ERI_TRAINING, B_ERI_BLEACH): d.add_paragraph(b, style="List Bullet")
d.add_paragraph("M.S. thesis, Example Pacific University (2021 - 2023):")
for b in (B_THESIS_STATS, B_THESIS_PUB): d.add_paragraph(b, style="List Bullet")
d.add_paragraph("Florida Keys coral nursery seasons (2020 - 2021):")
d.add_paragraph(B_KEYS_BOAT, style="List Bullet")
d.add_heading("Methods I operate", level=2)
for lab, txt in CV_SKILLS.values(): d.add_paragraph(f"{lab}: {txt}")
d.add_heading("Certifications", level=2)
for c in CV_CERTIFICATIONS: d.add_paragraph(c, style="List Bullet")
d.add_heading("Data management", level=2)
d.add_paragraph(PROJECTS["cover_qc"][0] + ": " + PROJECTS["cover_qc"][1])
d.add_paragraph("Work authorization: " + _work_auth()["resume_line"] + ".")
sp = os.path.join(APP, "Statement_Marina_Example.docx"); d.save(sp)
hits = audit(sp); print(("AUDIT CLEAN " if not hits else f"AUDIT FAIL {hits} ") + sp)
