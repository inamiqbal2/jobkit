"""v1.0 (audit M30): the dedupe / mirror-collapse algorithm of daily.py as pure functions - lists in, lists + ledger lines out.
Covers the two regressions of 2026-10-01 (mirrors of one job judged twice; distinct requisitions collapsed as mirrors) and the
re-surfacings of 2026-10-04/05 (Corning "(req 78269)", Leidos "(NETL)", Mondelēz accent).
Run: <jobkit python> -m unittest tests.test_daily_dedupe   (from system/engine/tools)"""
import json, os, sys, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.join(os.path.dirname(os.path.dirname(TOOLS)), "examples", "jordan_example")   # system/examples/jordan_example
os.environ.setdefault("JOBKIT_WORKSPACE", WS)   # daily.py resolves its workspace at import; the pure functions never touch it
sys.path.insert(0, TOOLS)
import daily   # noqa: E402  (importing runs nothing: v0.8)

TODAY = "2026-10-20"


def cand(src, title, loc, url, age=3):
    return dict(src=src, title=title, loc=loc, url=url, age=age)


class TestMirrorCollapse(unittest.TestCase):
    def test_aggregator_copy_collapses_to_the_official_posting(self):
        official = cand("acmerobotics", "Mechanical Engineer II", "Boston, MA", "https://boards.greenhouse.io/acmerobotics/jobs/123", age=5)
        mirror = cand("li:Acme Robotics", "Mechanical Engineer II", "Boston, MA", "https://www.linkedin.com/jobs/view/999", age=1)
        kept, lines, n_mirror, n_mirror_judged, judged = daily.collapse_mirrors([mirror, official], set(), TODAY)
        self.assertEqual([x['url'] for x in kept], [official['url']])        # the official one survives, whatever the input order / age
        self.assertEqual((n_mirror, n_mirror_judged), (1, 0))
        self.assertEqual(len(lines), 1)
        d = json.loads(lines[0])
        self.assertEqual((d['date'], d['decision']), (TODAY, "SKIP"))
        self.assertEqual(d['url'], daily._curl(mirror['url']))
        self.assertEqual(d['reason'], f"DUPLICATE(mirror of {daily._curl(official['url'])} via li:Acme Robotics)")
        self.assertIn(daily._curl(mirror['url']), judged)                     # the ledger count includes the collapsed mirror
        self.assertNotIn(daily._curl(official['url']), judged)

    def test_mirror_of_an_already_judged_job_is_counted_separately(self):
        official = cand("acmerobotics", "Mechanical Engineer II", "Boston, MA", "https://boards.greenhouse.io/acmerobotics/jobs/123")
        mirror = cand("in:Acme Robotics", "Mechanical Engineer II", "Boston, MA", "https://www.indeed.com/viewjob?jk=abc")
        kept, lines, n_mirror, n_mirror_judged, judged = daily.collapse_mirrors([official, mirror], {daily._curl(official['url'])}, TODAY)
        self.assertEqual((n_mirror, n_mirror_judged, len(lines)), (0, 1, 1))
        self.assertEqual(daily.not_judged(kept, judged), [])                  # nothing left for the screen: the job was judged

    def test_different_cities_are_not_mirrors(self):
        official = cand("acmerobotics", "Mechanical Engineer II", "Austin, TX", "https://boards.greenhouse.io/acmerobotics/jobs/123")
        other = cand("li:Acme Robotics", "Mechanical Engineer II", "Boston, MA", "https://www.linkedin.com/jobs/view/999")
        kept, lines, n_mirror, n_mirror_judged, judged = daily.collapse_mirrors([official, other], set(), TODAY)
        self.assertEqual(len(kept), 2)
        self.assertEqual((lines, n_mirror, n_mirror_judged, judged), ([], 0, 0, set()))

    def test_two_official_postings_and_two_listings_of_one_aggregator_are_never_mirrors(self):
        # the 2026-10-01 regression: same title, same Workday board, different req id
        a = cand("acmerobotics", "Mechanical Engineer II", "Boston, MA", "https://acme.wd5.myworkdayjobs.com/en-US/x/job/R-1")
        b = cand("acmerobotics", "Mechanical Engineer II", "Boston, MA", "https://acme.wd5.myworkdayjobs.com/en-US/x/job/R-2")
        li1 = cand("li:Acme Robotics", "Mechanical Engineer II", "", "https://www.linkedin.com/jobs/view/1")
        li2 = cand("li:Acme Robotics", "Mechanical Engineer II", "", "https://www.linkedin.com/jobs/view/2")
        kept, lines, *_ = daily.collapse_mirrors([a, b], set(), TODAY)
        self.assertEqual((len(kept), lines), (2, []))
        kept, lines, *_ = daily.collapse_mirrors([li1, li2], set(), TODAY)
        self.assertEqual((len(kept), lines), (2, []))

    def test_unknown_city_matches_any_city(self):
        official = cand("acmerobotics", "Mechanical Engineer II", "Austin, TX", "https://boards.greenhouse.io/acmerobotics/jobs/123")
        placeholder = cand("adzuna:Acme Robotics", "Mechanical Engineer II", "3 Locations", "https://www.adzuna.com/details/77")
        kept, lines, *_ = daily.collapse_mirrors([official, placeholder], set(), TODAY)
        self.assertEqual([x['url'] for x in kept], [official['url']])
        self.assertEqual(len(lines), 1)


class TestAppliedFilter(unittest.TestCase):
    def test_backfill_expression_is_case_insensitive(self):
        # the exact expression tests/test_screen_and_skip.py::TestBackfillApplied checks, now behind is_applied()
        applied = daily.applied_set([("Acme Robotics", "Mechanical Engineer II")])
        self.assertTrue(daily.is_applied("acmerobotics", "MECHANICAL ENGINEER II", applied))
        self.assertFalse(daily.is_applied("acmerobotics", "Mechanical Engineer III", applied))   # full-title equality, not a prefix
        self.assertFalse(daily.is_applied("othercorp", "Mechanical Engineer II", applied))

    def test_accents_and_req_suffixes_are_folded(self):
        applied = daily.applied_set([("Mondelēz International", "Research Scientist (req 78269)"), ("Leidos (NETL)", "Engineer")])
        c = [cand("mondelez", "research scientist", "x", "u1"), cand("li:Leidos", "Engineer", "x", "u2"), cand("li:Leidos", "Senior Engineer", "x", "u3")]
        self.assertEqual([x['url'] for x in daily.not_applied(c, applied)], ["u3"])


class TestLedger(unittest.TestCase):
    def test_hiding_decisions_versus_open_ones(self):
        lines = [json.dumps(dict(date=TODAY, url=u, decision=d, reason="r")) for u, d in (
            ("https://a.example/1", "BUILT"), ("https://a.example/2", "SKIP"), ("https://a.example/3", "APPLIED"),
            ("https://a.example/4", "WATCH"), ("https://a.example/5", "REOPEN"), ("https://a.example/6", "DEFER"))]
        judged, bad = daily.ledger_judged(lines)
        self.assertEqual(judged, {"https://a.example/1", "https://a.example/2", "https://a.example/3"})
        self.assertEqual(bad, [])
        c = [cand("s", "t", "", f"https://a.example/{i}") for i in range(1, 7)]
        self.assertEqual([x['url'] for x in daily.not_judged(c, judged)], ["https://a.example/4", "https://a.example/5", "https://a.example/6"])

    def test_last_decision_per_canonical_url_wins_and_bad_lines_are_reported(self):
        lines = [json.dumps(dict(url="https://a.example/1?utm_source=x", decision="SKIP")), "", "   ", "{not json",
                 json.dumps(dict(url="https://a.example/1", decision="WATCH"))]
        judged, bad = daily.ledger_judged(lines)
        self.assertEqual(judged, set())            # SKIP then WATCH on the same canonical url -> open again
        self.assertEqual(bad, ["{not json"])


if __name__ == "__main__":
    unittest.main()
