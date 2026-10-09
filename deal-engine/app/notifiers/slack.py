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


def _window_words(btype: str) -> str:
    if btype == "median_lifetime":
        return "over its whole price history"
    days = btype.removeprefix("median_").removesuffix("d")
    return "over the last year" if days == "365" else f"over the last {days} days"


_TITLES = {"EXTREME": ("🔥", "Huge price drop"), "GREAT": ("🚨", "Big price drop"), "GOOD": ("📉", "Price drop")}
_CONF = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}


def build_blocks(p: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Plain-English Slack message (Block Kit) + one-line fallback. Pure function (unit-tested)."""
    emoji, label = _TITLES.get(p["severity"], ("📉", "Price drop"))
    best, base = p["best"], p["baseline"]
    stats = p["stats"]
    pct = round(p["discount"])
    save = max(0, base["price"] - best["price"])
    name = _esc(p["product_name"])
    when = _window_words(base["type"])

    rating = f"{p['rating']:.1f}★" if p.get("rating") is not None else "not rated"
    reviews = f" from {p['review_count']:,} reviews" if p.get("review_count") else ""

    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {label}: {pct}% cheaper than usual"[:150], "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*{_link(name, best['url'])}*\n"
            f"Now *{format_inr(best['price'])}* at *{_esc(best['retailer_name'])}*"
            f"{' (the brand\'s own store)' if best.get('official') else ''}\n"
            f"Usually {format_inr(base['price'])} {when}, so you save about *{format_inr(save)}* ({pct}%).\n"
            f"Rating: {rating}{reviews}")}},
    ]

    options = [best, *p["others"]]
    lines = []
    for i, o in enumerate(options[:6]):
        tag = "  ← cheapest" if i == 0 else ""
        lines.append(f"{i + 1}. {_link(_esc(o['retailer_name']), o['url'])} — {format_inr(o['price'])}{tag}")
    title = "Where to buy (cheapest first)" if len(options) > 1 else "Where to buy"
    extra = "" if len(options) > 1 else "\n_Only one store checked so far, so no comparison yet._"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*\n" + "\n".join(lines) + extra}})

    rng = p.get("range_90d")
    history = (f"Price history: lowest {format_inr(stats['min'])}, highest {format_inr(stats['robust_max'])}"
               f"{f', last 3 months {format_inr(rng[0])} to {format_inr(rng[1])}' if rng else ''}. "
               f"Based on {stats['n_observations']:,} price checks over {stats['span_days']} days.")
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": history}})

    notes = [f"How sure are we: {_CONF.get(p['confidence'], 'low')} (history quality {_CONF.get(p['history_quality'], 'low')})."]
    if "no_cross_retailer_confirmation" in p.get("flags", []):
        notes.append("Only one store confirms this price.")
    if p.get("history_quality") != "HIGH":
        notes.append("Short price history, so double-check before buying.")
    if p.get("uses_imported_history"):
        notes.append("Part of the history was imported, not watched by us.")
    notes.append('"Usually" is the typical price we saw, not the printed MRP.')
    ts = p["detected_at"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    notes.append(ts.strftime("Checked %d %b %Y, %H:%M UTC."))
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": " ".join(notes)}]})

    buttons = []
    for i, o in enumerate(options[:5]):
        btn = {"type": "button", "text": {"type": "plain_text", "text": f"Buy at {o['retailer_name']}"[:75]}, "url": o["url"]}
        if i == 0:
            btn["style"] = "primary"
        buttons.append(btn)
    blocks.append({"type": "actions", "elements": buttons})
    fallback = (f"{label}: {p['product_name']} is now {format_inr(best['price'])} at {best['retailer_name']} "
                f"({pct}% cheaper than usual). {best['url']}")
    return blocks, fallback


def build_quick_drop(p: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Simple 'the price just went down' message used by the watchlist runner (no long-history claim)."""
    drop = round((p["old_price"] - p["new_price"]) / p["old_price"] * 100)
    save = p["old_price"] - p["new_price"]
    text = (f"*{_link(_esc(p['title']), p['url'])}*\n"
            f"Price dropped from {format_inr(p['old_price'])} to *{format_inr(p['new_price'])}* at *{_esc(p['retailer_name'])}*"
            f" — {drop}% cheaper, you save about {format_inr(save)}.")
    if p.get("rating") is not None:
        text += f"\nRating: {p['rating']:.1f}★" + (f" from {p['review_count']:,} reviews" if p.get("review_count") else "")
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"📉 Price drop: {drop}% cheaper", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": (
            f"This compares with the last price we saw ({p['history_days']} days of watching). "
            "It is not yet checked against a long price history, so it may not be a genuinely great deal.")}]},
        {"type": "actions", "elements": [{"type": "button", "style": "primary", "url": p["url"],
                                           "text": {"type": "plain_text", "text": f"Buy at {p['retailer_name']}"[:75]}}]},
    ]
    return blocks, (f"Price drop: {p['title']} {format_inr(p['old_price'])} → {format_inr(p['new_price'])} "
                    f"at {p['retailer_name']}. {p['url']}")


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

    def send_quick_drop(self, payload: dict[str, Any]) -> None:
        blocks, text = build_quick_drop(payload)
        self._post(blocks, text, payload.get("category"))

    def send_deal(self, payload: dict[str, Any]) -> None:
        blocks, text = build_blocks(payload)
        self._post(blocks, text, payload.get("category"))

    def _post(self, blocks: list[dict[str, Any]], text: str, category: str | None) -> None:
        payload = {"category": category}
        if not self.is_configured():
            raise NotifierNotConfigured("Set SLACK_WEBHOOK_URL, or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID")
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
