"""Analyzer node - uses LLM to generate insights from price data."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState, PriceChange, PriceRecord
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
2. **Key Price Changes** - highlight the most significant changes
3. **Trends** - any patterns you notice
4. **Actionable Recommendations** - what should the business do
5. **Alerts** - any prices that need immediate attention

Be concise, data-driven, and specific. Reference actual numbers."""


def _generate_demo_analysis(
    prices: list[PriceRecord], changes: list[PriceChange]
) -> tuple[str, list[str]]:
    """Generate a rule-based analysis when demo_mode is active or the LLM is unavailable.

    Returns (analysis_text, key_insights). No external calls are made.
    """
    # Single pass to categorize changes
    new_items: list[PriceChange] = []
    price_ups: list[PriceChange] = []
    price_downs: list[PriceChange] = []
    for c in changes:
        if c.direction == "new":
            new_items.append(c)
        elif c.direction == "up":
            price_ups.append(c)
        else:
            price_downs.append(c)
    competitors = sorted({p.competitor for p in prices})

    lines: list[str] = []

    # --- 1. Executive Summary ---
    lines.append("## 1. Executive Summary")
    if not prices:
        lines.append("No price data was collected in this run.")
        return "\n".join(lines), []

    lines.append(
        f"Monitored **{len(prices)} products** across "
        f"**{len(competitors)} competitor(s)** ({', '.join(competitors)}). "
        f"Detected **{len(new_items)} new listing(s)**, "
        f"**{len(price_ups)} price increase(s)**, and "
        f"**{len(price_downs)} price decrease(s)**."
    )

    # --- 2. Key Price Changes ---
    lines.append("\n## 2. Key Price Changes")
    if changes:
        top = sorted(changes, key=lambda c: abs(c.change_pct), reverse=True)[:5]
        for c in top:
            if c.direction == "new":
                lines.append(f"- **NEW**: {c.competitor} | {c.product}: ${c.new_price:.2f}")
            else:
                arrow = "UP" if c.direction == "up" else "DOWN"
                lines.append(
                    f"- {arrow} **{c.change_pct:+.1f}%**: "
                    f"{c.competitor} | {c.product}: "
                    f"${c.old_price:.2f} -> ${c.new_price:.2f}"
                )
    else:
        lines.append("- No price changes detected since last run.")

    # --- 3. Trends ---
    lines.append("\n## 3. Trends")
    if prices:
        min_price = min(p.price for p in prices)
        max_price = max(p.price for p in prices)
        avg_price = sum(p.price for p in prices) / len(prices)
        lines.append(
            f"Price range across all products: ${min_price:.2f}-${max_price:.2f} "
            f"(avg: ${avg_price:.2f})."
        )
    if price_ups and price_downs:
        lines.append(
            "Mixed signals: some competitors raising prices while others are lowering them."
        )
    elif price_ups:
        lines.append(
            f"Upward trend: {len(price_ups)} product(s) increased in price this period."
        )
    elif price_downs:
        lines.append(
            f"Downward trend: {len(price_downs)} product(s) decreased in price this period."
        )
    elif new_items:
        lines.append(
            f"First-run baseline established for {len(new_items)} product(s). "
            "Future runs will show price movements."
        )
    else:
        lines.append("Prices are stable: no significant changes detected.")

    # --- 4. Actionable Recommendations ---
    lines.append("\n## 4. Actionable Recommendations")
    if new_items:
        lines.append(
            f"- Review {len(new_items)} newly listed product(s) and assess "
            "competitive positioning."
        )
    if price_ups:
        lines.append(
            f"- {len(price_ups)} competitor price increase(s) detected: "
            "evaluate whether to hold or adjust your own pricing."
        )
    if price_downs:
        lines.append(
            f"- {len(price_downs)} competitor price decrease(s) detected: "
            "investigate motivation (clearance, promotion, or strategic cut)."
        )
    if not changes:
        lines.append(
            "- Market appears stable. Schedule the next scan to monitor for future changes."
        )

    # --- 5. Alerts ---
    lines.append("\n## 5. Alerts")
    big_changes = [c for c in changes if c.direction != "new" and abs(c.change_pct) >= 10]
    if big_changes:
        for c in big_changes:
            lines.append(
                f"- [!] Large swing: {c.competitor} | {c.product}: "
                f"{c.change_pct:+.1f}%"
            )
    else:
        lines.append("- No large price swings (>=10%) detected.")

    lines.append(
        "\n---\n"
        "*[Demo mode: generated without LLM. "
        "Set OPENAI_API_KEY for AI-powered analysis.]*"
    )

    analysis = "\n".join(lines)

    # Key insights: top changes summarised as bullet strings
    insights: list[str] = []
    for c in (new_items + price_ups + price_downs)[:5]:
        if c.direction == "new":
            insights.append(f"{c.competitor}: new listing '{c.product}' at ${c.new_price:.2f}")
        else:
            insights.append(f"{c.competitor}: '{c.product}' changed {c.change_pct:+.1f}%")

    return analysis, insights


def _extract_insights_from_text(analysis: str) -> list[str]:
    """Pull bullet-point recommendations and alerts from LLM output."""
    insights: list[str] = []
    in_section = False
    for line in analysis.split("\n"):
        stripped = line.strip()
        if "recommendation" in stripped.lower() or "alert" in stripped.lower():
            in_section = True
        elif stripped.startswith("#") or stripped.startswith("**"):
            in_section = False
        if in_section and stripped.startswith("-"):
            insights.append(stripped.lstrip("- "))
    return insights[:10]


async def analyze_prices(state: AgentState) -> dict[str, Any]:
    """Use LLM to analyze price data and generate insights.

    Falls back to rule-based analysis (no external calls) when:
    * ``state.demo_mode`` is ``True`` (explicit demo run), or
    * the OpenAI API is unreachable / returns an error.
    """
    if state.demo_mode:
        logger.info("Running demo analysis (no LLM)...")
        analysis, insights = _generate_demo_analysis(
            state.consolidated_prices, state.price_changes
        )
        logger.info("Demo analysis complete")
        return {"analysis_summary": analysis, "key_insights": insights}

    logger.info("Analyzing price data with LLM...")
    settings = get_settings()

    price_lines = [
        f"- {p.competitor} | {p.product}: ${p.price:.2f}"
        for p in state.consolidated_prices
    ]
    price_snapshot = "\n".join(price_lines) if price_lines else "No prices collected."

    change_lines = []
    for c in state.price_changes:
        arrow = "^" if c.direction == "up" else "v" if c.direction == "down" else "*"
        if c.direction == "new":
            change_lines.append(
                f"- [{arrow} NEW] {c.competitor} | {c.product}: ${c.new_price:.2f}"
            )
        else:
            change_lines.append(
                f"- [{arrow} {c.change_pct:+.1f}%] {c.competitor} | {c.product}: "
                f"${c.old_price:.2f} -> ${c.new_price:.2f}"
            )
    changes_text = "\n".join(change_lines) if change_lines else "No changes detected."
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

    # Call the LLM; fall back gracefully on any connection / auth error
    try:
        response = await llm.ainvoke([
            SystemMessage(content="You are a competitive pricing analyst assistant."),
            HumanMessage(content=prompt),
        ])
        analysis = response.content
        logger.info("LLM analysis complete")
        insights = _extract_insights_from_text(analysis)
    except Exception as exc:
        logger.warning(
            f"LLM call failed ({type(exc).__name__}: {exc}). "
            "Falling back to rule-based demo analysis."
        )
        analysis, insights = _generate_demo_analysis(
            state.consolidated_prices, state.price_changes
        )

    return {"analysis_summary": analysis, "key_insights": insights}
