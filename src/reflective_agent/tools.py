"""
tools.py — Search tool implementations, JSON schemas, and dispatcher.

Tools exposed to the LLM:
  • arxiv_search  — search arXiv for academic papers
  • web_search    — Tavily (preferred) or DuckDuckGo fallback

The ``TOOL_SCHEMAS`` list follows the OpenAI function-calling spec and is
passed verbatim to the chat-completion API.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── arXiv ─────────────────────────────────────────────────────────────────────

def arxiv_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Search arXiv for papers matching *query*.

    Parameters
    ----------
    query:
        Free-form search string.
    max_results:
        Maximum number of results to return (1–20).

    Returns
    -------
    list[dict]
        Each dict has keys: title, authors, published, summary, url.
        On error, returns a single-element list with an ``error`` key.
    """
    try:
        import arxiv  # type: ignore[import]

        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for paper in client.results(search):
            results.append(
                {
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors],
                    "published": paper.published.strftime("%Y-%m-%d") if paper.published else "unknown",
                    "summary": paper.summary[:600].replace("\n", " "),
                    "url": paper.entry_id,
                }
            )
        logger.info("arxiv_search('%s') → %d results", query, len(results))
        return results if results else [{"error": f"No arXiv results found for: {query!r}"}]

    except Exception as exc:  # noqa: BLE001
        logger.error("arxiv_search error: %s", exc)
        return [{"error": f"arxiv_search failed: {exc}"}]


# ── Web search ────────────────────────────────────────────────────────────────

def _tavily_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """Inner helper that uses Tavily; raises if key not set."""
    from . import config

    if not config.TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")

    from tavily import TavilyClient  # type: ignore[import]

    client = TavilyClient(api_key=config.TAVILY_API_KEY)
    response = client.search(query=query, max_results=max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:600],
        }
        for r in response.get("results", [])
    ]


def _ddgs_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """Inner helper that uses DuckDuckGo (no key required)."""
    from ddgs import DDGS  # type: ignore[import]

    with DDGS() as ddgs:
        hits = list(ddgs.text(query, max_results=max_results))

    return [
        {
            "title": h.get("title", ""),
            "url": h.get("href", ""),
            "content": h.get("body", "")[:600],
        }
        for h in hits
    ]


def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Search the web for *query*, preferring Tavily, falling back to DuckDuckGo.

    Parameters
    ----------
    query:
        Free-form search string.
    max_results:
        Maximum number of results to return (1–20).

    Returns
    -------
    list[dict]
        Each dict has keys: title, url, content.
        On error, returns a single-element list with an ``error`` key.
    """
    try:
        results = _tavily_search(query, max_results)
        logger.info("web_search (Tavily) '%s' → %d results", query, len(results))
        return results or [{"error": f"No Tavily results for: {query!r}"}]
    except ValueError:
        logger.debug("Tavily key not set; falling back to DuckDuckGo")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tavily failed (%s); falling back to DuckDuckGo", exc)

    try:
        results = _ddgs_search(query, max_results)
        logger.info("web_search (DuckDuckGo) '%s' → %d results", query, len(results))
        return results or [{"error": f"No DuckDuckGo results for: {query!r}"}]
    except Exception as exc:  # noqa: BLE001
        logger.error("web_search (DuckDuckGo) error: %s", exc)
        return [{"error": f"web_search failed: {exc}"}]


# ── OpenAI tool schemas ───────────────────────────────────────────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "arxiv_search",
            "description": (
                "Search arXiv for academic papers relevant to a query. "
                "Returns title, authors, publication date, abstract summary, and URL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (keywords, phrases, or paper titles).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 20).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information on a topic. "
                "Uses Tavily if a key is configured, otherwise DuckDuckGo. "
                "Returns title, URL, and a content snippet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 20).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# ── Dispatcher ────────────────────────────────────────────────────────────────

_TOOL_MAP: dict[str, Any] = {
    "arxiv_search": arxiv_search,
    "web_search": web_search,
}


def dispatch_tool(name: str, arguments_json: str) -> str:
    """
    Parse *arguments_json*, call the named tool, and return a JSON string result.

    Parameters
    ----------
    name:
        Tool name (must match a key in ``_TOOL_MAP``).
    arguments_json:
        Raw JSON string of arguments as returned by the model.

    Returns
    -------
    str
        JSON-encoded result ready to be inserted as a ``tool`` role message.
    """
    if name not in _TOOL_MAP:
        result = {"error": f"Unknown tool: {name!r}. Available: {list(_TOOL_MAP)}"}
        logger.warning("Dispatch: %s", result["error"])
        return json.dumps(result)

    try:
        args: dict[str, Any] = json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        result = {"error": f"Invalid JSON arguments for {name!r}: {exc}"}
        logger.error("Dispatch JSON parse error: %s", exc)
        return json.dumps(result)

    if not isinstance(args, dict):
        result = {"error": f"Arguments for {name!r} must be a JSON object, got {type(args).__name__}"}
        return json.dumps(result)

    logger.info("Dispatching tool %r with args: %s", name, args)
    try:
        output = _TOOL_MAP[name](**args)
        return json.dumps(output, ensure_ascii=False)
    except TypeError as exc:
        result = {"error": f"Tool {name!r} called with invalid arguments: {exc}"}
        logger.error("Dispatch TypeError: %s", exc)
        return json.dumps(result)
    except Exception as exc:  # noqa: BLE001
        result = {"error": f"Tool {name!r} raised an unexpected error: {exc}"}
        logger.error("Dispatch unexpected error: %s", exc, exc_info=True)
        return json.dumps(result)
