"""Regression tests for urlcanon.canon.  Run: <jobkit python> -m unittest system/engine/tools/tests/test_urlcanon.py
(or: <jobkit python> system/engine/tools/tests/test_urlcanon.py)"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urlcanon import canon


class TestCanon(unittest.TestCase):
    def test_achievement_first_gh_jid_is_part_of_the_key(self):
        # audit v0.4 bug 4: 62 Greenhouse postings embedded on achievementfirst.org shared one ledger key
        base = "https://www.achievementfirst.org/careers/career-opportunities-apply-teaching-roles"
        a = canon(f"{base}?gh_jid=5735741004&gh_src=abc&utm_source=linkedin")
        b = canon(f"{base}?gh_jid=5735741005")
        self.assertNotEqual(a, b)
        self.assertEqual(a, f"{base}?gh_jid=5735741004")
        self.assertEqual(canon(f"{base}?gh_jid=5735741004#top"), a)
        self.assertEqual(canon(f"{base}?utm_source=x&gh_jid=5735741004"), a)

    def test_tracking_params_and_fragment_dropped(self):
        self.assertEqual(canon("https://Example.com/jobs/123/?utm_campaign=x&ref=y#frag"), "https://example.com/jobs/123")

    def test_greenhouse_host_variants_collapse(self):
        self.assertEqual(canon("https://boards.greenhouse.io/acme/jobs/42?gh_src=li"), "https://job-boards.greenhouse.io/acme/jobs/42")

    def test_job_id_params_kept_on_any_host(self):
        self.assertIn("jk=abc123", canon("https://www.indeed.com/viewjob?jk=abc123&from=serp"))
        self.assertIn("jobId=77", canon("https://careers.example.org/search?jobId=77&src=rss"))
        self.assertNotEqual(canon("https://careers.example.org/search?jobId=77"), canon("https://careers.example.org/search?jobId=78"))

    def test_path_ids_untouched(self):
        self.assertEqual(canon("https://jobs.lever.co/acme/1b2c-3d4e/"), "https://jobs.lever.co/acme/1b2c-3d4e")
        self.assertEqual(canon("https://acme.wd1.myworkdayjobs.com/en-US/Careers/job/Denver/Nurse_R123"), "https://acme.wd1.myworkdayjobs.com/en-US/Careers/job/Denver/Nurse_R123")

    def test_adzuna_session_tokens_collapse(self):
        self.assertEqual(canon("https://www.adzuna.com/land/ad/555?se=abc&v=xyz"), "https://www.adzuna.com/details/555")

    def test_empty(self):
        self.assertEqual(canon(""), "")


if __name__ == "__main__":
    unittest.main()
