"""
config.py — Load environment variables and expose typed configuration defaults.

All sensitive values are read from the environment (via .env through python-dotenv).
No secrets are hard-coded here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


# ── DeepSeek ──────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

# "disabled" | "enabled"
DEEPSEEK_THINKING: str = os.environ.get("DEEPSEEK_THINKING", "disabled")

# ── Tool keys ─────────────────────────────────────────────────────────────────
TAVILY_API_KEY: str = os.environ.get("TAVILY_API_KEY", "")

# ── Agent defaults ────────────────────────────────────────────────────────────
DEFAULT_MAX_ITERATIONS: int = int(os.environ.get("MAX_ITERATIONS", "6"))
DEFAULT_OUTPUT_DIR: str = os.environ.get("OUTPUT_DIR", "outputs")

# ── Retry / back-off ──────────────────────────────────────────────────────────
LLM_MAX_RETRIES: int = 3
LLM_BACKOFF_BASE: float = 2.0  # seconds; doubled each attempt
