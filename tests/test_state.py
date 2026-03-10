"""Tests for state models."""

from datetime import datetime

from agent.state import (
    AgentState,
    CompetitorSource,
    PriceChange,
    PriceRecord,
    ReportFormat,
)


def test_competitor_source_creation():
    source = CompetitorSource(
        name="TestStore",
        source_type="api",
        url="https://example.com/api",
        product_key="title",
        price_key="price",
    )
    assert source.name == "TestStore"
    assert source.source_type == "api"


def test_price_record_defaults():
    record = PriceRecord(competitor="Store", product="Widget", price=9.99)
    assert record.currency == "USD"
    assert record.url == ""
    assert isinstance(record.scraped_at, datetime)


def test_price_change_model():
    change = PriceChange(
        competitor="Store",
        product="Widget",
        old_price=10.0,
        new_price=8.0,
        change_pct=-20.0,
        direction="down",
    )
    assert change.direction == "down"
    assert change.change_pct == -20.0


def test_agent_state_defaults():
    state = AgentState()
    assert state.competitors == []
    assert state.report_format == ReportFormat.CONSOLE
    assert state.scraped_prices == []
    assert state.total_products_tracked == 0
    assert state.hitl_approved is False


def test_agent_state_hitl_approved():
    """hitl_approved=True routes to send_notifications (see test_graph.py::test_should_notify_*)."""
    state = AgentState(hitl_approved=True)
    assert state.hitl_approved is True


def test_agent_state_with_data():
    source = CompetitorSource(
        name="Test", source_type="api", url="http://test.com"
    )
    state = AgentState(
        competitors=[source],
        report_format=ReportFormat.BOTH,
    )
    assert len(state.competitors) == 1
    assert state.report_format == ReportFormat.BOTH
