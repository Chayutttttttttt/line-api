"""Separate current school/role from enrolment and retain course creators."""

import sqlalchemy as sa

from alembic import op

revision = "20261107_school_roster"
down_revision = "20261028_semantic_chunks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("school_id", sa.Uuid(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(32),
            nullable=False,
            server_default="student",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "membership_revision",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_foreign_key("fk_user_school", "users", "schools", ["school_id"], ["id"])
    op.create_index("ix_users_school_id", "users", ["school_id"])
    op.create_check_constraint(
        "ck_user_role", "users", "role IN ('student', 'teacher')"
    )
    op.add_column("courses", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_course_owner", "courses", "users", ["owner_id"], ["id"])
    op.create_index("ix_courses_owner_id", "courses", ["owner_id"])

    # Multiple old affiliations cannot tell us which school is current.
    # Leave those accounts unassigned for an administrator to resolve explicitly.
    op.execute("""
        UPDATE users u SET school_id = sm.school_id,
            role = CASE WHEN sm.role IN ('teacher', 'admin')
                        THEN 'teacher' ELSE 'student' END
        FROM school_memberships sm
        WHERE sm.user_id = u.id AND sm.status = 'active'
          AND (SELECT count(*) FROM school_memberships all_sm
               WHERE all_sm.user_id = u.id AND all_sm.status = 'active') = 1
    """)
    op.execute("""
        UPDATE school_memberships sm SET role = u.role
        FROM users u WHERE u.id = sm.user_id AND u.school_id = sm.school_id
          AND sm.status = 'active'
    """)
    op.execute("""
        UPDATE courses c SET owner_id = (
            SELECT a.actor_id FROM audit_events a
            JOIN users u ON u.id = a.actor_id
            WHERE a.object_id = c.id
              AND a.action IN ('course.create', 'admin.course.create')
            ORDER BY a.created_at, a.id LIMIT 1
        )
    """)
    op.execute("""
        UPDATE courses c SET owner_id = cm.user_id
        FROM course_memberships cm
        WHERE c.owner_id IS NULL AND cm.course_id = c.id
          AND cm.role IN ('teacher', 'admin') AND cm.status = 'active'
          AND (SELECT count(*) FROM course_memberships teachers
               WHERE teachers.course_id = c.id AND teachers.status = 'active'
                 AND teachers.role IN ('teacher', 'admin')) = 1
    """)


def downgrade():
    op.drop_index("ix_courses_owner_id", table_name="courses")
    op.drop_constraint("fk_course_owner", "courses", type_="foreignkey")
    op.drop_column("courses", "owner_id")
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.drop_index("ix_users_school_id", table_name="users")
    op.drop_constraint("fk_user_school", "users", type_="foreignkey")
    op.drop_column("users", "membership_revision")
    op.drop_column("users", "role")
    op.drop_column("users", "school_id")
