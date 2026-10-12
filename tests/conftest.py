import os
from datetime import datetime

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-abcdefghijklmnop")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ["ALLOW_LIVE_SEND"] = "false"

from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from bizdev import core  # noqa: E402
from bizdev.db import Base  # noqa: E402
from bizdev.integrations.calendar import MockCalendar  # noqa: E402
from bizdev.integrations.email import MockEmailProvider  # noqa: E402
from bizdev.integrations.linkedin import LinkedInIntegration  # noqa: E402
from bizdev.models import CompanyProfile  # noqa: E402
from bizdev.providers import registry  # noqa: E402
from bizdev.seed import seed_reference  # noqa: E402

# Tuesday 13 Oct 2026, 08:00 UTC = 12:00 Dubai (inside business hours)
FIXED_NOW = datetime(2026, 10, 13, 8, 0, 0)


@pytest.fixture
def clock():
    state = {"now": FIXED_NOW}
    core.set_clock(lambda: state["now"])
    yield state
    core.set_clock(lambda: datetime.utcnow())


@pytest.fixture
def db(clock):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    s = S()
    seed_reference(s)
    p = s.query(CompanyProfile).one()
    p.sender_name, p.sender_title, p.sender_email = "Test Sender", "BD Lead", "bd@epohtech.example"
    p.website = "https://epohtech.example"
    p.description = "Technology services company (test)."
    s.commit()
    registry.email = MockEmailProvider()
    registry.calendar = MockCalendar()
    registry.linkedin = LinkedInIntegration()
    yield s
    s.close()


@pytest.fixture
def live(monkeypatch, db):
    """Turn on live sending (still to the MOCK provider)."""
    monkeypatch.setenv("ALLOW_LIVE_SEND", "true")
    core.set_rule(db, "system.live_send_authorized", True, "test")
    db.commit()
    return db
