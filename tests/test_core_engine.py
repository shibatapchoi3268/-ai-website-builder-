import os
import shutil
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.core_engine import _strip_code_fence, _validate_html, generate_website


VALID_HTML = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><main>Hello</main><script>document.title = "Ready";</script></body>
</html>"""


class CoreEngineTests(unittest.TestCase):
    def test_strips_html_code_fence(self):
        self.assertEqual(_strip_code_fence(f"```html\n{VALID_HTML}\n```"), VALID_HTML)

    def test_validator_reports_missing_document_tags(self):
        issues = _validate_html("<div>not a complete document</div>")
        self.assertTrue(any("DOCTYPE" in issue for issue in issues))
        self.assertTrue(any("<html>" in issue for issue in issues))
        self.assertTrue(any("<head>" in issue for issue in issues))
        self.assertTrue(any("<body>" in issue for issue in issues))

    def test_validator_reports_unclosed_script(self):
        html = "<!DOCTYPE html><html><head></head><body><script>let x = 1;"
        issues = _validate_html(html)
        self.assertTrue(any("chưa được đóng" in issue for issue in issues))

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_validator_reports_invalid_javascript(self):
        html = VALID_HTML.replace('document.title = "Ready";', "const = ;")
        self.assertTrue(any("JavaScript" in issue for issue in _validate_html(html)))

    @patch("services.core_engine.LLM")
    @patch("services.core_engine.Agent")
    @patch("services.core_engine.Task")
    @patch("services.core_engine.Crew")
    def test_passes_api_key_to_llm_without_changing_process_environment(
        self, crew, task, agent, llm
    ):
        responses = iter(
            [
                SimpleNamespace(raw="<html><body>incomplete</body></html>"),
                SimpleNamespace(raw=VALID_HTML),
            ]
        )
        crew.return_value.kickoff.side_effect = lambda: next(responses)
        original_key = os.environ.get("GEMINI_API_KEY")
        had_original_key = "GEMINI_API_KEY" in os.environ
        os.environ["GEMINI_API_KEY"] = "existing-process-key"

        try:
            result = generate_website("gemini", "request-key", "Create a test page")
            self.assertEqual(result, VALID_HTML)
            self.assertEqual(crew.return_value.kickoff.call_count, 2)
            llm.assert_called_once_with(
                model="gemini/gemini-3.8-flash",
                api_key="request-key",
            )
            self.assertEqual(os.environ["GEMINI_API_KEY"], "existing-process-key")
        finally:
            if not had_original_key:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = original_key

    @patch("services.core_engine.LLM")
    @patch("services.core_engine.Agent")
    @patch("services.core_engine.Task")
    @patch("services.core_engine.Crew")
    def test_failure_after_retries_is_reported(self, crew, task, agent, llm):
        crew.return_value.kickoff.return_value = SimpleNamespace(raw="<p>invalid</p>")
        with self.assertRaisesRegex(RuntimeError, "sau 2 lần thử"):
            generate_website("groq", "test-key", "Create a page", max_attempts=2)

    def test_rejects_empty_prompt_before_calling_provider(self):
        with self.assertRaisesRegex(ValueError, "yêu cầu"):
            generate_website("gemini", "test-key", " ")


if __name__ == "__main__":
    unittest.main()
