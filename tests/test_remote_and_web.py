import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from bizdev import remote
from bizdev.models import Opportunity


def test_remote_eligibility_and_no_invented_comp(db):
    o = remote.add_opportunity(db, title="DE", source_url="https://example.com/r1",
                               text="Contract Databricks data engineer. Remote, India-based contractors welcome.",
                               contract_type="contract")
    assert o.remote_eligibility == "india_ok" and o.compensation_min is None and o.currency is None
    r = remote.add_opportunity(db, title="OIC", source_url="https://example.com/r2",
                               text="OIC developer, remote, US only, must have work authorization.")
    assert r.remote_eligibility == "restricted" and "country_or_work_authorization_restriction" in r.flags
    assert o.score > r.score
    assert remote.add_opportunity(db, title="dup", source_url="https://example.com/r1", text="x").id == o.id


def test_application_requires_authorization(db):
    o = remote.add_opportunity(db, title="x", source_url="https://example.com/r3", text="remote worldwide")
    with pytest.raises(PermissionError):
        remote.mark_applied(db, o, "admin")
    remote.authorize_application(db, o, "admin")
    assert remote.mark_applied(db, o, "admin").status == "SUBMITTED"


def test_seed_is_labelled_synthetic(db):
    from bizdev.seed import seed_synthetic
    from bizdev.models import Organization
    seed_synthetic(db)
    for o in db.query(Organization):
        assert o.is_synthetic and o.name.startswith("[SYNTHETIC]") and o.website.endswith(".example")
    assert all(x.is_synthetic for x in db.query(Opportunity))


@pytest.fixture
def client(db, monkeypatch):
    """End-to-end through the HTTP layer, sharing the test DB."""
    from bizdev.db import get_db
    from bizdev.models import User
    from bizdev.security import hash_password
    from bizdev.web.app import app
    db.add(User(email="admin@test.example", password_hash=hash_password("correct horse battery")))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr("bizdev.web.app.startup", lambda: None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(c):
    r = c.post("/login", data={"email": "admin@test.example", "password": "correct horse battery"}, follow_redirects=False)
    assert r.status_code == 303
    page = c.get("/settings").text
    return re.search(r'name="csrf" value="([^"]+)"', page).group(1)


def test_e2e_auth_required(client):
    r = client.get("/leads", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert client.post("/login", data={"email": "admin@test.example", "password": "nope"}).status_code == 401


def test_e2e_csrf_enforced(client):
    _login(client)
    assert client.post("/settings/control", data={"action": "stop", "csrf": "wrong"}).status_code == 403


def test_e2e_import_draft_approve_dispatch_dry_run(client, db):
    from bizdev.providers import registry
    csrf = _login(client)
    csv = ("company_name,source_url,signal_type,summary,website,country,category,evidence_date,remote_ok,"
           "contact_name,contact_role,contact_email,contact_verified\n"
           "Acme FZ-LLC,https://example.com/acme,hiring,Hiring contract Data Engineer (Databricks),https://acme.example,"
           "AE,consulting,2026-10-10,true,Jane Doe,Head of Data,jane@acme.example,true\n")
    r = client.post("/import", data={"csrf": csrf, "campaign": "A_DUBAI"}, files={"file": ("l.csv", csv, "text/csv")})
    assert r.status_code == 200 and "Acme FZ-LLC" in client.get("/leads").text
    from bizdev.models import Message, Organization
    org = db.query(Organization).one()
    client.post(f"/leads/{org.id}/draft", data={"csrf": csrf, "contact_id": org.contacts[0].id, "kind": "intro",
                                                "channel": "email", "campaign": "A_DUBAI"})
    m = db.query(Message).one()
    assert m.status.value == "DRAFTED"
    client.post(f"/queue/{m.id}/approve", data={"csrf": csrf, "body": m.body + "\n", "subject": m.subject})
    client.post(f"/queue/{m.id}/dispatch", data={"csrf": csrf})
    db.refresh(m)
    assert m.status.value == "DRY_RUN" and registry.email.sent == []
    assert "Dry-run mode" in client.get("/").text
    assert client.get("/api/metrics").json()["overview"]["dry_run"] == 1


def test_e2e_live_authorization_needs_env_flag(client, db):
    from bizdev.core import get_rule
    csrf = _login(client)
    client.post("/settings/control", data={"csrf": csrf, "action": "authorize_live", "confirm": "I AUTHORIZE LIVE SENDING"})
    assert get_rule(db, "system.live_send_authorized") is False


def test_e2e_all_pages_render(client, db):
    from bizdev.seed import seed_synthetic
    seed_synthetic(db)
    _login(client)
    for p in ["/", "/leads", "/leads/1", "/queue", "/appointments", "/remote", "/reports", "/settings", "/onboarding", "/audit"]:
        assert client.get(p).status_code == 200, p


def test_e2e_zoho_settings_encrypted_and_test_send(client, db, monkeypatch):
    import smtplib
    from bizdev.models import IntegrationAccount
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, context=None, timeout=None): sent["host"] = host
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, u, p): sent["login"] = (u, p)
        def send_message(self, m): sent["msg"] = m; return {}
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    csrf = _login(client)
    client.post("/settings/zoho", data={"csrf": csrf, "email": "dheeraj@theepoh.com", "from_name": "Dheeraj",
                                        "host": "smtp.zoho.in", "app_password": "super-secret-app-pw"})
    acct = db.query(IntegrationAccount).filter_by(provider="zoho").one()
    assert acct.status == "connected" and "super-secret-app-pw" not in acct.encrypted_token
    assert "super-secret-app-pw" not in client.get("/settings").text
    r = client.post("/settings/zoho/test", data={"csrf": csrf, "to": "me@example.com"})
    assert "accepted" in r.text
    assert sent["login"] == ("dheeraj@theepoh.com", "super-secret-app-pw") and sent["host"] == "smtp.zoho.in"
    assert sent["msg"]["To"] == "me@example.com" and "Dheeraj" in sent["msg"]["From"]
