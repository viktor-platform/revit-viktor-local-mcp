@echo off
setlocal

set VIKTOR_MCP_SERVER_URL=http://127.0.0.1:5099/mcp
set VIKTOR_MCP_BRIDGE_HOST=127.0.0.1
set VIKTOR_MCP_BRIDGE_PORT=8765
set VIKTOR_MCP_TOOL_CACHE_TTL_SECONDS=300

C:\VIKTOR\MCPWorker\.venv\Scripts\mcp-bridge-service.exe

endlocal
