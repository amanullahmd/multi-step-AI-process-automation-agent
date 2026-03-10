"""Tests for the SQLite database layer."""

import tempfile
from pathlib import Path

import pytest

from agent.state import PriceRecord
from agent.utils.database import PriceDatabase


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        yield PriceDatabase(Path(tmpdir) / "test.db")


def test_save_and_retrieve_prices(db):
    prices = [
        PriceRecord(competitor="StoreA", product="Widget", price=10.0),
        PriceRecord(competitor="StoreA", product="Gadget", price=20.0),
        PriceRecord(competitor="StoreB", product="Widget", price=12.0),
    ]
    saved = db.save_prices(prices)
    assert saved == 3

    previous = db.get_previous_prices()
    assert ("StoreA", "Widget") in previous
    assert previous[("StoreA", "Widget")] == 10.0
    assert previous[("StoreB", "Widget")] == 12.0


def test_detect_changes_price_increase(db):
    # Save initial prices
    db.save_prices([
        PriceRecord(competitor="Store", product="Widget", price=10.0),
    ])

    # Detect changes with new higher price
    new_prices = [PriceRecord(competitor="Store", product="Widget", price=12.0)]
    changes = db.detect_changes(new_prices)

    assert len(changes) == 1
    assert changes[0].direction == "up"
    assert changes[0].change_pct == 20.0
    assert changes[0].old_price == 10.0
    assert changes[0].new_price == 12.0


def test_detect_changes_price_decrease(db):
    db.save_prices([
        PriceRecord(competitor="Store", product="Widget", price=10.0),
    ])

    new_prices = [PriceRecord(competitor="Store", product="Widget", price=8.0)]
    changes = db.detect_changes(new_prices)

    assert len(changes) == 1
    assert changes[0].direction == "down"
    assert changes[0].change_pct == -20.0


def test_detect_new_product(db):
    new_prices = [PriceRecord(competitor="Store", product="NewItem", price=15.0)]
    changes = db.detect_changes(new_prices)

    assert len(changes) == 1
    assert changes[0].direction == "new"
    assert changes[0].new_price == 15.0


def test_no_change_detected(db):
    db.save_prices([
        PriceRecord(competitor="Store", product="Widget", price=10.0),
    ])

    same_prices = [PriceRecord(competitor="Store", product="Widget", price=10.0)]
    changes = db.detect_changes(same_prices)

    assert len(changes) == 0


def test_get_price_history(db):
    db.save_prices([
        PriceRecord(competitor="Store", product="Widget", price=10.0),
    ])
    db.save_prices([
        PriceRecord(competitor="Store", product="Widget", price=12.0),
    ])

    history = db.get_price_history("Store", "Widget")
    assert len(history) == 2


def test_get_stats_empty(db):
    stats = db.get_stats()
    assert stats["total_records"] == 0
    assert stats["unique_products"] == 0


def test_get_stats_with_data(db):
    db.save_prices([
        PriceRecord(competitor="A", product="X", price=1.0),
        PriceRecord(competitor="A", product="Y", price=2.0),
        PriceRecord(competitor="B", product="X", price=3.0),
    ])
    stats = db.get_stats()
    assert stats["total_records"] == 3
    assert stats["unique_products"] == 3
