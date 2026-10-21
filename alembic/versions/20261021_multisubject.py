"""Course-specific teaching, evaluation and manual grading (hand-written)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261021_multisubject"
down_revision = "20261018_acceptance"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve the original pilot scope for existing courses. New courses use general defaults in the app.
    for name, kind, default in [
        ("subject", sa.String(255), "คณิตศาสตร์"),
        ("learning_scope", sa.Text(), "โดเมน เรนจ์ และการเป็นฟังก์ชันจากเซตคู่อันดับจำนวนเต็ม ไม่รวมสมการ กราฟ อินเวอร์ส ช่วงค่า และข้อพิสูจน์"),
        ("response_language", sa.String(64), "ไทย"),
        ("revision", sa.Integer(), "1"),
        ("evaluation_profile", sa.Text(), "relations-pilot"),
        ("evaluation_overrides", JSONB(), "{}"),
    ]:
        op.add_column("courses", sa.Column(name, kind, nullable=False, server_default=default))
        op.alter_column("courses", name, server_default=None)
    op.add_column("topics", sa.Column("keywords", JSONB(), nullable=False, server_default="[]"))
    op.alter_column("topics", "keywords", server_default=None)
    op.add_column("attempts", sa.Column("score_status", sa.Text(), nullable=False, server_default="graded"))
    op.alter_column("attempts", "score_status", server_default=None)
    op.add_column("evaluation_results", sa.Column("course_revision", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column("evaluation_results", "course_revision", server_default=None)


def downgrade():
    op.drop_column("evaluation_results", "course_revision")
    op.drop_column("attempts", "score_status")
    op.drop_column("topics", "keywords")
    for name in ("subject", "learning_scope", "response_language", "revision", "evaluation_profile", "evaluation_overrides"):
        op.drop_column("courses", name)
