"""SQLite database for storing historical price data."""

import sqlite3
from datetime import datetime
from pathlib import Path

from agent.state import PriceChange, PriceRecord


class PriceDatabase:
    """Manages price history in SQLite."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor TEXT NOT NULL,
                    product TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    url TEXT DEFAULT '',
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_competitor_product
                ON price_history(competitor, product)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_at
                ON price_history(scraped_at)
            """)

    def save_prices(self, prices: list[PriceRecord]) -> int:
        """Save a batch of price records. Returns count saved."""
        with self._get_conn() as conn:
            conn.executemany(
                """INSERT INTO price_history (competitor, product, price, currency, url, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (p.competitor, p.product, p.price, p.currency, p.url, p.scraped_at.isoformat())
                    for p in prices
                ],
            )
        return len(prices)

    def get_previous_prices(self) -> dict[tuple[str, str], float]:
        """Get the most recent price for each (competitor, product) pair.

        Returns a dict of {(competitor, product): price}.
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT competitor, product, price
                FROM price_history
                WHERE (competitor, product, scraped_at) IN (
                    SELECT competitor, product, MAX(scraped_at)
                    FROM price_history
                    GROUP BY competitor, product
                )
            """).fetchall()
        return {(row["competitor"], row["product"]): row["price"] for row in rows}

    def detect_changes(self, current_prices: list[PriceRecord]) -> list[PriceChange]:
        """Compare current prices against the last known prices and return changes."""
        previous = self.get_previous_prices()
        changes: list[PriceChange] = []

        for record in current_prices:
            key = (record.competitor, record.product)
            if key in previous:
                old_price = previous[key]
                if old_price != record.price and old_price > 0:
                    change_pct = ((record.price - old_price) / old_price) * 100
                    direction = "up" if record.price > old_price else "down"
                    changes.append(
                        PriceChange(
                            competitor=record.competitor,
                            product=record.product,
                            old_price=old_price,
                            new_price=record.price,
                            change_pct=round(change_pct, 2),
                            direction=direction,
                        )
                    )
            else:
                changes.append(
                    PriceChange(
                        competitor=record.competitor,
                        product=record.product,
                        old_price=0.0,
                        new_price=record.price,
                        change_pct=0.0,
                        direction="new",
                    )
                )

        return changes

    def get_price_history(
        self, competitor: str, product: str, limit: int = 30
    ) -> list[dict]:
        """Get price history for a specific product."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT price, currency, scraped_at
                   FROM price_history
                   WHERE competitor = ? AND product = ?
                   ORDER BY scraped_at DESC
                   LIMIT ?""",
                (competitor, product, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM price_history").fetchone()["c"]
            products = conn.execute(
                "SELECT COUNT(DISTINCT competitor || '|' || product) as c FROM price_history"
            ).fetchone()["c"]
            latest = conn.execute(
                "SELECT MAX(scraped_at) as latest FROM price_history"
            ).fetchone()["latest"]
        return {
            "total_records": total,
            "unique_products": products,
            "latest_scrape": latest,
        }
