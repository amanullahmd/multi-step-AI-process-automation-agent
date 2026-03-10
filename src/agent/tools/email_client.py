"""Email notification client using SendGrid."""

import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Mail

logger = logging.getLogger(__name__)


def send_email_report(
    api_key: str,
    from_email: str,
    to_email: str,
    subject: str,
    html_content: str,
) -> bool:
    """Send an HTML email report via SendGrid.

    Returns True if sent successfully.
    """
    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=Content("text/html", html_content),
    )

    client = SendGridAPIClient(api_key)
    response = client.send(message)

    if response.status_code in (200, 201, 202):
        logger.info(f"Email sent to {to_email}")
        return True
    else:
        logger.error(f"Email failed: {response.status_code} - {response.body}")
        return False


def build_email_html(
    summary: str,
    price_changes: list[dict],
    insights: list[str],
    total_products: int,
    errors: list[str],
    timestamp: str,
) -> str:
    """Build a clean HTML email for the price monitoring report."""

    # Price changes table rows
    change_rows = ""
    for c in price_changes:
        if c["direction"] == "new":
            badge = '<span style="color:#2196F3;font-weight:bold">NEW</span>'
            price_cell = f"${c['new_price']:.2f}"
        elif c["direction"] == "up":
            badge = f'<span style="color:#f44336;font-weight:bold">+{c["change_pct"]:.1f}%</span>'
            price_cell = f"${c['old_price']:.2f} &rarr; ${c['new_price']:.2f}"
        else:
            badge = f'<span style="color:#4CAF50;font-weight:bold">{c["change_pct"]:.1f}%</span>'
            price_cell = f"${c['old_price']:.2f} &rarr; ${c['new_price']:.2f}"

        change_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee">{c['competitor']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{c['product']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{price_cell}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{badge}</td>
        </tr>"""

    changes_table = ""
    if change_rows:
        changes_table = f"""
        <h2 style="color:#333;border-bottom:2px solid #667eea;padding-bottom:8px">
            Price Changes ({len(price_changes)})
        </h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
                <tr style="background:#f5f5f5">
                    <th style="padding:10px;text-align:left">Competitor</th>
                    <th style="padding:10px;text-align:left">Product</th>
                    <th style="padding:10px;text-align:left">Price</th>
                    <th style="padding:10px;text-align:left">Change</th>
                </tr>
            </thead>
            <tbody>{change_rows}</tbody>
        </table>"""

    # Insights list
    insight_items = "".join(f"<li style='margin-bottom:6px'>{i}</li>" for i in insights)
    insights_section = ""
    if insight_items:
        insights_section = f"""
        <h2 style="color:#333;border-bottom:2px solid #667eea;padding-bottom:8px">
            Key Insights
        </h2>
        <ul style="line-height:1.6">{insight_items}</ul>"""

    # Error banner
    error_banner = ""
    if errors:
        error_list = "".join(f"<li>{e}</li>" for e in errors)
        error_banner = f"""
        <div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;border-radius:6px;margin-bottom:20px">
            <strong>Scraping Warnings ({len(errors)}):</strong>
            <ul style="margin:8px 0 0 0">{error_list}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#333">
    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:24px;border-radius:10px 10px 0 0">
        <h1 style="color:white;margin:0;font-size:24px">Price Monitor Report</h1>
        <p style="color:rgba(255,255,255,0.85);margin:8px 0 0 0">{timestamp}</p>
    </div>

    <div style="background:white;padding:24px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 10px 10px">
        <div style="display:flex;gap:20px;margin-bottom:20px">
            <div style="background:#f0f4ff;padding:16px;border-radius:8px;flex:1;text-align:center">
                <div style="font-size:28px;font-weight:bold;color:#667eea">{total_products}</div>
                <div style="color:#666;font-size:13px">Products Tracked</div>
            </div>
            <div style="background:#f0fff4;padding:16px;border-radius:8px;flex:1;text-align:center">
                <div style="font-size:28px;font-weight:bold;color:#4CAF50">{len(price_changes)}</div>
                <div style="color:#666;font-size:13px">Price Changes</div>
            </div>
        </div>

        {error_banner}
        {changes_table}
        {insights_section}

        <h2 style="color:#333;border-bottom:2px solid #667eea;padding-bottom:8px">Full Analysis</h2>
        <div style="background:#f9f9f9;padding:16px;border-radius:8px;line-height:1.7;white-space:pre-wrap;font-size:14px">{summary}</div>

        <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
        <p style="color:#999;font-size:12px;text-align:center">
            Generated by Price Monitor Agent | Automated Competitive Intelligence
        </p>
    </div>
</body>
</html>"""
