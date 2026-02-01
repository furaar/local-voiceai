from contextlib import AsyncExitStack
from typing import Dict, Optional
import os

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from src.utils.logger import get_logger

# Defaults for stdio subprocess (match mcp.client.stdio defaults)
DEFAULT_ENCODING = "utf-8"
DEFAULT_ENCODING_ERROR_HANDLER = "strict"


class MCPClientManager:
    """
    Manages the lifecycle of multiple MCP clients (either stdio or SSE).
    Handles creation, storage, and graceful cleanup of client sessions.
    """

    def __init__(self):
        self.stack = AsyncExitStack()
        self.clients: Dict[str, ClientSession] = {}
        self.logger = get_logger("multi_mcp.ClientManager")

    async def create_clients(self, config: dict) -> Dict[str, ClientSession]:
        """
        Creates MCP clients defined in the given config.
        Supports both stdio and SSE transport.

        Args:
            config (dict): Configuration dictionary with "mcpServers" mapping
                           server names to their connection parameters.

        Returns:
            Dict[str, ClientSession]: Dictionary mapping server names to live ClientSession objects.
        """
        await self.stack.__aenter__()  # manually enter the stack once

        for name, server in config.get("mcpServers", {}).items():
            if name in self.clients:
                self.logger.warning(f"⚠️ Client '{name}' already exists and will be overridden.")
            try:
                command = server.get("command")
                url = server.get("url")
                args = server.get("args", [])
                env = server.get("env", {})
                encoding = server.get("encoding", DEFAULT_ENCODING)
                encoding_error_handler = server.get("encoding_error_handler", DEFAULT_ENCODING_ERROR_HANDLER)

                merged_env = os.environ.copy()
                merged_env.update(env)

                if command:
                    self.logger.info(f"🔌 Creating stdio client for {name}")
                    params = StdioServerParameters(
                        command=command,
                        args=args,
                        env=merged_env,
                        encoding=encoding,
                        encoding_error_handler=encoding_error_handler,
                    )
                    read, write = await self.stack.enter_async_context(stdio_client(params))
                    session = await self.stack.enter_async_context(ClientSession(read, write))

                elif url:
                    self.logger.info(f"🌐 Creating SSE client for {name}")
                    read, write = await self.stack.enter_async_context(sse_client(url=url))
                    session = await self.stack.enter_async_context(ClientSession(read, write))

                else:
                    self.logger.warning(f"⚠️ Skipping {name}: No command or URL provided.")
                    continue

                self.clients[name] = session
                self.logger.info(f"✅ Connected to {name}")

            except Exception as e:
                self.logger.error(f"❌ Failed to create client for {name}: {e}")

        return self.clients

    def get_client(self, name: str) -> Optional[ClientSession]:
        """
        Retrieves an existing client by name.

        Args:
            name (str): The name of the client (as defined in config).

        Returns:
            Optional[ClientSession]: The ClientSession object, or None if not found.
        """
        return self.clients.get(name)

    async def close(self) -> None:
        """
        Closes all clients and releases resources managed by the async context stack.
        """
        await self.stack.aclose()
