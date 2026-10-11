#!/usr/bin/env python3
"""jobkit build (daily ritual 2026-10-11) - DenverHealth_RegisteredNurse_MedicalICU (FABRICATED Jordan Example claims, REAL posting).
Every tuple / bullet / skills line is imported from approved_claims.yaml; nothing is typed here that the YAML does not approve.
CRITIC: CLEAR (level/band advisory only: the posting's years bar is "less than 1 year", below the tenure line - no tenure line printed).
ENTRY SCORER: ERMC + ECH + BSN (the only 3-entry combination; anchor ERMC; min 3 honored).
ANGLE: the posting names CRRT, IABP, VAD and ECLS as unit equipment -> lead with the MICU entry, CRRT bullet (hands-on) and the
hedged ECMO/IABP bullet (bedside RN only). HONEST GAPS kept off the page and on the job card: IABP / ECLS circuits were never
operated; rotating days/nights (Jordan prefers days); VAD patients never cared for.
Run: JOBKIT_WORKSPACE=<workspace> system/.venv/bin/python <this file>"""
import sys, os
JOBKIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))   # <jobkit>
sys.path.insert(0, os.path.join(JOBKIT, "engine", "tools"))
from resume_builder import Resume
from approved_claims import (ERMC, ECH, BSN, B_ERMC_CARE, B_ERMC_TTM, B_ERMC_CRRT, B_ERMC_ECMO, B_ERMC_PRECEPT, B_ERMC_SEPSIS,
                             B_ERMC_CHARGE, B_ECH_CARE, B_ECH_TELE, B_ECH_SKIN, B_ECH_PRECEPT, B_BSN_PRACTICUM, B_BSN_CAPSTONE,
                             SUMMARIES, PROJECTS, CLINICAL, DEVICES, TEACHING, CREDENTIALS, audit)
from userconfig import get as _cfg
APP = os.path.dirname(os.path.abspath(__file__))
r = Resume(location_line="Denver, CO")                      # commutable -> the metro name, never "local"
r.summary("Medical ICU registered nurse candidate: " + SUMMARIES["icu-staff-nurse"])
r.job(*ERMC, bullets=[B_ERMC_CARE, B_ERMC_CRRT, B_ERMC_TTM, B_ERMC_ECMO, B_ERMC_PRECEPT, B_ERMC_CHARGE])
r.job(*ECH, bullets=[B_ECH_CARE, B_ECH_TELE, B_ECH_SKIN, B_ECH_PRECEPT])
r.job(*BSN, bullets=[B_BSN_PRACTICUM, B_BSN_CAPSTONE])
r.projects_heading("Unit Education & Governance")
r.project(*PROJECTS["sepsis_education"])
r.project(*PROJECTS["practice_council"])
r.education()
r.skills([CREDENTIALS, CLINICAL, DEVICES, TEACHING])
p = r.save(os.path.join(APP, _cfg("build.resume_filename", "Resume.docx")))
hits = audit(p); print(("AUDIT CLEAN " if not hits else f"AUDIT FAIL {hits} ") + p)
