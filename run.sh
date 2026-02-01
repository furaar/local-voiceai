#!/usr/bin/env bash
# Start MCP server in background, then voice bot. Run from repo root.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

# MCP in background; kill on exit
uv run python main_mcp.py --transport sse --port 8081 --host 0.0.0.0 &
MCP_PID=$!
trap 'kill $MCP_PID 2>/dev/null' EXIT
sleep 2
exec uv run python bot.py --local
