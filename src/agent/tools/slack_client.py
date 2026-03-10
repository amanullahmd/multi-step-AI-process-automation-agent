"""Slack notification client using incoming webhooks."""

import logging

from slack_sdk.webhook import WebhookClient

logger = logging.getLogger(__name__)


def send_slack_report(webhook_url: str, blocks: list[dict], fallback_text: str) -> bool:
    """Send a formatted report to Slack via webhook.

    Args:
        webhook_url: Slack incoming webhook URL
        blocks: Slack Block Kit blocks for rich formatting
        fallback_text: Plain text fallback for notifications

    Returns:
        True if sent successfully
    """
    client = WebhookClient(webhook_url)

    response = client.send(text=fallback_text, blocks=blocks)

    if response.status_code == 200:
        logger.info("Slack notification sent successfully")
        return True
    else:
        logger.error(f"Slack send failed: {response.status_code} - {response.body}")
        return False


def build_slack_blocks(
    summary: str,
    price_changes: list[dict],
    insights: list[str],
    total_products: int,
    errors: list[str],
) -> list[dict]:
    """Build Slack Block Kit blocks for a price monitoring report.

    Returns a list of block dicts ready for the Slack API.
    """
    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "Price Monitor Report", "emoji": True},
    })

    # Stats bar
    change_count = len(price_changes)
    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*Products Tracked:*\n{total_products}"},
            {"type": "mrkdwn", "text": f"*Price Changes:*\n{change_count}"},
        ],
    })

    blocks.append({"type": "divider"})

    # Price changes
    if price_changes:
        change_lines = []
        for c in price_changes[:15]:  # Limit to 15 for readability
            if c["direction"] == "new":
                change_lines.append(f"*NEW* {c['competitor']} — {c['product']}: ${c['new_price']:.2f}")
            else:
                arrow = ":arrow_up:" if c["direction"] == "up" else ":arrow_down:"
                change_lines.append(
                    f"{arrow} *{c['change_pct']:+.1f}%* {c['competitor']} — "
                    f"{c['product']}: ${c['old_price']:.2f} -> ${c['new_price']:.2f}"
                )

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Price Changes:*\n" + "\n".join(change_lines)},
        })
        blocks.append({"type": "divider"})

    # Key insights
    if insights:
        insight_text = "\n".join(f"• {i}" for i in insights[:5])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Key Insights:*\n{insight_text}"},
        })

    # Errors
    if errors:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":warning: {len(errors)} scraping error(s) occurred"},
            ],
        })

    return blocks
