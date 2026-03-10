"""LangGraph pipeline — the core agent graph definition.

Pipeline: Scrape -> Consolidate -> Analyze (LLM) -> Human Review -> Generate Report -> Send
"""

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

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


def should_notify(state: AgentState) -> str:
    """Conditional edge: route to human review or directly to notifications.

    When ``hitl_approved`` is already True (e.g. automated / CI runs), the
    graph jumps straight to ``send_notifications``.  Otherwise it pauses at
    ``human_review`` so a human can inspect the report and decide whether to
    approve or abort the dispatch.
    """
    if state.hitl_approved:
        return "notify"
    return "review"


def build_graph(checkpointer=None) -> StateGraph:
    """Construct and compile the price monitoring agent graph.

    Graph flow:
        START
          |
        scrape_prices         (async fan-out across all sources)
          |
        consolidate_data      (deduplicate, store in DB, detect changes)
          |
        [conditional: has data?]
          |-- yes --> analyze_prices     (LLM insight generation)
          |-- no  --> generate_report
          |
        generate_report       (format HTML, Slack blocks, plain text)
          |
        [conditional: hitl_approved?]
          |-- yes --> send_notifications  (dispatch via configured channels)
          |-- no  --> human_review        (interrupt — waits for approval)
          |
        send_notifications
          |
        END

    The ``human_review`` node is a LangGraph *interrupt* point. When the
    graph reaches it the run is suspended and control returns to the caller.
    The caller can inspect ``state.report_text`` and then resume by invoking
    the compiled graph again with ``hitl_approved=True``.

    Pass a ``checkpointer`` (e.g. ``MemorySaver()``) to enable HITL; without
    one the graph compiles without the interrupt capability (useful for
    automated / test runs where ``hitl_approved`` is always True).
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("scrape_prices", scrape_prices)
    graph.add_node("consolidate_data", consolidate_data)
    graph.add_node("analyze_prices", analyze_prices)
    graph.add_node("generate_report", generate_report)
    graph.add_node("human_review", _human_review_node)
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

    # Conditional: pause for human review unless already approved
    graph.add_conditional_edges(
        "generate_report",
        should_notify,
        {"notify": "send_notifications", "review": "human_review"},
    )

    graph.add_edge("human_review", "send_notifications")
    graph.add_edge("send_notifications", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer, interrupt_before=["human_review"])
    return graph.compile()


def _human_review_node(state: AgentState) -> dict:
    """Human-in-the-Loop (HITL) passthrough node.

    This node is declared as an *interrupt_before* target when a
    checkpointer is supplied to ``build_graph``.  LangGraph will pause
    execution *before* entering this node, serialize the state to the
    checkpointer, and return control to the caller.

    To resume, invoke the compiled graph again with the same ``thread_id``
    and an updated state where ``hitl_approved=True``.
    """
    logger.info("Human review checkpoint reached — report is ready for inspection")
    return {"hitl_approved": True}


# Pre-compiled graph instance (no checkpointer — automated runs)
agent = build_graph()

# HITL-enabled graph with in-memory checkpointer for interactive runs
hitl_agent = build_graph(checkpointer=MemorySaver())
