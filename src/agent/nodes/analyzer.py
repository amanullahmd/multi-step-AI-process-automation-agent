"""Analyzer node — uses LLM to generate insights from price data."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.utils.config import get_settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are a competitive pricing analyst. \
Analyze the following price monitoring data and provide actionable insights.

## Current Price Snapshot
{price_snapshot}

## Detected Price Changes
{price_changes}

## Scraping Errors (if any)
{errors}

Provide your analysis in this format:
1. **Executive Summary** (2-3 sentences)
2. **Key Price Changes** — highlight the most significant changes
3. **Trends** — any patterns you notice
4. **Actionable Recommendations** — what should the business do
5. **Alerts** — any prices that need immediate attention

Be concise, data-driven, and specific. Reference actual numbers."""


async def analyze_prices(state: AgentState) -> dict[str, Any]:
    """Use LLM to analyze price data and generate insights."""
    settings = get_settings()

    logger.info("Analyzing price data with LLM...")

    # Format price snapshot
    price_lines = []
    for p in state.consolidated_prices:
        price_lines.append(f"- {p.competitor} | {p.product}: ${p.price:.2f}")
    price_snapshot = "\n".join(price_lines) if price_lines else "No prices collected."

    # Format changes
    change_lines = []
    for c in state.price_changes:
        arrow = "^" if c.direction == "up" else "v" if c.direction == "down" else "*"
        if c.direction == "new":
            change_lines.append(f"- [{arrow} NEW] {c.competitor} | {c.product}: ${c.new_price:.2f}")
        else:
            change_lines.append(
                f"- [{arrow} {c.change_pct:+.1f}%] {c.competitor} | {c.product}: "
                f"${c.old_price:.2f} -> ${c.new_price:.2f}"
            )
    changes_text = "\n".join(change_lines) if change_lines else "No changes detected."

    # Format errors
    errors_text = "\n".join(state.scrape_errors) if state.scrape_errors else "None"

    prompt = ANALYSIS_PROMPT.format(
        price_snapshot=price_snapshot,
        price_changes=changes_text,
        errors=errors_text,
    )

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
    )

    response = await llm.ainvoke([
        SystemMessage(content="You are a competitive pricing analyst assistant."),
        HumanMessage(content=prompt),
    ])

    analysis = response.content
    logger.info("LLM analysis complete")

    # Extract key insights (lines starting with - or * in recommendations)
    insights = []
    in_recommendations = False
    for line in analysis.split("\n"):
        stripped = line.strip()
        if "recommendation" in stripped.lower() or "alert" in stripped.lower():
            in_recommendations = True
        elif stripped.startswith("#") or stripped.startswith("**"):
            in_recommendations = False
        if in_recommendations and stripped.startswith("-"):
            insights.append(stripped.lstrip("- "))

    return {
        "analysis_summary": analysis,
        "key_insights": insights[:10],
    }
