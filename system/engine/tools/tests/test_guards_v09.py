"""v0.9 regression (engineering audit round 2): the fetch scheme allow-list, cap_text keeping the requirements block,
range-aware years bars, clause-ending negation, tolerant ledger readers, and the stay-local setup guard.
Run: <jobkit python> -m unittest system/engine/tools/tests/test_guards_v09.py"""
import json, os, subprocess, sys, tempfile, textwrap, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.join(os.path.dirname(os.path.dirname(TOOLS)), "examples", "jordan_example")   # system/examples/jordan_example


def run(code, ws=WS):
    out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + textwrap.dedent(code)],
                         env=dict(os.environ, JOBKIT_WORKSPACE=ws), capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(out.stderr[-2500:])
    return json.loads(out.stdout.strip().splitlines()[-1])


class TestFetchSchemes(unittest.TestCase):
    def test_only_http_and_https_are_fetched(self):
        r = run("""
        import json; from urlcanon import safe_http, UnsafeURL
        res = {}
        for u in ("file:///etc/hosts", "data:text/plain,x", "javascript:alert(1)", "ftp://a/b", "http://a.example/", "https://a.example/x?y=1"):
            try: safe_http(u); res[u] = "ok"
            except UnsafeURL: res[u] = "refused"
        print(json.dumps(res))""")
        self.assertEqual([v for k, v in res.items() if k.startswith("http")], ["ok", "ok"]) if (res := r) else None
        self.assertTrue(all(v == "refused" for k, v in r.items() if not k.startswith("http")))

    def test_screen_refuses_a_local_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("PRIVATE. " * 200); p = f.name
        r = run(f"""
        import json, screen_minquals as s
        v = s.screen(dict(url="file://{p}", title="Analyst", loc="New York, NY"))
        print(json.dumps([v["verdict"], "PRIVATE" in open(v["jd"]).read() if v.get("jd") else False]))""")
        os.unlink(p)
        self.assertEqual(r, ["FETCHFAIL", False])


class TestCapText(unittest.TestCase):
    def _cap(self, text):
        return run(f"import json, rubric; print(json.dumps(rubric.cap_text({text!r}, 6000)))")

    def test_late_requirements_block_is_kept(self):
        t = "Company story. " * 450 + "Basic Qualifications: five years validating models. " * 10 + "Equal opportunity employer. " * 200
        out = self._cap(t)
        self.assertIn("Basic Qualifications", out); self.assertLessEqual(len(out), 6200)

    def test_late_requirements_with_line_breaks(self):
        t = "Company story.\n" * 450 + "\nBasic Qualifications:\n- five years validating models\n" * 10 + "Equal opportunity employer.\n" * 200
        self.assertIn("Basic Qualifications", self._cap(t))

    def test_early_requirements_and_short_text(self):
        self.assertIn("Requirements:", self._cap("Intro. " * 100 + "Requirements: 5 years of CAD. " * 20 + "EEO. " * 500))
        self.assertEqual(self._cap("short posting"), "short posting")


class TestScreenRules(unittest.TestCase):
    def test_years_range_keeps_lower_bound(self):
        r = run("""import json, screen_minquals as s; print(json.dumps([s.years_mentioned("3-5 years"), s.years_mentioned("5 to 7 years"), s.years_mentioned("8+ years and 80 years of history"), s.years_mentioned("25 years of company heritage")]))""")
        self.assertEqual(r, [[3], [5], [8], [25]])

    def test_negation_ends_at_a_comma(self):
        r = run("""
        import json, screen_minquals as s
        P = r"security clearance|clearance is required"
        print(json.dumps([s._hit(P, "Security clearance required, no exceptions."), s._hit(P, "No security clearance required."),
                          s._hit(P, "Ability to obtain a clearance is required (no exceptions)."), s._hit(P, "Security Clearance: None required")]))""")
        self.assertEqual(r, [True, False, True, False])


class TestLedgerAndSetup(unittest.TestCase):
    def test_bad_ledger_line_is_skipped_not_fatal(self):
        ws = tempfile.mkdtemp(); os.makedirs(os.path.join(ws, "tracking"))
        with open(os.path.join(ws, "settings.yaml"), "w") as f:
            f.write(open(os.path.join(WS, "settings.yaml")).read())
        with open(os.path.join(ws, "tracking", "dispositions.jsonl"), "w") as f:
            f.write('{"date":"2026-10-20","url":"https://x.example/1","decision":"WATCH","reason":"ok"}\n{"date":"2026-10-20","url":"https://x.exa')
        r = run("import json, decide; print(json.dumps([d['decision'] for d in decide.load()]))", ws)
        self.assertEqual(r, ["WATCH"])

    def test_stay_local_with_default_commuting_pattern_is_refused(self):
        import yaml
        ws = tempfile.mkdtemp(); s = yaml.safe_load(open(os.path.join(WS, "settings.yaml")))
        s["location"]["mode"] = "local_only"; s["location"]["tier1_regex"] = "Remote"; s["location"]["commutable_metros"] = []
        yaml.safe_dump(s, open(os.path.join(ws, "settings.yaml"), "w"))
        out = subprocess.run([sys.executable, os.path.join(TOOLS, "userconfig.py"), "--validate"], env=dict(os.environ, JOBKIT_WORKSPACE=ws), capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0); self.assertIn("commuting area", out.stdout)

    def test_nonexistent_workspace_is_refused(self):
        out = subprocess.run([sys.executable, os.path.join(TOOLS, "userconfig.py"), "--validate"], env=dict(os.environ, JOBKIT_WORKSPACE="/nonexistent/jobkit/ws"), capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0); self.assertIn("not a folder", out.stderr + out.stdout)


class TestCriticInProcess(unittest.TestCase):
    def test_review_returns_a_verdict(self):
        # a workspace where clearance roles are CLOSED, so a clearance requirement is a real knockout
        import yaml
        ws = tempfile.mkdtemp(); s = yaml.safe_load(open(os.path.join(WS, "settings.yaml")))
        s["work_authorization"]["clearance_possible"] = False; s["work_authorization"]["citizenship_only_roles_open"] = False
        yaml.safe_dump(s, open(os.path.join(ws, "settings.yaml"), "w")); os.makedirs(os.path.join(ws, "tracking"))
        jd = os.path.join(tempfile.mkdtemp(), "JobDescription.txt")
        with open(jd, "w") as f:
            f.write("ICU Registered Nurse\nDenver, CO\nhttps://x.example/1\n==========\nRequirements: active security clearance required. BSN. " * 5)
        r = run(f"""
        import json, io, contextlib, critic
        with contextlib.redirect_stdout(io.StringIO()): v = critic.review({jd!r})
        print(json.dumps([v["hold"], int(v) > 0, critic.queue_line(v)[:4]]))""", ws)
        self.assertEqual(r, [True, True, "HOLD"])


if __name__ == "__main__":
    unittest.main()
