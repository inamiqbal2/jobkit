#!/usr/bin/env python3
"""Onboarding phase 19 test build for the FABRICATED Jordan Example workspace (one-page nursing resume, jobkit v0.3, 2026-10-11).
Posting: Denver Health - Registered Nurse (RN), Medical ICU (MICU), Rotating (a REAL public posting found by the daily run through
the Workday board that discover_boards.py registered; the JD text is a run artifact and is not committed).
This runner executes the application's own build script (applications/DenverHealth_RegisteredNurse_MedicalICU/build.py), which
imports every tuple / bullet / skills line from approved_claims.yaml by name. Run:
  JOBKIT_WORKSPACE=system/examples/jordan_example system/.venv/bin/python system/examples/jordan_example/build_test_example.py"""
import os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("JOBKIT_WORKSPACE", HERE)
runpy.run_path(os.path.join(HERE, "applications", "DenverHealth_RegisteredNurse_MedicalICU", "build.py"), run_name="__main__")
