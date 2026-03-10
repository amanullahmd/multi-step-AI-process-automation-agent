"""Reporter node — generates and sends formatted reports via Slack/email/console."""

import logging
from typing import Any

from agent.state import AgentState, ReportFormat
from agent.tools.email_client import build_email_html, send_email_report
from agent.tools.slack_client import build_slack_blocks, send_slack_report
from agent.utils.config import get_settings

logger = logging.getLogger(__name__)


async def generate_report(state: AgentState) -> dict[str, Any]:
    """Generate formatted reports (HTML email + Slack blocks + plain text)."""

    changes_dicts = [c.model_dump() for c in state.price_changes]
    timestamp = state.run_timestamp.strftime("%B %d, %Y at %H:%M")

    # Build Slack blocks
    slack_blocks = build_slack_blocks(
        summary=state.analysis_summary,
        price_changes=changes_dicts,
        insights=state.key_insights,
        total_products=state.total_products_tracked,
        errors=state.scrape_errors,
    )

    # Build email HTML
    report_html = build_email_html(
        summary=state.analysis_summary,
        price_changes=changes_dicts,
        insights=state.key_insights,
        total_products=state.total_products_tracked,
        errors=state.scrape_errors,
        timestamp=timestamp,
    )

    # Build plain text report
    report_text = _build_text_report(state, timestamp)

    return {
        "report_html": report_html,
        "report_slack_blocks": slack_blocks,
        "report_text": report_text,
    }


async def send_notifications(state: AgentState) -> dict[str, Any]:
    """Send the report via configured channels."""
    settings = get_settings()
    sent: list[str] = []
    fmt = state.report_format

    # Console output (always available)
    if fmt in (ReportFormat.CONSOLE, ReportFormat.BOTH):
        print("\n" + "=" * 60)
        print(state.report_text)
        print("=" * 60 + "\n")
        sent.append("console")

    # Slack
    if fmt in (ReportFormat.SLACK, ReportFormat.BOTH) and settings.slack_enabled:
        try:
            success = send_slack_report(
                webhook_url=settings.slack_webhook_url,
                blocks=state.report_slack_blocks,
                fallback_text=f"Price Monitor Report — {state.total_products_tracked} products tracked, {len(state.price_changes)} changes",
            )
            if success:
                sent.append("slack")
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    # Email
    if fmt in (ReportFormat.EMAIL, ReportFormat.BOTH) and settings.email_enabled:
        try:
            success = send_email_report(
                api_key=settings.sendgrid_api_key,
                from_email=settings.email_from,
                to_email=settings.email_to,
                subject=f"Price Monitor Report — {len(state.price_changes)} changes detected",
                html_content=state.report_html,
            )
            if success:
                sent.append("email")
        except Exception as e:
            logger.error(f"Email notification failed: {e}")

    logger.info(f"Notifications sent via: {', '.join(sent) or 'none'}")

    return {"notifications_sent": sent}


def _build_text_report(state: AgentState, timestamp: str) -> str:
    """Build a plain-text version of the report for console output."""
    lines = [
        f"PRICE MONITOR REPORT — {timestamp}",
        f"Products Tracked: {state.total_products_tracked}",
        f"Price Changes: {len(state.price_changes)}",
        "",
    ]

    if state.price_changes:
        lines.append("--- PRICE CHANGES ---")
        for c in state.price_changes:
            if c.direction == "new":
                lines.append(f"  [NEW] {c.competitor} | {c.product}: ${c.new_price:.2f}")
            else:
                arrow = "UP" if c.direction == "up" else "DOWN"
                lines.append(
                    f"  [{arrow} {c.change_pct:+.1f}%] {c.competitor} | {c.product}: "
                    f"${c.old_price:.2f} -> ${c.new_price:.2f}"
                )
        lines.append("")

    if state.key_insights:
        lines.append("--- KEY INSIGHTS ---")
        for insight in state.key_insights:
            lines.append(f"  - {insight}")
        lines.append("")

    lines.append("--- FULL ANALYSIS ---")
    lines.append(state.analysis_summary)

    if state.scrape_errors:
        lines.append("")
        lines.append(f"--- WARNINGS ({len(state.scrape_errors)}) ---")
        for err in state.scrape_errors:
            lines.append(f"  ! {err}")

    return "\n".join(lines)
