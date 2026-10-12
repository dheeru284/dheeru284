"""Provider registry. Tests swap these for mocks; production builds them from config."""
from __future__ import annotations

from datetime import timedelta

import httpx
from sqlalchemy import select

from .config import get_settings
from .integrations.calendar import GoogleCalendar, MockCalendar
from .integrations.email import GmailProvider, MockEmailProvider
from .integrations.linkedin import LinkedInIntegration
from .models import IntegrationAccount
from .security import decrypt_secret, encrypt_secret


class Registry:
    def __init__(self):
        self.email = MockEmailProvider()
        self.calendar = MockCalendar()
        self.linkedin = LinkedInIntegration()

    def configure_from_db(self, db) -> None:
        s = get_settings()
        if s.email_provider == "zoho" and s.zoho_user and s.zoho_app_password:
            from .integrations.email import ZohoSMTPProvider
            self.email = ZohoSMTPProvider(s.zoho_user, s.zoho_app_password, s.zoho_host, from_name=s.sender_name or None)
        if s.email_provider == "gmail":
            acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "google"))
            if acct and acct.encrypted_token:
                self.email = GmailProvider(lambda: google_access_token(db))
        if s.calendar_provider == "gcal":
            acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "google"))
            if acct and acct.encrypted_token:
                self.calendar = GoogleCalendar(lambda: google_access_token(db))
        li = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "linkedin"))
        self.linkedin = LinkedInIntegration(li.capabilities if li else None)


registry = Registry()


def google_access_token(db) -> str:
    """Refresh the Google access token from the encrypted refresh token. Tokens never leave this function."""
    import json
    from .core import now_utc
    acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "google"))
    tok = json.loads(decrypt_secret(acct.encrypted_token))
    if tok.get("expires_at", 0) > now_utc().timestamp() + 60:
        return tok["access_token"]
    s = get_settings()
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "client_id": s.google_client_id, "client_secret": s.google_client_secret,
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    tok["access_token"] = j["access_token"]
    tok["expires_at"] = (now_utc() + timedelta(seconds=j.get("expires_in", 3600))).timestamp()
    acct.encrypted_token = encrypt_secret(json.dumps(tok))
    db.commit()
    return tok["access_token"]
