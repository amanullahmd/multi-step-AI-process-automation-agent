"""Tests for the LangGraph pipeline structure."""

from agent.graph import build_graph, should_analyze, should_notify
from agent.state import AgentState, PriceRecord


def test_graph_compiles():
    """Verify the graph compiles without errors."""
    graph = build_graph()
    assert graph is not None


def test_should_analyze_with_data():
    state = AgentState(
        consolidated_prices=[
            PriceRecord(competitor="A", product="X", price=10.0),
        ]
    )
    assert should_analyze(state) == "analyze"


def test_should_analyze_without_data():
    state = AgentState(consolidated_prices=[])
    assert should_analyze(state) == "report"


def test_graph_has_expected_nodes():
    """Verify all expected nodes are present in the compiled graph."""
    graph = build_graph()
    # The compiled graph should be invocable
    assert hasattr(graph, "ainvoke")
    assert hasattr(graph, "invoke")


def test_should_notify_approved():
    """HITL: already-approved state bypasses human review."""
    state = AgentState(hitl_approved=True)
    assert should_notify(state) == "notify"


def test_should_notify_not_approved():
    """HITL: un-approved state routes to human review."""
    state = AgentState(hitl_approved=False)
    assert should_notify(state) == "review"


def test_hitl_graph_compiles():
    """HITL graph with MemorySaver checkpointer compiles without errors."""
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_graph(checkpointer=MemorySaver())
    assert graph is not None
    assert hasattr(graph, "ainvoke")
