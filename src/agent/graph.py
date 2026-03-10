"""LangGraph pipeline — the core agent graph definition.

Pipeline: Scrape -> Consolidate -> Analyze (LLM) -> Generate Report -> Send Notifications
"""

import logging

from langgraph.graph import StateGraph, END

from agent.nodes.analyzer import analyze_prices
from agent.nodes.consolidator import consolidate_data
from agent.nodes.reporter import generate_report, send_notifications
from agent.nodes.scraper import scrape_prices
from agent.state import AgentState

logger = logging.getLogger(__name__)


def should_analyze(state: AgentState) -> str:
    """Conditional edge: skip LLM analysis if no prices were scraped."""
    if state.consolidated_prices:
        return "analyze"
    logger.warning("No prices consolidated — skipping analysis")
    return "report"


def build_graph() -> StateGraph:
    """Construct and compile the price monitoring agent graph.

    Graph flow:
        START
          |
        scrape_prices         (async fan-out across all sources)
          |
        consolidate_data      (deduplicate, store in DB, detect changes)
          |
        [conditional]
          |-- has data --> analyze_prices     (LLM insight generation)
          |-- no data  --> generate_report
          |
        generate_report       (format HTML, Slack blocks, plain text)
          |
        send_notifications    (dispatch via configured channels)
          |
        END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("scrape_prices", scrape_prices)
    graph.add_node("consolidate_data", consolidate_data)
    graph.add_node("analyze_prices", analyze_prices)
    graph.add_node("generate_report", generate_report)
    graph.add_node("send_notifications", send_notifications)

    # Define edges
    graph.set_entry_point("scrape_prices")
    graph.add_edge("scrape_prices", "consolidate_data")

    # Conditional: skip analysis if nothing scraped
    graph.add_conditional_edges(
        "consolidate_data",
        should_analyze,
        {"analyze": "analyze_prices", "report": "generate_report"},
    )

    graph.add_edge("analyze_prices", "generate_report")
    graph.add_edge("generate_report", "send_notifications")
    graph.add_edge("send_notifications", END)

    return graph.compile()


# Pre-compiled graph instance
agent = build_graph()
