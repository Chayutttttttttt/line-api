"""Create a durable Global Admin identity using the existing verified sole user.

This one-time migration never grants admin to subsequent users or on API startup.
If there is not exactly one existing user with a LINE identity, it grants nobody.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261027_global_admin"
down_revision = "20261021_multisubject"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_users",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Exactly one *existing* active account with verified LINE identity is required.
    # This statement is executed only once by Alembic, never for future registrations.
    op.execute(sa.text("""
        INSERT INTO admin_users (user_id)
        SELECT u.id
        FROM users AS u
        WHERE u.status = 'active'
          AND EXISTS (SELECT 1 FROM line_identities AS li WHERE li.user_id = u.id)
          AND (SELECT COUNT(*) FROM users) = 1
    """))


def downgrade():
    op.drop_table("admin_users")
