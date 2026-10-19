"""Release check (v0.7): the templates a new person starts from contain NO rules or preferences from anyone else.
Every rule and preference must come from that person's own setup answers.
Run: <jobkit python> -m unittest system/engine/tools/tests/test_templates_clean.py"""
import os, re, sys, unittest
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
MJS = os.path.join(ROOT, "My Job Search")


class TestTemplatesClean(unittest.TestCase):
    def test_rules_template_has_only_placeholders(self):
        t = open(os.path.join(MJS, "my-rules.TEMPLATE.md"), encoding="utf-8").read()
        for h in re.findall(r"^## (.+)$", t, re.M):
            self.assertIn("<date>", h, f"my-rules template has a filled-in rule heading: {h!r}")

    def test_settings_template_preferences_empty(self):
        s = yaml.safe_load(open(os.path.join(MJS, "settings.yaml.example"), encoding="utf-8"))
        self.assertEqual(s.get("lanes"), [], "settings template ships with lanes")
        ex = s.get("exclusions") or {}
        self.assertEqual(ex.get("employers"), [], "settings template excludes employers")
        self.assertEqual(ex.get("role_types"), [], "settings template excludes role types")
        loc = s.get("location") or {}
        self.assertEqual(loc.get("never_places"), [], "settings template has never_places")
        self.assertEqual(loc.get("other_countries"), [], "settings template has other_countries")
        self.assertIn(str(loc.get("mode") or ""), ("",), "settings template pre-picks a location mode")
        self.assertEqual((s.get("targets") or {}).get("position_types"), [], "settings template pre-picks position types")

    def test_profile_templates_are_placeholders(self):
        for f in ("profile/profile_blind.TEMPLATE.md", "profile/skills-inventory.TEMPLATE.md"):
            t = open(os.path.join(MJS, f), encoding="utf-8").read()
            self.assertIn("<", t, f"{f} has no placeholders")


if __name__ == "__main__":
    unittest.main()
