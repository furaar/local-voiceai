# search_server.py — MCP tool: web search + fetch page content
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote_plus

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# Port 8081 is multi-mcp; use 8082 for SearXNG so it does not conflict.
# Set SEARX_URL in .env (e.g. http://localhost:8082) to use SearXNG; if unset, uses DuckDuckGo.
MAX_RESULTS = 5
MAX_PAGE_CONTENT_CHARS = 10_000

mcp = FastMCP("Search")


def _normalize_searx_url(url: str) -> str:
    return url.rstrip("/")


def _search_searx(base_url: str, query: str) -> list[dict[str, Any]]:
    import httpx

    url = f"{base_url}/search?q={quote_plus(query)}&format=json"
    headers = {
        "X-Forwarded-For": "127.0.0.1",
        "X-Real-IP": "127.0.0.1",
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    results = []
    for r in data.get("results", [])[:MAX_RESULTS]:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "") or "",
        })
    return results


def _search_duckduckgo(query: str) -> list[dict[str, Any]]:
    from duckduckgo_search import DDGS

    results = []
    for r in DDGS().text(query, max_results=MAX_RESULTS):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", "") or "",
        })
    return results


@mcp.tool()
async def web(query: str) -> dict[str, Any]:
    """Search the web. Returns a short list of results (title, url, snippet) for the given query.
    Uses SearXNG if SEARX_URL is set (e.g. http://localhost:8082), otherwise DuckDuckGo (no config)."""
    query = (query or "").strip()
    if not query:
        return {"error": "query is empty", "results": []}

    searx_url = _normalize_searx_url(os.getenv("SEARX_URL", "").strip())

    # Use SearXNG if SEARX_URL is set (e.g. http://localhost:8082); otherwise DuckDuckGo
    if searx_url:
        try:
            results = _search_searx(searx_url, query)
            return {"backend": "searxng", "query": query, "results": results}
        except Exception as e:
            return {
                "backend": "searxng",
                "error": str(e),
                "query": query,
                "results": [],
                "hint": "Is SearXNG running? Try SEARX_URL= or unset to use DuckDuckGo.",
            }

    # Fallback: DuckDuckGo (no API key)
    try:
        results = _search_duckduckgo(query)
        return {"backend": "duckduckgo", "query": query, "results": results}
    except Exception as e:
        return {"backend": "duckduckgo", "error": str(e), "query": query, "results": []}


def _fetch_page_content(url: str) -> dict[str, Any]:
    """Fetch URL and extract main text with trafilatura; cap length. Returns dict with content and optional error."""
    import httpx

    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        return {"url": url, "error": f"Could not fetch: {e}", "content": ""}

    try:
        from trafilatura import extract

        text = extract(html, include_comments=False, include_tables=False)
        if not text or not text.strip():
            return {"url": url, "error": "No main content extracted", "content": ""}
        text = re.sub(r"\n{3,}", "\n\n", text.strip())
        if len(text) > MAX_PAGE_CONTENT_CHARS:
            text = text[:MAX_PAGE_CONTENT_CHARS] + "\n[... truncated]"
        return {"url": url, "content": text, "error": ""}
    except Exception as e:
        return {"url": url, "error": str(e), "content": ""}


@mcp.tool()
async def fetch_page(url: str) -> dict[str, Any]:
    """Fetch the main text content of a web page. Use this for URLs from search results; call for up to 5 pages per query to get full content before summarizing."""
    url = (url or "").strip()
    if not url:
        return {"error": "url is empty", "content": ""}
    if not url.startswith("http://") and not url.startswith("https://"):
        return {"error": "url must start with http:// or https://", "content": ""}
    return _fetch_page_content(url)


if __name__ == "__main__":
    mcp.run()
