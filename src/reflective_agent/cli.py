"""
cli.py — Command-line interface for the Reflective Research Agent.

Entry point: ``research-agent <topic> [options]``

Orchestrates the three pipeline stages:
  Stage 1 → Tool-calling research agent (agent.py)
  Stage 2 → Reflection + rewrite        (reflection.py)
  Stage 3 → HTML export                 (html_export.py)

All output files are saved under ``<output_dir>/<slug>-<timestamp>/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from . import agent, config, html_export, reflection

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert *text* to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quieten noisy third-party loggers unless verbose
    if not verbose:
        for noisy in ("httpx", "httpcore", "openai", "arxiv", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def _make_output_dir(base_dir: str, topic: str) -> Path:
    slug = _slugify(topic)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(base_dir) / f"{slug}-{timestamp}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save(path: Path, content: str, label: str) -> None:
    path.write_text(content, encoding="utf-8")
    logger.info("💾  Saved %s → %s", label, path)


def _print_banner(topic: str) -> None:
    width = 70
    print("\n" + "═" * width)
    print("  🔬  Reflective Research Agent")
    print(f"  📌  Topic: {topic}")
    print("═" * width + "\n")


def _print_stage(n: int, name: str) -> None:
    icons = {1: "🔍", 2: "🪞", 3: "🌐"}
    print(f"\n{'─' * 60}")
    print(f"  {icons.get(n, '▶')}  Stage {n}: {name}")
    print(f"{'─' * 60}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace) -> None:
    """Execute the full three-stage pipeline."""
    _print_banner(args.topic)

    # ── Stage 1 ───────────────────────────────────────────────────────────
    _print_stage(1, "Gathering sources with tool-calling agent …")
    draft = agent.run_research_agent(
        topic=args.topic,
        model=args.model,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
    )
    print(f"✅  Draft report ready ({len(draft)} chars)")

    # ── Stage 2 ───────────────────────────────────────────────────────────
    _print_stage(2, "Reflecting and rewriting …")
    reflection_data = reflection.reflect_and_rewrite(draft=draft, model=args.model)
    revised = reflection_data["revised_report"]
    ref = reflection_data["reflection"]

    print("✅  Reflection complete.")
    print(f"   Strengths : {len(ref.get('strengths', []))}")
    print(f"   Weaknesses: {len(ref.get('weaknesses', []))}")
    print(f"   Suggestions applied: {len(ref.get('suggestions', []))}")

    # ── Stage 3 ───────────────────────────────────────────────────────────
    _print_stage(3, "Generating HTML report …")
    html = html_export.convert_to_html(report=revised, model=args.model)
    print(f"✅  HTML report ready ({len(html)} chars)")

    # ── Save outputs ──────────────────────────────────────────────────────
    out_dir = _make_output_dir(args.output_dir, args.topic)
    _save(out_dir / "draft.md", draft, "Draft report")
    _save(out_dir / "final_report.md", revised, "Final report (Markdown)")
    _save(out_dir / "report.html", html, "Final report (HTML)")

    if args.save_json:
        _save(
            out_dir / "reflection.json",
            json.dumps(reflection_data, indent=2, ensure_ascii=False),
            "Reflection JSON",
        )
    else:
        # Always save reflection JSON alongside other outputs
        _save(
            out_dir / "reflection.json",
            json.dumps(reflection_data, indent=2, ensure_ascii=False),
            "Reflection JSON",
        )

    html_path = out_dir / "report.html"
    print(f"\n{'═' * 70}")
    print(f"  🎉  All done!  Output folder: {out_dir}")
    print(f"  📄  HTML report: {html_path}")
    print(f"{'═' * 70}\n")

    if args.open:
        webbrowser.open(html_path.resolve().as_uri())
        print("🌐  Opened report in your default browser.")


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-agent",
        description=(
            "Reflective Research Agent — gather sources, write, reflect, "
            "and export a research report as HTML."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  research-agent \"quantum computing applications\"\n"
            "  research-agent \"CRISPR gene editing\" --model deepseek-v4-flash --max-iterations 8\n"
            "  research-agent \"large language models\" --output-dir ./my-reports --open\n"
        ),
    )

    parser.add_argument(
        "topic",
        metavar="TOPIC",
        help="The research topic to investigate (wrap in quotes if multi-word).",
    )
    parser.add_argument(
        "--model",
        default=config.DEEPSEEK_MODEL,
        metavar="MODEL",
        help=f"DeepSeek model name (default: {config.DEEPSEEK_MODEL}).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=config.DEFAULT_MAX_ITERATIONS,
        metavar="N",
        help=f"Max tool-calling iterations in Stage 1 (default: {config.DEFAULT_MAX_ITERATIONS}).",
    )
    parser.add_argument(
        "--output-dir",
        default=config.DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Directory for output files (default: {config.DEFAULT_OUTPUT_DIR!r}).",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save the reflection JSON separately (it is always saved; this flag is a no-op kept for backwards compat).",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated HTML report in your default browser when done.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging (prints tool arguments, raw API responses, etc.).",
    )

    return parser


def main() -> None:
    """CLI entry point called by the ``research-agent`` console script."""
    parser = build_parser()
    args = parser.parse_args()

    _setup_logging(args.verbose)

    # Validate API key early
    if not config.DEEPSEEK_API_KEY:
        print(
            "❌  Error: DEEPSEEK_API_KEY environment variable is not set.\n"
            "    1. Get a free key at https://platform.deepseek.com\n"
            "    2. Copy .env.example to .env and add your key.\n"
            "    3. Re-run the command.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        run_pipeline(args)
    except RuntimeError as exc:
        logger.error("Pipeline error: %s", exc)
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️   Interrupted by user. Partial outputs may have been saved.", file=sys.stderr)
        sys.exit(130)
