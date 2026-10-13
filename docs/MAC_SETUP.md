# Run on your Mac and connect Zoho (no Zoho app needed)

1. Create a Zoho app password in your **browser**: accounts.zoho.in (or accounts.zoho.com) → Security → App Passwords → Generate, then copy it.
2. Open Terminal and run:
```bash
git clone https://github.com/dheeru284/dheeru284.git && cd dheeru284 && git checkout claude/bold-hopper-ygpdhk
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m bizdev.cli gen-keys > .env && echo "DATABASE_URL=sqlite:///./bizdev.db" >> .env
set -a; source .env; set +a
alembic upgrade head
python -m bizdev.cli create-admin dheeraj@theepoh.com
python -m bizdev.cli import-csv docs/outreach/leads_2026-10-12.csv
uvicorn bizdev.web.app:app --port 8000
```
3. Go to http://localhost:8000 → **Automation settings** → **Zoho Mail**. Enter your email, the name "Dheeraj", the host, and the app password, then Save.
4. Enter your own address under **Send test**. If authentication fails, try `smtp.zoho.com` or `smtppro.zoho.in`.
