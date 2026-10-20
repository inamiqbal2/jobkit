"""v1.0 regression (code audit M29 + the v0.9 'rejected me' crash): the three CLIs accept exactly the forms the skills use,
exit with the statuses in exitcodes.py, and `outcome rejected` classifies the note (TIMING / MERIT) without crashing.
Each case runs in a throwaway workspace. Run: <jobkit python> -m unittest system/engine/tools/tests/test_cli_v10.py"""
import json, os, sqlite3, subprocess, sys, tempfile, textwrap, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = """
identity: {name: "Test Person", first_name: "Test", email: "t@example.com", phone: "555", city_state: "Pittsburgh, PA"}
work_authorization: {resume_line: "U.S. Citizen", citizenship_only_roles_open: true, clearance_possible: true,
                     export_controlled_open: true, sponsorship_needed: false}
location: {country: US, mode: fit_first}
lanes: [{name: "mech", description: "mechanical engineering", example_titles: ["Mechanical Engineer"], priority: false, packs: []}]
"""


class CLI(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.ws, "tracking"))
        with open(os.path.join(self.ws, "settings.yaml"), "w") as f:
            f.write(textwrap.dedent(SETTINGS))
        self.env = dict(os.environ, JOBKIT_WORKSPACE=self.ws)

    def run_tool(self, tool, *args):
        r = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], env=self.env, capture_output=True, text=True, cwd=self.ws)
        return r.returncode, r.stdout + r.stderr

    def test_decide_forms_and_codes(self):
        code, out = self.run_tool("decide.py", "--help"); self.assertEqual(code, 0); self.assertIn("usage:", out)
        code, out = self.run_tool("decide.py"); self.assertEqual(code, 2, "no arguments = REFUSED with the usage text")
        code, out = self.run_tool("decide.py", "https://x.example/j/1", "FOO", "r"); self.assertEqual(code, 2); self.assertIn("decision must be", out)
        code, out = self.run_tool("decide.py", "https://x.example/j/1?utm_source=li", "WATCH", "waiting for the posting to reopen")
        self.assertEqual(code, 0); self.assertIn("logged: WATCH https://x.example/j/1", out)
        code, out = self.run_tool("decide.py", "--list", "5"); self.assertEqual(code, 0); self.assertIn("WATCH", out)
        self.assertNotIn("Traceback", out)

    def test_state_applied_then_rejected_classifies_timing_and_merit(self):
        code, out = self.run_tool("state.py", "applied", "Acme Robotics", "Position=Mechanical Engineer"); self.assertEqual(code, 0, out)
        code, out = self.run_tool("state.py", "outcome", "Acme Robotics", "rejected", "the position was filled internally")
        self.assertEqual(code, 0, out); self.assertNotIn("Traceback", out)
        c = sqlite3.connect(os.path.join(self.ws, "tracking", "state.db"))
        self.assertEqual(c.execute('select "Reject Type" from applications where Company="Acme Robotics"').fetchone()[0], "TIMING")
        self.run_tool("state.py", "applied", "Beta Labs", "Position=Analyst")
        self.run_tool("state.py", "outcome", "Beta Labs", "rejected", "they went with another candidate with more experience")
        self.assertEqual(c.execute('select "Reject Type" from applications where Company="Beta Labs"').fetchone()[0], "MERIT")
        self.run_tool("state.py", "applied", "Gamma Co")
        self.run_tool("state.py", "outcome", "Gamma Co", "rejected")
        self.assertEqual(c.execute('select "Reject Type" from applications where Company="Gamma Co"').fetchone()[0], "UNKNOWN")

    def test_state_unknown_employer_is_exit_1_not_a_crash(self):
        code, out = self.run_tool("state.py", "outcome", "Nobody Inc", "rejected")
        self.assertEqual(code, 1); self.assertIn("say 'I applied to Nobody Inc' first", out); self.assertNotIn("Traceback", out)
        code, out = self.run_tool("state.py"); self.assertEqual(code, 0, "bare state.py = stats")

    def test_rubric_help_and_bare(self):
        code, out = self.run_tool("rubric.py", "--help"); self.assertEqual(code, 0); self.assertIn("prep-b", out)
        code, out = self.run_tool("rubric.py"); self.assertEqual(code, 0); self.assertIn("RUBRIC", out)


if __name__ == "__main__":
    unittest.main()
