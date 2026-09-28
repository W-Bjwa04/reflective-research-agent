"""
tests/test_html_validation.py — Tests for HTML export validation logic.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from reflective_agent.html_export import _validate_html, _strip_markdown_fences


# ── _validate_html ────────────────────────────────────────────────────────────

def test_validate_html_valid_doctype():
    html = "<!DOCTYPE html>\n<html><head></head><body></body></html>"
    assert _validate_html(html) is True


def test_validate_html_valid_lowercase_doctype():
    html = "<!doctype html>\n<html></html>"
    assert _validate_html(html) is True


def test_validate_html_leading_whitespace():
    html = "  \n<!DOCTYPE html><html></html>"
    assert _validate_html(html) is True


def test_validate_html_no_doctype():
    html = "<html><head></head><body></body></html>"
    assert _validate_html(html) is False


def test_validate_html_markdown_fence_not_valid():
    html = "```html\n<!DOCTYPE html><html></html>\n```"
    assert _validate_html(html) is False


def test_validate_html_empty_string():
    assert _validate_html("") is False


# ── _strip_markdown_fences ────────────────────────────────────────────────────

def test_strip_html_fence():
    raw = "```html\n<!DOCTYPE html>\n```"
    assert _strip_markdown_fences(raw) == "<!DOCTYPE html>"


def test_strip_plain_fence():
    raw = "```\n<!DOCTYPE html>\n```"
    assert _strip_markdown_fences(raw) == "<!DOCTYPE html>"


def test_strip_no_fence_passthrough():
    raw = "<!DOCTYPE html><html></html>"
    assert _strip_markdown_fences(raw) == raw


# ── convert_to_html (mocked LLM) ─────────────────────────────────────────────

def _make_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


@patch("reflective_agent.html_export.llm.chat_completion")
def test_convert_to_html_valid_on_first_try(mock_llm):
    html_content = "<!DOCTYPE html>\n<html><body><h1>Report</h1></body></html>"
    mock_llm.return_value = _make_response(html_content)

    from reflective_agent.html_export import convert_to_html
    result = convert_to_html("# Test Report\n\nSome content.")
    assert result.strip().lower().startswith("<!doctype html")
    assert mock_llm.call_count == 1


@patch("reflective_agent.html_export.llm.chat_completion")
def test_convert_to_html_strips_fences(mock_llm):
    html_content = "<!DOCTYPE html>\n<html><body>Report</body></html>"
    mock_llm.return_value = _make_response(f"```html\n{html_content}\n```")

    from reflective_agent.html_export import convert_to_html
    result = convert_to_html("# Test")
    assert result.strip().lower().startswith("<!doctype html")


@patch("reflective_agent.html_export.llm.chat_completion")
def test_convert_to_html_retries_on_bad_output(mock_llm):
    bad_response = _make_response("Sorry, here is some text without DOCTYPE.")
    good_html = "<!DOCTYPE html>\n<html><body>Fixed</body></html>"
    good_response = _make_response(good_html)
    mock_llm.side_effect = [bad_response, good_response]

    from reflective_agent.html_export import convert_to_html
    result = convert_to_html("# Test")
    assert result.strip().lower().startswith("<!doctype html")
    assert mock_llm.call_count == 2


@patch("reflective_agent.html_export.llm.chat_completion")
def test_convert_to_html_raises_after_two_failures(mock_llm):
    bad_response = _make_response("Not HTML at all.")
    mock_llm.return_value = bad_response

    from reflective_agent.html_export import convert_to_html
    with pytest.raises(RuntimeError, match="Stage 3 failed"):
        convert_to_html("# Test")
