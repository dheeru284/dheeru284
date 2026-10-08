"""Structured JSON logging with secret redaction."""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

_REDACTIONS = [
    (re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"), "https://hooks.slack.com/services/[REDACTED]"),
    (re.compile(r"xox[abprs]-[A-Za-z0-9-]+"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)(\"?\s*[:=]\s*\"?)[^\s\"&,}]+"), r"\1\2[REDACTED]"),
    (re.compile(r"(://[^:/\s]+:)[^@/\s]+@"), r"\1[REDACTED]@"),
]


def redact(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STD and not key.startswith("_"):
                payload[key] = redact(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx logs full URLs
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
