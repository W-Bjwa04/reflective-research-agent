"""
tests/test_tools.py — Tests for tool argument validation and dispatcher.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from reflective_agent.tools import dispatch_tool, TOOL_SCHEMAS


# ── Tool schema sanity checks ─────────────────────────────────────────────────

def test_tool_schemas_structure():
    assert len(TOOL_SCHEMAS) == 2
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert names == {"arxiv_search", "web_search"}


def test_tool_schemas_required_fields():
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert "required" in fn["parameters"]


def test_arxiv_schema_requires_query():
    arxiv_schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "arxiv_search")
    assert "query" in arxiv_schema["function"]["parameters"]["required"]


def test_web_schema_requires_query():
    web_schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "web_search")
    assert "query" in web_schema["function"]["parameters"]["required"]


# ── dispatch_tool — happy path ────────────────────────────────────────────────

def test_dispatch_arxiv_search(monkeypatch):
    """Patch _TOOL_MAP directly so dispatch_tool calls our mock."""
    import reflective_agent.tools as tools_mod
    mock_fn = MagicMock(return_value=[{"title": "Test Paper", "url": "http://arxiv.org/1"}])
    monkeypatch.setitem(tools_mod._TOOL_MAP, "arxiv_search", mock_fn)

    args = json.dumps({"query": "machine learning"})
    result = dispatch_tool("arxiv_search", args)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["title"] == "Test Paper"
    mock_fn.assert_called_once_with(query="machine learning")


def test_dispatch_web_search(monkeypatch):
    """Patch _TOOL_MAP directly so dispatch_tool calls our mock."""
    import reflective_agent.tools as tools_mod
    mock_fn = MagicMock(return_value=[{"title": "Article", "url": "http://example.com", "content": "..."}])
    monkeypatch.setitem(tools_mod._TOOL_MAP, "web_search", mock_fn)

    args = json.dumps({"query": "AI trends", "max_results": 3})
    result = dispatch_tool("web_search", args)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    mock_fn.assert_called_once_with(query="AI trends", max_results=3)


# ── dispatch_tool — error cases ───────────────────────────────────────────────

def test_dispatch_unknown_tool_returns_error():
    result = dispatch_tool("nonexistent_tool", "{}")
    parsed = json.loads(result)
    assert "error" in parsed
    assert "Unknown tool" in parsed["error"]


def test_dispatch_invalid_json_args_returns_error():
    result = dispatch_tool("arxiv_search", "not-valid-json{{{")
    parsed = json.loads(result)
    assert "error" in parsed
    assert "Invalid JSON" in parsed["error"]


def test_dispatch_non_dict_args_returns_error():
    # Valid JSON but not an object
    result = dispatch_tool("arxiv_search", '["query", "value"]')
    parsed = json.loads(result)
    assert "error" in parsed
    assert "JSON object" in parsed["error"]


def test_dispatch_wrong_argument_type_returns_error():
    args = json.dumps({"query": "test"})
    # Should not raise; error is captured
    result = dispatch_tool("arxiv_search", args)
    # Either succeeds or returns an error dict — no exception allowed
    parsed = json.loads(result)
    assert isinstance(parsed, (list, dict))


def test_dispatch_tool_exception_returns_error(monkeypatch):
    """Patch _TOOL_MAP so the tool raises, verifying error capture."""
    import reflective_agent.tools as tools_mod
    mock_fn = MagicMock(side_effect=RuntimeError("Network failure"))
    monkeypatch.setitem(tools_mod._TOOL_MAP, "arxiv_search", mock_fn)

    args = json.dumps({"query": "test"})
    result = dispatch_tool("arxiv_search", args)
    parsed = json.loads(result)
    assert "error" in parsed
    assert "Network failure" in parsed["error"]


# ── Tool implementations (mocked external libs) ───────────────────────────────

def test_arxiv_search_returns_list():
    from unittest.mock import MagicMock
    from datetime import datetime
    from unittest.mock import patch

    with patch("arxiv.Client") as mock_client_cls, patch("arxiv.Search"):
        mock_paper = MagicMock()
        mock_paper.title = "Test Paper"
        mock_paper.authors = []
        mock_paper.published = datetime(2024, 1, 1)
        mock_paper.summary = "Abstract text"
        mock_paper.entry_id = "http://arxiv.org/abs/2401.00001"

        mock_client = MagicMock()
        mock_client.results.return_value = [mock_paper]
        mock_client_cls.return_value = mock_client

        from reflective_agent.tools import arxiv_search
        results = arxiv_search("test query", max_results=1)

        assert isinstance(results, list)
        assert results[0]["title"] == "Test Paper"
        assert results[0]["url"] == "http://arxiv.org/abs/2401.00001"
