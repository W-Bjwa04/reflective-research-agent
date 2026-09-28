"""
tests/conftest.py — Shared pytest fixtures and helpers.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


# ── Factories for fake OpenAI response objects ────────────────────────────────

def make_chat_response(
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str = "stop",
    reasoning_content: str | None = None,
) -> MagicMock:
    """Build a minimal fake ``openai.types.chat.ChatCompletion``."""
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()

    message.content = content
    message.tool_calls = None
    message.model_extra = {}

    if reasoning_content:
        message.model_extra = {"reasoning_content": reasoning_content}

    if tool_calls:
        tc_mocks = []
        for tc in tool_calls:
            tc_mock = MagicMock()
            tc_mock.id = tc["id"]
            tc_mock.type = "function"
            fn_mock = MagicMock()
            fn_mock.name = tc["function"]["name"]
            fn_mock.arguments = json.dumps(tc["function"]["arguments"])
            tc_mock.function = fn_mock
            tc_mocks.append(tc_mock)
        message.tool_calls = tc_mocks

    choice.message = message
    choice.finish_reason = finish_reason
    response.choices = [choice]
    return response


@pytest.fixture
def fake_stop_response():
    """A simple stop response with text content."""
    return make_chat_response(content="This is the final report.", finish_reason="stop")


@pytest.fixture
def fake_tool_call_response():
    """A response that requests one tool call."""
    return make_chat_response(
        content="",
        tool_calls=[
            {
                "id": "call_abc123",
                "function": {
                    "name": "arxiv_search",
                    "arguments": {"query": "quantum computing"},
                },
            }
        ],
        finish_reason="tool_calls",
    )
