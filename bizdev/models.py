"""Data model. Every table has timestamps; dedup is enforced with unique keys."""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # stored as naive UTC


class TS:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class LeadStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"; QUALIFIED = "QUALIFIED"; MESSAGE_DRAFTED = "MESSAGE_DRAFTED"
    APPROVED = "APPROVED"; SENT = "SENT"; REPLIED = "REPLIED"; MEETING_PROPOSED = "MEETING_PROPOSED"
    MEETING_BOOKED = "MEETING_BOOKED"; COMPLETED = "COMPLETED"; NEEDS_REVIEW = "NEEDS_REVIEW"
    BOUNCED = "BOUNCED"; FOLLOW_UP_DUE = "FOLLOW_UP_DUE"; NOT_INTERESTED = "NOT_INTERESTED"
    UNSUBSCRIBED = "UNSUBSCRIBED"; DO_NOT_CONTACT = "DO_NOT_CONTACT"; CLOSED = "CLOSED"; FAILED = "FAILED"


class MessageStatus(str, enum.Enum):
    DRAFTED = "DRAFTED"; APPROVED = "APPROVED"; REJECTED = "REJECTED"
    QUEUED = "QUEUED"                      # waiting for dispatch (email) or manual send (LinkedIn)
    MANUAL_PENDING = "MANUAL_PENDING"      # admin must send by hand; not yet confirmed
    SENT = "SENT"; DRY_RUN = "DRY_RUN"; ACKNOWLEDGED = "ACKNOWLEDGED"
    BOUNCED = "BOUNCED"; FAILED = "FAILED"; SUPPRESSED = "SUPPRESSED"; CANCELLED = "CANCELLED"


class User(Base, TS):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CompanyProfile(Base, TS):
    """EpohTech's own verified profile. Only `verified` facts may appear in outreach."""
    __tablename__ = "company_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="EpohTech Private Limited")
    website: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    sender_name: Mapped[str | None] = mapped_column(String(255))
    sender_title: Mapped[str | None] = mapped_column(String(255))
    sender_email: Mapped[str | None] = mapped_column(String(255))
    sender_phone: Mapped[str | None] = mapped_column(String(64))
    postal_address: Mapped[str | None] = mapped_column(Text)  # anti-spam laws often require one
    verified_facts: Mapped[list] = mapped_column(JSON, default=list)  # [{"fact":..., "verified":bool}]
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    case_studies: Mapped[list] = mapped_column(JSON, default=list)
    delivery_capacity: Mapped[str | None] = mapped_column(Text)
    min_rates: Mapped[dict] = mapped_column(JSON, default=dict)
    target_countries: Mapped[list] = mapped_column(JSON, default=list)
    target_industries: Mapped[list] = mapped_column(JSON, default=list)
    onboarding: Mapped[dict] = mapped_column(JSON, default=dict)


class ServiceOffering(Base, TS):
    __tablename__ = "service_offerings"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(128))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("category", "title"),)


class Organization(Base, TS):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)  # dedup key
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128))
    timezone: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(64))  # consulting|staffing_agency|end_client|freelance_platform|...
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.DISCOVERED, index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    tier: Mapped[str] = mapped_column(String(1), default="C", index=True)
    evidence_confidence: Mapped[int] = mapped_column(Integer, default=0)
    commercial_score: Mapped[int] = mapped_column(Integer, default=0)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_action: Mapped[str | None] = mapped_column(Text)
    contacts = relationship("Contact", back_populates="organization", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="organization", cascade="all, delete-orphan")


class Contact(Base, TS):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)  # lower-cased, dedup key
    linkedin_url: Mapped[str | None] = mapped_column(String(512), unique=True)
    timezone: Mapped[str | None] = mapped_column(String(64))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # identity+role confirmed by a source
    source_url: Mapped[str | None] = mapped_column(String(1024))
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_for_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    organization = relationship("Organization", back_populates="contacts")


class Evidence(Base, TS):
    """A sourced signal. `is_inference` marks things we concluded rather than read."""
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(1024))
    signal_type: Mapped[str] = mapped_column(String(64))  # hiring|rfp|oic_project|cloud_migration|...
    summary: Mapped[str] = mapped_column(Text)
    raw_excerpt: Mapped[str | None] = mapped_column(Text)  # untrusted; never fed to LLM unfenced
    evidence_date: Mapped[date | None] = mapped_column(Date)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_inference: Mapped[bool] = mapped_column(Boolean, default=False)
    remote_ok: Mapped[bool | None] = mapped_column(Boolean)
    matched_services: Mapped[list] = mapped_column(JSON, default=list)
    organization = relationship("Organization", back_populates="evidence")
    __table_args__ = (UniqueConstraint("organization_id", "source_url", "signal_type"),)


class Opportunity(Base, TS):
    """Job posting / project / remote contract (Campaign B pipeline)."""
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    title: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    contract_type: Mapped[str | None] = mapped_column(String(64))
    remote_eligibility: Mapped[str] = mapped_column(String(32), default="unknown")  # india_ok|global|restricted|onsite|unknown
    country_restrictions: Mapped[str | None] = mapped_column(String(255))
    timezone_requirements: Mapped[str | None] = mapped_column(String(255))
    compensation_min: Mapped[float | None] = mapped_column(Float)   # only if published
    compensation_max: Mapped[float | None] = mapped_column(Float)
    compensation_period: Mapped[str | None] = mapped_column(String(16))  # hour|day|month|year
    currency: Mapped[str | None] = mapped_column(String(3))
    duration: Mapped[str | None] = mapped_column(String(64))
    deadline: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(1024), unique=True)
    application_method: Mapped[str | None] = mapped_column(String(255))
    evidence_date: Mapped[date | None] = mapped_column(Date)
    score: Mapped[int] = mapped_column(Integer, default=0)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="NEW")  # NEW|SHORTLISTED|APPLY_APPROVED|APPLIED|REJECTED|CLOSED
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Application(Base, TS):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    authorized_by: Mapped[str | None] = mapped_column(String(255))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)


class Assessment(Base, TS):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(1))
    breakdown: Mapped[dict] = mapped_column(JSON)
    evidence_confidence: Mapped[int] = mapped_column(Integer)
    commercial_score: Mapped[int] = mapped_column(Integer)


class Campaign(Base, TS):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # A_DUBAI | B_REMOTE
    name: Mapped[str] = mapped_column(String(255))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Thread(Base, TS):
    __tablename__ = "threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    provider_thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    state: Mapped[str] = mapped_column(String(32), default="OPEN")  # OPEN|ACTIVE_DISCUSSION|CLOSED
    last_classification: Mapped[str | None] = mapped_column(String(32))


class Message(Base, TS):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), index=True)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))
    direction: Mapped[str] = mapped_column(String(8), default="out")  # out|in
    channel: Mapped[str] = mapped_column(String(16))  # email|linkedin
    kind: Mapped[str] = mapped_column(String(32))  # intro|followup_brief|...|reply
    template_key: Mapped[str | None] = mapped_column(String(64))
    variant: Mapped[str | None] = mapped_column(String(8))
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    facts_used: Mapped[list] = mapped_column(JSON, default=list)  # evidence ids referenced
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.DRAFTED, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(String(32))
    __table_args__ = (Index("ix_msg_contact_status", "contact_id", "status"),)


class Suppression(Base, TS):
    __tablename__ = "suppressions"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # email|domain|linkedin
    value: Mapped[str] = mapped_column(String(512))
    reason: Mapped[str] = mapped_column(String(64))  # opt_out|bounce|not_interested|manual|do_not_contact
    source: Mapped[str | None] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("kind", "value"),)


class Consent(Base, TS):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    basis: Mapped[str] = mapped_column(String(64))  # legitimate_interest_b2b|explicit_opt_in|existing_relationship
    channel: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)


class Job(Base, TS):
    """DB-backed job queue (follow-ups, dispatch, reminders). Dead letters stay with status DEAD."""
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    run_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)  # PENDING|DONE|FAILED|DEAD|CANCELLED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class Appointment(Base, TS):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))
    status: Mapped[str] = mapped_column(String(16), default="PROPOSED")  # PROPOSED|CONFIRMED|RESCHEDULED|CANCELLED|COMPLETED|NO_SHOW
    format: Mapped[str] = mapped_column(String(16), default="remote")  # in_person|remote
    proposed_slots: Mapped[list] = mapped_column(JSON, default=list)  # ISO UTC strings
    start_utc: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    end_utc: Mapped[datetime | None] = mapped_column(DateTime)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dubai")
    location: Mapped[str | None] = mapped_column(String(512))
    location_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    meeting_link: Mapped[str | None] = mapped_column(String(512))
    agenda: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    attended: Mapped[bool | None] = mapped_column(Boolean)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255))


class CalendarEvent(Base, TS):
    """Busy blocks pulled from the connected calendar (or added manually)."""
    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    start_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))


class IntegrationAccount(Base, TS):
    __tablename__ = "integration_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), unique=True)  # gmail|outlook|gcal|linkedin|apollo
    account_email: Mapped[str | None] = mapped_column(String(255))
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    encrypted_token: Mapped[str | None] = mapped_column(Text)  # Fernet ciphertext only
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="disconnected")


class AutomationRule(Base, TS):
    __tablename__ = "automation_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[object] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    level: Mapped[str] = mapped_column(String(8), default="info")
