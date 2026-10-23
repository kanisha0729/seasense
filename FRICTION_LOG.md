# SeaSense Friction Log

Problems we hit while building, written down as they happened. Used for the Devpost product feedback.

| When (IST) | Tool | What happened | Workaround |
| --- | --- | --- | --- |
| Thu 22 Oct, 10:00 PM | MCP Python SDK 2.3.0 | `from mcp.server.fastmcp import FastMCP` (the import most tutorials and examples show) fails with ModuleNotFoundError. In 2.x, FastMCP was renamed to `MCPServer` in `mcp.server.mcpserver`. The error message pointed to the migration guide, which helped. | Switched to `from mcp.server.mcpserver import MCPServer`. |
| Thu 22 Oct, 9:45 PM | Windows PowerShell | `.venv\Scripts\activate` was blocked because running scripts is disabled by default. | Ran `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first. |
| Thu 22 Oct, 10:10 PM | MCP CLI (`mcp dev`) + MCP Inspector 2.12.0 | `mcp dev server.py` launches the server via `uv run --with mcp==2.3.0`. Without uv installed it fails, and the Inspector only says "Connection closed" with no reason. It also ignores the project venv, so packages like httpx are missing. | Ran `npx @modelcontextprotocol/inspector .venv\Scripts\python.exe server.py` instead. |