"""v1.0 (audit M28): ONE eligibility-regex module. The citizenship / clearance / negation patterns and the "is this match
negated?" guard live in eligibility.py; match.py, screen_minquals.py and critic.py import them. These cases pin the shared
semantics and prove the three callers agree.
Run: <jobkit python> -m unittest system/engine/tools/tests/test_eligibility.py"""
import json, os, subprocess, sys, tempfile, textwrap, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.join(os.path.dirname(os.path.dirname(TOOLS)), "examples", "jordan_example")   # system/examples/jordan_example


def run(code, ws=WS):
    out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + textwrap.dedent(code)],
                         env=dict(os.environ, JOBKIT_WORKSPACE=ws), capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(out.stderr[-2500:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def closed_workspace():
    """A copy of the example settings with BOTH work-authorization classes closed, so every gate is live."""
    import yaml
    ws = tempfile.mkdtemp(); s = yaml.safe_load(open(os.path.join(WS, "settings.yaml")))
    s["work_authorization"]["clearance_possible"] = False; s["work_authorization"]["citizenship_only_roles_open"] = False
    yaml.safe_dump(s, open(os.path.join(ws, "settings.yaml"), "w")); os.makedirs(os.path.join(ws, "tracking"))
    return ws


# the six sentences every caller must read the same way: (text, is it a knockout for a person with both classes closed)
SHARED = [("No security clearance required.", False),
          ("Must hold an active security clearance.", True),
          ("U.S. citizenship required.", True),
          ("Must be a U.S. citizen or lawful permanent resident.", False),
          ("Clearance: none required.", False),
          ("Active security clearance required, no exceptions.", True)]


class TestSharedPatterns(unittest.TestCase):
    def _hits(self, texts, rx="CLEARANCE_MENTION_RX"):
        return run(f"""
        import json, eligibility as e
        print(json.dumps([e.negated_hit(e.{rx}, t) for t in {texts!r}]))""")

    def test_negated_clearance_is_not_a_hit(self):
        self.assertEqual(self._hits(["No security clearance required", "Clearance: none required",
                                     "Security Clearance: None required", "Certain positions may require a security clearance"]),
                         [False, False, False, False])

    def test_real_clearance_is_a_hit(self):
        self.assertEqual(self._hits(["Must hold an active security clearance", "Must hold an active security clearance"], "CLEARANCE_RX"), [True, True])

    def test_negation_after_the_match_in_another_clause_does_not_fail_open(self):
        # audit M20: the clause AFTER the match ends at , ( . ; or a line break, so "no exceptions" never reaches the match's
        # own clause; a colon is deliberately NOT a boundary because "Clearance: none required" is the common negated form
        self.assertEqual(self._hits(["Security clearance required, no exceptions", "Security clearance required (no exceptions)",
                                     "Security clearance required. No remote work."]), [True, True, True])

    def test_citizenship(self):
        self.assertEqual(self._hits(["U.S. citizenship required", "U.S. citizen or lawful permanent resident",
                                     "Must be a U.S. citizen or green card holder", "U.S. citizens only", "Only U.S. Citizens may apply"], "CITIZEN_ONLY_RX"),
                         [True, False, False, True, True])

    def test_switch_is_a_never_matching_pattern(self):
        # the example workspace opens both classes -> the switched names are NEVER_RX and short-circuit
        r = run("""
        import json, eligibility as e
        print(json.dumps([e.CITIZEN_ONLY is e.NEVER_RX, e.CLEARANCE is e.NEVER_RX, e.negated_hit(e.CLEARANCE, "active security clearance required")]))""")
        self.assertEqual(r, [True, True, False])
        r = run("""
        import json, eligibility as e
        print(json.dumps([e.CITIZEN_ONLY is e.CITIZEN_ONLY_RX, e.CLEARANCE is e.CLEARANCE_RX, e.negated_hit(e.CLEARANCE, "active security clearance required")]))""", closed_workspace())
        self.assertEqual(r, [True, True, True])

    def test_permanent_resident_guard_admits_a_green_card_holder(self):
        import yaml
        ws = closed_workspace(); s = yaml.safe_load(open(os.path.join(ws, "settings.yaml")))
        s["work_authorization"]["permanent_resident"] = True; yaml.safe_dump(s, open(os.path.join(ws, "settings.yaml"), "w"))
        r = run("""
        import json, eligibility as e
        t = "Only U.S. Citizens, Green Card holders, and political asylees are eligible to apply."
        print(json.dumps([e.negated_hit(e.CITIZEN_ONLY, t), e.eligibility_hit(e.CITIZEN_ONLY, t), e.eligibility_hit(e.CITIZEN_ONLY, "U.S. citizens only. No exceptions.")]))""", ws)
        self.assertEqual(r, [True, False, True])

    def test_one_us_state_table(self):
        r = run("""
        import json, eligibility as e, geo
        print(json.dumps([e._US_STATES == geo.US_STATES, geo._US_STATES == geo.US_STATES, "D\\\\.?C" in geo.US_STATES,
                          e._us_primary("Washington, D.C."), e._us_primary("San Juan, PR; London"), e._us_primary("London, UK")]))""")
        self.assertEqual(r, [True, True, True, True, True, False])


class TestThreeCallersAgree(unittest.TestCase):
    """match (corpus drop), screen_minquals (INELIGIBLE) and critic (HOLD) read the same sentence the same way."""

    def test_match_screen_critic_same_verdict(self):
        ws = closed_workspace(); jd_dir = tempfile.mkdtemp()
        r = run(f"""
        import json, io, contextlib, os
        import match, screen_minquals as s, critic, eligibility as e
        out = []
        for i, (t, _) in enumerate({SHARED!r}):
            m = bool(match._elig_hit(match.CITIZEN_ONLY, t) or match._elig_hit(match.CLEARANCE, t))
            s.fetch = lambda u, _t=t: _t
            v = s.screen(dict(url=f"https://x.example/{{i}}", title="Analyst", loc="Denver, CO"))
            sc = v["verdict"] == "INELIGIBLE"
            p = os.path.join({jd_dir!r}, f"jd{{i}}.txt")
            open(p, "w").write("Analyst\\nDenver, CO\\nhttps://x.example/\\n\\n" + t)
            with contextlib.redirect_stdout(io.StringIO()): c = critic.review(p)["hold"]
            out.append([m, sc, c, e.negated_hit(e.CITIZEN_ONLY, t) or e.negated_hit(e.CLEARANCE, t)])
        print(json.dumps(out))""", ws)
        for (text, expected), (m, sc, c, el) in zip(SHARED, r):
            self.assertEqual([m, sc, c, el], [expected] * 4, text)

    def test_public_names_are_aliases(self):
        r = run("""
        import json, match, screen_minquals as s, critic, eligibility as e
        print(json.dumps([match._elig_hit is e.eligibility_hit, s._elig_hit is e.eligibility_hit, match.CITIZEN_ONLY is e.CITIZEN_ONLY,
                          match.CLEARANCE is e.CLEARANCE, match._NEG_WORDS is e.NEGATION_RX, s._NEG is e.NEGATION_RX, critic._NEG is e.NEGATION_RX,
                          callable(s._hit), hasattr(critic, "Verdict") and callable(critic.review)]))""")
        self.assertEqual(r, [True] * 9)


if __name__ == "__main__":
    unittest.main()
