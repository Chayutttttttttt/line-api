"""Keep extracted keywords with each chunk for scoped hybrid retrieval."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261028_chunk_keywords"
down_revision = "20261028_course_materials"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chunks", sa.Column("keywords", JSONB(), nullable=False,
        server_default=sa.text("'[]'::jsonb")))


def downgrade():
    op.drop_column("chunks", "keywords")
