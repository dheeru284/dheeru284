"""Reference data (services, campaigns) and a clearly-labelled SYNTHETIC demo dataset.

Synthetic organizations use the reserved `.example` TLD and `example.com`
URLs so they can never be mistaken for, or delivered to, real businesses.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import ensure_default_rules, now_utc
from .discovery import RawContact, RawLead, StaticSource, run_source
from .models import Campaign, CompanyProfile, ServiceOffering

SERVICES = {
    "Data & Analytics": {
        "Data Engineer": ["data engineer", "data engineering", "pyspark", "spark", "databricks", "data pipeline"],
        "Senior Data Engineer": ["senior data engineer"],
        "Data Analyst": ["data analyst", "data analysis"],
        "Business Intelligence Developer": ["bi developer", "power bi", "tableau", "business intelligence"],
        "SQL Developer": ["sql developer", "t-sql", "pl/sql"],
        "ETL/ELT Developer": ["etl", "elt", "informatica", "azure data factory", "adf", "dbt"],
        "Data Warehouse Developer": ["data warehouse", "snowflake", "synapse", "redshift", "bigquery"],
        "Analytics Engineer": ["analytics engineer"],
        "Data Platform Engineer": ["data platform", "lakehouse", "microsoft fabric"],
        "Reporting and Dashboard Developer": ["dashboard", "reporting"],
    },
    "Project & Business Delivery": {
        "Scrum Master": ["scrum master", "scrum"], "Business Analyst": ["business analyst"],
        "Program Manager": ["program manager", "programme manager"], "Project Manager": ["project manager"],
        "Product Owner": ["product owner"], "Business Operations": ["business operations"],
        "Product and Delivery Management": ["delivery manager", "delivery management"],
        "Agile Transformation Consultant": ["agile transformation", "agile coach"],
    },
    "Enterprise Integration & Technology": {
        "Oracle Integration Cloud Consultant": ["oracle integration cloud", "oic"],
        "Oracle Integration Developer": ["oracle integration"],
        "API Integration Consultant": ["api integration", "rest api", "mulesoft"],
        "Cloud Data Consultant": ["cloud data", "azure", "aws", "gcp", "cloud migration"],
        "Database Developer": ["database developer", "oracle database", "postgresql"],
        "Enterprise Application Integration Consultant": ["enterprise integration", "eai", "middleware"],
    },
}


def seed_reference(db: Session) -> None:
    ensure_default_rules(db)
    for cat, items in SERVICES.items():
        for title, kws in items.items():
            if not db.scalar(select(ServiceOffering).where(ServiceOffering.category == cat, ServiceOffering.title == title)):
                db.add(ServiceOffering(category=cat, title=title, keywords=kws))
    for code, name in (("A_DUBAI", "Campaign A — Dubai business development"),
                       ("B_REMOTE", "Campaign B — International remote business")):
        if not db.scalar(select(Campaign).where(Campaign.code == code)):
            db.add(Campaign(code=code, name=name))
    if not db.scalar(select(CompanyProfile)):
        # Only the legal name is known. Everything else must be entered and verified in onboarding.
        db.add(CompanyProfile(name="EpohTech Private Limited"))
    db.commit()


def synthetic_leads() -> list[RawLead]:
    d = now_utc().date()
    S = "https://example.com/synthetic/"
    return [
        RawLead("[SYNTHETIC] Falcon Data Consulting FZ-LLC", "synthetic", S + "falcon/jobs/1", "hiring",
                "Hiring 2 contract Senior Data Engineers (Databricks, PySpark, Azure Data Factory); remote from India accepted.",
                website="https://falcon-data.example", country="AE", city="Dubai", industry="IT consulting",
                category="consulting", evidence_date=d - timedelta(days=6), remote_ok=True, is_synthetic=True,
                contacts=[RawContact("Aisha Synthetic", "Head of Data & Analytics", "aisha@falcon-data.example", verified=True)]),
        RawLead("[SYNTHETIC] Gulf Oracle Partners LLC", "synthetic", S + "gop/rfp", "subcontracting",
                "Seeking subcontract partner for an Oracle Integration Cloud (OIC) rollout; offshore delivery acceptable.",
                website="https://gulf-oracle.example", country="AE", city="Dubai", industry="ERP implementation",
                category="oracle_partner", evidence_date=d - timedelta(days=12), remote_ok=True, is_synthetic=True,
                contacts=[RawContact("Rahul Synthetic", "Delivery Director", "rahul@gulf-oracle.example", verified=True)]),
        RawLead("[SYNTHETIC] Desert Talent Staffing", "synthetic", S + "dts/about", "directory_listing",
                "IT staffing agency listed in a business directory (no specific requirement found).",
                website="https://desert-talent.example", country="AE", city="Dubai", industry="Recruitment",
                category="staffing_agency", is_synthetic=True,
                contacts=[RawContact(None, None, "info@desert-talent.example", verified=False)]),
        RawLead("[SYNTHETIC] Northwind Analytics Ltd", "synthetic", S + "nw/jobs/scrum", "contract_requirement",
                "6-month contract Scrum Master and Business Analyst for analytics modernization; worldwide remote.",
                website="https://northwind-analytics.example", country="GB", city="London", industry="Analytics",
                category="data_consulting", evidence_date=d - timedelta(days=3), remote_ok=True, is_synthetic=True,
                contacts=[RawContact("Sam Synthetic", "Resource Manager", "sam@northwind-analytics.example", verified=True)]),
        RawLead("[SYNTHETIC] Oasis Retail Group", "synthetic", S + "oasis/news", "cloud_migration",
                "Announced cloud data platform migration (inferred need for SQL/ETL resources).",
                website="https://oasis-retail.example", country="AE", city="Abu Dhabi", industry="Retail",
                category="end_client", evidence_date=d - timedelta(days=40), is_inference=True, is_synthetic=True),
    ]


def seed_synthetic(db: Session) -> dict:
    seed_reference(db)
    stats = run_source(db, StaticSource("synthetic", synthetic_leads()))
    from .remote import add_opportunity
    d = now_utc().date()
    add_opportunity(db, title="[SYNTHETIC] Contract Data Engineer (Databricks) — remote, India OK",
                    source_url="https://example.com/synthetic/opp/1",
                    text="Contract data engineer, Databricks, PySpark, dbt. Remote; candidates in India welcome.",
                    contract_type="contract", currency="USD", evidence_date=d - timedelta(days=2),
                    deadline=d + timedelta(days=10), application_method="Apply via posting", is_synthetic=True)
    add_opportunity(db, title="[SYNTHETIC] OIC Integration Developer — US only",
                    source_url="https://example.com/synthetic/opp/2",
                    text="Oracle Integration Cloud developer. Remote, US only; must have work authorization in the US.",
                    contract_type="contract", currency="USD", evidence_date=d - timedelta(days=5), is_synthetic=True)
    db.commit()
    return stats
