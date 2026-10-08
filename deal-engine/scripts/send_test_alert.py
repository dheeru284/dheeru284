"""Send a clearly-labelled SAMPLE price-drop alert to your configured Slack (webhook or bot token).
Verifies credentials/channel and shows exactly how real alerts look. Usage: python -m scripts.send_test_alert"""
import sys

from app.notifiers.slack import SlackNotifier
from tests.test_slack import payload

if __name__ == "__main__":
    n = SlackNotifier()
    if not n.is_configured():
        sys.exit("Slack not configured: set SLACK_WEBHOOK_URL, or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID in .env")
    p = payload(product_name="[SAMPLE - not a real deal] " + payload()["product_name"])
    n.send_deal(p)
    print("sample alert sent")
