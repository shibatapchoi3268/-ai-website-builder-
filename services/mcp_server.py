import asyncio
import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from services.core_engine import generate_website as build_website


PORT = int(os.environ.get("MCP_PORT", "8000"))
PROVIDER_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}

mcp = FastMCP(
    "AI Website Builder",
    host="127.0.0.1",
    port=PORT,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
async def status_page(request: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "service": "AI Website Builder MCP",
            "mcp_endpoint": "/mcp",
            "message": "Dùng MCP client để kết nối; trình duyệt không hiển thị giao diện MCP tại /mcp.",
        }
    )


@mcp.tool()
async def generate_website(prompt: str, provider: str | None = None) -> str:
    """Create, validate, and return a single-file HTML website for the user's prompt."""
    selected_provider = (provider or os.environ.get("AI_PROVIDER", "gemini")).strip().lower()
    api_key_env = PROVIDER_KEYS.get(selected_provider)
    if api_key_env is None:
        supported = ", ".join(sorted(PROVIDER_KEYS))
        raise ValueError(f"Unsupported provider '{selected_provider}'. Choose one of: {supported}.")

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(
            f"Missing {api_key_env}. Configure the provider API key in the MCP server environment."
        )

    return await asyncio.to_thread(
        build_website,
        provider=selected_provider,
        api_key=api_key,
        user_prompt=prompt,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
