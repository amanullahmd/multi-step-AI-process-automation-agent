"""Web scraping tools for fetching prices from various sources."""

import asyncio
import json
import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from agent.state import CompetitorSource, PriceRecord
from agent.utils.config import get_settings

logger = logging.getLogger(__name__)


async def scrape_api(source: CompetitorSource, client: httpx.AsyncClient) -> list[PriceRecord]:
    """Fetch product prices from a JSON API endpoint."""
    response = await client.get(source.url)
    response.raise_for_status()
    data = response.json()

    # Handle both list responses and nested data
    items = data if isinstance(data, list) else data.get("products", data.get("items", []))

    records = []
    product_key = source.product_key or "title"
    price_key = source.price_key or "price"

    for item in items:
        try:
            product_name = _get_nested(item, product_key)
            price_value = float(_get_nested(item, price_key))
            records.append(
                PriceRecord(
                    competitor=source.name,
                    product=str(product_name),
                    price=price_value,
                    url=source.url,
                    scraped_at=datetime.now(),
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping item from {source.name}: {e}")

    return records


async def scrape_web(source: CompetitorSource, client: httpx.AsyncClient) -> list[PriceRecord]:
    """Scrape product prices from a web page using CSS selectors.

    Expects selector format: "product_selector|price_selector"
    Example: ".product-name|.price"
    """
    response = await client.get(source.url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    selectors = source.selector.split("|")
    if len(selectors) != 2:
        raise ValueError(
            f"Selector must be 'product_selector|price_selector', got: {source.selector}"
        )

    product_selector, price_selector = selectors
    products = soup.select(product_selector)
    prices = soup.select(price_selector)

    records = []
    for prod_el, price_el in zip(products, prices):
        try:
            product_name = prod_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True)
            price_value = _parse_price(price_text)
            records.append(
                PriceRecord(
                    competitor=source.name,
                    product=product_name,
                    price=price_value,
                    url=source.url,
                    scraped_at=datetime.now(),
                )
            )
        except (ValueError, AttributeError) as e:
            logger.warning(f"Skipping element from {source.name}: {e}")

    return records


async def scrape_file(source: CompetitorSource, _client: httpx.AsyncClient) -> list[PriceRecord]:
    """Load product prices from a local JSON file."""
    with open(source.url, "r") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else data.get("products", [])
    product_key = source.product_key or "title"
    price_key = source.price_key or "price"

    records = []
    for item in items:
        try:
            records.append(
                PriceRecord(
                    competitor=source.name,
                    product=str(_get_nested(item, product_key)),
                    price=float(_get_nested(item, price_key)),
                    url=source.url,
                    scraped_at=datetime.now(),
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping item from {source.name}: {e}")

    return records


async def fetch_prices(source: CompetitorSource) -> list[PriceRecord]:
    """Route to the correct scraper based on source type."""
    settings = get_settings()

    scrapers = {
        "api": scrape_api,
        "web": scrape_web,
        "file": scrape_file,
    }

    scraper_fn = scrapers.get(source.source_type)
    if not scraper_fn:
        raise ValueError(f"Unknown source type: {source.source_type}")

    async with httpx.AsyncClient(
        timeout=settings.scrape_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    ) as client:
        # Rate limit
        await asyncio.sleep(settings.scrape_delay_seconds)
        return await scraper_fn(source, client)


def _get_nested(data: dict, key_path: str):
    """Get a value from nested dict using dot notation. e.g. 'category.name'."""
    keys = key_path.split(".")
    value = data
    for k in keys:
        value = value[k]
    return value


def _parse_price(text: str) -> float:
    """Parse a price string like '$29.99' or '29,99 EUR' into a float."""
    cleaned = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            cleaned += ch
        elif ch == ",":
            cleaned += "."
    if not cleaned:
        raise ValueError(f"Cannot parse price from: {text}")
    return float(cleaned)
