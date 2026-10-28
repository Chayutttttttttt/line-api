"""Classify course materials and flag pages with incomplete text extraction.

Safe additive migration; existing documents remain teaching lessons.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261028_course_materials"
down_revision = "20261027_global_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("material_type", sa.String(32), nullable=False,
        server_default="lesson"))
    op.add_column("documents", sa.Column("topic_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_documents_topic_id_topics", "documents", "topics",
        ["topic_id"], ["id"])
    op.add_column("document_versions", sa.Column("extraction_warning", sa.Text(),
        nullable=True))


def downgrade():
    op.drop_column("document_versions", "extraction_warning")
    op.drop_constraint("fk_documents_topic_id_topics", "documents", type_="foreignkey")
    op.drop_column("documents", "topic_id")
    op.drop_column("documents", "material_type")
