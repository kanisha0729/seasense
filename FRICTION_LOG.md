# SeaSense Friction Log

Real problems we hit while building SeaSense for the Alexa+ track, in the format the hackathon asks for.

---

### 1. MCP Python SDK 2.x: `FastMCP` import no longer works

| | |
| --- | --- |
| **Task** | Create our first MCP server in Python |
| **Steps** | `pip install "mcp[cli]"` (installed 2.3.0) → wrote `from mcp.server.fastmcp import FastMCP` as most tutorials and examples show → ran it |
| **Expected** | Server starts |
| **Actual** | `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. In 2.x the class was renamed to `MCPServer` in `mcp.server.mcpserver`. The error message did point to the migration guide, which helped. |
| **Severity** | Medium (blocks every beginner who copies a tutorial) |
| **Workaround** | `from mcp.server.mcpserver import MCPServer` |
| **Suggestion** | Keep a deprecated `fastmcp` alias for one major version, and update the getting-started pages and examples to 2.x |

### 2. `mcp dev` fails silently without `uv`

| | |
| --- | --- |
| **Task** | Test our tools in MCP Inspector |
| **Steps** | Ran `mcp dev server.py` on Windows inside a venv → Inspector 2.12.0 opened in the browser |
| **Expected** | Inspector connects to our server |
| **Actual** | Status "Failed", toast "Connection closed" with no reason. `mcp dev` launches the server with `uv run --with mcp==2.3.0`. We didn't have `uv`, and it also ignores the project's venv, so `httpx` would have been missing anyway. |
| **Severity** | High (first-run experience fails with no hint why) |
| **Workaround** | `npx @modelcontextprotocol/inspector .venv\Scripts\python.exe server.py` |
| **Suggestion** | Detect a missing `uv` and print a clear error, fall back to the active Python, and show the server's stderr in the Inspector |

### 3. Server defaults to stdio, but the track requires Streamable HTTP

| | |
| --- | --- |
| **Task** | Meet the Alexa+ requirement: MCP 2025-11-25 over Streamable HTTP |
| **Steps** | Built and tested with `server.run()` and the Inspector's stdio mode; then reread the rules |
| **Expected** | The quick-start path produces a server that satisfies the track |
| **Actual** | `run()` defaults to stdio, and `mcp dev` and the tutorials are stdio-first, so our "working" server didn't meet the transport requirement until late |
| **Severity** | High (easy to miss; affects eligibility) |
| **Workaround** | `server.run(transport="streamable-http", host=..., port=8000)` and connect the Inspector to `http://127.0.0.1:8000/mcp` |
| **Suggestion** | Put "Streamable HTTP" in the Alexa+ getting-started steps with a runnable example, and add a `--transport` flag to `mcp dev` |

### 4. Inspector shows an error toast for a harmless setting

| | |
| --- | --- |
| **Task** | Browse tools in MCP Inspector 2.12.0 |
| **Steps** | Clicked the "Paginated" toggle in an ad-hoc session |
| **Expected** | Setting changes, or the toggle is disabled |
| **Actual** | Red toast "Failed to save pagination setting: server list is read-only for this session" |
| **Severity** | Low (cosmetic, but it looks like our server broke) |
| **Workaround** | Ignored it |
| **Suggestion** | Disable the toggle in read-only sessions instead of failing |

### 5. Windows: venv activation blocked by default

| | |
| --- | --- |
| **Task** | Activate the Python virtual environment on Windows |
| **Steps** | `python -m venv .venv` → `.venv\Scripts\activate` in PowerShell |
| **Expected** | Prompt shows `(.venv)` |
| **Actual** | "running scripts is disabled on this system" |
| **Severity** | Medium (every Windows beginner hits it) |
| **Workaround** | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first |
| **Suggestion** | Include the Windows PowerShell steps in the MCP Python quick start |
