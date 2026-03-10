"""Tests for the consolidator node — deduplication and significance filtering."""

from unittest.mock import patch

import pytest

from agent.state import AgentState, PriceRecord
from agent.utils.database import PriceDatabase


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db(tmp_db_path):
    return PriceDatabase(tmp_db_path)


@pytest.mark.asyncio
async def test_consolidate_deduplicates(tmp_db_path):
    """Consolidator keeps the last occurrence when the same product appears twice."""
    from agent.nodes.consolidator import consolidate_data

    state = AgentState(
        competitors=[],
        scraped_prices=[
            PriceRecord(competitor="A", product="X", price=10.0),
            PriceRecord(competitor="A", product="X", price=11.0),  # duplicate -- wins
        ],
    )

    with patch("agent.nodes.consolidator.get_settings") as mock_cfg:
        mock_cfg.return_value.db_path = tmp_db_path
        mock_cfg.return_value.min_change_pct = 2.0
        result = await consolidate_data(state)

    assert result["total_products_tracked"] == 1
    assert result["consolidated_prices"][0].price == 11.0


@pytest.mark.asyncio
async def test_consolidate_filters_insignificant_changes(tmp_db_path, db):
    """Changes below min_change_pct are filtered out."""
    from agent.nodes.consolidator import consolidate_data

    # Seed the database with an existing price
    db.save_prices([PriceRecord(competitor="A", product="X", price=100.0)])

    # A 1% change should be filtered with a 2% threshold
    state = AgentState(
        scraped_prices=[PriceRecord(competitor="A", product="X", price=101.0)],
    )

    with patch("agent.nodes.consolidator.get_settings") as mock_cfg:
        mock_cfg.return_value.db_path = tmp_db_path
        mock_cfg.return_value.min_change_pct = 2.0
        result = await consolidate_data(state)

    assert result["price_changes"] == []


@pytest.mark.asyncio
async def test_consolidate_keeps_significant_changes(tmp_db_path, db):
    """Changes at or above min_change_pct are reported."""
    from agent.nodes.consolidator import consolidate_data

    db.save_prices([PriceRecord(competitor="A", product="X", price=100.0)])

    # A 5% change should pass a 2% threshold
    state = AgentState(
        scraped_prices=[PriceRecord(competitor="A", product="X", price=105.0)],
    )

    with patch("agent.nodes.consolidator.get_settings") as mock_cfg:
        mock_cfg.return_value.db_path = tmp_db_path
        mock_cfg.return_value.min_change_pct = 2.0
        result = await consolidate_data(state)

    assert len(result["price_changes"]) == 1
    assert result["price_changes"][0].direction == "up"


@pytest.mark.asyncio
async def test_consolidate_new_products_always_reported(tmp_db_path):
    """New products are always included regardless of the threshold."""
    from agent.nodes.consolidator import consolidate_data

    state = AgentState(
        scraped_prices=[PriceRecord(competitor="A", product="Brand New", price=9.99)],
    )

    with patch("agent.nodes.consolidator.get_settings") as mock_cfg:
        mock_cfg.return_value.db_path = tmp_db_path
        mock_cfg.return_value.min_change_pct = 50.0  # very high threshold
        result = await consolidate_data(state)

    assert len(result["price_changes"]) == 1
    assert result["price_changes"][0].direction == "new"
