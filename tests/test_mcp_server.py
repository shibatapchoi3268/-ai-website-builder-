import os
import unittest
from unittest.mock import patch

from services.mcp_server import generate_website


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_uses_configured_provider_and_key(self):
        with patch.dict(
            os.environ,
            {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"},
            clear=True,
        ), patch("services.mcp_server.build_website", return_value="<html></html>") as build:
            result = await generate_website("Build a page")

        self.assertEqual(result, "<html></html>")
        build.assert_called_once_with(
            provider="openai",
            api_key="test-key",
            user_prompt="Build a page",
        )

    async def test_tool_rejects_missing_provider_key(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "groq"}, clear=True):
            with self.assertRaisesRegex(ValueError, "GROQ_API_KEY"):
                await generate_website("Build a page")

    async def test_tool_rejects_unknown_provider(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "unknown"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Unsupported provider"):
                await generate_website("Build a page")


if __name__ == "__main__":
    unittest.main()
