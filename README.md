# Multi-Step AI Process Automation Agent

[![CI](https://github.com/amanullahmd/multi-step-AI-process-automation-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/amanullahmd/multi-step-AI-process-automation-agent/actions/workflows/ci.yml)

A production-grade **Agentic AI workflow** built with **LangGraph** and Python 3.11+. The agent autonomously monitors competitor pricing across multiple data sources, performs LLM-powered analysis, and dispatches formatted reports via Slack and email — all while persisting state in SQLite to avoid duplicate alerts.

## 📊 Why This Matters in 2026

Companies have moved past "chatbots" and are hungry for **Agentic Workflows** — systems that don't just talk, but actually *act*. This project demonstrates:

| Feature | Implementation |
|---|---|
| **Statefulness** | `AgentState` (Pydantic) flows through every node; SQLite persists history across runs |
| **Tool Calling** | Web scraper, JSON API fetcher, email (SendGrid) and Slack (Webhook) integrations |
| **Significance Filtering** | `MIN_CHANGE_PCT` threshold silences noise — only meaningful price movements reach the LLM |
| **HITL** | Human-in-the-Loop interrupt checkpoint before notifications are dispatched |
| **Observability** | Native LangSmith tracing — every node's tokens, latency and I/O in one dashboard |
| **Reliability/Logs** | Structured logging; each node is independently debuggable |

---

## 🏗️ Architecture — Directed Acyclic Graph (DAG)

```
START
  │
scrape_prices ─────── fan-out: all competitor sources scraped concurrently
  │
consolidate_data ───── deduplicate → detect changes → filter noise → save to DB
  │
  ├─ [has prices] ──► analyze_prices ── LLM generates insights + recommendations
  │
  └─ [no prices] ─────────────────────┐
                                       ▼
                               generate_report ── builds HTML, Slack blocks, plain text
                                       │
                    ┌──────────────────┴──────────────────────┐
                    │ hitl_approved=True (automated)           │ hitl_approved=False (interactive)
                    ▼                                          ▼
            send_notifications                        human_review  ← INTERRUPT POINT
                    │                                          │ (resume with hitl_approved=True)
                    │◄─────────────────────────────────────────┘
                    ▼
                   END
```

### Node Responsibilities

| Node | File | What it does |
|---|---|---|
| `scrape_prices` | `nodes/scraper.py` | Concurrent fetch from all sources (API / Web / File) |
| `consolidate_data` | `nodes/consolidator.py` | Deduplicate, diff against DB, apply significance threshold |
| `analyze_prices` | `nodes/analyzer.py` | GPT-4o/Claude — executive summary, trends, recommendations |
| `generate_report` | `nodes/reporter.py` | HTML email, Slack Block Kit, plain text |
| `human_review` | `graph.py` | LangGraph interrupt — waits for human approval |
| `send_notifications` | `nodes/reporter.py` | Dispatches via Slack webhook and/or SendGrid email |

---

## 📂 Project Structure

```
ai-automation-agent/
├── src/agent/
│   ├── graph.py          # LangGraph DAG definition + HITL checkpoint
│   ├── state.py          # AgentState TypedDict (Pydantic) — agent memory
│   ├── main.py           # CLI entry point (run / schedule / stats)
│   ├── nodes/
│   │   ├── scraper.py    # Web scraping / API / file fetching
│   │   ├── consolidator.py # Dedup, change detection, noise filter
│   │   ├── analyzer.py   # LLM insight generation
│   │   └── reporter.py   # Report formatting + notification dispatch
│   ├── tools/
│   │   ├── web_scraper.py  # httpx + BeautifulSoup helpers
│   │   ├── email_client.py # SendGrid HTML email builder
│   │   └── slack_client.py # Slack Block Kit builder + webhook sender
│   └── utils/
│       ├── config.py     # Pydantic Settings (env vars)
│       └── database.py   # SQLite price history
├── data/
│   ├── competitors.json        # Your competitor sources config
│   └── sample_competitors.json # Example config with comments
├── tests/                      # pytest test suite
├── .env.example                # All supported env vars with docs
├── .github/workflows/ci.yml    # GitHub Actions — lint + test on Python 3.11/3.12
├── pyproject.toml
└── langgraph.json              # LangGraph Cloud deployment config
```

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/amanullahmd/multi-step-AI-process-automation-agent.git
cd multi-step-AI-process-automation-agent
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY at minimum
```

### 3. Add competitor sources

Edit `data/competitors.json`:

```json
{
  "competitors": [
    {
      "name": "FakeStore",
      "source_type": "api",
      "url": "https://fakestoreapi.com/products",
      "product_key": "title",
      "price_key": "price"
    },
    {
      "name": "MyWebShop",
      "source_type": "web",
      "url": "https://example.com/products",
      "selector": ".product-title|.product-price"
    }
  ]
}
```

Supported `source_type` values:

| Type | Description |
|---|---|
| `api` | JSON REST endpoint — specify `product_key` and `price_key` |
| `web` | HTML page — specify `selector` as `"product_css\|price_css"` |
| `file` | Local JSON file — same keys as `api` |

### 4. Run

```bash
# One-off run, results printed to console
price-monitor run

# Send report to Slack
price-monitor run --report slack

# Send to both Slack and email
price-monitor run --report both

# Run on a schedule (cron, blocks until Ctrl+C)
price-monitor schedule

# View database stats
price-monitor stats
```

---

## ⚙️ Configuration

All settings are loaded from `.env` (see `.env.example` for the full list):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model to use |
| `MIN_CHANGE_PCT` | `2.0` | Minimum % change to report (filters noise) |
| `SLACK_WEBHOOK_URL` | `""` | Slack incoming webhook URL |
| `SLACK_ENABLED` | `false` | Enable Slack notifications |
| `SENDGRID_API_KEY` | `""` | SendGrid API key |
| `EMAIL_FROM` / `EMAIL_TO` | `""` | Email addresses |
| `EMAIL_ENABLED` | `false` | Enable email notifications |
| `SCHEDULE_CRON` | `0 9 * * 1` | APScheduler cron (Monday 9 AM) |
| `DATABASE_PATH` | `data/price_history.db` | SQLite path |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | `""` | LangSmith API key |
| `LANGCHAIN_PROJECT` | `price-monitor-agent` | LangSmith project name |

---

## 🔬 Human-in-the-Loop (HITL)

The graph ships with an **interrupt checkpoint** before notifications are dispatched. In **interactive mode** you can inspect the report and decide whether to send it:

```python
from agent.graph import hitl_agent
from agent.state import AgentState, CompetitorSource

config = {"configurable": {"thread_id": "run-001"}}

# Phase 1 — run until the interrupt (human_review node)
result = await hitl_agent.ainvoke(initial_state, config=config)
# result is None / partial — execution paused

# Inspect the report
snapshot = hitl_agent.get_state(config)
print(snapshot.values["report_text"])

# Phase 2 — approve and resume
await hitl_agent.ainvoke(
    {"hitl_approved": True},
    config=config,
)
```

In **automated runs** (CLI / scheduler), set `hitl_approved=True` in the initial state or use the standard `agent` graph which bypasses the interrupt seamlessly.

---

## 👁️ LangSmith Observability

Enable tracing by setting these in `.env`:

```dotenv
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your-langsmith-api-key
LANGCHAIN_PROJECT=price-monitor-agent
```

Sign up for free at [smith.langchain.com](https://smith.langchain.com). You'll get a dashboard showing:
- Every node's input/output state
- LLM token usage and cost per run
- End-to-end latency breakdown
- Full run history for debugging

---

## 🧪 Development

```bash
pip install -e ".[dev]"

# Run all tests
pytest

# Lint
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/
```

CI runs automatically on every push and pull request (Python 3.11 and 3.12).

---

## 🗓️ Scheduling

The scheduler uses **APScheduler** with a configurable cron expression:

```bash
# Start the scheduler (runs immediately, then on schedule)
price-monitor schedule --report both

# Custom cron: run every day at 8 AM
SCHEDULE_CRON="0 8 * * *" price-monitor schedule
```

For production deployments, host on **Railway**, **Render**, or use **n8n** to trigger the CLI command.

---

## 💼 Skills Demonstrated

> **Agentic AI Automation Engineer**
>
> * Designed and deployed a multi-step autonomous agent using **LangGraph** and **Python** to automate competitor market analysis.
> * Implemented **stateful logic** with SQLite persistence to track price fluctuations and avoid duplicate alerts.
> * Built a **Human-in-the-Loop (HITL)** approval checkpoint using LangGraph's `interrupt_before` pattern — a gold-standard reliability technique.
> * Added **LangSmith observability** integration for production monitoring of the agent's thought process and token spend.
> * Engineered a significance-filtering pipeline that ignores price noise (< 2%) so the LLM only reasons about actionable movements.

---

## License

MIT License — see LICENSE file for details.
