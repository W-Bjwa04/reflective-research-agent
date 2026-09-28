# 🔬 Reflective Research Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Powered by DeepSeek](https://img.shields.io/badge/Powered%20by-DeepSeek-8b5cf6)](https://platform.deepseek.com)
[![arXiv](https://img.shields.io/badge/arXiv-search-red)](https://arxiv.org/)
[![Tests](https://img.shields.io/badge/tests-59%20passed-brightgreen)](tests/)

> A CLI agentic-AI tool that researches any topic, reflects on its own output, and exports a polished HTML report — all powered by the DeepSeek API.

---

## ✨ What It Does

Give it a research topic. It handles the rest:

1. **🔍 Stage 1 — Research** &nbsp;|&nbsp; The LLM autonomously calls `arxiv_search` and `web_search` tools, accumulates academic papers and web sources, then writes a fully-cited Markdown draft.
2. **🪞 Stage 2 — Reflect & Rewrite** &nbsp;|&nbsp; A second LLM pass critiques the draft (strengths, weaknesses, suggestions) and produces a structured JSON payload containing an improved report.
3. **🌐 Stage 3 — HTML Export** &nbsp;|&nbsp; The revised report is converted into a beautiful, self-contained HTML file with inline CSS, responsive layout, dark-mode support, and clickable citations.

```
research-agent "radio observations of recurrent novae"
```

That's it. Three stages, one command, zero manual effort.

---

## 🗺️ Architecture

```
User: research topic
        │
        ▼
┌──────────────────────────────────────┐
│  Stage 1 · Tool-Calling Loop         │
│  agent.py                            │
│                                      │
│  LLM ──► arxiv_search ──► results   │
│      └──► web_search  ──► results   │
│  (repeats up to max_iterations)      │
│                            │         │
│                      Draft Report    │
└────────────────────────────┼─────────┘
                             │
                             ▼
┌──────────────────────────────────────┐
│  Stage 2 · Reflection + Rewrite      │
│  reflection.py                       │
│                                      │
│  LLM (JSON mode) ──► reflection.json │
│    • strengths / weaknesses          │
│    • suggestions applied             │
│    • revised_report (Markdown)       │
└────────────────────────────┼─────────┘
                             │
                             ▼
┌──────────────────────────────────────┐
│  Stage 3 · HTML Export               │
│  html_export.py                      │
│                                      │
│  LLM converts Markdown → HTML        │
│  DOCTYPE validation + retry          │
│                            │         │
│                      report.html     │
└────────────────────────────┼─────────┘
                             │
                             ▼
                    📄 Open in browser
```

---

## 📦 Installation

**Requirements:** Python 3.10+, a free [DeepSeek API key](https://platform.deepseek.com)

```bash
# 1. Clone
git clone https://github.com/W-Bjwa04/reflective-research-agent.git
cd reflective-research-agent

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install (also registers the `research-agent` CLI command)
pip install -e .
```

---

## 🔑 Configuration

Copy the template and add your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# ── Required ───────────────────────────────
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# ── Optional (shown with defaults) ─────────
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled      # "enabled" to turn on chain-of-thought
TAVILY_API_KEY=tvly-xxxx        # leave blank → auto-falls back to DuckDuckGo
OUTPUT_DIR=outputs
MAX_ITERATIONS=6
```

> ⚠️ **Never commit your `.env` file.** It is in `.gitignore`.

---

## 🚀 Usage

### Basic

```bash
research-agent "quantum computing applications in cryptography"
```

### With options

```bash
# More research depth + open browser when done
research-agent "CRISPR gene editing ethics" --max-iterations 8 --open

# Custom output folder + verbose logging
research-agent "fusion energy breakthroughs" --output-dir ./reports --verbose
```

### Run without installing (via module)

```bash
python -m src.reflective_agent "large language model alignment"
```

### Help

```bash
research-agent --help
```

---

## 📋 CLI Reference

| Argument | Default | Description |
|---|---|---|
| `TOPIC` | *(required)* | Research topic — quote if multi-word |
| `--model` | `deepseek-v4-flash` | DeepSeek model name |
| `--max-iterations N` | `6` | Max tool-calling rounds in Stage 1 |
| `--output-dir DIR` | `outputs` | Base directory for saved files |
| `--open` | off | Open HTML report in browser when done |
| `--verbose` | off | Debug logging (tool args, raw responses) |

---

## 📂 Output Files

Each run creates `outputs/<topic-slug>-<YYYYMMDD-HHMMSS>/`:

| File | Stage | Contents |
|---|---|---|
| `draft.md` | 1 | Raw first-pass Markdown report |
| `reflection.json` | 2 | Structured JSON: strengths, weaknesses, suggestions, revised text |
| `final_report.md` | 2 | Improved Markdown (post-reflection) |
| `report.html` | 3 | Self-contained HTML — open in any browser |

---

## 📁 Project Structure

```
reflective-research-agent/
├── src/reflective_agent/
│   ├── cli.py             # Entry point — orchestrates all 3 stages
│   ├── agent.py           # Stage 1: tool-calling research loop
│   ├── reflection.py      # Stage 2: reflect + rewrite (JSON mode)
│   ├── html_export.py     # Stage 3: HTML export + DOCTYPE validation
│   ├── tools.py           # arxiv_search, web_search, schemas, dispatcher
│   ├── llm.py             # DeepSeek client (retries, thinking mode)
│   ├── config.py          # Environment variable loading
│   ├── __init__.py
│   └── __main__.py
├── tests/                 # 59 unit tests — no real API calls
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_json_parsing.py
│   ├── test_tools.py
│   ├── test_html_validation.py
│   └── test_llm.py
├── docs/
│   └── index.html         # Sample HTML report (GitHub Pages)
├── examples/
│   └── reflection.json    # Pre-generated reflection example
├── .env.example
├── pyproject.toml
├── requirements.txt
└── LICENSE
```

---

## 🧪 Tests

```bash
# Run all 59 tests (no API key needed — everything is mocked)
pytest

# With coverage
pytest --cov=reflective_agent --cov-report=term-missing
```

---

## 🌐 Live Sample Report

A sample HTML report is included in [`docs/index.html`](docs/index.html).

**View it instantly:** [htmlpreview.github.io](https://htmlpreview.github.io/?https://github.com/W-Bjwa04/reflective-research-agent/blob/main/docs/index.html)

**Enable GitHub Pages:**
> Settings → Pages → Branch: `main` → Folder: `/docs` → Save
>
> Your report will be live at `https://W-Bjwa04.github.io/reflective-research-agent/`

---

## ⚠️ Limitations

- LLM-generated content may contain inaccuracies — always verify key claims against the cited URLs.
- DuckDuckGo fallback returns lower-quality snippets than Tavily; set `TAVILY_API_KEY` for best results.
- arXiv is strongest for CS, physics, and math; weaker coverage for humanities.

---

## 📄 License

[MIT](LICENSE) © 2026 Waleed Shahid
