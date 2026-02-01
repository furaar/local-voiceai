import asyncio
import argparse
import os

from dotenv import load_dotenv

from src.multimcp.multi_mcp import MultiMCP, _resolve_config_path

load_dotenv()


def parse_args():
    default_config = os.getenv("MCP_CONFIG", "config/mcp.json")
    parser = argparse.ArgumentParser(description="Run MultiMCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=default_config,
        help="Path to MCP config JSON file (default: config/mcp.json or MCP_CONFIG env)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the SSE server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind the SSE server",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = _resolve_config_path(args.config)
    server = MultiMCP(
        transport=args.transport,
        config=config_path,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
