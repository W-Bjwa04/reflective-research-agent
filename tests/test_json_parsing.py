"""
tests/test_json_parsing.py — Tests for reflection.py JSON parsing and repair logic.
"""

from __future__ import annotations

import json
import pytest

from reflective_agent.reflection import _parse_reflection_json, _strip_fences


# ── _strip_fences ─────────────────────────────────────────────────────────────

def test_strip_fences_plain_json():
    raw = '{"key": "value"}'
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_with_json_fence():
    raw = '```json\n{"key": "value"}\n```'
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_with_plain_fence():
    raw = '```\n{"key": "value"}\n```'
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_empty_string():
    assert _strip_fences("") == ""


def test_strip_fences_whitespace_only():
    assert _strip_fences("   \n  ") == ""


# ── _parse_reflection_json ────────────────────────────────────────────────────

VALID_REFLECTION: dict = {
    "reflection": {
        "strengths": ["Clear structure", "Good citations"],
        "weaknesses": ["Thin analysis", "Missing data"],
        "suggestions": ["Add statistics", "Expand conclusion"],
    },
    "revised_report": "# Revised Report\n\nContent here.",
}


def test_parse_valid_json():
    raw = json.dumps(VALID_REFLECTION)
    result = _parse_reflection_json(raw)
    assert result["revised_report"] == "# Revised Report\n\nContent here."
    assert result["reflection"]["strengths"] == ["Clear structure", "Good citations"]


def test_parse_valid_json_with_fences():
    raw = "```json\n" + json.dumps(VALID_REFLECTION) + "\n```"
    result = _parse_reflection_json(raw)
    assert "revised_report" in result


def test_parse_empty_string_raises():
    with pytest.raises(ValueError, match="empty"):
        _parse_reflection_json("")


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="JSON decode error"):
        _parse_reflection_json("{not valid json}")


def test_parse_missing_top_key_raises():
    bad = {"reflection": VALID_REFLECTION["reflection"]}  # missing revised_report
    with pytest.raises(ValueError, match="Missing top-level keys"):
        _parse_reflection_json(json.dumps(bad))


def test_parse_missing_reflection_subkey_raises():
    bad = {
        "reflection": {"strengths": [], "weaknesses": []},  # missing suggestions
        "revised_report": "text",
    }
    with pytest.raises(ValueError, match="Missing reflection sub-keys"):
        _parse_reflection_json(json.dumps(bad))


def test_parse_reflection_not_object_raises():
    bad = {"reflection": ["a", "b"], "revised_report": "text"}
    with pytest.raises(ValueError, match="must be an object"):
        _parse_reflection_json(json.dumps(bad))


def test_parse_top_level_not_object_raises():
    with pytest.raises(ValueError, match="Expected JSON object"):
        _parse_reflection_json(json.dumps(["a", "b"]))
