# MCP server

The project exposes the website generator as an MCP tool over Streamable HTTP at
`http://127.0.0.1:8000/mcp`. The server binds to loopback only; do not expose this
endpoint to a network without adding authentication and TLS at a trusted proxy.
Opening `http://127.0.0.1:8000/` in a browser shows a JSON health/status response;
MCP clients must connect to the `/mcp` endpoint instead.

Install the project dependencies and configure a model API key in the environment
before starting the server:

```powershell
python -m pip install -r requirements.txt
$env:AI_PROVIDER = "gemini"
$env:GEMINI_API_KEY = "<your-gemini-api-key>"
python -m services.mcp_server
```

`AI_PROVIDER` accepts `gemini`, `openai`, or `groq`. Configure the matching
`GEMINI_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY`. `AI_PROVIDER` defaults to
`gemini`; `MCP_PORT` can be set to change the default port `8000`.

The workspace includes `.vscode/mcp.json` for VS Code MCP clients. Start the
server in a terminal, then use the `ai-website-builder` server in VS Code. Its
`generate_website` tool accepts a required `prompt` and an optional
`provider`, and returns validated single-file HTML. The API key remains in the
server environment and is not an MCP tool argument.

To request a website, open **Copilot Chat** in VS Code, select **Agent** mode,
and type your request in ordinary language, for example:

> Use the `ai-website-builder` MCP server's `generate_website` tool to create a
> dark, responsive product landing page for a smartwatch, with a feature list
> and a purchase button.

The website description is the tool's `prompt` argument. You can optionally
specify a provider such as `gemini`, `openai`, or `groq`. There is no separate
terminal command for each prompt; the server must remain running while Copilot
Chat calls the tool.
