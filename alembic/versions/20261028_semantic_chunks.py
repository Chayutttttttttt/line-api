"""Store page ranges and semantic topics alongside existing chunk citations."""
from alembic import op
import sqlalchemy as sa

revision = "20261028_semantic_chunks"
down_revision = "20261028_chunk_keywords"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("topic", sa.String(255), nullable=False,
        server_default=""))
    op.execute("UPDATE chunks SET page_end = page_no WHERE page_no IS NOT NULL")


def downgrade():
    op.drop_column("chunks", "topic")
    op.drop_column("chunks", "page_end")
