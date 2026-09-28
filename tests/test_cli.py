"""
tests/test_cli.py — Tests for CLI argument parsing.
"""

from __future__ import annotations

import pytest

from reflective_agent.cli import build_parser, _slugify


# ── _slugify ──────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert _slugify("Quantum Computing") == "quantum-computing"


def test_slugify_special_chars():
    assert _slugify("AI & Machine Learning!") == "ai-machine-learning"


def test_slugify_multiple_spaces():
    assert _slugify("large  language   models") == "large-language-models"


def test_slugify_already_slugified():
    assert _slugify("deep-learning") == "deep-learning"


def test_slugify_long_string():
    long = "a" * 100
    result = _slugify(long)
    assert len(result) <= 60


# ── Argument parser ───────────────────────────────────────────────────────────

def test_parser_topic_required():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_topic_parsed():
    parser = build_parser()
    args = parser.parse_args(["quantum entanglement"])
    assert args.topic == "quantum entanglement"


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["test topic"])
    assert args.max_iterations == 6
    assert args.output_dir == "outputs"
    assert args.open is False
    assert args.verbose is False
    assert args.save_json is False


def test_parser_custom_model():
    parser = build_parser()
    args = parser.parse_args(["topic", "--model", "deepseek-v4-flash"])
    assert args.model == "deepseek-v4-flash"


def test_parser_max_iterations():
    parser = build_parser()
    args = parser.parse_args(["topic", "--max-iterations", "10"])
    assert args.max_iterations == 10


def test_parser_output_dir():
    parser = build_parser()
    args = parser.parse_args(["topic", "--output-dir", "my-reports"])
    assert args.output_dir == "my-reports"


def test_parser_open_flag():
    parser = build_parser()
    args = parser.parse_args(["topic", "--open"])
    assert args.open is True


def test_parser_verbose_flag():
    parser = build_parser()
    args = parser.parse_args(["topic", "--verbose"])
    assert args.verbose is True


def test_parser_save_json_flag():
    parser = build_parser()
    args = parser.parse_args(["topic", "--save-json"])
    assert args.save_json is True


def test_parser_all_flags():
    parser = build_parser()
    args = parser.parse_args([
        "CRISPR gene editing",
        "--model", "deepseek-v4-flash",
        "--max-iterations", "8",
        "--output-dir", "./reports",
        "--save-json",
        "--open",
        "--verbose",
    ])
    assert args.topic == "CRISPR gene editing"
    assert args.model == "deepseek-v4-flash"
    assert args.max_iterations == 8
    assert args.output_dir == "./reports"
    assert args.save_json is True
    assert args.open is True
    assert args.verbose is True
