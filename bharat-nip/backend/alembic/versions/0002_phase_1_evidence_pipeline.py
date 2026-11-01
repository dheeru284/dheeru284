"""phase 1 evidence pipeline

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01

Phase 1 schema (DATABASE_DESIGN.md): submission types and uploaded files, structured
claims (subject/predicate/object, time, location, entities), the source registry
(replaces Phase 0 ``publishers``), search queries/results (replace ``retrieval_results``),
evidence relevance/directness, structured fact-check results, the critic's
deterministic findings, and the PENDING_REVIEW / APPROVED / REJECTED /
NEEDS_MORE_RESEARCH review model.

Hand-written: autogenerate does not detect CHECK-constraint changes on non-native
enums, so every changed enum constraint is dropped and recreated explicitly.
Enum values are frozen here (migrations must not import application code).

Data: Phase 0 had no code path that wrote pipeline rows. To be safe, both
upgrade and downgrade refuse to run if the reshaped tables contain rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESHAPED_TABLES = (
    "submissions",
    "claims",
    "sources",
    "evidence",
    "evidence_rankings",
    "assessments",
    "assessment_citations",
    "critiques",
    "review_tasks",
    "review_decisions",
    "pipeline_jobs",
    "publishers",
    "retrieval_results",
    "registry_sources",
    "search_queries",
    "search_results",
    "stored_files",
)

CLASSIFICATIONS = (
    "TRUE",
    "MOSTLY_TRUE",
    "MISLEADING",
    "OUT_OF_CONTEXT",
    "FALSE",
    "UNVERIFIED",
    "INSUFFICIENT_EVIDENCE",
    "OPINION",
    "PREDICTION",
    "SATIRE",
)

# (table, constraint suffix, column, phase-0 values, phase-1 values)
ENUM_CHANGES = [
    (
        "entities",
        "entity_type",
        "entity_type",
        ("PERSON", "ORGANIZATION", "POLITICAL_PARTY", "GOVERNMENT_BODY", "MEDIA_OUTLET", "OTHER"),
        (
            "PERSON",
            "ORGANIZATION",
            "POLITICAL_PARTY",
            "GOVERNMENT_BODY",
            "MEDIA_OUTLET",
            "PLACE",
            "OTHER",
        ),
    ),
    (
        "submissions",
        "status",
        "status",
        ("RECEIVED", "EXTRACTING", "EXTRACTED", "FAILED"),
        ("RECEIVED", "PROCESSING", "PROCESSED", "NEEDS_TRANSCRIPTION", "NO_CLAIMS", "FAILED"),
    ),
    (
        "claims",
        "status",
        "status",
        (
            "EXTRACTED",
            "RETRIEVING",
            "EVIDENCE_READY",
            "ASSESSING",
            "CRITIQUING",
            "NEEDS_REVIEW",
            "IN_REVIEW",
            "APPROVED",
            "REJECTED",
            "FAILED",
        ),
        (
            "EXTRACTED",
            "RESEARCHING",
            "ASSESSING",
            "CRITIQUING",
            "PENDING_REVIEW",
            "APPROVED",
            "REJECTED",
            "NEEDS_MORE_RESEARCH",
            "FAILED",
        ),
    ),
    (
        "sources",
        "source_type",
        "source_type",
        (
            "OFFICIAL_RECORD",
            "STATISTICAL_DATA",
            "LEGAL_DOCUMENT",
            "ACADEMIC",
            "NEWS_REPORT",
            "FACT_CHECK",
            "PRESS_RELEASE",
            "OTHER",
        ),
        (
            "OFFICIAL_RECORD",
            "STATISTICAL_DATA",
            "LEGAL_DOCUMENT",
            "ACADEMIC",
            "NEWS_REPORT",
            "FACT_CHECK",
            "PRESS_RELEASE",
            "SOCIAL_MEDIA_POST",
            "OTHER",
        ),
    ),
    (
        "assessments",
        "status",
        "status",
        ("DRAFT", "CRITIQUED", "SUPERSEDED", "IN_REVIEW", "APPROVED", "AMENDED", "REJECTED"),
        (
            "DRAFT",
            "CRITIQUED",
            "SUPERSEDED",
            "PENDING_REVIEW",
            "APPROVED",
            "REJECTED",
            "NEEDS_MORE_RESEARCH",
        ),
    ),
    (
        "review_tasks",
        "reason",
        "reason",
        (
            "ROUTINE",
            "CRITIC_ESCALATION",
            "LOOP_LIMIT",
            "LOW_CONFIDENCE",
            "INSUFFICIENT_EVIDENCE",
            "STAGE_FAILURE",
        ),
        (
            "ROUTINE",
            "CRITIC_ESCALATION",
            "RULE_FLAG",
            "LOOP_LIMIT",
            "LOW_CONFIDENCE",
            "INSUFFICIENT_EVIDENCE",
            "STAGE_FAILURE",
        ),
    ),
    (
        "review_tasks",
        "status",
        "status",
        ("OPEN", "CLAIMED", "DECIDED", "CANCELLED"),
        ("OPEN", "DECIDED", "CANCELLED"),
    ),
    (
        "review_decisions",
        "decision",
        "decision",
        ("APPROVE", "AMEND", "REJECT", "REQUEST_MORE_EVIDENCE"),
        ("APPROVE", "REJECT", "NEEDS_MORE_RESEARCH"),
    ),
    (
        "pipeline_jobs",
        "stage",
        "stage",
        (
            "EXTRACTION",
            "RETRIEVAL",
            "EVIDENCE",
            "RANKING",
            "ASSESSMENT",
            "CRITIQUE",
            "REVIEW_ROUTING",
        ),
        (
            "CONTENT",
            "EXTRACTION",
            "SEARCH",
            "EVIDENCE",
            "RANKING",
            "ASSESSMENT",
            "CRITIQUE",
            "REVIEW_ROUTING",
        ),
    ),
]


def _in_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _set_enum_check(table: str, suffix: str, column: str, values: Sequence[str]) -> None:
    name = f"ck_{table}_{suffix}"
    op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')
    op.create_check_constraint(op.f(name), table, f"{column} IN ({_in_list(values)})")


def _require_empty(tables: Sequence[str]) -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    for table in tables:
        if table in existing:
            n = conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
            if n:
                raise RuntimeError(
                    f"Migration 0002 reshapes '{table}', which has {n} rows. "
                    "Phase 0 had no writers for these tables; inspect the data first."
                )


def _add_checked(table: str, column: str, values: Sequence[str], length: int, **kw) -> None:
    op.add_column(table, sa.Column(column, sa.String(length=length), **kw))
    op.create_check_constraint(
        op.f(f"ck_{table}_{column}"), table, f"{column} IN ({_in_list(values)})"
    )


def upgrade() -> None:
    _require_empty(RESHAPED_TABLES)

    # --- new tables ---------------------------------------------------------------------
    op.create_table(
        "registry_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "GOVERNMENT",
                "STATISTICAL_AGENCY",
                "REGULATOR",
                "COURT",
                "LEGISLATURE",
                "ELECTION_BODY",
                "INTERNATIONAL_ORGANIZATION",
                "ACADEMIC",
                "NEWS_MEDIA",
                "FACT_CHECKER",
                "NGO",
                "CORPORATE",
                "POLITICAL_PARTY",
                "SOCIAL_MEDIA",
                "OTHER",
                name="category",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String(length=20), nullable=False),
        sa.Column(
            "authority_level",
            sa.Enum(
                "PRIMARY_AUTHORITY",
                "ESTABLISHED",
                "GENERAL",
                "LIMITED",
                "UNASSESSED",
                name="authority_level",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="UNASSESSED",
            nullable=False,
        ),
        sa.Column("authority_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("authority_rationale", sa.Text(), nullable=True),
        sa.Column(
            "default_source_type",
            sa.Enum(
                "OFFICIAL_RECORD",
                "STATISTICAL_DATA",
                "LEGAL_DOCUMENT",
                "ACADEMIC",
                "NEWS_REPORT",
                "FACT_CHECK",
                "PRESS_RELEASE",
                "SOCIAL_MEDIA_POST",
                "OTHER",
                name="default_source_type",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("is_primary_source", sa.Boolean(), nullable=False),
        sa.Column(
            "verification_status",
            sa.Enum(
                "UNVERIFIED",
                "VERIFIED",
                "DISPUTED",
                name="verification_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("verification_method", sa.Text(), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("verified_by_id", sa.UUID(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "authority_level = 'UNASSESSED' OR authority_rationale IS NOT NULL",
            name=op.f("ck_registry_sources_authority_rationale_required"),
        ),
        sa.CheckConstraint(
            "verification_status <> 'VERIFIED' OR (verified_by_id IS NOT NULL AND verified_at IS NOT NULL AND review_due_at IS NOT NULL)",
            name=op.f("ck_registry_sources_verification_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_registry_sources_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_id"], ["users.id"], name=op.f("fk_registry_sources_verified_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registry_sources")),
        sa.UniqueConstraint("domain", name=op.f("uq_registry_sources_domain")),
    )
    op.create_table(
        "stored_files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], name=op.f("fk_stored_files_uploaded_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_files")),
    )
    op.create_index(op.f("ix_stored_files_sha256"), "stored_files", ["sha256"], unique=False)
    op.create_table(
        "search_queries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SUCCEEDED",
                "FAILED",
                name="status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("pipeline_job_id", sa.UUID(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name=op.f("fk_search_queries_claim_id_claims")
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_job_id"],
            ["pipeline_jobs.id"],
            name=op.f("fk_search_queries_pipeline_job_id_pipeline_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_queries")),
    )
    op.create_index(
        op.f("ix_search_queries_claim_id"), "search_queries", ["claim_id"], unique=False
    )
    op.create_table(
        "search_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("search_query_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("provider_score", sa.Float(), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column(
            "fetch_status",
            sa.Enum(
                "FETCHED",
                "PROVIDED",
                "REUSED",
                "FAILED",
                "SKIPPED",
                name="fetch_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["search_query_id"],
            ["search_queries.id"],
            name=op.f("fk_search_results_search_query_id_search_queries"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_search_results_source_id_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_results")),
    )
    op.create_index(
        op.f("ix_search_results_search_query_id"),
        "search_results",
        ["search_query_id"],
        unique=False,
    )

    # --- removed Phase 0 tables -----------------------------------------------------------
    op.drop_constraint("fk_sources_publisher_id_publishers", "sources", type_="foreignkey")
    op.drop_column("sources", "publisher_id")
    op.drop_table("publishers")
    op.drop_index("ix_retrieval_results_claim_id", table_name="retrieval_results")
    op.drop_table("retrieval_results")

    # --- enum CHECK constraints -----------------------------------------------------------
    for table, suffix, column, _old, new in ENUM_CHANGES:
        _set_enum_check(table, suffix, column, new)

    # --- submissions ----------------------------------------------------------------------
    _add_checked(
        "submissions",
        "submission_type",
        ("TEXT", "URL", "ARTICLE", "IMAGE", "PDF", "VIDEO_METADATA"),
        20,
        nullable=False,
    )
    op.add_column("submissions", sa.Column("title", sa.String(length=1000), nullable=True))
    op.add_column("submissions", sa.Column("publisher_name", sa.String(length=300), nullable=True))
    op.add_column(
        "submissions", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "submissions",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.add_column("submissions", sa.Column("file_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_submissions_file_id_stored_files"),
        "submissions",
        "stored_files",
        ["file_id"],
        ["id"],
    )
    op.add_column("submissions", sa.Column("extracted_text", sa.Text(), nullable=True))
    _add_checked(
        "submissions",
        "extraction_method",
        ("USER_TEXT", "HTML_EXTRACTION", "PDF_TEXT", "OCR", "USER_TRANSCRIPTION", "VIDEO_METADATA"),
        30,
        nullable=True,
    )
    op.add_column("submissions", sa.Column("extraction_notes", sa.Text(), nullable=True))
    op.alter_column("submissions", "raw_text", existing_type=sa.Text(), nullable=True)
    op.alter_column(
        "submissions", "status", existing_type=sa.String(length=20), type_=sa.String(length=30)
    )
    op.execute('ALTER TABLE submissions DROP CONSTRAINT "ck_submissions_raw_text_length"')
    op.create_check_constraint(
        op.f("ck_submissions_raw_text_length"),
        "submissions",
        "raw_text IS NULL OR char_length(raw_text) <= 20000",
    )
    op.create_check_constraint(
        op.f("ck_submissions_extracted_text_length"),
        "submissions",
        "extracted_text IS NULL OR char_length(extracted_text) <= 200000",
    )
    op.create_index(
        op.f("ix_submissions_submitted_by_id"), "submissions", ["submitted_by_id"], unique=False
    )

    # --- claims ---------------------------------------------------------------------------
    for col in ("subject", "predicate", "object"):
        op.add_column("claims", sa.Column(col, sa.Text(), nullable=False))
    op.add_column("claims", sa.Column("time_reference", sa.Text(), nullable=True))
    op.add_column("claims", sa.Column("claim_date", sa.Date(), nullable=True))
    op.add_column("claims", sa.Column("location", sa.Text(), nullable=True))
    for col in ("entities", "original_source"):
        op.add_column(
            "claims", sa.Column(col, postgresql.JSONB(astext_type=sa.Text()), nullable=False)
        )
    op.add_column("claims", sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False))

    # --- sources --------------------------------------------------------------------------
    op.add_column("sources", sa.Column("registry_source_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_sources_registry_source_id_registry_sources"),
        "sources",
        "registry_sources",
        ["registry_source_id"],
        ["id"],
    )
    op.add_column("sources", sa.Column("is_primary", sa.Boolean(), nullable=False))
    op.add_column("sources", sa.Column("publisher_name", sa.String(length=300), nullable=True))
    op.add_column(
        "sources",
        sa.Column("fetch_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    # --- evidence -------------------------------------------------------------------------
    _add_checked("evidence", "directness", ("DIRECT", "INDIRECT"), 20, nullable=False)
    op.add_column("evidence", sa.Column("relevance", sa.Float(), nullable=False))
    op.add_column("evidence", sa.Column("lexical_relevance", sa.Float(), nullable=False))
    op.add_column("evidence", sa.Column("agent_relevance", sa.Float(), nullable=True))
    op.create_check_constraint(
        op.f("ck_evidence_relevance_range"), "evidence", "relevance >= 0 AND relevance <= 1"
    )

    # --- assessments ----------------------------------------------------------------------
    op.drop_column("assessments", "verdict")
    op.drop_column("assessments", "rationale")
    op.drop_column("assessments", "missing_context")
    op.execute('ALTER TABLE assessments DROP CONSTRAINT "ck_assessments_confidence"')
    op.alter_column(
        "assessments",
        "confidence",
        existing_type=sa.String(length=10),
        type_=sa.Float(),
        postgresql_using="NULL::double precision",
    )
    op.create_check_constraint(
        op.f("ck_assessments_confidence_range"),
        "assessments",
        "confidence >= 0 AND confidence <= 1",
    )
    op.alter_column(
        "assessments", "status", existing_type=sa.String(length=20), type_=sa.String(length=30)
    )
    _add_checked("assessments", "classification", CLASSIFICATIONS, 30, nullable=False)
    op.add_column("assessments", sa.Column("confidence_raw", sa.Float(), nullable=True))
    op.add_column("assessments", sa.Column("summary", sa.Text(), nullable=False))
    op.add_column("assessments", sa.Column("reasoning", sa.Text(), nullable=False))
    for col in ("missing_information", "guardrails"):
        op.add_column(
            "assessments",
            sa.Column(col, postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        )
    _add_checked(
        "assessments",
        "recommended_action",
        (
            "CONFIRM_IN_REVIEW",
            "ADD_CONTEXT_NOTE",
            "SEEK_PRIMARY_SOURCE",
            "GATHER_MORE_EVIDENCE",
            "CONSULT_SUBJECT_EXPERT",
            "NOT_FACT_CHECKABLE",
        ),
        30,
        nullable=False,
    )

    # --- critiques ------------------------------------------------------------------------
    _add_checked("critiques", "agent_outcome", ("PASS", "REVISE", "ESCALATE"), 20, nullable=False)
    op.add_column("critiques", sa.Column("outcome_overridden", sa.Boolean(), nullable=False))
    op.add_column(
        "critiques",
        sa.Column(
            "deterministic_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
    )
    op.add_column("critiques", sa.Column("counter_argument", sa.Text(), nullable=False))
    _add_checked("critiques", "suggested_classification", CLASSIFICATIONS, 30, nullable=True)

    # --- review ---------------------------------------------------------------------------
    op.add_column("review_tasks", sa.Column("reason_detail", sa.Text(), nullable=True))
    op.alter_column("review_tasks", "assessment_id", existing_type=sa.UUID(), nullable=True)
    op.drop_column("review_decisions", "final_verdict")  # also drops its CHECKs
    _add_checked("review_decisions", "final_classification", CLASSIFICATIONS, 30, nullable=True)
    op.execute(
        'ALTER TABLE review_decisions DROP CONSTRAINT IF EXISTS "ck_review_decisions_notes_required"'
    )
    op.create_check_constraint(
        op.f("ck_review_decisions_final_classification_required"),
        "review_decisions",
        "decision <> 'APPROVE' OR final_classification IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_review_decisions_notes_required"),
        "review_decisions",
        "decision = 'APPROVE' OR (notes IS NOT NULL AND notes <> '')",
    )


def downgrade() -> None:
    _require_empty(RESHAPED_TABLES)

    # --- review ---------------------------------------------------------------------------
    op.execute('ALTER TABLE review_decisions DROP CONSTRAINT "ck_review_decisions_notes_required"')
    op.drop_column("review_decisions", "final_classification")
    op.add_column(
        "review_decisions", sa.Column("final_verdict", sa.String(length=30), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_review_decisions_final_verdict"),
        "review_decisions",
        f"final_verdict IN ({_in_list(CLASSIFICATIONS)})",
    )
    op.create_check_constraint(
        op.f("ck_review_decisions_final_verdict_required"),
        "review_decisions",
        "decision NOT IN ('APPROVE', 'AMEND') OR final_verdict IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_review_decisions_notes_required"),
        "review_decisions",
        "decision NOT IN ('AMEND', 'REJECT') OR (notes IS NOT NULL AND notes <> '')",
    )
    op.alter_column("review_tasks", "assessment_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("review_tasks", "reason_detail")

    # --- critiques ------------------------------------------------------------------------
    for col in (
        "suggested_classification",
        "counter_argument",
        "deterministic_findings",
        "outcome_overridden",
        "agent_outcome",
    ):
        op.drop_column("critiques", col)

    # --- assessments ----------------------------------------------------------------------
    for col in (
        "recommended_action",
        "guardrails",
        "missing_information",
        "reasoning",
        "summary",
        "confidence_raw",
        "classification",
    ):
        op.drop_column("assessments", col)
    op.alter_column(
        "assessments", "status", existing_type=sa.String(length=30), type_=sa.String(length=20)
    )
    op.execute('ALTER TABLE assessments DROP CONSTRAINT "ck_assessments_confidence_range"')
    op.alter_column(
        "assessments",
        "confidence",
        existing_type=sa.Float(),
        type_=sa.String(length=10),
        postgresql_using="NULL::varchar",
    )
    op.create_check_constraint(
        op.f("ck_assessments_confidence"), "assessments", "confidence IN ('LOW', 'MEDIUM', 'HIGH')"
    )
    op.add_column("assessments", sa.Column("verdict", sa.String(length=30), nullable=False))
    op.create_check_constraint(
        op.f("ck_assessments_verdict"), "assessments", f"verdict IN ({_in_list(CLASSIFICATIONS)})"
    )
    op.add_column("assessments", sa.Column("rationale", sa.Text(), nullable=False))
    op.add_column("assessments", sa.Column("missing_context", sa.Text(), nullable=True))

    # --- evidence -------------------------------------------------------------------------
    for col in ("agent_relevance", "lexical_relevance", "relevance", "directness"):
        op.drop_column("evidence", col)

    # --- sources --------------------------------------------------------------------------
    op.drop_constraint(
        "fk_sources_registry_source_id_registry_sources", "sources", type_="foreignkey"
    )
    for col in ("fetch_metadata", "publisher_name", "is_primary", "registry_source_id"):
        op.drop_column("sources", col)

    # --- claims ---------------------------------------------------------------------------
    for col in (
        "extracted_at",
        "original_source",
        "entities",
        "location",
        "claim_date",
        "time_reference",
        "object",
        "predicate",
        "subject",
    ):
        op.drop_column("claims", col)

    # --- submissions ----------------------------------------------------------------------
    op.drop_index(op.f("ix_submissions_submitted_by_id"), table_name="submissions")
    op.execute('ALTER TABLE submissions DROP CONSTRAINT "ck_submissions_extracted_text_length"')
    op.execute('ALTER TABLE submissions DROP CONSTRAINT "ck_submissions_raw_text_length"')
    op.create_check_constraint(
        op.f("ck_submissions_raw_text_length"), "submissions", "char_length(raw_text) <= 20000"
    )
    op.alter_column("submissions", "raw_text", existing_type=sa.Text(), nullable=False)
    op.drop_constraint("fk_submissions_file_id_stored_files", "submissions", type_="foreignkey")
    for col in (
        "extraction_notes",
        "extraction_method",
        "extracted_text",
        "file_id",
        "metadata",
        "published_at",
        "publisher_name",
        "title",
        "submission_type",
    ):
        op.drop_column("submissions", col)
    op.alter_column(
        "submissions", "status", existing_type=sa.String(length=30), type_=sa.String(length=20)
    )

    # --- enum CHECK constraints back to Phase 0 -------------------------------------------
    for table, suffix, column, old, _new in ENUM_CHANGES:
        _set_enum_check(table, suffix, column, old)

    # --- restore Phase 0 tables -----------------------------------------------------------
    op.create_table(
        "publishers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column(
            "reliability_tier",
            sa.Enum(
                "TIER_1",
                "TIER_2",
                "TIER_3",
                "TIER_4",
                "UNRATED",
                name="reliability_tier",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            server_default="UNRATED",
            nullable=False,
        ),
        sa.Column("tier_rationale", sa.Text(), nullable=True),
        sa.Column("tier_set_by_id", sa.UUID(), nullable=True),
        sa.Column("tier_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tier_set_by_id"], ["users.id"], name=op.f("fk_publishers_tier_set_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publishers")),
        sa.UniqueConstraint("domain", name=op.f("uq_publishers_domain")),
    )
    op.add_column("sources", sa.Column("publisher_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_sources_publisher_id_publishers"),
        "sources",
        "publishers",
        ["publisher_id"],
        ["id"],
    )
    op.create_table(
        "retrieval_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "method",
            sa.Enum(
                "VECTOR",
                "KEYWORD",
                "HYBRID",
                name="method",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("pipeline_job_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["source_chunks.id"],
            name=op.f("fk_retrieval_results_chunk_id_source_chunks"),
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name=op.f("fk_retrieval_results_claim_id_claims")
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_job_id"],
            ["pipeline_jobs.id"],
            name=op.f("fk_retrieval_results_pipeline_job_id_pipeline_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retrieval_results")),
    )
    op.create_index(
        op.f("ix_retrieval_results_claim_id"), "retrieval_results", ["claim_id"], unique=False
    )

    # --- drop Phase 1 tables --------------------------------------------------------------
    op.drop_index(op.f("ix_search_results_search_query_id"), table_name="search_results")
    op.drop_table("search_results")
    op.drop_index(op.f("ix_search_queries_claim_id"), table_name="search_queries")
    op.drop_table("search_queries")
    op.drop_index(op.f("ix_stored_files_sha256"), table_name="stored_files")
    op.drop_table("stored_files")
    op.drop_table("registry_sources")
