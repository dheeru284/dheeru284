"""Notification channels. Add Email/Telegram/Discord by subclassing Notifier and registering it -
the deal engine only talks to this interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NotifierNotConfigured(RuntimeError):
    pass


class Notifier(ABC):
    channel: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def send_deal(self, payload: dict[str, Any]) -> None:
        """Raise on failure (the caller records status and retries)."""


NOTIFIERS: dict[str, type[Notifier]] = {}


def register_notifier(cls: type[Notifier]) -> type[Notifier]:
    NOTIFIERS[cls.channel] = cls
    return cls
