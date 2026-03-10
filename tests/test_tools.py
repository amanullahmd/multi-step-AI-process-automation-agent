"""Tests for scraping tools and notification builders."""

import json
import tempfile
from pathlib import Path

import pytest

from agent.state import CompetitorSource
from agent.tools.email_client import build_email_html
from agent.tools.slack_client import build_slack_blocks
from agent.tools.web_scraper import _parse_price, fetch_prices


class TestPriceParser:
    def test_parse_usd(self):
        assert _parse_price("$29.99") == 29.99

    def test_parse_euro_comma(self):
        assert _parse_price("29,99 EUR") == 29.99

    def test_parse_plain_number(self):
        assert _parse_price("100.50") == 100.50

    def test_parse_with_currency_symbol(self):
        assert _parse_price("£45.00") == 45.00

    def test_parse_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_price("no price here")


class TestSlackBlockBuilder:
    def test_builds_header(self):
        blocks = build_slack_blocks(
            summary="Test",
            price_changes=[],
            insights=[],
            total_products=5,
            errors=[],
        )
        assert blocks[0]["type"] == "header"

    def test_includes_stats(self):
        blocks = build_slack_blocks(
            summary="Test",
            price_changes=[],
            insights=["Buy low"],
            total_products=10,
            errors=[],
        )
        stats = blocks[1]
        assert "10" in stats["fields"][0]["text"]

    def test_includes_changes(self):
        changes = [
            {"competitor": "A", "product": "X", "old_price": 10, "new_price": 12, "change_pct": 20, "direction": "up"},
        ]
        blocks = build_slack_blocks(
            summary="Test",
            price_changes=changes,
            insights=[],
            total_products=1,
            errors=[],
        )
        change_block = [b for b in blocks if b["type"] == "section" and "Price Changes" in b.get("text", {}).get("text", "")]
        assert len(change_block) == 1

    def test_includes_errors(self):
        blocks = build_slack_blocks(
            summary="Test",
            price_changes=[],
            insights=[],
            total_products=0,
            errors=["Connection failed"],
        )
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 1


class TestEmailBuilder:
    def test_builds_valid_html(self):
        html = build_email_html(
            summary="Price analysis here",
            price_changes=[
                {"competitor": "A", "product": "X", "old_price": 10, "new_price": 8, "change_pct": -20, "direction": "down"},
            ],
            insights=["Good time to buy"],
            total_products=5,
            errors=[],
            timestamp="March 9, 2026",
        )
        assert "<!DOCTYPE html>" in html
        assert "Price Monitor Report" in html
        assert "Price analysis here" in html
        assert "Good time to buy" in html

    def test_html_with_errors(self):
        html = build_email_html(
            summary="Test",
            price_changes=[],
            insights=[],
            total_products=0,
            errors=["Scrape failed"],
            timestamp="Test",
        )
        assert "Scraping Warnings" in html


@pytest.mark.asyncio
async def test_fetch_prices_from_file():
    """Test the file scraper with a temp JSON file."""
    data = {"products": [
        {"name": "Test Item", "price": 19.99},
        {"name": "Another Item", "price": 29.99},
    ]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        tmp_path = f.name

    source = CompetitorSource(
        name="TestFile",
        source_type="file",
        url=tmp_path,
        product_key="name",
        price_key="price",
    )

    records = await fetch_prices(source)
    assert len(records) == 2
    assert records[0].product == "Test Item"
    assert records[0].price == 19.99
    assert records[1].competitor == "TestFile"

    Path(tmp_path).unlink()
