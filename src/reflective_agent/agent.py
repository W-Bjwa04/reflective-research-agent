"""
agent.py — Stage 1: Tool-calling research agent.

Runs a conversation loop with the LLM:
  1. Inject the research topic and tool schemas.
  2. If the model asks to call a tool, dispatch it and append the result.
  3. Repeat until the model produces a final draft (no more tool calls)
     or until ``max_iterations`` is reached.

The final draft is expected to be a well-structured Markdown report with
inline citations and a Sources section.
"""

from __future__ import annotations

import logging
from typing import Any

from . import llm, tools

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert research analyst. Your task is to investigate the given topic \
thoroughly by using the available search tools, then write a comprehensive research report.

## Workflow
1. Use `arxiv_search` to find relevant academic papers (call it multiple times \
   with different queries if needed).
2. Use `web_search` to gather current news, blogs, and practical insights.
3. Once you have enough information (typically 3–6 tool calls), write the final \
   research report in Markdown.

## Report requirements
- Length: 800–1500 words.
- Sections: Executive Summary, Background, Key Findings, Analysis, Conclusion, Sources.
- Cite every claim with inline brackets like [1], [2] … and list all sources \
  at the end with full URLs.
- Be factual, objective, and comprehensive.

Do not write the report until you have gathered sufficient evidence. \
Use the tools first.
"""


def _extract_assistant_message(response: Any) -> dict[str, Any]:
    """
    Build the assistant message dict to append to history.

    When thinking mode is enabled, DeepSeek includes ``reasoning_content``
    in the response.  We preserve it here to avoid a 400 error on the
    next request.
    """
    choice = response.choices[0]
    msg = choice.message

    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content or "",
    }

    # Preserve tool calls if present
    if msg.tool_calls:
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]

    # Preserve reasoning_content (thinking mode)
    raw = getattr(msg, "model_extra", {}) or {}
    if "reasoning_content" in raw and raw["reasoning_content"]:
        assistant_msg["reasoning_content"] = raw["reasoning_content"]

    return assistant_msg


def run_research_agent(
    topic: str,
    model: str | None = None,
    max_iterations: int = 6,
    verbose: bool = False,
) -> str:
    """
    Run the Stage-1 tool-calling loop and return the final draft report.

    Parameters
    ----------
    topic:
        The research topic supplied by the user.
    model:
        Model override (falls back to ``config.DEEPSEEK_MODEL``).
    max_iterations:
        Maximum tool-calling rounds before forcing a final answer.
    verbose:
        If True, log tool call names and args at INFO level.

    Returns
    -------
    str
        The draft research report in Markdown.

    Raises
    ------
    RuntimeError
        If the agent fails to produce a report within ``max_iterations``.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Research topic: {topic}"},
    ]

    logger.info("Stage 1 — Starting research agent for topic: %r", topic)

    for iteration in range(1, max_iterations + 1):
        logger.info("Stage 1 — Iteration %d/%d", iteration, max_iterations)

        # On the last iteration, tell the model to stop calling tools
        if iteration == max_iterations:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You have reached the maximum number of research iterations. "
                        "Write the final research report now based on the information gathered. "
                        "Do NOT call any more tools."
                    ),
                }
            )
            response = llm.chat_completion(
                messages=messages,
                model=model,
                tools=None,  # Disable tool calling for final answer
            )
        else:
            response = llm.chat_completion(
                messages=messages,
                model=model,
                tools=tools.TOOL_SCHEMAS,
            )

        assistant_msg = _extract_assistant_message(response)
        messages.append(assistant_msg)

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        # ── Handle tool calls ─────────────────────────────────────────────
        if finish_reason == "tool_calls" and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                fn_args = tc.function.arguments

                if verbose:
                    logger.info("  Tool call: %s(%s)", fn_name, fn_args[:200])
                else:
                    logger.info("  Tool call: %s", fn_name)

                result_json = tools.dispatch_tool(fn_name, fn_args)
                logger.debug("  Tool result (first 300 chars): %s", result_json[:300])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_json,
                    }
                )
            continue  # Next iteration to let the model process results

        # ── Final answer ──────────────────────────────────────────────────
        if finish_reason in ("stop", "length") or not choice.message.tool_calls:
            draft = (assistant_msg.get("content") or "").strip()
            if draft:
                logger.info("Stage 1 — Draft report produced (%d chars).", len(draft))
                return draft
            # Empty content — push the model to answer
            messages.append(
                {
                    "role": "user",
                    "content": "Please write the final research report now.",
                }
            )

    raise RuntimeError(
        f"Research agent did not produce a report within {max_iterations} iterations."
    )
