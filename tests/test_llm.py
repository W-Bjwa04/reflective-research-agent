"""
tests/test_llm.py — Tests for LLM wrapper: thinking mode params and retry logic.

All tests mock the OpenAI client; no real API calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import openai
import pytest


# ── Thinking mode extra_body ──────────────────────────────────────────────────

def test_thinking_disabled_extra_body():
    """Default thinking mode should produce type=disabled in extra_body."""
    with patch("reflective_agent.llm.config") as mock_cfg:
        mock_cfg.DEEPSEEK_THINKING = "disabled"
        mock_cfg.DEEPSEEK_API_KEY = "test-key"
        mock_cfg.DEEPSEEK_BASE_URL = "https://api.deepseek.com"
        mock_cfg.DEEPSEEK_MODEL = "deepseek-v4-flash"
        mock_cfg.LLM_MAX_RETRIES = 3
        mock_cfg.LLM_BACKOFF_BASE = 0.01

        from reflective_agent.llm import _build_extra_body
        body = _build_extra_body()
        assert body == {"thinking": {"type": "disabled"}}


def test_thinking_enabled_extra_body():
    """When DEEPSEEK_THINKING=enabled, extra_body should reflect it."""
    with patch("reflective_agent.llm.config") as mock_cfg:
        mock_cfg.DEEPSEEK_THINKING = "enabled"
        mock_cfg.DEEPSEEK_API_KEY = "test-key"
        mock_cfg.DEEPSEEK_BASE_URL = "https://api.deepseek.com"
        mock_cfg.DEEPSEEK_MODEL = "deepseek-v4-flash"
        mock_cfg.LLM_MAX_RETRIES = 3
        mock_cfg.LLM_BACKOFF_BASE = 0.01

        from reflective_agent.llm import _build_extra_body
        body = _build_extra_body()
        assert body == {"thinking": {"type": "enabled"}}


# ── API key check ─────────────────────────────────────────────────────────────

def test_missing_api_key_raises_system_exit():
    with patch("reflective_agent.llm.config") as mock_cfg:
        mock_cfg.DEEPSEEK_API_KEY = ""
        mock_cfg.DEEPSEEK_BASE_URL = "https://api.deepseek.com"

        # Reset module-level client singleton
        import reflective_agent.llm as llm_mod
        llm_mod._client = None

        with pytest.raises(SystemExit) as exc_info:
            llm_mod._make_client()
        assert "DEEPSEEK_API_KEY" in str(exc_info.value)


# ── Retry logic ───────────────────────────────────────────────────────────────

@patch("reflective_agent.llm.time.sleep", return_value=None)
@patch("reflective_agent.llm.get_client")
@patch("reflective_agent.llm._build_extra_body", return_value={"thinking": {"type": "disabled"}})
@patch("reflective_agent.llm.config")
def test_rate_limit_retries(mock_cfg, mock_body, mock_client_fn, mock_sleep):
    mock_cfg.DEEPSEEK_MODEL = "deepseek-v4-flash"
    mock_cfg.LLM_MAX_RETRIES = 3
    mock_cfg.LLM_BACKOFF_BASE = 0.01

    fake_client = MagicMock()
    # Fail twice with rate limit, succeed on third
    good_response = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        openai.RateLimitError("rate limited", response=MagicMock(), body={}),
        openai.RateLimitError("rate limited", response=MagicMock(), body={}),
        good_response,
    ]
    mock_client_fn.return_value = fake_client

    from reflective_agent.llm import chat_completion
    result = chat_completion(messages=[{"role": "user", "content": "hello"}])
    assert result is good_response
    assert fake_client.chat.completions.create.call_count == 3


@patch("reflective_agent.llm.time.sleep", return_value=None)
@patch("reflective_agent.llm.get_client")
@patch("reflective_agent.llm._build_extra_body", return_value={"thinking": {"type": "disabled"}})
@patch("reflective_agent.llm.config")
def test_exhausted_retries_raises_runtime_error(mock_cfg, mock_body, mock_client_fn, mock_sleep):
    mock_cfg.DEEPSEEK_MODEL = "deepseek-v4-flash"
    mock_cfg.LLM_MAX_RETRIES = 3
    mock_cfg.LLM_BACKOFF_BASE = 0.01

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = openai.RateLimitError(
        "always rate limited", response=MagicMock(), body={}
    )
    mock_client_fn.return_value = fake_client

    from reflective_agent.llm import chat_completion
    with pytest.raises(RuntimeError, match="failed after"):
        chat_completion(messages=[{"role": "user", "content": "hello"}])


# ── get_thinking_mode ─────────────────────────────────────────────────────────

def test_get_thinking_mode_default():
    with patch("reflective_agent.llm.config") as mock_cfg:
        mock_cfg.DEEPSEEK_THINKING = "disabled"
        from reflective_agent.llm import get_thinking_mode
        assert get_thinking_mode() == "disabled"
