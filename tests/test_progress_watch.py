import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "idea_enhancer_progress_watch.py"
SPEC = importlib.util.spec_from_file_location("progress_watch", SCRIPT)
progress_watch = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(progress_watch)


class ProgressWatchTests(unittest.TestCase):
    def test_sensitive_and_bulk_files_are_withheld(self):
        self.assertTrue(progress_watch.should_withhold_file(".env")[0])
        self.assertTrue(progress_watch.should_withhold_file("config/production.key")[0])
        self.assertTrue(progress_watch.should_withhold_file("data/historical_projects.csv")[0])
        self.assertTrue(progress_watch.should_withhold_file("src/live_search/providers.py")[0] is False)

    def test_env_example_is_allowed_as_a_placeholder_file(self):
        withheld, reason = progress_watch.should_withhold_file(".env.example")
        self.assertFalse(withheld, reason)

    def test_secret_patterns_are_redacted(self):
        source = (
            'GEMINI_API_KEY = "AIzaSyA12345678901234567890123456789012"\n'
            'token: ghp_abcdefghijklmnopqrstuvwxyz1234567890\n'
            'Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890\n'
        )
        redacted = progress_watch.redact_secrets(source)
        self.assertNotIn("AIzaSyA12345678901234567890123456789012", redacted)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz1234567890", redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz1234567890", redacted)
        self.assertIn("<REDACTED_SECRET>", redacted)

    def test_assessment_requires_known_diff_evidence_and_high_confidence(self):
        allowed_shas = {"a" * 40}
        allowed_files = {"a" * 40: {"src/main.py"}}
        base = {
            "notify": True,
            "category": "milestone",
            "title": "New API integration",
            "summary": "A substantive API path was added.",
            "significance": "This creates a new user-facing capability.",
            "evidence": [{"commit_sha": "a" * 40, "file": "src/main.py", "detail": "Adds a route."}],
            "verification_note": "The diff shows implementation; runtime behavior is unverified.",
            "confidence": 0.9,
        }
        should_notify, normalized = progress_watch.validate_assessment(base, allowed_shas, allowed_files)
        self.assertTrue(should_notify)
        self.assertEqual(normalized["category"], "milestone")

        bad_path = dict(base)
        bad_path["evidence"] = [{"commit_sha": "a" * 40, "file": "README.md", "detail": "Not in diff."}]
        should_notify, _ = progress_watch.validate_assessment(bad_path, allowed_shas, allowed_files)
        self.assertFalse(should_notify)

        low_confidence = dict(base)
        low_confidence["confidence"] = 0.5
        should_notify, _ = progress_watch.validate_assessment(low_confidence, allowed_shas, allowed_files)
        self.assertFalse(should_notify)

    def test_model_text_cannot_add_external_links_or_mentions(self):
        cleaned = progress_watch.clean_model_text(
            "See https://example.invalid/path and ping @someone <script>.", 500
        )
        self.assertNotIn("https://example.invalid", cleaned)
        self.assertNotIn("@someone", cleaned)
        self.assertNotIn("<script>", cleaned)
        self.assertIn("external link omitted", cleaned)

    def test_no_notification_stays_suppressed(self):
        assessment = {
            "notify": False,
            "category": "none",
            "title": "Routine cleanup",
            "summary": "Only minor cleanup was found.",
            "significance": "No meaningful milestone.",
            "evidence": [{"commit_sha": "b" * 40, "file": "src/main.py", "detail": "Small edit."}],
            "verification_note": "No tests run.",
            "confidence": 0.99,
        }
        should_notify, _ = progress_watch.validate_assessment(
            assessment, {"b" * 40}, {"b" * 40: {"src/main.py"}}
        )
        self.assertFalse(should_notify)

    def test_report_includes_verification_boundary_and_dedup_marker(self):
        sha = "c" * 40
        commit = {
            "sha": sha,
            "short_sha": sha[:12],
            "url": f"https://github.com/seepatimeghashyam/Idea-Enhancer/commit/{sha}",
        }
        assessment = {
            "category": "milestone",
            "title": "Live search route added",
            "summary": "A separate live search route was added.",
            "significance": "The external-provider flow now has an API entry point.",
            "verification_note": "The diff shows code and tests, but no runtime verification.",
            "evidence": [{"commit_sha": sha, "file": "src/main.py", "detail": "Adds POST /live-search."}],
        }
        body = progress_watch.build_report_body(
            "seepatimeghashyam/Idea-Enhancer", progress_watch.TARGET_BRANCH,
            "0" * 40, sha, [commit], assessment
        )
        self.assertIn("did not run the test suite", body)
        self.assertIn(f"idea-enhancer-progress-watch:{sha}", body)
        self.assertIn("@seepatimeghashyam", body)


if __name__ == "__main__":
    unittest.main()
