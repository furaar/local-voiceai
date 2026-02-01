import asyncio
import os
import pytest
import httpx
import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from tests.utils import run_e2e_test_with_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MCP_SERVER_URL = "http://127.0.0.1:8080"
HEADERS = {"Content-Type": "application/json"}
EXPECTED_TOOLS=["convert_temperature","convert_length", "calculator::add", "calculator::multiply"]
TEST_PROMPTS=[
        ("Convert temperature of 100 Celsius to Fahrenheit?", "212"),
        ("what's the answer for (10 + 5)?", "15"),
    ]

ADD_PAYLOAD = {
    "mcpServers": {
        "unit_converter": {
            "command": "python",
            "args": ["./tools/unit_convertor.py"]
        }
    }
}


@pytest.mark.asyncio
async def test_mcp_servers_lifecycle():
    """
    Test the lifecycle of adding, verifying, and removing an MCP server dynamically via the HTTP API.
    Also verifies the new server's tools can be used through the proxy.
    """
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
        await asyncio.sleep(4)  # wait for the server to be up

        async with httpx.AsyncClient() as client:
            # GET existing servers
            resp = await client.get(f"{MCP_SERVER_URL}/mcp_servers")
            assert resp.status_code == 200
            servers = resp.json().get("active_servers", [])
            print("🧪 Server list Before Add:", servers)

            # POST new server
            resp = await client.post(
                f"{MCP_SERVER_URL}/mcp_servers",
                headers=HEADERS,
                content=json.dumps(ADD_PAYLOAD)
            )
            assert resp.status_code == 200
            print("✅ Add Response:", resp.json())

            # GET again to verify it's added
            resp = await client.get(f"{MCP_SERVER_URL}/mcp_servers")
            assert resp.status_code == 200
            servers = resp.json().get("active_servers", [])
            assert "unit_converter" in servers
            print("🧪 Server list After Add:", servers)

            # Get tool list
            resp = await client.get(f"{MCP_SERVER_URL}/mcp_tools")
            assert resp.status_code == 200
            tools_by_server = resp.json().get("tools", {})

            all_tools = []
            for _, tools in tools_by_server.items():
                if isinstance(tools, list):
                    all_tools.extend(tools)
            print("🔧 Tools list:", all_tools)

        # Test the tools
        await asyncio.sleep(4)
        async with MultiServerMCPClient() as mcp_client:
            await mcp_client.connect_to_server(
                "multi-mcp",
                transport="sse",
                url="http://127.0.0.1:8080/sse",
            )
            await run_e2e_test_with_client(mcp_client,
                                            all_tools,
                                            test_prompts=[("Convert temperature of 100 Celsius to Fahrenheit?", "212"),
                                                        ("what's the answer for (10 + 5)?", "15")])

        async with httpx.AsyncClient() as client:
            # DELETE the server
            resp = await client.delete(f"{MCP_SERVER_URL}/mcp_servers/unit_converter")
            assert resp.status_code == 200
            print("🗑️ Remove Response:", resp.json())

            # GET to confirm removal
            resp = await client.get(f"{MCP_SERVER_URL}/mcp_servers")
            assert resp.status_code == 200
            servers = resp.json().get("active_servers", [])
            assert "unit_converter" not in servers
            print("🧪 After Remove:", servers)

    finally:
        process.kill()
        if process.stdout:
            await process.stdout.read()
        if process.stderr:
            await process.stderr.read()
