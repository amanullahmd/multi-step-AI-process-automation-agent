"""Consolidator node — deduplicates, stores, and detects price changes."""

import logging
from typing import Any

from agent.state import AgentState
from agent.utils.config import get_settings
from agent.utils.database import PriceDatabase

logger = logging.getLogger(__name__)


async def consolidate_data(state: AgentState) -> dict[str, Any]:
    """Deduplicate scraped prices, save to DB, and detect changes.

    Returns partial state with consolidated data and detected price changes.
    """
    settings = get_settings()
    db = PriceDatabase(settings.db_path)

    prices = state.scraped_prices
    logger.info(f"Consolidating {len(prices)} scraped price records...")

    # Deduplicate: keep latest per (competitor, product)
    seen: dict[tuple[str, str], int] = {}
    for i, record in enumerate(prices):
        key = (record.competitor, record.product)
        seen[key] = i  # last occurrence wins

    unique_prices = [prices[i] for i in seen.values()]
    logger.info(f"Deduplicated to {len(unique_prices)} unique products")

    # Detect changes against previous scrape
    changes = db.detect_changes(unique_prices)
    logger.info(f"Detected {len(changes)} price changes")

    # Save current prices to history
    saved = db.save_prices(unique_prices)
    logger.info(f"Saved {saved} records to database")

    return {
        "consolidated_prices": unique_prices,
        "price_changes": changes,
        "total_products_tracked": len(unique_prices),
    }
