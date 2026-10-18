"""Add pre-pilot document reviews, evidence and verified sessions.

Hand-written migration; the initial generated migration is preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261018_acceptance"
down_revision = "9bce9b6e09b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_course_school", "courses", ["id", "school_id"])
    op.create_foreign_key("fk_membership_course_school", "course_memberships", "courses", ["course_id", "school_id"], ["id", "school_id"])
    op.create_foreign_key("fk_membership_school_user", "course_memberships", "school_memberships", ["school_id", "user_id"], ["school_id", "user_id"])
    op.create_foreign_key("fk_document_course_school", "documents", "courses", ["course_id", "school_id"], ["id", "school_id"])
    op.add_column("conversations", sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id")))
    op.add_column("practice_session_items", sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("practice_session_items", "hints_used", server_default=None)
    op.add_column("documents", sa.Column("purpose", sa.Text(), nullable=False, server_default="teaching"))
    op.alter_column("documents", "purpose", server_default=None)
    for name, kind, default in [
        ("revision", sa.Integer(), "1"), ("filename", sa.Text(), "document.pdf"),
        ("content_type", sa.Text(), "application/pdf"), ("size_bytes", sa.Integer(), "0"),
    ]:
        op.add_column("document_versions", sa.Column(name, kind, nullable=False, server_default=default))
        op.alter_column("document_versions", name, server_default=None)
    op.add_column("document_versions", sa.Column("extraction_error", sa.Text()))
    for name in ("prompt", "hint", "explanation"):
        op.add_column("questions", sa.Column(name, sa.Text(), nullable=False, server_default=""))
        op.alter_column("questions", name, server_default=None)
    op.add_column("questions", sa.Column("source_version_id", sa.Uuid(), sa.ForeignKey("document_versions.id")))
    op.add_column("message_outbox", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("message_outbox", "attempts", server_default=None)
    for name in ("lease_until", "next_run_at"):
        op.add_column("message_outbox", sa.Column(name, sa.DateTime(timezone=True)))
    op.create_table("auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("idempotency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scope", sa.String(128), nullable=False), sa.Column("key", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("result", JSONB(), nullable=False),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_idempotency"))
    op.create_table("content_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False), sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("checklist", JSONB(), nullable=False), sa.Column("rubric", JSONB(), nullable=False), sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_content_reviews_version_id", "content_reviews", ["version_id"])
    op.create_table("acceptance_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("document_versions.id")),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requirement", sa.String(64), nullable=False), sa.Column("result", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), sa.ForeignKey("document_versions.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_acceptance_evidence_course_id", "acceptance_evidence", ["course_id"])
    op.create_table("evaluation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False), sa.Column("case_id", sa.String(32), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), sa.ForeignKey("acceptance_evidence.id"), nullable=False),
        sa.Column("scores", JSONB(), nullable=False), sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False), sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("course_id", "run_id", "case_id", "reviewer_id", name="uq_evaluation_case"))
    op.create_index("ix_evaluation_results_course_id", "evaluation_results", ["course_id"])


def downgrade():
    op.drop_constraint("fk_document_course_school", "documents", type_="foreignkey")
    op.drop_constraint("fk_membership_school_user", "course_memberships", type_="foreignkey")
    op.drop_constraint("fk_membership_course_school", "course_memberships", type_="foreignkey")
    op.drop_constraint("uq_course_school", "courses", type_="unique")
    op.drop_column("conversations", "course_id")
    op.drop_column("practice_session_items", "hints_used")
    for table in ("evaluation_results", "acceptance_evidence", "content_reviews", "idempotency_records", "auth_sessions"):
        op.drop_table(table)
    for name in ("attempts", "lease_until", "next_run_at"):
        op.drop_column("message_outbox", name)
    for name in ("prompt", "hint", "explanation", "source_version_id"):
        op.drop_column("questions", name)
    for name in ("revision", "filename", "content_type", "size_bytes", "extraction_error"):
        op.drop_column("document_versions", name)
    op.drop_column("documents", "purpose")
