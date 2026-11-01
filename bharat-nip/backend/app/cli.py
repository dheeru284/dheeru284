"""Admin CLI. Usage:

uv run python -m app.cli create-user --email a@b.c --name "A" --role ADMIN
(password is read from BNIP_NEW_USER_PASSWORD or prompted)
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.db.session import get_sessionmaker
from app.domain.enums import UserRole
from app.services.errors import DomainError
from app.services.users import create_user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    sub.add_parser("seed-demo", help="Fictional demo users, registry entry and source")
    args = parser.parse_args(argv)
    if args.command == "seed-demo":
        return seed_demo()

    password = os.environ.get("BNIP_NEW_USER_PASSWORD") or getpass.getpass("Password: ")
    with get_sessionmaker()() as session:
        try:
            user = create_user(
                session,
                email=args.email,
                display_name=args.name,
                role=UserRole(args.role),
                password=password,
                created_by=None,
            )
            session.commit()
        except (DomainError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    print(f"created {user.role.value} {user.email} ({user.id})")
    return 0


DEMO_SOURCE = (
    "Riverland Statistics Office. Annual Education Bulletin 2023.\n\n"
    "The Riverland Statistics Office reports that the state literacy rate was 81.2 percent "
    "in 2023, up from 78.4 percent in 2021. The estimate comes from the 2023 household "
    "education survey covering 42,000 households across all districts.\n\n"
    "Methodology: literacy is defined as the ability to read and write a short statement "
    "in any language, for persons aged seven and above. The margin of error is 0.6 points."
)


def seed_demo() -> int:
    """Create FICTIONAL demo data (Riverland does not exist). Refused in production."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.core.config import get_settings
    from app.domain.enums import (
        AuthorityLevel,
        RegistryVerificationStatus,
        SourceCategory,
        SourceType,
    )
    from app.models import RegistrySource, User
    from app.services.registry import create_entry, set_verification
    from app.services.sources import store_source

    if get_settings().env == "production":
        print("error: seed-demo is refused in production", file=sys.stderr)
        return 1
    password = os.environ.get("BNIP_DEMO_PASSWORD")
    if not password or len(password) < 10:
        print("error: set BNIP_DEMO_PASSWORD (>= 10 chars)", file=sys.stderr)
        return 1
    with get_sessionmaker()() as session:
        users = {}
        for email, name, role in [
            ("admin@demo.example", "Demo Admin", UserRole.ADMIN),
            ("analyst@demo.example", "Demo Analyst", UserRole.ANALYST),
            ("reviewer@demo.example", "Demo Reviewer", UserRole.REVIEWER),
        ]:
            existing = session.scalar(select(User).where(User.email == email))
            users[role] = existing or create_user(
                session,
                email=email,
                display_name=name,
                role=role,
                password=password,
                created_by=None,
            )
        admin = users[UserRole.ADMIN]
        if not session.scalar(
            select(RegistrySource).where(RegistrySource.domain == "stats.riverland.example")
        ):
            entry = create_entry(
                session,
                admin,
                {
                    "name": "Riverland Statistics Office (fictional)",
                    "domain": "stats.riverland.example",
                    "category": SourceCategory.STATISTICAL_AGENCY,
                    "jurisdiction": "RL",
                    "authority_level": AuthorityLevel.PRIMARY_AUTHORITY,
                    "authority_scope": ["literacy", "education", "census"],
                    "authority_rationale": "Fictional statutory producer of education statistics.",
                    "default_source_type": SourceType.STATISTICAL_DATA,
                    "is_primary_source": True,
                },
            )
            set_verification(
                session,
                admin,
                entry.id,
                status=RegistryVerificationStatus.VERIFIED,
                method="Demo data: fictional entry.",
                notes=None,
            )
        store_source(
            session,
            title="Annual Education Bulletin 2023 (fictional)",
            content_text=DEMO_SOURCE,
            url="https://stats.riverland.example/bulletins/literacy-2023",
            publisher_name="Riverland Statistics Office (fictional)",
            published_at=datetime(2024, 1, 15, tzinfo=UTC),
            source_type=SourceType.STATISTICAL_DATA,
            language="en",
            retrieval_provider="human_ingest",
            ingested_by=users[UserRole.ANALYST],
        )
        session.commit()
    print("seeded fictional demo data: admin@, analyst@, reviewer@demo.example")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
