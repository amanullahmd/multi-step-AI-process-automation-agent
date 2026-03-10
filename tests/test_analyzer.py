"""Tests for the analyzer node — demo mode and LLM fallback."""

import pytest

from agent.nodes.analyzer import _extract_insights_from_text, _generate_demo_analysis
from agent.state import AgentState, PriceChange, PriceRecord

# ---------------------------------------------------------------------------
# Unit tests for _generate_demo_analysis
# ---------------------------------------------------------------------------

def _make_prices(*pairs) -> list[PriceRecord]:
    return [PriceRecord(competitor=c, product=p, price=price) for c, p, price in pairs]


def _make_change(competitor, product, old, new, direction, pct) -> PriceChange:
    return PriceChange(
        competitor=competitor,
        product=product,
        old_price=old,
        new_price=new,
        change_pct=pct,
        direction=direction,
    )


class TestGenerateDemoAnalysis:
    def test_empty_prices_returns_summary(self):
        analysis, insights = _generate_demo_analysis([], [])
        assert "No price data" in analysis
        assert insights == []

    def test_new_listings_detected(self):
        prices = _make_prices(("Acme", "Widget", 9.99))
        changes = [_make_change("Acme", "Widget", 0, 9.99, "new", 0.0)]
        analysis, insights = _generate_demo_analysis(prices, changes)

        assert "new listing(s)" in analysis  # "1 new listing(s)" from the summary
        assert "Widget" in analysis
        assert len(insights) == 1
        assert "Acme" in insights[0]

    def test_price_increase_shows_in_trends(self):
        prices = _make_prices(("Shop", "Gadget", 12.0))
        changes = [_make_change("Shop", "Gadget", 10.0, 12.0, "up", 20.0)]
        analysis, insights = _generate_demo_analysis(prices, changes)

        assert "Upward trend" in analysis
        assert "4. Actionable Recommendations" in analysis
        assert len(insights) == 1

    def test_price_decrease_shows_in_trends(self):
        prices = _make_prices(("Shop", "Gadget", 8.0))
        changes = [_make_change("Shop", "Gadget", 10.0, 8.0, "down", -20.0)]
        analysis, insights = _generate_demo_analysis(prices, changes)

        assert "Downward trend" in analysis

    def test_large_change_triggers_alert(self):
        prices = _make_prices(("Shop", "Gadget", 20.0))
        changes = [_make_change("Shop", "Gadget", 10.0, 20.0, "up", 100.0)]
        analysis, insights = _generate_demo_analysis(prices, changes)

        assert "Large swing" in analysis or "[!]" in analysis

    def test_no_changes_stable_message(self):
        prices = _make_prices(("Shop", "Widget", 10.0))
        analysis, insights = _generate_demo_analysis(prices, [])

        assert "stable" in analysis.lower()
        assert insights == []

    def test_demo_footer_present(self):
        prices = _make_prices(("A", "X", 5.0))
        analysis, _ = _generate_demo_analysis(prices, [])
        assert "Demo mode" in analysis

    def test_price_range_stats_present(self):
        prices = _make_prices(("A", "Cheap", 5.0), ("A", "Expensive", 50.0))
        analysis, _ = _generate_demo_analysis(prices, [])
        assert "$5.00" in analysis
        assert "$50.00" in analysis


# ---------------------------------------------------------------------------
# Unit test for _extract_insights_from_text
# ---------------------------------------------------------------------------

def test_extract_insights_from_llm_text():
    fake_llm_output = """
## 3. Trends
Some trend text.

## 4. Actionable Recommendations
- Review competitor X pricing.
- Consider lowering price on Widget.

## 5. Alerts
- Watch for sudden drops on Gadget.
"""
    insights = _extract_insights_from_text(fake_llm_output)
    assert len(insights) >= 1
    assert any("competitor" in i.lower() or "pricing" in i.lower() for i in insights)


# ---------------------------------------------------------------------------
# Integration test: analyze_prices node in demo mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_prices_demo_mode():
    """analyze_prices returns a demo analysis without calling any external API."""
    from agent.nodes.analyzer import analyze_prices

    state = AgentState(
        demo_mode=True,
        consolidated_prices=_make_prices(("Shop", "Widget", 9.99)),
        price_changes=[_make_change("Shop", "Widget", 0, 9.99, "new", 0.0)],
    )

    result = await analyze_prices(state)

    assert "analysis_summary" in result
    assert "key_insights" in result
    assert "Demo mode" in result["analysis_summary"]
    assert len(result["key_insights"]) >= 1


@pytest.mark.asyncio
async def test_analyze_prices_llm_fallback(monkeypatch):
    """When the LLM raises an exception, analyze_prices falls back to demo analysis."""
    import agent.nodes.analyzer as analyzer_module
    from agent.nodes.analyzer import analyze_prices

    # Patch ChatOpenAI so ainvoke raises a connection error
    class _FakeLLM:
        async def ainvoke(self, _messages):
            raise ConnectionError("Simulated network error")

    monkeypatch.setattr(analyzer_module, "ChatOpenAI", lambda **_: _FakeLLM())

    state = AgentState(
        demo_mode=False,
        consolidated_prices=_make_prices(("Shop", "Widget", 9.99)),
        price_changes=[_make_change("Shop", "Widget", 0, 9.99, "new", 0.0)],
    )

    result = await analyze_prices(state)

    # Should not raise; should have a fallback analysis
    assert "analysis_summary" in result
    assert result["analysis_summary"] != ""
    assert "Demo mode" in result["analysis_summary"]


# ---------------------------------------------------------------------------
# State: demo_mode field defaults
# ---------------------------------------------------------------------------

def test_agent_state_demo_mode_default():
    state = AgentState()
    assert state.demo_mode is False


def test_agent_state_demo_mode_set():
    state = AgentState(demo_mode=True)
    assert state.demo_mode is True
