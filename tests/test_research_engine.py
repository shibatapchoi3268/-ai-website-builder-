import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from google.genai.errors import APIError

from services.research_engine import research


def _response(text="Found answer.", chunks=None):
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(text=text, thought=False)]
                ),
                grounding_metadata=SimpleNamespace(grounding_chunks=chunks or []),
            )
        ]
    )


class ResearchEngineTests(unittest.TestCase):
    @patch("services.research_engine.genai.Client")
    def test_uses_google_search_and_extracts_deduplicated_web_sources(self, client_factory):
        source = SimpleNamespace(
            uri="https://example.com/article",
            title="Example article",
        )
        client = client_factory.return_value
        client.models.generate_content.return_value = _response(
            chunks=[
                SimpleNamespace(web=source),
                SimpleNamespace(web=source),
                SimpleNamespace(
                    web=SimpleNamespace(uri="file:///private", title="Not a web source")
                ),
            ]
        )

        answer = research(
            "Who won?",
            "test-key",
            [
                {"role": "user", "content": "What happened?"},
                {"role": "assistant", "content": "I will look it up."},
            ],
        )

        self.assertEqual(answer.text, "Found answer.")
        self.assertEqual(
            [(item.title, item.url) for item in answer.sources],
            [("Example article", "https://example.com/article")],
        )
        request = client.models.generate_content.call_args.kwargs
        self.assertEqual(request["model"], "gemini-3.8-flash")
        self.assertIsNotNone(request["config"].tools[0].google_search)
        self.assertEqual(
            [(item.role, item.parts[0].text) for item in request["contents"]],
            [
                ("user", "What happened?"),
                ("model", "I will look it up."),
                ("user", "Who won?"),
            ],
        )
        client.close.assert_called_once_with()

    @patch("services.research_engine.time.sleep")
    @patch("services.research_engine.genai.Client")
    def test_retries_503_then_uses_fallback_model(self, client_factory, sleep):
        client = client_factory.return_value
        unavailable = APIError(
            503, {"error": {"message": "temporarily unavailable"}}
        )
        client.models.generate_content.side_effect = [
            unavailable,
            unavailable,
            _response(),
        ]

        answer = research("Find an update", "test-key")

        self.assertEqual(answer.text, "Found answer.")
        self.assertEqual(
            [
                item.kwargs["model"]
                for item in client.models.generate_content.call_args_list
            ],
            ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.6-flash"],
        )
        self.assertEqual(sleep.call_args_list, [call(2)])
        client.close.assert_called_once_with()

    @patch("services.research_engine.genai.Client")
    def test_rejects_missing_api_key_before_creating_client(self, client_factory):
        with self.assertRaisesRegex(ValueError, "API key"):
            research("Find an update", " ")
        client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
