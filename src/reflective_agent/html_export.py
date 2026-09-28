"""
html_export.py — Stage 3: Convert the revised Markdown report to self-contained HTML.

The LLM generates clean, valid, standalone HTML with inline CSS.
We validate that it starts with <!DOCTYPE html> and retry once if not.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from . import llm

logger = logging.getLogger(__name__)

_HTML_SYSTEM = """\
You are an expert web developer. Convert the given Markdown research report \
into a clean, professional, self-contained HTML document.

## Requirements
- Start with <!DOCTYPE html> on the very first line — no exceptions.
- All CSS must be inline (inside a <style> tag in <head>). No external stylesheets.
- Use a modern, readable typography stack: font-family: 'Segoe UI', system-ui, sans-serif.
- Comfortable line-height (1.7), max-width 860px, centered, padding 2rem.
- Responsive: looks good on both desktop and mobile.
- Dark-mode aware: use @media (prefers-color-scheme: dark) to invert backgrounds \
  and use light text.
- Light mode: white background, near-black text (#1a1a2e or similar).
- Dark mode: dark background (#0f0f1a), light text (#e8e8f0).
- Style headings with a colored accent (e.g. #4f46e5 indigo works in both modes).
- Clickable Sources section: render each [N] citation as a real <a href="..."> link.
- Add a subtle top gradient banner with the report title.
- No JavaScript required; pure HTML + CSS only.
- Output ONLY the HTML document. No prose, no code fences, no explanation.
"""

_HTML_USER_TEMPLATE = """\
Convert this Markdown research report to HTML:

---
{report}
---

Output the complete HTML document starting with <!DOCTYPE html>.
"""

_RETRY_PROMPT = """\
Your previous response did not start with <!DOCTYPE html>.
Return ONLY the HTML document, starting with <!DOCTYPE html> on the very first line.
No code fences, no backticks, no explanation — just raw HTML.
"""


def _strip_markdown_fences(text: str) -> str:
    """Remove ```html ... ``` or ``` ... ``` wrappers."""
    text = text.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _validate_html(html: str) -> bool:
    """Return True if *html* looks like a valid HTML document."""
    return html.strip().lower().startswith("<!doctype html")


def convert_to_html(
    report: str,
    model: str | None = None,
) -> str:
    """
    Ask the LLM to convert *report* (Markdown) into a standalone HTML file.

    Parameters
    ----------
    report:
        The revised Markdown report from Stage 2.
    model:
        Model override.

    Returns
    -------
    str
        A valid, self-contained HTML document string.

    Raises
    ------
    RuntimeError
        If validation fails after one retry.
    """
    logger.info("Stage 3 — Converting report to HTML (%d chars) …", len(report))

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _HTML_SYSTEM},
        {"role": "user", "content": _HTML_USER_TEMPLATE.format(report=report)},
    ]

    response = llm.chat_completion(
        messages=messages,
        model=model,
        temperature=0.3,
    )

    raw = (response.choices[0].message.content or "").strip()
    html = _strip_markdown_fences(raw)

    if _validate_html(html):
        logger.info("Stage 3 — HTML validation passed (%d chars).", len(html))
        return html

    logger.warning("Stage 3 — HTML validation failed; retrying …")

    # ── Retry with a stricter prompt ──────────────────────────────────────
    retry_messages = messages + [
        {"role": "assistant", "content": raw},
        {"role": "user", "content": _RETRY_PROMPT},
    ]

    retry_response = llm.chat_completion(
        messages=retry_messages,
        model=model,
        temperature=0.1,
    )

    retry_raw = (retry_response.choices[0].message.content or "").strip()
    html = _strip_markdown_fences(retry_raw)

    if _validate_html(html):
        logger.info("Stage 3 — HTML validation passed after retry (%d chars).", len(html))
        return html

    raise RuntimeError(
        "Stage 3 failed: LLM did not produce a valid HTML document after retry.\n"
        f"Response start: {html[:200]!r}"
    )
