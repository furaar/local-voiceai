from typing import Any, Optional
from mcp import server, types
from mcp.client.session import ClientSession
from src.utils.logger import get_logger
from src.multimcp.mcp_client import MCPClientManager
from dataclasses import dataclass

@dataclass
class ToolMapping:
    server_name: str
    client: ClientSession
    tool :types.Tool

class MCPProxyServer(server.Server):
    """An MCP Proxy Server that forwards requests to remote MCP servers."""

    def __init__(self, client_manager: MCPClientManager):
        super().__init__("MultiMCP proxy Server")
        self.capabilities: dict[str, types.ServerCapabilities] = {}
        self.tool_to_server: dict[str, ToolMapping] = {}      # Support same tool name in diffrent mcp server
        self.prompt_to_server: dict[str, ClientSession] = {}
        self.resource_to_server: dict[str, ClientSession] = {}
        self._register_request_handlers()
        self.logger = get_logger("multi_mcp.ProxyServer")
        self.client_manager: Optional[MCPClientManager] = client_manager

    @classmethod
    async def create(cls, client_manager: MCPClientManager) -> "MCPProxyServer":
        """Factory method to create and initialize the proxy with clients."""
        proxy = cls(client_manager)
        await proxy.initialize_remote_clients()
        return proxy

    async def initialize_remote_clients(self) -> None:
        """Initialize all remote clients and store their capabilities."""
        for name, client in self.client_manager.clients.items():
            try:
                await self.initialize_single_client(name, client)
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize client {name}: {e}")

    async def initialize_single_client(self, name: str, client: ClientSession) -> None:
        """Initialize a specific client and map its capabilities."""

        self.logger.info(f"try initialize client {name}: {client}")
        result = await client.initialize()
        self.capabilities[name] = result.capabilities

        if result.capabilities.tools:
            await self._initialize_tools_for_client(name,client)

        if result.capabilities.prompts:
            prompts_result = await client.list_prompts()
            for prompt in prompts_result.prompts:
                self.prompt_to_server[prompt.name] = client

        if result.capabilities.resources:
            resources_result = await client.list_resources()
            for resource in resources_result.resources:
                self.resource_to_server[resource.name] = client

    async def register_client(self, name: str, client: ClientSession) -> None:
        """Add a new client and register its capabilities."""
        self.client_manager.clients[name] = client
        # Re-fetch capabilities (like on startup)
        await self.initialize_single_client(name, client)

    async def unregister_client(self, name: str) -> None:
        """Remove a client and clean up all its associated mappings."""
        client = self.client_manager.clients.get(name)
        if not client:
            self.logger.warning(f"⚠️ Tried to unregister unknown client: {name}")
            return

        self.logger.info(f"🗑️ Unregistering client: {name}")
        del self.client_manager.clients[name]

        self.capabilities.pop(name, None)

        self.tool_to_server     = {k: v for k, v in self.tool_to_server.items() if v.client != client}
        self.prompt_to_server   = {k: v for k, v in self.prompt_to_server.items() if client != client}
        self.resource_to_server = {k: v for k, v in self.resource_to_server.items() if client != client}

        self.logger.info(f"✅ Client '{name}' fully unregistered.")


    ## Tools capabilities
    async def _list_tools(self, _: Any) -> types.ServerResult:
        """Aggregate tools from all remote MCP servers and return a combined list."""
        all_tools = []
        for name, client in self.client_manager.clients.items():
            try:
                tools = await self._initialize_tools_for_client(name, client)
                all_tools.extend(tools)  # .tools, not raw list
            except Exception as e:
                self.logger.error(f"Error fetching tools from {name}: {e}")

        return types.ServerResult(tools=all_tools)
    async def _call_tool(self, req: types.CallToolRequest) -> types.ServerResult:
        """Invoke a tool on the correct backend MCP server."""
        tool_name = req.params.name
        tool_item = self.tool_to_server.get(tool_name)

        if tool_item:
            try:
                self.logger.info(f"✅ Calling tool '{tool_name}' on its associated server")
                result = await tool_item.client.call_tool(tool_item.tool.name, req.params.arguments or {})
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to call tool '{tool_name}': {e}")
        else:
            self.logger.error(f"⚠️ Tool '{tool_name}' not found in any server.")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=f"Tool '{tool_name}' not found!")],
            isError=True,
        )

    ## Prompts capabilities
    async def _list_prompts(self, _: Any) -> types.ServerResult:
        """Aggregate prompts from all remote MCP servers and return a combined list."""
        all_prompts = []
        for name, client in self.client_manager.clients.items():
            # Only call servers that support prompts capability
            if not self.capabilities.get(name, {}).get('prompts'):
                continue
            try:
                prompts = await client.list_prompts()
                all_prompts.extend(prompts.prompts)  # .prompts, not raw list
            except Exception as e:
                self.logger.error(f"Error fetching prompts from {name}: {e}")

        return types.ServerResult(prompts=all_prompts)

    async def _get_prompt(self, req: types.GetPromptRequest) -> types.ServerResult:
        """Fetch a specific prompt from the correct backend MCP server."""
        prompt_name = req.params.name
        client = self.prompt_to_server.get(prompt_name)

        if client:
            try:
                result = await client.get_prompt(req.params)
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to get prompt '{prompt_name}': {e}")
        else:
            self.logger.error(f"⚠️ Prompt '{prompt_name}' not found in any server.")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=f"Prompt '{prompt_name}' not found!")],
            isError=True,
        )

    async def _complete(self, req: types.CompleteRequest) -> types.ServerResult:
        """Execute a prompt completion on the relevant MCP server."""
        prompt_name = req.params.prompt
        client = self.prompt_to_server.get(prompt_name)

        if client:
            try:
                result = await client.complete(req.params)
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to complete prompt '{prompt_name}': {e}")
        else:
            self.logger.error(f"⚠️ Prompt '{prompt_name}' not found for completion.")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=f"Prompt '{prompt_name}' not found for completion!")],
            isError=True,
        )

    ## Resources capabilities
    async def _list_resources(self, _: Any) -> types.ServerResult:
        """Aggregate resources from all remote MCP servers and return a combined list."""
        all_resources = []
        for name, client in self.client_manager.clients.items():
            # Only call servers that support resources capability
            if not self.capabilities.get(name, {}).get('resources'):
                continue
            try:
                resources = await client.list_resources()
                all_resources.extend(resources.resources)  # .resources, not raw list
            except Exception as e:
                self.logger.error(f"Error fetching resources from {name}: {e}")

        return types.ServerResult(resources=all_resources)

    async def _read_resource(self, req: types.ReadResourceRequest) -> types.ServerResult:
        """Read a resource from the appropriate backend MCP server."""
        resource_uri = req.params.uri
        client = self.resource_to_server.get(resource_uri)

        if client:
            try:
                result = await client.read_resource(req.params)
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to read resource '{resource_uri}': {e}")
        else:
            self.logger.error(f"⚠️ Resource '{resource_uri}' not found in any server.")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=f"Resource '{resource_uri}' not found!")],
            isError=True,
        )
    async def _subscribe_resource(self, req: types.SubscribeRequest) -> types.ServerResult:
        """Subscribe to a resource for updates on a backend MCP server."""
        uri = req.params.uri
        client = self.resource_to_server.get(uri)

        if client:
            try:
                await client.subscribe_resource(uri)
                return types.ServerResult(types.EmptyResult())
            except Exception as e:
                self.logger.error(f"❌ Failed to subscribe to resource '{uri}': {e}")
        else:
            self.logger.error(f"⚠️ Resource '{uri}' not found for subscription.")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=f"Resource '{uri}' not found for subscription!")],
            isError=True,
        )

    async def _unsubscribe_resource(self, req: types.UnsubscribeRequest) -> types.ServerResult:
        """Unsubscribe from a previously subscribed resource."""
        uri = req.params.uri
        client = self.resource_to_server.get(uri)

        if client:
            try:
                await client.unsubscribe_resource(uri)
                return types.ServerResult(types.EmptyResult())
            except Exception as e:
                self.logger.error(f"❌ Failed to unsubscribe from resource '{uri}': {e}")
        else:
            self.logger.error(f"⚠️ Resource '{uri}' not found for unsubscription.")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=f"Resource '{uri}' not found for unsubscription!")],
            isError=True,
        )

    # Utilization function
    async def _set_logging_level(self, req: types.SetLevelRequest) -> types.ServerResult:
        """Broadcast a new logging level to all connected clients."""
        for client in self.client_manager.clients.values():
            try:
                await client.set_logging_level(req.params.level)
            except Exception as e:
                self.logger.error(f"❌ Failed to set logging level on client: {e}")

        return types.ServerResult(types.EmptyResult())

    async def _send_progress_notification(self, req: types.ProgressNotification) -> None:
        """Relay a progress update to all backend clients."""
        for client in self.client_manager.clients.values():
            try:
                await client.send_progress_notification(
                    req.params.progressToken,
                    req.params.progress,
                    req.params.total,
                )
            except Exception as e:
                self.logger.error(f"❌ Failed to send progress notification: {e}")


    def _register_request_handlers(self) -> None:
        """Dynamically registers handlers for all MCP requests."""

        # Register all request handlers
        self.request_handlers[types.ListPromptsRequest] = self._list_prompts
        self.request_handlers[types.GetPromptRequest]   = self._get_prompt
        self.request_handlers[types.CompleteRequest]    = self._complete

        self.request_handlers[types.ListResourcesRequest] = self._list_resources
        self.request_handlers[types.ReadResourceRequest]  = self._read_resource
        self.request_handlers[types.SubscribeRequest]     = self._subscribe_resource
        self.request_handlers[types.UnsubscribeRequest]   = self._unsubscribe_resource


        self.request_handlers[types.ListToolsRequest] = self._list_tools
        self.request_handlers[types.CallToolRequest]  = self._call_tool

        self.notification_handlers[types.ProgressNotification] = self._send_progress_notification

        self.request_handlers[types.SetLevelRequest]           = self._set_logging_level

    async def _initialize_tools_for_client(self, server_name: str, client: ClientSession) -> list[types.Tool]:
        """Fetch tools from a client, populate tool_to_server, and return them with namespaced keys."""
        tool_list = []

        tools_result = await client.list_tools()
        for tool in tools_result.tools:
            key = self._make_key(server_name, tool.name)

            # Store ToolMapping object
            self.tool_to_server[key] = ToolMapping(
                server_name=server_name,
                client=client,
                tool=tool
            )

            # Create a copy of the tool with updated key as name
            namespaced_tool = tool.model_copy()
            namespaced_tool.name = key
            tool_list.append(namespaced_tool)

        return tool_list

    @staticmethod
    def _make_key(server_name: str, item_name: str) -> str:
        """Returns a namespaced key like 'server_item' to uniquely identify items per server."""
        return f"{server_name}_{item_name}"

    @staticmethod
    def _split_key(key: str) -> tuple[str, str]:
        """Splits a namespaced key back into (server, item)."""
        return key.split("_", 1)
