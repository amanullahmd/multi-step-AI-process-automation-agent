"""Consolidator node — deduplicates, stores, and detects price changes."""

import logging
from typing import Any

from agent.state import AgentState
from agent.utils.config import get_settings
from agent.utils.database import PriceDatabase

logger = logging.getLogger(__name__)


async def consolidate_data(state: AgentState) -> dict[str, Any]:
    """Deduplicate scraped prices, save to DB, and detect changes.

    Applies a minimum change threshold (``min_change_pct``) to filter noise:
    changes smaller than the threshold are silently dropped so the LLM is
    only asked to reason about meaningful price movements.

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
    all_changes = db.detect_changes(unique_prices)

    # Filter out insignificant changes below the configured threshold.
    # "new" products are always kept regardless of threshold.
    min_pct = settings.min_change_pct
    significant_changes = [
        c for c in all_changes
        if c.direction == "new" or abs(c.change_pct) >= min_pct
    ]
    filtered_count = len(all_changes) - len(significant_changes)
    if filtered_count:
        logger.info(
            f"Filtered {filtered_count} insignificant change(s) below {min_pct}% threshold"
        )
    logger.info(f"Detected {len(significant_changes)} significant price changes")

    # Save current prices to history
    saved = db.save_prices(unique_prices)
    logger.info(f"Saved {saved} records to database")

    return {
        "consolidated_prices": unique_prices,
        "price_changes": significant_changes,
        "total_products_tracked": len(unique_prices),
    }
