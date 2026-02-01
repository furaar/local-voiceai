import asyncio
import os
import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient
from tests.utils import run_e2e_test_with_client

# Run from repo root so main_mcp.py and config/ resolve
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPECTED_TOOLS=["weather::get_weather", "calculator::add", "calculator::multiply"]
TEST_PROMPTS=[
        ("what is the weather in London?", "weather in london"),
        ("what's the answer for (10 + 5)?", "15"),
    ]

@pytest.mark.asyncio
async def test_stdio_mode():
    """Test the MultiMCP server running in stdio mode. Run pytest from repo root with PYTHONPATH=."""
    async with MultiServerMCPClient() as client:
        await client.connect_to_server(
            "multi-mcp",
            command="python",
            args=["main_mcp.py"],
        )
        await run_e2e_test_with_client(client, EXPECTED_TOOLS, TEST_PROMPTS)


@pytest.mark.asyncio
async def test_sse_mode():
    """Test the MultiMCP server running in SSE mode via subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    process = await asyncio.create_subprocess_exec(
        "python", "main_mcp.py", "--transport", "sse", "--port", "8080",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=ROOT,
        env=env,
    )
    try:
        await asyncio.sleep(4)
        async with MultiServerMCPClient() as client:
            await client.connect_to_server(
                "multi-mcp",
                transport="sse",
                url="http://127.0.0.1:8080/sse",
            )
            await run_e2e_test_with_client(client, EXPECTED_TOOLS, TEST_PROMPTS)
    finally:
        process.kill()
        if process.stdout:
            await process.stdout.read()
        if process.stderr:
            await process.stderr.read()


@pytest.mark.asyncio
async def test_sse_clients_mode():
    """Test MultiMCP with SSE-configured backend clients from a config file. Run pytest from repo root."""
    async with MultiServerMCPClient() as client:
        await client.connect_to_server(
            "multi-mcp",
            command="python",
            args=["main_mcp.py", "--config", "config/mcp_sse.json"],
        )
        await run_e2e_test_with_client(client, EXPECTED_TOOLS, TEST_PROMPTS)
