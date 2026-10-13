"""Admin dashboard (server-rendered) + small JSON API.

Auth: HMAC-signed session cookie (HttpOnly, SameSite=Strict) + per-session CSRF
token on every POST. All state changes go through the domain modules, which
enforce the safety rules; the UI cannot bypass them.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import messaging, onboarding, outreach, remote, reports, scheduling
from ..config import get_settings
from ..core import audit, get_rule, now_utc, set_rule
from ..db import Base, engine, get_db
from ..discovery import CSVImportSource, run_source
from ..models import (Appointment, AuditLog, CompanyProfile, Contact, IntegrationAccount, Job, LeadStatus, Message,
                      MessageStatus, Opportunity, Organization, ServiceOffering, User)
from ..providers import registry
from ..security import encrypt_secret, hash_password, install_log_redaction, verify_password
from ..seed import seed_reference

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
COOKIE = "bizdev_session"
SESSION_TTL = 8 * 3600
EDITABLE_RULES = ["scoring.weights", "scoring.tiers", "limits.email", "limits.linkedin", "limits.per_company_days",
                  "limits.per_contact_days", "quiet_hours", "approval.policy", "approval.segments",
                  "followup.sequence", "followup.enabled", "campaign.dubai", "availability", "email.delivery"]



def _key() -> bytes:
    k = get_settings().secret_key
    if not k or len(k) < 32:
        raise RuntimeError("SECRET_KEY must be set (>=32 chars)")
    return k.encode()


def _sign(data: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    sig = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _unsign(tok: str | None) -> dict | None:
    if not tok or "." not in tok:
        return None
    raw, sig = tok.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()):
        return None
    data = json.loads(base64.urlsafe_b64decode(raw))
    return data if data.get("exp", 0) > time.time() else None


def current_user(request: Request) -> dict:
    s = _unsign(request.cookies.get(COOKIE))
    if not s:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return s


async def csrf(request: Request, user: dict = Depends(current_user)) -> dict:
    if request.method == "POST":
        form = await request.form()
        if not hmac.compare_digest(str(form.get("csrf", "")), user["csrf"]):
            raise HTTPException(403, "CSRF token invalid")
    return user


def page(request, name, user, **ctx):
    ctx.update(request=request, user=user, csrf=user["csrf"] if user else "", now=now_utc(),
               flash=request.query_params.get("flash"))
    gen = app.dependency_overrides.get(get_db, get_db)()  # banner must reflect real state on every page
    _db = next(gen) if hasattr(gen, "__next__") else gen
    try:
        ctx["halted"], ctx["live"] = outreach.halted(_db), outreach.live_sending_enabled(_db)
        ctx["delivery"] = get_rule(_db, "email.delivery")
    finally:
        if hasattr(gen, "__next__"):
            gen.close()
    return TEMPLATES.TemplateResponse(request, name, ctx)


def back(url: str, msg: str | None = None):
    return RedirectResponse(url + (("&" if "?" in url else "?") + urlencode({"flash": msg}) if msg else ""), 303)


_login_attempts: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(_app):
    startup()
    yield


def startup():
    install_log_redaction()
    Base.metadata.create_all(engine)  # dev convenience; production uses `alembic upgrade head`
    from ..db import SessionLocal
    with SessionLocal() as db:
        seed_reference(db)
        s = get_settings()
        if s.admin_password and not db.scalar(select(User).where(User.email == s.admin_email)):
            db.add(User(email=s.admin_email, password_hash=hash_password(s.admin_password)))
            db.commit()
        registry.configure_from_db(db)


app = FastAPI(title="EpohTech BizDev", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self' https://accounts.google.com; frame-ancestors 'none'"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


# ------------------------------------------------------------------ auth

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return TEMPLATES.TemplateResponse(request, "login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    hist = [t for t in _login_attempts.get(ip, []) if t > time.time() - 900]
    if len(hist) >= 10:
        raise HTTPException(429, "Too many login attempts")
    u = db.scalar(select(User).where(User.email == email.strip().lower(), User.is_active.is_(True)))
    if not u or not verify_password(password, u.password_hash):
        _login_attempts[ip] = hist + [time.time()]
        audit(db, email[:80], "auth.failed", level="warn"); db.commit()
        return TEMPLATES.TemplateResponse(request, "login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)
    audit(db, u.email, "auth.login"); db.commit()
    r = RedirectResponse("/", 303)
    r.set_cookie(COOKIE, _sign({"email": u.email, "csrf": secrets.token_urlsafe(24), "exp": time.time() + SESSION_TTL}),
                 httponly=True, samesite="strict", secure=get_settings().oauth_redirect_base.startswith("https"))
    return r


@app.post("/logout")
def logout(user=Depends(csrf)):
    r = RedirectResponse("/login", 303); r.delete_cookie(COOKIE); return r


# ------------------------------------------------------------------ overview & reports

@app.get("/", response_class=HTMLResponse)
def home(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    m = reports.overview(db)
    top = list(db.scalars(select(Organization).where(Organization.tier == "A").order_by(Organization.score.desc()).limit(10)))
    due = list(db.scalars(select(Organization).where(Organization.status.in_([LeadStatus.FOLLOW_UP_DUE, LeadStatus.NEEDS_REVIEW, LeadStatus.REPLIED]))))
    return page(request, "overview.html", user, m=m, top=top, due=due, halted=outreach.halted(db),
                live=outreach.live_sending_enabled(db), ob=onboarding.checklist(db))


@app.get("/api/metrics")
def api_metrics(user=Depends(current_user), db: Session = Depends(get_db)):
    return JSONResponse({"overview": reports.overview(db), "detail": reports.detailed(db)})


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    return page(request, "reports.html", user, m=reports.overview(db), d=reports.detailed(db))


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, user=Depends(current_user), db: Session = Depends(get_db), level: str = ""):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(300)
    if level:
        q = q.where(AuditLog.level == level)
    return page(request, "audit.html", user, rows=list(db.scalars(q)))


# ------------------------------------------------------------------ leads

@app.get("/leads", response_class=HTMLResponse)
def leads(request: Request, user=Depends(current_user), db: Session = Depends(get_db), q: str = "", tier: str = "",
          status: str = "", country: str = "", sort: str = "score"):
    stmt = select(Organization)
    if q:
        stmt = stmt.where(or_(Organization.name.ilike(f"%{q}%"), Organization.industry.ilike(f"%{q}%")))
    if tier:
        stmt = stmt.where(Organization.tier == tier)
    if status:
        stmt = stmt.where(Organization.status == LeadStatus(status))
    if country:
        stmt = stmt.where(Organization.country == country)
    order = {"score": Organization.score.desc(), "name": Organization.name, "recent": Organization.created_at.desc()}.get(sort, Organization.score.desc())
    return page(request, "leads.html", user, rows=list(db.scalars(stmt.order_by(order))), statuses=[s.value for s in LeadStatus],
                f={"q": q, "tier": tier, "status": status, "country": country, "sort": sort})


@app.get("/leads/{oid}", response_class=HTMLResponse)
def lead_detail(oid: int, request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, oid) or _404()
    msgs = list(db.scalars(select(Message).where(Message.organization_id == oid).order_by(Message.id.desc())))
    appts = list(db.scalars(select(Appointment).where(Appointment.organization_id == oid)))
    return page(request, "lead.html", user, o=org, msgs=msgs, appts=appts, statuses=[s.value for s in LeadStatus])


@app.post("/leads/{oid}/status")
def lead_status(oid: int, status: str = Form(...), user=Depends(csrf), db: Session = Depends(get_db)):
    org = db.get(Organization, oid) or _404()
    new = LeadStatus(status)
    org.status = new
    if new in (LeadStatus.DO_NOT_CONTACT, LeadStatus.UNSUBSCRIBED, LeadStatus.NOT_INTERESTED):
        for c in org.contacts:
            outreach.suppress(db, c, new.value.lower(), user["email"], new)
    audit(db, user["email"], "lead.status", "organization", oid, status=status); db.commit()
    return back(f"/leads/{oid}", "Status updated")


@app.post("/leads/{oid}/draft")
def lead_draft(oid: int, contact_id: int = Form(...), kind: str = Form("intro"), channel: str = Form("email"),
               campaign: str = Form("A_DUBAI"), user=Depends(csrf), db: Session = Depends(get_db)):
    org = db.get(Organization, oid) or _404()
    ok, missing = onboarding.can(db, "draft")
    if not ok:
        return back(f"/leads/{oid}", "Complete onboarding first: " + "; ".join(missing))
    c = db.get(Contact, contact_id)
    if outreach.is_suppressed(db, c):
        return back(f"/leads/{oid}", "Contact is suppressed")
    try:
        messaging.draft(db, org, c, kind=kind, channel=channel, campaign_code=campaign, actor=user["email"])
        db.commit()
    except messaging.GenerationBlocked as e:
        db.rollback(); return back(f"/leads/{oid}", str(e))
    return back("/queue", "Draft created — review it below")


@app.post("/import")
async def import_csv(file: UploadFile, campaign: str = Form("A_DUBAI"), user=Depends(csrf), db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        stats = run_source(db, CSVImportSource(text), campaign_code=campaign)
    except ValueError as e:
        return back("/leads", str(e))
    return back("/leads", f"Imported: {stats}")


# ------------------------------------------------------------------ outreach queue

@app.get("/queue", response_class=HTMLResponse)
def queue(request: Request, user=Depends(current_user), db: Session = Depends(get_db), status: str = ""):
    stmt = select(Message).where(Message.direction == "out").order_by(Message.id.desc())
    if status:
        stmt = stmt.where(Message.status == MessageStatus(status))
    rows = list(db.scalars(stmt.limit(200)))
    orgs = {o.id: o for o in db.scalars(select(Organization))}
    contacts = {c.id: c for c in db.scalars(select(Contact))}
    return page(request, "queue.html", user, rows=rows, orgs=orgs, contacts=contacts, statuses=[s.value for s in MessageStatus],
                live=outreach.live_sending_enabled(db), halted=outreach.halted(db), fstatus=status)


@app.post("/queue/save_all_drafts")
def queue_save_all(user=Depends(csrf), db: Session = Depends(get_db)):
    n = {}
    for m in list(db.scalars(select(Message).where(Message.status == MessageStatus.APPROVED, Message.channel == "email"))):
        st = outreach.dispatch(db, m, user["email"]).value
        n[st] = n.get(st, 0) + 1
        db.commit()
    return back("/queue", f"Results: {n}" if n else "No approved emails to save")


@app.post("/queue/{mid}/{action}")
def queue_action(mid: int, action: str, body: str = Form(None), subject: str = Form(None), reason: str = Form(""),
                 user=Depends(csrf), db: Session = Depends(get_db)):
    m = db.get(Message, mid) or _404()
    try:
        if action == "approve":
            outreach.approve(db, m, user["email"], edited_body=body, edited_subject=subject)
        elif action == "reject":
            outreach.reject(db, m, user["email"], reason)
        elif action == "dispatch":
            if m.status == MessageStatus.APPROVED:
                outreach.enqueue_dispatch(db, m)
                db.commit()
                outreach.run_due_jobs(db)
        elif action == "confirm_manual":
            outreach.confirm_manual_sent(db, m, user["email"])
        elif action == "acknowledge":
            outreach.mark_acknowledged(db, m, user["email"])
        else:
            _404()
        db.commit()
    except outreach.DispatchBlocked as e:
        db.rollback(); return back("/queue", str(e))
    return back("/queue", f"{action}: {db.get(Message, mid).status.value}")


@app.post("/inbox/poll")
def inbox_poll(user=Depends(csrf), db: Session = Depends(get_db)):
    try:
        n = outreach.poll_inbox(db)
    except Exception as e:  # noqa: BLE001
        audit(db, user["email"], "inbox.poll_failed", error=str(e), level="error"); db.commit()
        return back("/queue", f"Inbox poll failed: {e}")
    return back("/queue", f"{n} new replies processed")


@app.post("/worker/run")
def worker_run(user=Depends(csrf), db: Session = Depends(get_db)):
    return back("/", f"Jobs: {outreach.run_due_jobs(db)}")


# ------------------------------------------------------------------ appointments

@app.get("/appointments", response_class=HTMLResponse)
def appointments(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Appointment).order_by(Appointment.start_utc.is_(None), Appointment.start_utc)))
    orgs = {o.id: o for o in db.scalars(select(Organization))}
    return page(request, "appointments.html", user, rows=rows, orgs=orgs, to_local=scheduling.to_local,
                avail=scheduling.availability_status(db), fromiso=datetime.fromisoformat)


@app.post("/leads/{oid}/propose")
def propose(oid: int, fmt: str = Form("remote"), contact_id: int = Form(None), user=Depends(csrf), db: Session = Depends(get_db)):
    org = db.get(Organization, oid) or _404()
    try:
        scheduling.create_proposal(db, org, db.get(Contact, contact_id) if contact_id else None, fmt, user["email"])
        db.commit()
    except scheduling.SchedulingError as e:
        db.rollback(); return back(f"/leads/{oid}", str(e))
    return back("/appointments", "Slots proposed (send them to the prospect via a drafted reply)")


@app.post("/appointments/{aid}/confirm")
def appt_confirm(aid: int, slot: str = Form(...), prospect_agreed: str = Form(""), location: str = Form(""),
                 meeting_link: str = Form(""), user=Depends(csrf), db: Session = Depends(get_db)):
    a = db.get(Appointment, aid) or _404()
    c = db.get(Contact, a.contact_id) if a.contact_id else None
    try:
        scheduling.confirm(db, a, datetime.fromisoformat(slot), user["email"], prospect_agreed=prospect_agreed == "yes",
                           location=location or None, meeting_link=meeting_link or None,
                           attendee_email=c.email if c else None)
        if c:
            try:
                messaging.draft(db, db.get(Organization, a.organization_id), c, kind="meeting_confirm",
                                extra=scheduling.meeting_ctx(a), actor=user["email"])
            except messaging.GenerationBlocked:
                pass
        db.commit()
    except scheduling.SchedulingError as e:
        db.rollback(); return back("/appointments", str(e))
    return back("/appointments", "Confirmed; confirmation email drafted for approval")


@app.post("/appointments/{aid}/{action}")
def appt_action(aid: int, action: str, outcome: str = Form(""), next_action: str = Form(""), attended: str = Form(""),
                user=Depends(csrf), db: Session = Depends(get_db)):
    a = db.get(Appointment, aid) or _404()
    if action == "cancel":
        scheduling.cancel(db, a, user["email"])
    elif action == "outcome":
        scheduling.record_outcome(db, a, user["email"], attended == "yes", outcome, next_action)
    else:
        _404()
    db.commit()
    return back("/appointments", action)


# ------------------------------------------------------------------ remote opportunities

@app.get("/remote", response_class=HTMLResponse)
def remote_page(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Opportunity).order_by(Opportunity.score.desc())))
    return page(request, "remote.html", user, rows=rows, deadlines=remote.upcoming_deadlines(db))


@app.post("/remote/add")
def remote_add(title: str = Form(...), source_url: str = Form(...), text: str = Form(...), contract_type: str = Form(""),
               currency: str = Form(""), comp_min: str = Form(""), comp_max: str = Form(""), period: str = Form(""),
               deadline: str = Form(""), user=Depends(csrf), db: Session = Depends(get_db)):
    from datetime import date
    try:
        remote.add_opportunity(db, title=title, source_url=source_url, text=text, actor=user["email"],
                               contract_type=contract_type or None, currency=(currency or None) and currency.upper()[:3],
                               compensation_min=float(comp_min) if comp_min else None,
                               compensation_max=float(comp_max) if comp_max else None,
                               compensation_period=period or None,
                               deadline=date.fromisoformat(deadline) if deadline else None,
                               evidence_date=now_utc().date())
        db.commit()
    except ValueError as e:
        db.rollback(); return back("/remote", str(e))
    return back("/remote", "Added")


@app.post("/remote/{oid}/{action}")
def remote_action(oid: int, action: str, notes: str = Form(""), user=Depends(csrf), db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid) or _404()
    try:
        if action == "authorize":
            remote.authorize_application(db, o, user["email"])
        elif action == "applied":
            remote.mark_applied(db, o, user["email"], notes)
        elif action == "reject":
            o.status = "REJECTED"
        db.commit()
    except PermissionError as e:
        db.rollback(); return back("/remote", str(e))
    return back("/remote", action)


# ------------------------------------------------------------------ settings & onboarding

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    rules = {k: json.dumps(get_rule(db, k), indent=1) for k in EDITABLE_RULES}
    integ = list(db.scalars(select(IntegrationAccount)))
    services = list(db.scalars(select(ServiceOffering).order_by(ServiceOffering.category, ServiceOffering.title)))
    jobs = list(db.scalars(select(Job).where(Job.status.in_(["PENDING", "DEAD"])).order_by(Job.run_at).limit(50)))
    zoho = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "zoho"))
    zcfg = {}
    if zoho and zoho.encrypted_token:
        from ..security import decrypt_secret
        zcfg = {k: v for k, v in json.loads(decrypt_secret(zoho.encrypted_token)).items() if k != "app_password"}
    return page(request, "settings.html", user, zoho=zoho, zcfg=zcfg, zoho_hosts=ZOHO_HOSTS, rules=rules, integ=integ, services=services, jobs=jobs,
                s=get_settings(), halted=outreach.halted(db), live=outreach.live_sending_enabled(db),
                live_auth=get_rule(db, "system.live_send_authorized"), li=registry.linkedin.caps)


@app.post("/settings/rule")
def settings_rule(key: str = Form(...), value: str = Form(...), user=Depends(csrf), db: Session = Depends(get_db)):
    if key not in EDITABLE_RULES:
        raise HTTPException(400, "not editable")
    try:
        v = json.loads(value)
    except json.JSONDecodeError as e:
        return back("/settings", f"Invalid JSON for {key}: {e}")
    if key == "approval.policy" and v not in ("manual_every_message", "approve_new_contact", "approved_segments"):
        return back("/settings", "Unknown approval policy")
    set_rule(db, key, v, user["email"]); db.commit()
    return back("/settings", f"Saved {key}")


@app.post("/settings/control")
def settings_control(action: str = Form(...), confirm: str = Form(""), user=Depends(csrf), db: Session = Depends(get_db)):
    if action == "stop":
        outreach.emergency_stop(db, user["email"], True)
    elif action == "resume":
        outreach.emergency_stop(db, user["email"], False)
    elif action in ("pause", "unpause"):
        set_rule(db, "system.paused", action == "pause", user["email"])
    elif action == "authorize_live":
        if confirm != "I AUTHORIZE LIVE SENDING":
            return back("/settings", "Type the confirmation phrase exactly to authorize live sending")
        ok, missing = onboarding.can(db, "send_email")
        if not get_settings().allow_live_send:
            return back("/settings", "ALLOW_LIVE_SEND is false in the deployment environment")
        set_rule(db, "system.live_send_authorized", True, user["email"])
        audit(db, user["email"], "system.live_send_authorized", level="warn", outstanding=missing)
    elif action == "revoke_live":
        set_rule(db, "system.live_send_authorized", False, user["email"])
    db.commit()
    return back("/settings", action)


@app.post("/settings/service")
def settings_service(category: str = Form(...), title: str = Form(...), keywords: str = Form(""),
                     user=Depends(csrf), db: Session = Depends(get_db)):
    db.add(ServiceOffering(category=category.strip(), title=title.strip(),
                           keywords=[k.strip() for k in keywords.split(",") if k.strip()]))
    audit(db, user["email"], "service.added", title=title); db.commit()
    return back("/settings", "Service added")


@app.post("/settings/zoho")
def settings_zoho(email: str = Form(...), from_name: str = Form(""), host: str = Form("smtp.zoho.in"),
                  app_password: str = Form(""), user=Depends(csrf), db: Session = Depends(get_db)):
    """Save Zoho SMTP credentials. The app password is encrypted at rest and never shown again."""
    if host not in ZOHO_HOSTS:
        return back("/settings", "Unknown Zoho SMTP host")
    acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "zoho")) or IntegrationAccount(provider="zoho")
    old = {}
    if acct.encrypted_token:
        from ..security import decrypt_secret
        old = json.loads(decrypt_secret(acct.encrypted_token))
    pw = app_password.strip() or old.get("app_password")
    if not pw:
        return back("/settings", "Enter the Zoho app-specific password")
    acct.account_email = email.strip().lower()
    acct.encrypted_token = encrypt_secret(json.dumps({"app_password": pw, "host": host, "from_name": from_name.strip()}))
    acct.status, acct.scopes = "connected", ["smtp"]
    db.add(acct)
    audit(db, user["email"], "zoho.saved", account=acct.account_email, host=host)
    db.commit()
    registry.configure_from_db(db)
    return back("/settings", "Zoho saved — now send a test email")


@app.post("/settings/zoho/test")
def settings_zoho_test(to: str = Form(...), user=Depends(csrf), db: Session = Depends(get_db)):
    """Send docs/outreach/TEST_EMAIL.txt to ONE address the admin typed. Allowed in dry-run: it is a self-test."""
    from ..integrations.email import OutboundEmail, SendError
    from ..providers import zoho_provider_from_account
    acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "zoho"))
    if not acct or not acct.encrypted_token:
        return back("/settings", "Save Zoho settings first")
    raw = (Path(__file__).resolve().parents[2] / "docs/outreach/TEST_EMAIL.txt").read_text(encoding="utf-8")
    head, _, body = raw.partition("\n\n")
    try:
        res = zoho_provider_from_account(acct).send(OutboundEmail(
            to=to.strip(), subject=head.removeprefix("Subject: ").strip(), body=body, from_addr=acct.account_email,
            idempotency_key=f"selftest-{int(time.time())}"))
    except SendError as e:
        audit(db, user["email"], "zoho.test_failed", level="error", error=str(e)); db.commit()
        return back("/settings", f"Test FAILED: {e}")
    audit(db, user["email"], "zoho.test_sent", to=to.strip(), message_id=res.provider_message_id); db.commit()
    return back("/settings", f"Zoho accepted the test email to {to.strip()}. Check that inbox (and spam).")


@app.post("/settings/linkedin")
def settings_linkedin(partner_messaging: str = Form(""), evidence: str = Form(""), user=Depends(csrf), db: Session = Depends(get_db)):
    acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "linkedin")) or IntegrationAccount(provider="linkedin")
    want = partner_messaging == "yes"
    if want and len(evidence.strip()) < 10:
        return back("/settings", "Record the partner agreement reference before enabling partner messaging")
    acct.capabilities = {**(acct.capabilities or {}), "partner_messaging": want, "evidence": evidence[:500]}
    db.add(acct); audit(db, user["email"], "linkedin.capabilities", **acct.capabilities); db.commit()
    registry.configure_from_db(db)
    return back("/settings", "LinkedIn capabilities saved")


@app.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    return page(request, "onboarding.html", user, p=db.scalar(select(CompanyProfile)), ob=onboarding.checklist(db))


@app.post("/onboarding")
async def onboarding_save(request: Request, user=Depends(csrf), db: Session = Depends(get_db)):
    form = await request.form()
    p = db.scalar(select(CompanyProfile))
    for f in ("website", "description", "sender_name", "sender_title", "sender_email", "sender_phone",
              "postal_address", "delivery_capacity"):
        v = str(form.get(f, "")).strip()
        setattr(p, f, v or None)
    for f in ("certifications", "case_studies", "target_countries", "target_industries"):
        setattr(p, f, [x.strip() for x in str(form.get(f, "")).splitlines() if x.strip()])
    p.verified_facts = [{"fact": x.strip(), "verified": True} for x in str(form.get("verified_facts", "")).splitlines() if x.strip()]
    try:
        p.min_rates = json.loads(str(form.get("min_rates") or "{}"))
    except json.JSONDecodeError:
        return back("/onboarding", "min_rates must be JSON, e.g. {\"USD/hour\": 30}")
    if form.get("travel_confirmed") == "yes":
        cfg = get_rule(db, "campaign.dubai")
        for k in ("travel_date", "window_start", "window_end"):
            if form.get(k):
                cfg[k] = str(form.get(k))
        cfg["confirmed_by_admin"] = True
        set_rule(db, "campaign.dubai", cfg, user["email"])
    audit(db, user["email"], "profile.updated"); db.commit()
    return back("/onboarding", "Saved")


# ------------------------------------------------------------------ Google OAuth

ZOHO_HOSTS = ["smtp.zoho.in", "smtp.zoho.com", "smtp.zoho.eu", "smtppro.zoho.in", "smtppro.zoho.com", "smtppro.zoho.eu"]

GOOGLE_SCOPES = ["openid", "email", "https://www.googleapis.com/auth/gmail.send",
                 "https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.readonly",
                 "https://www.googleapis.com/auth/calendar.freebusy", "https://www.googleapis.com/auth/calendar.events"]


@app.get("/oauth/google/start")
def google_start(user=Depends(current_user)):
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(400, "GOOGLE_CLIENT_ID not configured")
    state = _sign({"u": user["email"], "exp": time.time() + 600, "n": secrets.token_hex(8)})
    q = urlencode({"client_id": s.google_client_id, "redirect_uri": s.oauth_redirect_base + "/oauth/google/callback",
                   "response_type": "code", "scope": " ".join(GOOGLE_SCOPES), "access_type": "offline",
                   "prompt": "consent", "state": state})
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + q, 303)


@app.get("/oauth/google/callback")
def google_callback(code: str, state: str, user=Depends(current_user), db: Session = Depends(get_db)):
    st = _unsign(state)
    if not st or st["u"] != user["email"]:
        raise HTTPException(400, "bad state")
    s = get_settings()
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": s.google_client_id, "client_secret": s.google_client_secret,
        "redirect_uri": s.oauth_redirect_base + "/oauth/google/callback", "grant_type": "authorization_code"}, timeout=20)
    if r.status_code != 200:
        audit(db, user["email"], "oauth.google_failed", level="error", status=r.status_code); db.commit()
        raise HTTPException(400, "token exchange failed")
    j = r.json()
    tok = {"access_token": j["access_token"], "refresh_token": j.get("refresh_token"),
           "expires_at": time.time() + j.get("expires_in", 3600)}
    acct = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "google")) or IntegrationAccount(provider="google")
    acct.encrypted_token, acct.scopes, acct.status = encrypt_secret(json.dumps(tok)), j.get("scope", "").split(), "connected"
    db.add(acct); audit(db, user["email"], "oauth.google_connected", scopes=acct.scopes); db.commit()
    registry.configure_from_db(db)
    return back("/settings", "Google connected")


def _404():
    raise HTTPException(404)
