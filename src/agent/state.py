"""Pydantic state models for the LangGraph agent."""

from datetime import datetime
from enum import Enum
from typing import Annotated

import operator
from pydantic import BaseModel, Field


class CompetitorSource(BaseModel):
    """A competitor data source to monitor."""

    name: str = Field(description="Competitor name")
    source_type: str = Field(description="Type: 'api', 'web', or 'file'")
    url: str = Field(description="URL or file path to scrape/fetch")
    selector: str = Field(default="", description="CSS selector for web scraping")
    product_key: str = Field(default="", description="JSON key path for product name in API")
    price_key: str = Field(default="", description="JSON key path for price in API")


class PriceRecord(BaseModel):
    """A single scraped price data point."""

    competitor: str
    product: str
    price: float
    currency: str = "USD"
    url: str = ""
    scraped_at: datetime = Field(default_factory=datetime.now)


class PriceChange(BaseModel):
    """A detected price change between scrapes."""

    competitor: str
    product: str
    old_price: float
    new_price: float
    change_pct: float
    direction: str  # "up", "down", "new"


class ReportFormat(str, Enum):
    """Output report format."""

    SLACK = "slack"
    EMAIL = "email"
    BOTH = "both"
    CONSOLE = "console"


class AgentState(BaseModel):
    """The main state passed through the LangGraph pipeline.

    Each node reads from and writes to this state.
    """

    # Input
    competitors: list[CompetitorSource] = Field(default_factory=list)
    report_format: ReportFormat = Field(default=ReportFormat.CONSOLE)

    # Scraping results (accumulated via fan-out)
    scraped_prices: Annotated[list[PriceRecord], operator.add] = Field(default_factory=list)
    scrape_errors: Annotated[list[str], operator.add] = Field(default_factory=list)

    # Consolidated data
    consolidated_prices: list[PriceRecord] = Field(default_factory=list)
    price_changes: list[PriceChange] = Field(default_factory=list)
    total_products_tracked: int = 0

    # LLM analysis
    analysis_summary: str = ""
    key_insights: list[str] = Field(default_factory=list)

    # Report output
    report_html: str = ""
    report_slack_blocks: list[dict] = Field(default_factory=list)
    report_text: str = ""

    # Status
    notifications_sent: list[str] = Field(default_factory=list)
    run_timestamp: datetime = Field(default_factory=datetime.now)
