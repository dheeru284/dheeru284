"""Email provider adapters.

`MockEmailProvider` records everything in memory and never touches the network.
`GmailProvider` uses the Gmail REST API with an OAuth token stored encrypted in
`integration_accounts`. It is written against Google's documented API and has
NOT been exercised against a live account from this build environment.
"""
from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import httpx


class SendError(Exception):
    def __init__(self, msg: str, permanent: bool = False):
        super().__init__(msg)
        self.permanent = permanent  # True -> don't retry (e.g. invalid recipient)


@dataclass
class OutboundEmail:
    to: str
    subject: str
    body: str
    from_addr: str
    idempotency_key: str
    thread_id: str | None = None
    in_reply_to: str | None = None
    list_unsubscribe: str | None = None


@dataclass
class SendResult:
    provider_message_id: str
    thread_id: str | None


@dataclass
class InboundEmail:
    provider_message_id: str
    thread_id: str | None
    from_addr: str
    subject: str
    body: str
    is_bounce: bool = False
    auto_submitted: bool = False


class EmailProvider(Protocol):
    name: str
    def send(self, m: OutboundEmail) -> SendResult: ...
    def create_draft(self, m: OutboundEmail) -> str: ...
    def fetch_replies(self, since_iso: str | None = None) -> list[InboundEmail]: ...


@dataclass
class MockEmailProvider:
    name: str = "mock"
    sent: list[OutboundEmail] = field(default_factory=list)
    drafts: list[OutboundEmail] = field(default_factory=list)
    inbox: list[InboundEmail] = field(default_factory=list)
    fail_with: SendError | None = None

    def send(self, m: OutboundEmail) -> SendResult:
        if self.fail_with:
            raise self.fail_with
        if any(s.idempotency_key == m.idempotency_key for s in self.sent):
            raise SendError("duplicate idempotency key", permanent=True)
        self.sent.append(m)
        return SendResult(provider_message_id=f"mock-{uuid.uuid4().hex[:12]}", thread_id=m.thread_id or f"t-{uuid.uuid4().hex[:8]}")

    def create_draft(self, m: OutboundEmail) -> str:
        self.drafts.append(m)
        return f"draft-{len(self.drafts)}"

    def fetch_replies(self, since_iso: str | None = None) -> list[InboundEmail]:
        out, self.inbox = self.inbox, []
        return out


def _mime(m: OutboundEmail) -> str:
    em = EmailMessage()
    em["To"], em["From"], em["Subject"] = m.to, m.from_addr, m.subject
    em["X-Idempotency-Key"] = m.idempotency_key
    if m.in_reply_to:
        em["In-Reply-To"] = em["References"] = m.in_reply_to
    if m.list_unsubscribe:
        em["List-Unsubscribe"] = m.list_unsubscribe
    em.set_content(m.body)
    return base64.urlsafe_b64encode(em.as_bytes()).decode()


class GmailProvider:
    """Least-privilege scopes: gmail.send, gmail.compose (drafts), gmail.readonly (replies)."""
    name = "gmail"
    SCOPES = ["https://www.googleapis.com/auth/gmail.send",
              "https://www.googleapis.com/auth/gmail.compose",
              "https://www.googleapis.com/auth/gmail.readonly"]
    BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, access_token_getter, client: httpx.Client | None = None):
        self._tok = access_token_getter  # callable -> fresh access token (handles refresh)
        self.client = client or httpx.Client(timeout=30)

    def _h(self):
        return {"Authorization": f"Bearer {self._tok()}"}

    def send(self, m: OutboundEmail) -> SendResult:
        payload = {"raw": _mime(m)}
        if m.thread_id:
            payload["threadId"] = m.thread_id
        r = self.client.post(f"{self.BASE}/messages/send", headers=self._h(), json=payload)
        if r.status_code >= 400:
            raise SendError(f"gmail send failed: HTTP {r.status_code}", permanent=r.status_code in (400, 403))
        j = r.json()
        if not j.get("id"):
            raise SendError("gmail returned no message id")
        return SendResult(provider_message_id=j["id"], thread_id=j.get("threadId"))

    def create_draft(self, m: OutboundEmail) -> str:
        r = self.client.post(f"{self.BASE}/drafts", headers=self._h(), json={"message": {"raw": _mime(m)}})
        r.raise_for_status()
        return r.json()["id"]

    def fetch_replies(self, since_iso: str | None = None) -> list[InboundEmail]:
        q = "in:inbox -from:me newer_than:14d"
        r = self.client.get(f"{self.BASE}/messages", headers=self._h(), params={"q": q, "maxResults": 50})
        r.raise_for_status()
        out = []
        for ref in r.json().get("messages", []):
            d = self.client.get(f"{self.BASE}/messages/{ref['id']}", headers=self._h(), params={"format": "full"}).json()
            hdr = {h["name"].lower(): h["value"] for h in d.get("payload", {}).get("headers", [])}
            body = _extract_text(d.get("payload", {}))
            frm = hdr.get("from", "")
            out.append(InboundEmail(provider_message_id=d["id"], thread_id=d.get("threadId"), from_addr=frm,
                                    subject=hdr.get("subject", ""), body=body,
                                    is_bounce="mailer-daemon" in frm.lower() or "postmaster" in frm.lower(),
                                    auto_submitted=hdr.get("auto-submitted", "no").lower() != "no"))
        return out


def _extract_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode(errors="replace")
    for p in payload.get("parts", []) or []:
        t = _extract_text(p)
        if t:
            return t
    return ""


class ZohoSMTPProvider:
    """Zoho Mail over SMTP (SSL 465) using a Zoho *app-specific password* from the environment.

    Credentials come only from ZOHO_SMTP_USER / ZOHO_APP_PASSWORD env vars (set them in your
    shell or secret manager, never in chat or code). Generate the app password in Zoho:
    My Account -> Security -> App Passwords. Region hosts: smtp.zoho.com (US), smtp.zoho.in (India),
    smtp.zoho.eu (EU); org accounts may need smtppro.zoho.*.
    """
    name = "zoho"

    def __init__(self, user: str, app_password: str, host: str = "smtp.zoho.in", port: int = 465,
                 from_name: str | None = None):
        self.user, self._pw, self.host, self.port, self.from_name = user, app_password, host, port, from_name

    def _build(self, m: OutboundEmail):
        from email.utils import formataddr, make_msgid
        em = EmailMessage()
        em["From"] = formataddr((self.from_name, self.user)) if self.from_name else self.user
        em["To"], em["Subject"] = m.to, m.subject
        em["Message-ID"] = make_msgid(idstring=m.idempotency_key[:40], domain=self.user.split("@")[-1])
        if m.in_reply_to:
            em["In-Reply-To"] = em["References"] = m.in_reply_to
        if m.list_unsubscribe:
            em["List-Unsubscribe"] = m.list_unsubscribe
        em.set_content(m.body)
        return em

    def send(self, m: OutboundEmail) -> SendResult:
        import smtplib
        import ssl
        em = self._build(m)
        try:
            with smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=30) as s:
                s.login(self.user, self._pw)
                refused = s.send_message(em)
        except smtplib.SMTPRecipientsRefused as e:
            raise SendError(f"recipient refused: {list(e.recipients)}", permanent=True) from None
        except smtplib.SMTPAuthenticationError:
            raise SendError("Zoho authentication failed (check app password / SMTP access)", permanent=True) from None
        except (smtplib.SMTPException, OSError) as e:
            raise SendError(f"zoho smtp error: {type(e).__name__}: {e}") from None
        if refused:
            raise SendError(f"recipient refused: {list(refused)}", permanent=True)
        return SendResult(provider_message_id=em["Message-ID"], thread_id=None)

    def create_draft(self, m: OutboundEmail) -> str:
        raise NotImplementedError("Drafts are kept in this app's queue; Zoho SMTP cannot create drafts.")

    def fetch_replies(self, since_iso: str | None = None) -> list[InboundEmail]:
        return []  # reply ingestion via Zoho IMAP not implemented yet; log replies manually in the dashboard
