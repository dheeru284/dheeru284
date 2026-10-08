from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.notifiers.base import Notifier, NotifierNotConfigured, register_notifier
from app.utils.currency import format_inr

SEVERITY = {
    "EXTREME": ("🔥", "EXTREME DEAL"),
    "GREAT": ("🚨", "GREAT DEAL"),
    "GOOD": ("🔥", "GOOD DEAL"),
}


def baseline_label(btype: str) -> str:
    if btype == "median_lifetime":
        return "lifetime median"
    return f"{btype.removeprefix('median_').removesuffix('d')}-day median"


def _link(label: str, url: str) -> str:
    safe = url.replace("<", "%3C").replace(">", "%3E").replace("|", "%7C")
    return f"<{safe}|{label}>"


def _trend(label: str, pct: float | None) -> str:
    if pct is None:
        return f"{label}: n/a"
    arrow = "↓" if pct < -0.5 else "↑" if pct > 0.5 else "→"
    return f"{label}: {arrow} {abs(pct):.0f}% vs avg"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_blocks(p: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Slack Block Kit payload + plain-text fallback. Pure function (unit-tested)."""
    emoji, label = SEVERITY.get(p["severity"], ("🔥", "DEAL"))
    best = p["best"]
    base_label = baseline_label(p["baseline"]["type"])
    stats = p["stats"]
    title = f"{emoji} {label}: {p['discount']:.0f}% below observed price history"
    header = {"type": "header", "text": {"type": "plain_text", "text": title[:150], "emoji": True}}
    name = f"*{_link(_esc(p['product_name']), best['url'])}*"
    if p.get("brand"):
        name += f"\nBrand: {_esc(str(p['brand']).title())}"
    rating = f"{p['rating']:.1f}/5" if p.get("rating") is not None else "n/a"
    reviews = f"{p['review_count']:,}" if p.get("review_count") else "n/a"

    fields = [
        {"type": "mrkdwn", "text": f"*⭐ Rating*\n{rating}"},
        {"type": "mrkdwn", "text": f"*📝 Reviews*\n{reviews}"},
        {"type": "mrkdwn", "text": f"*💰 Best price now*\n{format_inr(best['price'])}"},
        {"type": "mrkdwn", "text": f"*🏆 Best retailer*\n{_link(best['retailer_name'], best['url'])}"},
        {"type": "mrkdwn", "text": f"*📉 {base_label[0].upper() + base_label[1:]}*\n{format_inr(p['baseline']['price'])}"},
        {"type": "mrkdwn", "text": f"*📊 Discount vs history*\n{p['discount']:.1f}% (not MRP)"},
    ]
    blocks: list[dict[str, Any]] = [
        header,
        {"type": "section", "text": {"type": "mrkdwn", "text": name}, "fields": fields},
    ]

    if p["others"]:
        lines = [f"{_link(o['retailer_name'], o['url'])}{' (official brand store)' if o.get('official') else ''}"
                 f" — {format_inr(o['price'])}"
                 f"  (+{(o['price'] - best['price']) / best['price'] * 100:.1f}%)" for o in p["others"][:6]]
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Other verified prices*\n" + "\n".join(lines)}})
    else:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": "*Other verified prices*\n_No other retailer confirmed yet_"}})

    rng = p.get("range_90d")
    rng_txt = f"{format_inr(rng[0])} – {format_inr(rng[1])}" if rng else "n/a"
    hist = (
        f"*Historical:* min {format_inr(stats['min'])} · median {format_inr(stats['median'])} · "
        f"max {format_inr(stats['robust_max'])}"
        + (f" (spike-filtered; raw max {format_inr(stats['max'])})" if stats["max"] != stats["robust_max"] else "")
        + "\n"
        f"*90-day range:* {rng_txt}\n"
        f"{_trend('30-day trend', p.get('trend_30d'))} · {_trend('90-day trend', p.get('trend_90d'))}\n"
        f"vs max {p['discount_from_max']:.0f}% · vs median {p['discount_from_median']:.0f}% · "
        f"vs average {p['discount_from_average']:.0f}%"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": hist}})

    warn = []
    if "no_cross_retailer_confirmation" in p.get("flags", []):
        warn.append("only one retailer currently verified")
    if p.get("history_quality") != "HIGH":
        warn.append(f"{p['history_quality'].lower()}-confidence history")
    if p.get("uses_imported_history"):
        warn.append("includes imported (not self-observed) history")
    ts = p["detected_at"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    ctx = (f"🔎 Deal confidence: *{p['confidence']}* (score {p['score']:.0f}/100, internal ranking signal) · "
           f"History: *{p['history_quality']}* ({stats['n_observations']} obs / {stats['span_days']}d) · "
           f"Match confidence: {p['match_confidence']:.0f}% · {ts.strftime('%Y-%m-%d %H:%M UTC')}")
    if warn:
        ctx += "\n⚠️ " + "; ".join(warn)
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": ctx}]})

    buttons = []
    for i, o in enumerate([best, *p["others"]][:5]):
        btn = {"type": "button", "text": {"type": "plain_text", "text": f"Buy on {o['retailer_name']}"[:75]},
               "url": o["url"]}
        if i == 0:
            btn["style"] = "primary"
        buttons.append(btn)
    blocks.append({"type": "actions", "elements": buttons})
    fallback = (f"{label}: {p['product_name']} — {format_inr(best['price'])} at {best['retailer_name']} "
                f"({p['discount']:.0f}% below historical {base_label}) {best['url']}")
    return blocks, fallback


@register_notifier
class SlackNotifier(Notifier):
    channel = "slack"

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.s = settings or get_settings()
        self.client = client or httpx.Client(timeout=15)

    def is_configured(self) -> bool:
        return bool(self.s.slack_webhook_url or (self.s.slack_bot_token and self.s.slack_channel_id))

    def _channel_for(self, payload: dict[str, Any]) -> str | None:
        return self.s.channel_map.get(payload.get("category") or "") or self.s.slack_channel_id

    def send_deal(self, payload: dict[str, Any]) -> None:
        if not self.is_configured():
            raise NotifierNotConfigured("Set SLACK_WEBHOOK_URL, or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID")
        blocks, text = build_blocks(payload)
        if self.s.slack_bot_token and self._channel_for(payload):
            resp = self.client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.s.slack_bot_token}"},
                json={"channel": self._channel_for(payload), "text": text, "blocks": blocks,
                      "unfurl_links": False},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"slack api error: {data.get('error')}")
            return
        resp = self.client.post(self.s.slack_webhook_url, json={"text": text, "blocks": blocks})  # type: ignore[arg-type]
        if resp.status_code != 200 or resp.text.strip() != "ok":
            raise RuntimeError(f"slack webhook failed: {resp.status_code} {resp.text[:100]}")
