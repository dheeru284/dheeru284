"""Command line: init-db, create-admin, seed-demo, worker, import-csv, gen-keys."""
from __future__ import annotations

import argparse
import getpass
import time

from cryptography.fernet import Fernet
from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .security import hash_password, install_log_redaction


def main(argv=None):
    p = argparse.ArgumentParser(prog="bizdev")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen-keys")
    sub.add_parser("init-db")
    a = sub.add_parser("create-admin"); a.add_argument("email")
    sub.add_parser("seed-demo")
    w = sub.add_parser("worker"); w.add_argument("--interval", type=int, default=60); w.add_argument("--once", action="store_true")
    i = sub.add_parser("import-csv"); i.add_argument("path"); i.add_argument("--campaign", default="A_DUBAI")
    sub.add_parser("report")
    args = p.parse_args(argv)
    install_log_redaction()

    if args.cmd == "gen-keys":
        import secrets
        print(f"SECRET_KEY={secrets.token_urlsafe(48)}\nTOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
        return
    from .seed import seed_reference, seed_synthetic
    if args.cmd == "init-db":
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            seed_reference(db)
        print("database ready")
    elif args.cmd == "create-admin":
        from .models import User
        pw = getpass.getpass("Password (min 12 chars): ")
        if len(pw) < 12:
            raise SystemExit("password too short")
        with SessionLocal() as db:
            u = db.scalar(select(User).where(User.email == args.email.lower())) or User(email=args.email.lower())
            u.password_hash = hash_password(pw); db.add(u); db.commit()
        print("admin saved")
    elif args.cmd == "seed-demo":
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            print("synthetic data:", seed_synthetic(db))
    elif args.cmd == "import-csv":
        from .discovery import CSVImportSource, run_source
        with SessionLocal() as db, open(args.path, encoding="utf-8") as f:
            print(run_source(db, CSVImportSource(f.read()), campaign_code=args.campaign))
    elif args.cmd == "worker":
        from .outreach import poll_inbox, run_due_jobs
        from .providers import registry
        while True:
            with SessionLocal() as db:
                registry.configure_from_db(db)
                try:
                    poll_inbox(db)
                except Exception as e:  # noqa: BLE001
                    print("inbox poll failed:", e)
                print("jobs:", run_due_jobs(db))
            if args.once:
                break
            time.sleep(args.interval)
    elif args.cmd == "report":
        import json
        from .reports import detailed, overview
        with SessionLocal() as db:
            print(json.dumps({"overview": overview(db), "detail": detailed(db)}, indent=2, default=str))


if __name__ == "__main__":
    main()
