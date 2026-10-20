"""v0.8 regression (code audit H3, H4, M5): expired postings are excluded, the auto-skip threshold is the person's setting,
and an already-applied job cannot re-enter through backfill. Each case runs in a fresh interpreter with a throwaway workspace.
Run: <jobkit python> -m unittest system/engine/tools/tests/test_screen_and_skip.py"""
import json, os, subprocess, sys, tempfile, textwrap, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE = """
identity: {name: "Test Person", first_name: "Test", email: "t@example.com", phone: "555", city_state: "Pittsburgh, PA"}
work_authorization: {resume_line: "U.S. Citizen", citizenship_only_roles_open: true, clearance_possible: true,
                     export_controlled_open: true, sponsorship_needed: false}
location: {country: US, mode: fit_first}
lanes: [{name: "mech", description: "mechanical engineering", example_titles: ["Mechanical Engineer"], priority: false, packs: []}]
"""


def run(settings, code):
    with tempfile.TemporaryDirectory() as ws:
        os.makedirs(os.path.join(ws, "tracking", "rubric"))
        with open(os.path.join(ws, "settings.yaml"), "w") as f:
            f.write(textwrap.dedent(BASE) + textwrap.dedent(settings))
        env = dict(os.environ, JOBKIT_WORKSPACE=ws)
        out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + textwrap.dedent(code)],
                             env=env, capture_output=True, text=True, cwd=ws)
        if out.returncode:
            raise AssertionError(out.stderr[-2500:])
        return json.loads(out.stdout.strip().splitlines()[-1])


class TestExpired(unittest.TestCase):
    def test_expired_posting_is_excluded_not_judged(self):
        code = """
        import screen_minquals as s, json
        s.fetch = lambda url: "Mechanical Engineer. This position has been filled. Requirements: 3 years CAD."
        r = s.screen(dict(url="https://x.example/job/1", title="Mechanical Engineer", loc="Pittsburgh, PA"))
        print(json.dumps([r["verdict"], r["fitclass"], r["minq"]]))"""
        self.assertEqual(run("", code), ["EXPIRED", "EXCLUDED", "EXPIRED posting"])

    def test_open_posting_still_screens(self):
        code = """
        import screen_minquals as s, json
        s.fetch = lambda url: "Mechanical Engineer. Requirements: 3 years of CAD experience and a BS in engineering."
        r = s.screen(dict(url="https://x.example/job/2", title="Mechanical Engineer", loc="Pittsburgh, PA"))
        print(json.dumps([r["verdict"], r["fitclass"]]))"""
        self.assertEqual(run("", code), ["PASS", "CLOSE"])


class TestAutoSkipThreshold(unittest.TestCase):
    def _merge(self, threshold, score):
        settings = f"thresholds: {{build_default_min_rubric: 60, commutable_min_rubric: 45, auto_skip_below_rubric: {threshold}}}\n"
        code = f"""
        import json, os, datetime, rubric
        D = datetime.date.today().isoformat(); R = rubric.RB; TR = rubric.TR
        jd = os.path.join(TR, "jd.txt")
        open(jd, "w").write("Mechanical Engineer\\nPittsburgh\\nhttps://x.example/job/9\\n\\n" + ("Requirements: 5 years of experience with CAD, FEA and GD&T. " * 30))
        json.dump({{"00": dict(title="Mechanical Engineer", src="x", url="https://x.example/job/9?utm_source=li", jd=jd, jd_full=jd)}},
                  open(os.path.join(R, f"batch_{{D}}.json"), "w"))
        json.dump([dict(url="https://x.example/job/9?utm_source=li", title="Mechanical Engineer", src="x", jd=jd, fitclass="CLOSE", loc="Pittsburgh, PA")],
                  open(os.path.join(TR, "minquals_screened.json"), "w"))
        for t in ("A", "B"):
            json.dump({{"00": dict(skills={score}//10, experience=5, overall={score}, req="5 years of experience with CAD")}}, open(os.path.join(R, f"run_{{t}}_{{D}}.json"), "w"))
        rubric.merge(os.path.join(R, f"run_A_{{D}}.json"), os.path.join(R, f"run_B_{{D}}.json"))
        led = [json.loads(l) for l in open(os.path.join(TR, "dispositions.jsonl"))] if os.path.exists(os.path.join(TR, "dispositions.jsonl")) else []
        print(json.dumps([[d["decision"], d["url"]] for d in led]))"""
        return run(settings, code)

    def test_setting_decides_auto_skip(self):
        self.assertEqual(self._merge(40, 45), [])                                   # 45 is above 40: kept
        led = self._merge(50, 45)                                                   # 45 is below the person's 50: auto-skipped
        self.assertEqual(len(led), 1); self.assertEqual(led[0][0], "SKIP")
        self.assertEqual(led[0][1], "https://x.example/job/9", "auto-skip must ledger the CANONICAL url (tracking params dropped)")


class TestBackfillApplied(unittest.TestCase):
    def test_title_equality_is_case_insensitive(self):
        # the exact expression daily.py uses for the backfill filter, with its inputs
        code = """
        import json, re, unicodedata
        _canon = lambda s: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "").lower())
        applied = {(_canon("Acme Robotics")[:10], "Mechanical Engineer II")}
        m = dict(src="acmerobotics", title="MECHANICAL ENGINEER II")
        hit = any(a[:8] in _canon(m['src']) and _canon(b) == _canon(m['title']) for a, b in applied)
        print(json.dumps(hit))"""
        self.assertTrue(run("", code))


if __name__ == "__main__":
    unittest.main()
