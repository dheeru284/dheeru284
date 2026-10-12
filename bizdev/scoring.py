"""Lead qualification. Pure function + persistence wrapper.

Evidence confidence (how sure are we the opportunity is real) is kept separate
from commercial attractiveness (how valuable it is if real). A generic agency
with no active-requirement evidence cannot score on the 'evidence' axis.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .core import audit, get_rule, now_utc
from .models import Assessment, LeadStatus, Organization

ACTIVE_SIGNALS = {"hiring", "rfp", "contract_requirement", "staff_augmentation", "oic_project",
                  "data_platform", "cloud_migration", "analytics_modernization", "vendor_onboarding",
                  "subcontracting"}
CONTRACT_SIGNALS = {"rfp", "contract_requirement", "staff_augmentation", "vendor_onboarding", "subcontracting"}


@dataclass
class ScoreInput:
    evidence: list[dict]          # {signal_type, evidence_date, is_inference, remote_ok, matched_services}
    has_verified_decision_maker: bool
    has_any_verified_contact: bool
    country: str | None
    campaign: str                 # A_DUBAI | B_REMOTE
    today: date


def compute_score(inp: ScoreInput, weights: dict, tiers: dict) -> dict:
    fresh_cut = inp.today - timedelta(days=60)
    real = [e for e in inp.evidence if not e.get("is_inference")]
    active = [e for e in real if e["signal_type"] in ACTIVE_SIGNALS]
    recent_active = [e for e in active if e.get("evidence_date") and e["evidence_date"] >= fresh_cut]

    # 1. Evidence of a live requirement: full credit only for recent, sourced, non-inferred signals.
    ev = 1.0 if recent_active else (0.5 if active else (0.15 if inp.evidence else 0.0))
    # 2. Service match: distinct EpohTech services matched by evidence (3+ = full).
    services = {s for e in inp.evidence for s in (e.get("matched_services") or [])}
    sm = min(len(services), 3) / 3
    # 3. Offshore/remote: explicit True from sourced evidence beats inference.
    if any(e.get("remote_ok") is True for e in real):
        off = 1.0
    elif any(e.get("remote_ok") is True for e in inp.evidence):
        off = 0.5
    elif any(e.get("remote_ok") is False for e in real):
        off = 0.0
    else:
        off = 0.25
    # 4. Decision-maker access.
    dm = 1.0 if inp.has_verified_decision_maker else (0.4 if inp.has_any_verified_contact else 0.0)
    # 5. Geography/timing.
    uae = (inp.country or "").upper() in {"AE", "UAE", "UNITED ARAB EMIRATES"}
    if inp.campaign == "A_DUBAI":
        geo = 1.0 if uae else 0.3
    else:
        geo = 1.0 if off >= 0.5 else 0.4
    # 6. Contracting model.
    cm = 1.0 if any(e["signal_type"] in CONTRACT_SIGNALS for e in real) else (
        0.4 if any(e["signal_type"] in CONTRACT_SIGNALS for e in inp.evidence) else 0.0)

    parts = {"evidence": ev, "service_match": sm, "offshore": off, "decision_maker": dm,
             "geo_timing": geo, "contract_model": cm}
    breakdown = {k: round(parts[k] * weights.get(k, 0), 1) for k in parts}
    total_w = sum(weights.values()) or 1
    score = round(sum(breakdown.values()) * 100 / total_w)
    tier = "A" if score >= tiers["A"] else ("B" if score >= tiers["B"] else "C")
    conf = round(100 * (len(real) / len(inp.evidence))) if inp.evidence else 0
    conf = min(conf, 100 if recent_active else 60)
    commercial = round(100 * (0.5 * sm + 0.3 * cm + 0.2 * off))
    return {"score": score, "tier": tier, "breakdown": breakdown,
            "evidence_confidence": conf, "commercial_score": commercial}


def qualify(db: Session, org: Organization, campaign_code: str = "A_DUBAI", actor: str = "system") -> dict:
    inp = ScoreInput(
        evidence=[{"signal_type": e.signal_type, "evidence_date": e.evidence_date, "is_inference": e.is_inference,
                   "remote_ok": e.remote_ok, "matched_services": e.matched_services} for e in org.evidence],
        has_verified_decision_maker=any(c.verified and c.is_decision_maker for c in org.contacts),
        has_any_verified_contact=any(c.verified for c in org.contacts),
        country=org.country, campaign=campaign_code, today=now_utc().date())
    res = compute_score(inp, get_rule(db, "scoring.weights"), get_rule(db, "scoring.tiers"))
    org.score, org.tier = res["score"], res["tier"]
    org.evidence_confidence, org.commercial_score = res["evidence_confidence"], res["commercial_score"]
    if org.status == LeadStatus.DISCOVERED and res["tier"] in {"A", "B"}:
        org.status = LeadStatus.QUALIFIED
    db.add(Assessment(organization_id=org.id, **res))
    audit(db, actor, "lead.scored", "organization", org.id, score=res["score"], tier=res["tier"])
    return res
