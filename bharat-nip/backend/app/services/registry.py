"""Source registry (PRODUCT_REQUIREMENTS.md FR-3).

Not a true/false publisher list. An entry records what kind of source an origin is,
its jurisdiction, and the scope within which it is authoritative. Authority only counts
while the entry is VERIFIED, its review has not expired, and the claim falls within the
declared scope. Every change is audited with a rationale.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import ActorType, AuthorityLevel, RegistryVerificationStatus
from app.domain.text import terms
from app.models import RegistrySource, User
from app.services.errors import Conflict, NotFound, Unprocessable

DEFAULT_REVIEW_PERIOD = timedelta(days=365)
_DOWNGRADE = {
    AuthorityLevel.PRIMARY_AUTHORITY: AuthorityLevel.GENERAL,
    AuthorityLevel.ESTABLISHED: AuthorityLevel.GENERAL,
}


def normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    host = urlsplit(value).hostname if "://" in value else value.split("/")[0]
    host = (host or "").lower().strip(".")
    return host.removeprefix("www.") or None


def find_entry_for_url(session: Session, url: str | None) -> RegistrySource | None:
    """Match on the host and then each parent domain (pib.gov.in -> gov.in is NOT tried:
    we stop before the public suffix by requiring at least two labels)."""
    host = normalize_domain(url)
    if not host:
        return None
    labels = host.split(".")
    candidates = [".".join(labels[i:]) for i in range(len(labels) - 1)]
    rows = session.scalars(
        select(RegistrySource).where(RegistrySource.domain.in_(candidates))
    ).all()
    by_domain = {r.domain: r for r in rows}
    for c in candidates:  # most specific first
        if c in by_domain:
            return by_domain[c]
    return None


@dataclass(frozen=True)
class EffectiveAuthority:
    level: AuthorityLevel
    basis: str


def effective_authority(
    entry: RegistrySource | None, claim_text: str, now: datetime | None = None
) -> EffectiveAuthority:
    now = now or datetime.now(UTC)
    if entry is None:
        return EffectiveAuthority(AuthorityLevel.UNASSESSED, "origin not in registry")
    if entry.verification_status != RegistryVerificationStatus.VERIFIED:
        return EffectiveAuthority(
            AuthorityLevel.UNASSESSED, f"registry entry {entry.verification_status.value}"
        )
    if entry.review_due_at is None or entry.review_due_at <= now:
        return EffectiveAuthority(AuthorityLevel.UNASSESSED, "registry review expired")
    level = entry.authority_level
    if entry.authority_scope and level in _DOWNGRADE:
        claim_terms = terms(claim_text)
        scope_terms = set().union(*(terms(s) for s in entry.authority_scope))
        if not claim_terms & scope_terms:
            return EffectiveAuthority(
                _DOWNGRADE[level], f"{level.value} outside declared scope {entry.authority_scope}"
            )
    return EffectiveAuthority(level, f"{level.value} (verified, in scope)")


def _audit(session: Session, user: User, action: str, entry: RegistrySource, payload: dict):
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action=action,
        entity_type="registry_source",
        entity_id=entry.id,
        payload=payload,
    )


def _snapshot(entry: RegistrySource) -> dict[str, Any]:
    return {
        "name": entry.name,
        "domain": entry.domain,
        "category": entry.category.value,
        "jurisdiction": entry.jurisdiction,
        "authority_level": entry.authority_level.value,
        "authority_scope": entry.authority_scope,
        "authority_rationale": entry.authority_rationale,
        "default_source_type": entry.default_source_type.value,
        "is_primary_source": entry.is_primary_source,
        "verification_status": entry.verification_status.value,
    }


EDITABLE = {
    "name",
    "domain",
    "category",
    "jurisdiction",
    "authority_level",
    "authority_scope",
    "authority_rationale",
    "default_source_type",
    "is_primary_source",
}


def _validate(entry: RegistrySource) -> None:
    if entry.authority_level != AuthorityLevel.UNASSESSED and not (
        entry.authority_rationale and entry.authority_rationale.strip()
    ):
        raise Unprocessable("authority_rationale is required when authority_level is set.")


def create_entry(session: Session, user: User, data: dict[str, Any]) -> RegistrySource:
    data = {k: v for k, v in data.items() if k in EDITABLE}
    data["domain"] = normalize_domain(data.get("domain"))
    if data["domain"] and session.scalar(
        select(RegistrySource).where(RegistrySource.domain == data["domain"])
    ):
        raise Conflict(f"A registry entry for {data['domain']} already exists.")
    entry = RegistrySource(**data, created_by_id=user.id)
    _validate(entry)
    session.add(entry)
    session.flush()
    _audit(session, user, "registry.created", entry, _snapshot(entry))
    return entry


def update_entry(
    session: Session, user: User, entry_id: uuid.UUID, data: dict[str, Any]
) -> RegistrySource:
    entry = session.get(RegistrySource, entry_id)
    if entry is None:
        raise NotFound("Registry entry not found.")
    before = _snapshot(entry)
    for key, value in data.items():
        if key in EDITABLE:
            setattr(entry, key, normalize_domain(value) if key == "domain" else value)
    _validate(entry)
    # Any substantive change invalidates a previous verification.
    if entry.verification_status == RegistryVerificationStatus.VERIFIED and before != _snapshot(
        entry
    ):
        entry.verification_status = RegistryVerificationStatus.UNVERIFIED
    session.flush()
    _audit(session, user, "registry.updated", entry, {"before": before, "after": _snapshot(entry)})
    return entry


def set_verification(
    session: Session,
    user: User,
    entry_id: uuid.UUID,
    *,
    status: RegistryVerificationStatus,
    method: str,
    notes: str | None,
    review_period_days: int | None = None,
) -> RegistrySource:
    entry = session.get(RegistrySource, entry_id)
    if entry is None:
        raise NotFound("Registry entry not found.")
    if not method.strip():
        raise Unprocessable("verification_method is required.")
    now = datetime.now(UTC)
    entry.verification_status = status
    entry.verification_method = method
    entry.verification_notes = notes
    entry.verified_by_id = user.id
    entry.verified_at = now
    period = timedelta(days=review_period_days) if review_period_days else DEFAULT_REVIEW_PERIOD
    entry.review_due_at = now + period
    session.flush()
    _audit(
        session,
        user,
        "registry.verification_set",
        entry,
        {
            "status": status.value,
            "method": method,
            "notes": notes,
            "review_due_at": entry.review_due_at.isoformat(),
        },
    )
    return entry
