from app.config.settings import Settings
from scripts import check_credentials as cc


def test_reports_missing_without_leaking_secrets(capsys):
    s = Settings(_env_file=None)
    assert cc.check_amazon(s)[0] == "MISSING" and cc.check_flipkart(s)[0] == "MISSING"
    assert cc.check_slack(s)[0] == "MISSING"
    s2 = Settings(_env_file=None, slack_webhook_url="https://hooks.slack.com/services/T/B/SECRET")
    status, detail = cc.check_slack(s2)
    assert status == "SET" and "SECRET" not in detail
