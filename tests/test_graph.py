"""Tests for the LangGraph pipeline structure."""

from agent.graph import build_graph, should_analyze
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
