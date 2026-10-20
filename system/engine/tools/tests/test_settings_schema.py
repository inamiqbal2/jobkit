"""v1.0 (audit M27 + M26): settings.yaml has ONE schema. Every key a tool reads through userconfig.get() / _cfg() /
require() is in userconfig.SCHEMA; every SCHEMA key is documented in system/docs/ARCHITECTURE.md and the table there is
the current `userconfig.py --schema` output; the accessors agree with the SCHEMA defaults; configure() re-points the
workspace at run time; a fresh template validates to the same "not filled in yet" notes as v0.9.
Run: <jobkit python> -m unittest system/engine/tools/tests/test_settings_schema.py"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, textwrap, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM = os.path.dirname(os.path.dirname(TOOLS))
ROOT = os.path.dirname(SYSTEM)
ARCH = os.path.join(SYSTEM, "docs", "ARCHITECTURE.md")
TEMPLATE = os.path.join(ROOT, "My Job Search", "settings.yaml.example")
EXAMPLES = os.path.join(SYSTEM, "examples")
sys.path.insert(0, TOOLS)
import userconfig as u  # noqa: E402

# a dotted settings key read through userconfig: get("a.b"), _cfg('a.b'), require("a"); never a dict's own .get("x")
_READ = re.compile(r"""(?<![.\w])(?:get|_cfg|require)\(\s*(['"])([a-z_]+(?:\.[a-z_]+)*)\1""")


def read_keys():
    out = {}
    for p in glob.glob(os.path.join(TOOLS, "*.py")):
        src = open(p, encoding="utf-8").read()
        if "userconfig" not in src and os.path.basename(p) != "userconfig.py":
            continue
        for m in _READ.finditer(src):
            out.setdefault(m.group(2), set()).add(os.path.basename(p))
    return out


def run(code, ws):
    out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + textwrap.dedent(code)],
                         env=dict(os.environ, JOBKIT_WORKSPACE=ws), capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(out.stderr[-2500:])
    return json.loads(out.stdout.strip().splitlines()[-1])


class TestSchemaCoversTheCode(unittest.TestCase):
    def test_every_key_read_by_a_tool_is_in_schema(self):
        missing = {k: sorted(v) for k, v in read_keys().items() if k not in u.SCHEMA}
        self.assertEqual(missing, {}, f"settings keys read by tools but absent from userconfig.SCHEMA: {missing}")

    def test_the_tools_read_settings_at_all(self):
        self.assertGreater(len(read_keys()), 10, "the key-read scan found almost nothing; the regex is broken")

    def test_schema_is_well_formed(self):
        for f in u.SCHEMA.values():
            self.assertTrue(f.doc, f"{f.key} has no doc line")
            self.assertTrue(f.consumers, f"{f.key} names no consumer")
            if f.required and f.key.count("[].") == 0:
                self.assertTrue(f.missing, f"{f.key} is required but has no 'missing' sentence")
            if f.type == "enum":
                self.assertTrue(f.choices, f"{f.key} is an enum without choices")
            if f.type in ("int", "float"):
                self.assertTrue(f.rng, f"{f.key} has no range")
            if "." in f.key:
                top = f.key.split(".")[0].replace("[]", "")
                self.assertIn(top, u.SCHEMA, f"{f.key}: its section {top!r} is not a SCHEMA entry")


class TestSchemaMatchesTheDocs(unittest.TestCase):
    def test_every_schema_key_is_documented(self):
        doc = open(ARCH, encoding="utf-8").read()
        undocumented = [k for k in u.SCHEMA if f"`{k}`" not in doc]
        self.assertEqual(undocumented, [], f"SCHEMA keys missing from system/docs/ARCHITECTURE.md: {undocumented}")

    def test_architecture_table_is_the_generated_one(self):
        doc = open(ARCH, encoding="utf-8").read()
        m = re.search(r"<!-- schema:begin[^\n]*-->\n(.*?)\n<!-- schema:end -->", doc, re.S)
        self.assertIsNotNone(m, "ARCHITECTURE.md has no schema markers")
        self.assertEqual(m.group(1).strip(), u.schema_markdown().strip(),
                         "ARCHITECTURE.md's settings table differs from `userconfig.py --schema`; regenerate it")

    def test_template_keys_are_in_schema(self):
        import yaml
        t = yaml.safe_load(open(TEMPLATE, encoding="utf-8"))
        keys = []
        for sec, v in t.items():
            keys.append(sec)
            if isinstance(v, dict):
                keys += [f"{sec}.{k}" for k in v]
        stray = [k for k in keys if k not in u.SCHEMA]
        self.assertEqual(stray, [], f"settings.yaml.example has keys the schema does not know: {stray}")


class TestAccessorsUseSchemaDefaults(unittest.TestCase):
    def test_empty_file_gives_schema_defaults(self):
        ws = tempfile.mkdtemp()
        open(os.path.join(ws, "settings.yaml"), "w").write("identity: {name: x}\n")
        r = run("""
        import json, userconfig as u
        print(json.dumps({"th": u.thresholds(), "run": u.run_options(), "build": u.build(), "loc": u.location(),
                          "ex": u.exclusions(), "wa": u.work_auth(), "tg": u.targets(), "sc": u.scoring(),
                          "get_nodefault": u.get("run.judge_top_n"), "get_explicit": u.get("run.judge_top_n", None)}))""", ws)
        d = lambda k: u.SCHEMA[k].default
        self.assertEqual(r["th"]["build_default_min_rubric"], d("thresholds.build_default_min_rubric"))
        self.assertEqual(r["th"]["jd_gate"], d("thresholds.jd_gate"))
        self.assertEqual(r["run"]["judge_top_n"], d("run.judge_top_n"))
        self.assertEqual(r["build"]["format"], d("build.format"))
        self.assertEqual(r["loc"]["away_bar"], d("location.away_bar"))
        self.assertEqual(r["loc"]["tier2_regex"], d("location.tier2_regex"))
        self.assertEqual(r["ex"]["postdocs"], d("exclusions.postdocs"))
        self.assertEqual(r["wa"]["sponsorship_needed"], d("work_authorization.sponsorship_needed"))
        self.assertEqual(r["tg"]["part_time_ok"], d("targets.part_time_ok"))
        self.assertEqual(r["sc"]["career_fit"], d("scoring.career_fit"))
        self.assertEqual(r["get_nodefault"], d("run.judge_top_n"))
        self.assertIsNone(r["get_explicit"])


class TestValidateUnchangedForPeople(unittest.TestCase):
    def test_examples_validate_clean(self):
        for ex in ("jordan_example", "marina_example", "taylor_example"):
            r = run("import json, userconfig as u; print(json.dumps(u.validate()))", os.path.join(EXAMPLES, ex))
            self.assertEqual(r, [], f"{ex}: {r}")

    def test_fresh_template_reports_the_five_not_filled_in_notes(self):
        ws = tempfile.mkdtemp()
        shutil.copy(TEMPLATE, os.path.join(ws, "settings.yaml"))
        r = run("import json, userconfig as u; print(json.dumps(u.validate()))", ws)
        self.assertEqual(r, [
            ["missing", "identity.name is not filled in yet"],
            ["missing", "identity.email is not filled in yet"],
            ["missing", 'work_authorization.resume_line is not filled in yet (the exact words to print, or "" to print nothing)'],
            ["missing", "location.country is not filled in yet (US, CA, UK, or another two-letter code)"],
            ["missing", "no lanes yet (the kinds of job you want; the interview writes them in phase 5)"],
        ])

    def test_the_sentences_people_quote_are_unchanged(self):
        cfg = {"identity": {"name": "T", "email": "t@e.com", "links": "x"},
               "work_authorization": {"resume_line": "", "citizenship_only_roles_open": "yes"},
               "location": {"country": "US", "relocation": "maybe", "mode": "local_only", "tier1_regex": "Remote", "commutable_metros": [], "away_bar": 150},
               "scoring": {"location": "kinda"},
               "lanes": [{"name": "a", "packs": ["nope"]}],
               "thresholds": {"build_default_min_rubric": 30, "commutable_min_rubric": 45, "auto_skip_below_rubric": 40, "jd_gate": 2},
               "salary": {"floor": 100, "target": 50},
               "build": {"format": "pdf", "resume_filename": "R.pdf"}}
        msgs = [m for _, m in u.validate(cfg)]
        for want in ("identity.links should be a list of links (one per line starting with '- '), or []",
                     "work_authorization.citizenship_only_roles_open should be true or false, not 'yes'",
                     "work_authorization.clearance_possible is not set (true or false)",
                     "location.relocation should be yes, no or case-by-case, not 'maybe'",
                     "location.away_bar is 150; it must be between 0 and 100",
                     "scoring.location should be one of yes, a little, no, not 'kinda'",
                     "thresholds.jd_gate should be a number between 0 and 1, not 2",
                     "thresholds should go up: auto_skip_below_rubric (40) <= commutable_min_rubric (45) <= build_default_min_rubric (30)",
                     "salary.floor (100) is above salary.target (50)",
                     "build.format should be resume or academic_cv, not 'pdf'",
                     "build.resume_filename should end in .docx, not 'R.pdf'"):
            self.assertIn(want, msgs)
        self.assertTrue(any("commuting area" in m for m in msgs), "the v0.9 stay-local guard is gone")
        self.assertTrue(any("names a job-board pack that does not exist: 'nope'" in m for m in msgs))


class TestConfigure(unittest.TestCase):
    def test_configure_repoints_paths_and_caches(self):
        ex = os.path.join(EXAMPLES, "jordan_example")
        ws = tempfile.mkdtemp()
        open(os.path.join(ws, "settings.yaml"), "w").write("identity: {name: Other Person}\nmodules: {inbox_sweep: true}\n")
        r = run(f"""
        import json, os, userconfig as u
        before = [u.get("identity.name"), u.MODULES["inbox_sweep"], u.TRACKING]
        u.configure({ws!r})
        after = [u.get("identity.name"), u.MODULES["inbox_sweep"], u.TRACKING, u.USER_YAML, u.SIGNALS_YAML, u.WS, os.environ["JOBKIT_WORKSPACE"], u.path("x")]
        print(json.dumps([before, after]))""", ex)
        before, after = r
        self.assertEqual(before[0], "Jordan Example"); self.assertFalse(before[1]); self.assertEqual(before[2], os.path.join(ex, "tracking"))
        self.assertEqual(after[0], "Other Person"); self.assertTrue(after[1])
        self.assertEqual(after[2], os.path.join(ws, "tracking")); self.assertEqual(after[3], os.path.join(ws, "settings.yaml"))
        self.assertEqual(after[4], os.path.join(ws, "profile", "signals.yaml")); self.assertEqual(after[5], ws)
        self.assertEqual(after[6], ws); self.assertEqual(after[7], os.path.join(ws, "x"))

    def test_configure_refuses_a_non_folder(self):
        with self.assertRaises(NotADirectoryError):
            u.configure("/nonexistent/jobkit/ws")

    def test_import_reads_no_settings(self):
        ws = tempfile.mkdtemp()
        open(os.path.join(ws, "settings.yaml"), "w").write("identity: {name: Lazy}\n")
        r = run("""
        import json, userconfig as u
        print(json.dumps([u.load.cache_info().currsize, u.MODULES._filled, u.get("identity.name"), u.load.cache_info().currsize]))""", ws)
        self.assertEqual(r, [0, False, "Lazy", 1])


if __name__ == "__main__":
    unittest.main()
