"""
reflection.py — Stage 2: Reflect on the draft and produce a revised report.

The LLM is asked to return a strict JSON object with:
  {
    "reflection": {
      "strengths": ["..."],
      "weaknesses": ["..."],
      "suggestions": ["..."]
    },
    "revised_report": "..."
  }

Robust parsing: strip markdown code fences, validate required keys,
retry once with a repair prompt if output is malformed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from . import llm

logger = logging.getLogger(__name__)

_REFLECTION_SYSTEM = """\
You are a senior research editor. Your task is to critically evaluate a research \
report and produce an improved version.

You MUST return valid JSON only — no prose before or after the JSON block.

The JSON must have exactly this shape:
{
  "reflection": {
    "strengths": ["strength 1", "strength 2"],
    "weaknesses": ["weakness 1", "weakness 2"],
    "suggestions": ["suggestion 1", "suggestion 2"]
  },
  "revised_report": "Full revised Markdown report goes here as a single string."
}

## Instructions
- `strengths`: 2–4 things the draft does well.
- `weaknesses`: 2–4 specific gaps, errors, or weak areas.
- `suggestions`: 2–4 concrete improvements you applied.
- `revised_report`: A fully rewritten, improved Markdown report addressing the \
  weaknesses. Keep all citations and URLs. Expand thin sections. \
  Improve clarity and structure.
"""

_REFLECTION_USER_TEMPLATE = """\
Here is the draft research report to evaluate and improve:

---
{draft}
---

Return the JSON object now.
"""

_REPAIR_PROMPT = """\
Your previous response was not valid JSON or was missing required keys.
Required shape:
{{
  "reflection": {{"strengths": [...], "weaknesses": [...], "suggestions": [...]}},
  "revised_report": "..."
}}

Previous response (first 500 chars):
{prev}

Please return ONLY the corrected JSON object with no additional text.
"""


def _strip_fences(text: str) -> str:
    """Remove leading/trailing Markdown code fences (```json ... ```)."""
    text = text.strip()
    # Match ```json or ``` at start
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_reflection_json(raw: str) -> dict[str, Any]:
    """
    Attempt to parse *raw* as a reflection JSON object.

    Returns the parsed dict on success, raises ValueError otherwise.
    """
    cleaned = _strip_fences(raw)
    if not cleaned:
        raise ValueError("LLM returned an empty response")

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON decode error: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    required_top = {"reflection", "revised_report"}
    missing_top = required_top - data.keys()
    if missing_top:
        raise ValueError(f"Missing top-level keys: {missing_top}")

    reflection = data["reflection"]
    if not isinstance(reflection, dict):
        raise ValueError("'reflection' must be an object")

    required_reflection = {"strengths", "weaknesses", "suggestions"}
    missing_ref = required_reflection - reflection.keys()
    if missing_ref:
        raise ValueError(f"Missing reflection sub-keys: {missing_ref}")

    return data


def reflect_and_rewrite(
    draft: str,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Ask the LLM to critique and rewrite *draft*, returning structured JSON.

    Parameters
    ----------
    draft:
        The Markdown draft from Stage 1.
    model:
        Model override.

    Returns
    -------
    dict
        Parsed JSON with keys ``reflection`` (dict) and ``revised_report`` (str).

    Raises
    ------
    RuntimeError
        If both the initial request and the repair retry fail to produce
        valid JSON.
    """
    logger.info("Stage 2 — Reflecting on draft (%d chars) …", len(draft))

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _REFLECTION_SYSTEM},
        {
            "role": "user",
            "content": _REFLECTION_USER_TEMPLATE.format(draft=draft),
        },
    ]

    response = llm.chat_completion(
        messages=messages,
        model=model,
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    raw = (response.choices[0].message.content or "").strip()
    logger.debug("Stage 2 — Raw LLM response (first 500 chars): %s", raw[:500])

    # ── First parse attempt ───────────────────────────────────────────────
    try:
        result = _parse_reflection_json(raw)
        logger.info("Stage 2 — Reflection JSON parsed successfully.")
        return result
    except ValueError as exc:
        logger.warning("Stage 2 — First parse failed: %s. Attempting repair …", exc)

    # ── Repair retry ──────────────────────────────────────────────────────
    repair_messages = messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": _REPAIR_PROMPT.format(prev=raw[:500]),
        },
    ]

    repair_response = llm.chat_completion(
        messages=repair_messages,
        model=model,
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    repaired_raw = (repair_response.choices[0].message.content or "").strip()
    logger.debug("Stage 2 — Repaired response (first 500 chars): %s", repaired_raw[:500])

    try:
        result = _parse_reflection_json(repaired_raw)
        logger.info("Stage 2 — Reflection JSON repaired and parsed successfully.")
        return result
    except ValueError as exc:
        raise RuntimeError(
            f"Stage 2 failed: Could not obtain valid reflection JSON after repair. "
            f"Last error: {exc}\nLast raw response: {repaired_raw[:300]}"
        ) from exc
