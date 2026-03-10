"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration for the price monitoring agent."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # --- OpenAI ---
    openai_api_key: str = Field(description="OpenAI API key")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_temperature: float = Field(default=0.3)

    # --- Slack ---
    slack_webhook_url: str = Field(default="")
    slack_enabled: bool = Field(default=False)

    # --- Email (SendGrid) ---
    sendgrid_api_key: str = Field(default="")
    email_from: str = Field(default="")
    email_to: str = Field(default="")
    email_enabled: bool = Field(default=False)

    # --- Scheduling ---
    schedule_interval_hours: int = Field(default=168)
    schedule_cron: str = Field(default="0 9 * * 1")

    # --- Database ---
    database_path: str = Field(default="data/price_history.db")

    # --- Scraping ---
    scrape_delay_seconds: float = Field(default=2.0)
    scrape_timeout_seconds: int = Field(default=30)
    user_agent: str = Field(default="PriceMonitorAgent/1.0")

    # --- Logging ---
    log_level: str = Field(default="INFO")

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)


def get_settings() -> Settings:
    """Load and return application settings."""
    return Settings()
