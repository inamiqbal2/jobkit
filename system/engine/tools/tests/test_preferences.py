"""v0.7 regression: the person's own answers decide position types, location handling and what the judges score.
Each case writes a throwaway workspace (settings.yaml only) and runs the engine modules in a fresh interpreter, so no
module-level state leaks between people.
Run: <jobkit python> -m unittest system/engine/tools/tests/test_preferences.py"""
import json, os, subprocess, sys, tempfile, textwrap, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE = """
identity: {name: "Test Person", first_name: "Test", email: "t@example.com", phone: "555", city_state: "Pittsburgh, PA"}
work_authorization: {resume_line: "U.S. Citizen", citizenship_only_roles_open: true, clearance_possible: true,
                     export_controlled_open: true, sponsorship_needed: false}
lanes: [{name: "mech", description: "mechanical engineering", example_titles: ["Mechanical Engineer"], priority: true, packs: []}]
"""


def run(settings, code):
    with tempfile.TemporaryDirectory() as ws:
        with open(os.path.join(ws, "settings.yaml"), "w") as f:
            f.write(textwrap.dedent(BASE) + textwrap.dedent(settings))
        env = dict(os.environ, JOBKIT_WORKSPACE=ws)
        out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + textwrap.dedent(code)],
                             env=env, capture_output=True, text=True)
        if out.returncode:
            raise AssertionError(out.stderr[-2000:])
        return json.loads(out.stdout.strip().splitlines()[-1])


TITLES = ["Mechanical Engineering Intern - Summer 2027", "Co-op: Manufacturing Engineering", "New Grad Mechanical Engineer",
          "Mechanical Engineer II", "Temporary Lab Assistant"]
ELIG = "import eligibility as e, json; print(json.dumps({t: bool(e.ELIG.search(t)) for t in %r}))" % TITLES


class TestPositionTypes(unittest.TestCase):
    def test_student_seeking_internships_keeps_them(self):
        r = run("targets: {track: industry, position_types: [internships, co_ops, new_grad]}\n", ELIG)
        self.assertFalse(r[TITLES[0]], "internship dropped although the student asked for internships")
        self.assertFalse(r[TITLES[1]], "co-op dropped although asked for")
        self.assertFalse(r[TITLES[2]], "new-grad program dropped although asked for")
        self.assertTrue(r[TITLES[4]], "temporary kept although not asked for")

    def test_experienced_person_sets_them_aside(self):
        r = run("targets: {track: industry, position_types: [full_time]}\n", ELIG)
        self.assertTrue(all(r[t] for t in TITLES[:3]))
        self.assertFalse(r[TITLES[3]])

    def test_grad_gate_follows_new_grad_answer(self):
        code = "import critic, json; print(json.dumps([c[0][:9] for c in critic._GENERIC]))"
        self.assertNotIn("GRAD-GATE", run("targets: {position_types: [new_grad]}\n", code))
        self.assertIn("GRAD-GATE", run("targets: {position_types: [full_time]}\n", code))


class TestLocationAndScoring(unittest.TestCase):
    def test_modes_and_old_relocation_mapping(self):
        code = "from userconfig import location_mode; import json; print(json.dumps(location_mode()))"
        self.assertEqual(run('location: {country: US, relocation: "no"}\n', code), "local_only")
        self.assertEqual(run('location: {country: US, relocation: "case-by-case"}\n', code), "local_first")
        self.assertEqual(run('location: {country: US, mode: "unsure"}\n', code), "unsure")

    def test_fit_first_judges_ignore_location_and_career_when_asked(self):
        code = "import rubric, json; print(json.dumps(rubric.PROMPT_HEADER))"
        h = run('location: {country: US, mode: fit_first}\nscoring: {career_fit: "no"}\n', code)
        self.assertNotIn('"location": n', h)
        self.assertNotIn('"career": n', h)
        self.assertIn('"skills": n', h)
        self.assertIn("where the job is", h)

    def test_default_judges_score_location_and_career(self):
        code = "import rubric, json; print(json.dumps(rubric.PROMPT_HEADER))"
        h = run('location: {country: US, mode: local_first}\n', code)
        self.assertIn('"location": n', h)
        self.assertIn('"career": n', h)

    def test_other_country_kept_only_when_accepted(self):
        code = "import eligibility as e, json; print(json.dumps([e.non_us('Toronto, ON'), e.non_us('Berlin, Germany')]))"
        self.assertEqual(run('location: {country: US, other_countries: [CA]}\n', code), [False, True])
        self.assertEqual(run('location: {country: US}\n', code), [True, True])
        self.assertEqual(run('location: {country: US, other_countries: [any]}\n', code), [False, False])

    def test_location_skip_guard_follows_mode(self):
        def guard(settings, score):
            code = f"""
            import decide, json
            decide._score_now = lambda cu: {score}
            import rubric; rubric.best_recent = lambda u, days=14: None
            ok, msg = decide.skip_guard("https://example.com/job/1", "location: outside the commuting area")
            print(json.dumps(ok))"""
            return run(settings, code)
        self.assertTrue(guard('location: {country: US, mode: local_only}\n', 85))       # stay local: their own reason
        self.assertFalse(guard('location: {country: US, mode: fit_first}\n', 55))       # fit first: never for location alone
        self.assertTrue(guard('location: {country: US, mode: local_first, away_bar: 70}\n', 55))    # below the build line
        self.assertFalse(guard('location: {country: US, mode: local_first, away_bar: 70}\n', 66))   # 60-69: the person decides
        self.assertFalse(guard('location: {country: US, mode: local_first, away_bar: 70}\n', 75))   # above their moving bar
        self.assertFalse(guard('location: {country: US, mode: unsure}\n', 62))          # unsure: ask, never skip


if __name__ == "__main__":
    unittest.main()
