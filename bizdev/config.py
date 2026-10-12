"""Runtime configuration, read from environment variables only.

Secrets never live in code or in the database unencrypted. Business rules
(weights, limits, sequences) live in the `automation_rules` table so an
administrator can change them without code changes; the values below are
only the defaults used to seed that table.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./bizdev.db"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    token_encryption_key: str = field(default_factory=lambda: os.getenv("TOKEN_ENCRYPTION_KEY", ""))
    admin_email: str = field(default_factory=lambda: os.getenv("ADMIN_EMAIL", "admin@example.invalid"))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    # Global safety switch. External sending requires BOTH this env flag and the
    # in-app "live sending authorized" toggle. Default: off.
    allow_live_send: bool = field(default_factory=lambda: _bool("ALLOW_LIVE_SEND", False))
    email_provider: str = field(default_factory=lambda: os.getenv("EMAIL_PROVIDER", "mock"))  # mock|gmail|outlook
    calendar_provider: str = field(default_factory=lambda: os.getenv("CALENDAR_PROVIDER", "mock"))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "none"))  # none|anthropic
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-sonnet-5-5"))
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRET", ""))
    oauth_redirect_base: str = field(default_factory=lambda: os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8000"))
    zoho_user: str = field(default_factory=lambda: os.getenv("ZOHO_SMTP_USER", ""))
    zoho_app_password: str = field(default_factory=lambda: os.getenv("ZOHO_APP_PASSWORD", ""))
    zoho_host: str = field(default_factory=lambda: os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.in"))
    sender_name: str = field(default_factory=lambda: os.getenv("SENDER_NAME", ""))
    apollo_api_key: str = field(default_factory=lambda: os.getenv("APOLLO_API_KEY", ""))


def get_settings() -> Settings:
    return Settings()


DEFAULT_RULES: dict[str, object] = {
    "scoring.weights": {
        "evidence": 30, "service_match": 25, "offshore": 15,
        "decision_maker": 10, "geo_timing": 10, "contract_model": 10,
    },
    "scoring.tiers": {"A": 80, "B": 60},
    "limits.email": {"per_hour": 5, "per_day": 25},
    "limits.linkedin": {"per_hour": 5, "per_day": 15},
    "limits.per_company_days": 7,     # min days between new outreach to the same org
    "limits.per_contact_days": 4,     # min days between any two messages to one contact
    "quiet_hours": {"start": 19, "end": 8},  # recipient local time; weekends skipped too
    "approval.policy": "manual_every_message",  # | approve_new_contact | approved_segments
    "approval.segments": [],          # e.g. ["staffing_agency:AE"] for approved_segments
    "followup.sequence": [
        {"day": 4, "kind": "followup_brief"},
        {"day": 9, "kind": "followup_value"},
        {"day": 15, "kind": "followup_final"},
    ],
    "followup.enabled": True,
    "campaign.dubai": {
        "travel_date": "2026-11-27", "window_start": "2026-11-27", "window_end": "2026-12-01",
        "timezone": "Asia/Dubai",
    },
    "availability": {  # used when no calendar is connected; must be confirmed before booking
        "timezone": "Asia/Dubai", "days": [0, 1, 2, 3, 4, 5, 6], "start_hour": 10, "end_hour": 17,
        "meeting_minutes": 30, "buffer_minutes": 15, "confirmed_by_admin": False,
    },
    "system.paused": False,
    "system.emergency_stop": False,
    "system.live_send_authorized": False,
}
