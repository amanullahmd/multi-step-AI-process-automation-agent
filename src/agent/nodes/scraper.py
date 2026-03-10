"""Scraper node — fetches prices from all competitor sources."""

import asyncio
import logging
from typing import Any

from agent.state import AgentState
from agent.tools.web_scraper import fetch_prices

logger = logging.getLogger(__name__)


async def scrape_prices(state: AgentState) -> dict[str, Any]:
    """Fan-out: scrape all competitor sources concurrently.

    Returns partial state with scraped_prices and scrape_errors.
    """
    logger.info(f"Scraping {len(state.competitors)} competitor sources...")

    tasks = [fetch_prices(source) for source in state.competitors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_prices = []
    errors = []

    for source, result in zip(state.competitors, results):
        if isinstance(result, Exception):
            error_msg = f"[{source.name}] Scrape failed: {result}"
            logger.error(error_msg)
            errors.append(error_msg)
        else:
            logger.info(f"[{source.name}] Scraped {len(result)} products")
            all_prices.extend(result)

    return {
        "scraped_prices": all_prices,
        "scrape_errors": errors,
    }
