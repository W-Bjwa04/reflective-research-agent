"""
llm.py — DeepSeek API client wrapper.

Wraps the OpenAI-compatible DeepSeek endpoint with:
  - Configurable thinking mode (disabled by default)
  - Exponential-backoff retries for 429 / 5xx
  - Clear user-facing messages for 401 / 402
  - Optional tool-schema injection
"""

from __future__ import annotations

import logging
import time
from typing import Any

import openai

from . import config

logger = logging.getLogger(__name__)


def _build_extra_body() -> dict[str, Any]:
    """Return the extra_body dict that controls thinking mode."""
    thinking_mode = config.DEEPSEEK_THINKING.strip().lower()
    return {"thinking": {"type": thinking_mode}}


def _make_client() -> openai.OpenAI:
    """Instantiate the OpenAI-compatible DeepSeek client."""
    if not config.DEEPSEEK_API_KEY:
        raise SystemExit(
            "❌  DEEPSEEK_API_KEY is not set.\n"
            "    Get a free key at https://platform.deepseek.com and add it to your .env file."
        )
    return openai.OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )


# Module-level singleton so we don't re-instantiate on every call
_client: openai.OpenAI | None = None


def get_client() -> openai.OpenAI:
    """Return (or lazily create) the shared DeepSeek client."""
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def chat_completion(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] = "auto",
    response_format: dict[str, str] | None = None,
    temperature: float = 0.7,
) -> openai.types.chat.ChatCompletion:
    """
    Send a chat-completion request to DeepSeek with retry logic.

    Parameters
    ----------
    messages:
        The full conversation history in OpenAI message format.
    model:
        Model name; falls back to ``config.DEEPSEEK_MODEL``.
    tools:
        Optional list of tool schemas (function-calling).
    tool_choice:
        How the model should select a tool.  Defaults to ``"auto"``.
    response_format:
        E.g. ``{"type": "json_object"}`` for Stage 2.
    temperature:
        Sampling temperature.

    Returns
    -------
    openai.types.chat.ChatCompletion
        The raw API response object.

    Raises
    ------
    SystemExit
        On unrecoverable auth (401) or billing (402) errors.
    RuntimeError
        If all retry attempts are exhausted.
    """
    resolved_model = model or config.DEEPSEEK_MODEL
    extra_body = _build_extra_body()

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "extra_body": extra_body,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    if response_format:
        kwargs["response_format"] = response_format

    client = get_client()
    last_exc: Exception | None = None

    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        try:
            logger.debug(
                "LLM request attempt %d/%d model=%s",
                attempt,
                config.LLM_MAX_RETRIES,
                resolved_model,
            )
            response = client.chat.completions.create(**kwargs)
            return response

        except openai.AuthenticationError as exc:
            raise SystemExit(
                "❌  Authentication failed (401): your DEEPSEEK_API_KEY is invalid or expired.\n"
                "    Renew it at https://platform.deepseek.com"
            ) from exc

        except openai.PermissionDeniedError as exc:
            # DeepSeek returns 402 for insufficient balance via PermissionDeniedError
            if "402" in str(exc) or "balance" in str(exc).lower():
                raise SystemExit(
                    "❌  Insufficient balance (402): top up your DeepSeek account at "
                    "https://platform.deepseek.com"
                ) from exc
            raise

        except openai.RateLimitError as exc:
            last_exc = exc
            wait = config.LLM_BACKOFF_BASE ** attempt
            logger.warning("Rate limited (429). Retrying in %.1fs …", wait)
            time.sleep(wait)

        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
                wait = config.LLM_BACKOFF_BASE ** attempt
                logger.warning(
                    "Server error %d. Retrying in %.1fs …", exc.status_code, wait
                )
                time.sleep(wait)
            else:
                raise

        except openai.APIConnectionError as exc:
            last_exc = exc
            wait = config.LLM_BACKOFF_BASE ** attempt
            logger.warning("Connection error. Retrying in %.1fs …", wait)
            time.sleep(wait)

    raise RuntimeError(
        f"LLM request failed after {config.LLM_MAX_RETRIES} attempts. "
        f"Last error: {last_exc}"
    )


def get_thinking_mode() -> str:
    """Return the current thinking-mode setting (for display/logging)."""
    return config.DEEPSEEK_THINKING.strip().lower()
