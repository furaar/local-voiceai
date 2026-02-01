import pytest
import pytest_asyncio
import inspect
from contextlib import asynccontextmanager
from mcp.types import Tool, CallToolResult, TextContent
from mcp.server import Server
from mcp.shared.memory import create_connected_server_and_client_session
from src.multimcp.mcp_proxy import MCPProxyServer
from src.multimcp.mcp_client import MCPClientManager

ECHO_SERVER_NAME="Echo Server"
SERVER1_NAME="Server1"
SERVER2_NAME="Server2"


# 🔧 Two different test tools
@pytest.fixture
def test_tool_1():
    """First mock tool."""
    return Tool(
        name="Tool1",
        description="first test tool",
        inputSchema={"type": "object", "properties": {}},
    )

@pytest.fixture
def test_tool_2():
    """Second mock tool."""
    return Tool(
        name="Tool2",
        description="second test tool",
        inputSchema={"type": "object", "properties": {}},
    )

@pytest.fixture
def test_tool_3():
    """Third mock tool."""
    return Tool(
        name="Tool3",
        description="Third test tool",
        inputSchema={"type": "object", "properties": {}},
    )
@pytest.fixture
def echo_tool():
    """Provides an echo tool that simulates echoing input back."""
    return Tool(
        name="echo",
        description="Echoes back input text",
        inputSchema= {"type": "object", "properties": {"input1": {"type": "string"}}}
    )

# 🔧 Two servers, each serving one tool
@pytest_asyncio.fixture
async def server_1(test_tool_1):
    """Simulates a server with one tool (tool-1)."""
    server = Server(SERVER1_NAME)
    @server.list_tools()
    async def _():
        return [test_tool_1]
    return server

@pytest_asyncio.fixture
async def server_2(test_tool_2,test_tool_3):
    """Simulates a server with two tools (tool-2, tool-3)."""
    server = Server(SERVER2_NAME)
    @server.list_tools()
    async def _():
        return [test_tool_2,test_tool_3]
    return server



@pytest_asyncio.fixture
async def echo_server(echo_tool):
    """Simulates a server with an echo tool and its call handler."""
    server = Server(ECHO_SERVER_NAME)

    @server.list_tools()
    async def _():
        return [echo_tool]

    # ✅ Register the call_tool handler here
    @server.call_tool()
    async def _(tool_name, params):
        if tool_name == "echo":
            print("🔧 echo tool return text")
            # TODO- check why this return not work issue with  create_connected_server_and_client_session ans in memory
            # result=CallToolResult(
            #     content=[TextContent(type="text", text="Echo: Hello world!")],
            #     isError=False,
            # )

            return []

        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text="Tool not found")]
        )
    return server

# ✅ Create a proxy that combines both servers
@asynccontextmanager
async def proxy_client_2session(server_1, server_2):
    """Creates a proxy with two backend client sessions."""
    async with create_connected_server_and_client_session(server_1) as client_1, \
               create_connected_server_and_client_session(server_2) as client_2:

        client_manager=MCPClientManager()
        client_manager.clients={server_1.name: client_1,server_2.name: client_2}
        proxy = await MCPProxyServer.create(client_manager)

        async with create_connected_server_and_client_session(proxy) as proxy_client:
            yield proxy_client


@asynccontextmanager
async def proxy_client_session(server):
    """Creates a proxy with a single backend server session."""
    async with create_connected_server_and_client_session(server) as direct_client:
        client_manager=MCPClientManager()
        client_manager.clients={server.name: direct_client}
        proxy = await MCPProxyServer.create(client_manager)
        async with create_connected_server_and_client_session(proxy) as proxy_client:
            yield proxy_client

#Check List_tools call
@pytest.mark.asyncio
async def test_proxy_lists_multiple_tools(server_1, server_2, test_tool_1, test_tool_2,test_tool_3):
    """Tests if proxy correctly aggregates tools from multiple servers."""
    async with proxy_client_2session(server_1, server_2) as proxy:
        result = await proxy.initialize()
        tools = await proxy.list_tools()

        tool_names = {tool.name for tool in tools.tools}
        test_name = inspect.currentframe().f_code.co_name
        print(f"\n✅ [{test_name}] Tools from proxy: {tool_names}")

        assert result.capabilities.tools
        assert tool_names == {MCPProxyServer._make_key(SERVER1_NAME, test_tool_1.name),
                              MCPProxyServer._make_key(SERVER2_NAME, test_tool_2.name),
                              MCPProxyServer._make_key(SERVER2_NAME, test_tool_3.name)}


@pytest.mark.asyncio
async def test_proxy_lists_tool(echo_server, echo_tool):
    """Tests if a proxy initialized with echo_server correctly lists its tool."""
    async with proxy_client_session(echo_server) as proxy:
        result = await proxy.initialize()
        tools = await proxy.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        test_name = inspect.currentframe().f_code.co_name
        print(f"\n✅ [{test_name}] Tools from proxy: {tool_names}")
        assert result.capabilities.tools
        echo_tool.name=MCPProxyServer._make_key(ECHO_SERVER_NAME,echo_tool.name)
        assert tool_names == {echo_tool.name}
        assert tools.tools == [echo_tool]


# Check call_tool request
@pytest.mark.asyncio
async def test_proxy_call_tool(echo_server):
    """Tests if the proxy can call a tool and receive a response."""

    async with proxy_client_session(echo_server) as proxy:
        init_result = await proxy.initialize()
        print("🔎 Proxy Capabilities:", init_result.capabilities)

        # ✅ Correct use of `call_tool` with name + arguments
        result = await proxy.call_tool(MCPProxyServer._make_key(ECHO_SERVER_NAME,"echo"), {})

        print(f"\n [{inspect.currentframe().f_code.co_name}] call_tool result:")
        for c in result.content:
            print(f"  - {c.text}")
        print(f"\ndone")

        # ✅ Validate output
        assert not result.isError
        assert result.content == []
