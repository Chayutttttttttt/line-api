"""Verify school/role administration and creator-owned student rosters."""

import hashlib
import importlib.util
import os
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from components.memberships import assign_creator, set_affiliation
from db.database import get_session
from db.models import (
    AdminUser,
    AuditEvent,
    AuthSession,
    Course,
    CourseMembership,
    PracticeSession,
    School,
    SchoolMembership,
    User,
    UserProfile,
    utc_now,
)
from main import app


@unittest.skipUnless(
    os.getenv("QUIZ_TEST_DATABASE_URL"), "requires PostgreSQL/pgvector"
)
class SchoolRosterTests(unittest.TestCase):
    def setUp(self):
        url = os.environ["QUIZ_TEST_DATABASE_URL"]
        self.schema = "roster_test_" + uuid4().hex
        admin_engine = create_engine(url)
        self.addCleanup(admin_engine.dispose)
        with admin_engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {self.schema}"))

        def cleanup():
            with admin_engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))

        self.addCleanup(cleanup)
        self.engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={self.schema},public"},
        )
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine, checkfirst=False)

        def session():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        self.enterContext(patch.dict(app.dependency_overrides, {get_session: session}))
        self.client = self.enterContext(TestClient(app))
        self.accounts = {}
        self.tokens = {}
        with Session(self.engine, expire_on_commit=False) as db:
            self.school = School(name="โรงเรียน ก")
            self.other_school = School(name="โรงเรียน ข")
            db.add_all([self.school, self.other_school])
            db.flush()
            for name, school_id, role in [
                ("admin", self.school.id, "teacher"),
                ("teacher", self.school.id, "teacher"),
                ("other_teacher", self.school.id, "teacher"),
                ("student", self.school.id, "student"),
                ("foreign", self.other_school.id, "student"),
                ("unaffiliated", None, "student"),
                ("inactive", self.school.id, "student"),
            ]:
                user = User(display_name=name)
                db.add(user)
                db.flush()
                set_affiliation(db, user, school_id, role)
                if name == "inactive":
                    user.status = "inactive"
                    db.add(user)
                token = uuid4().hex
                self.accounts[name], self.tokens[name] = user, token
                db.add(
                    AuthSession(
                        user_id=user.id,
                        token_hash=hashlib.sha256(token.encode()).hexdigest(),
                        expires_at=utc_now() + timedelta(hours=1),
                    )
                )
            db.add(AdminUser(user_id=self.accounts["admin"].id))
            self.course = Course(school_id=self.school.id, title="คณิตศาสตร์")
            assign_creator(db, self.course, self.accounts["teacher"])
            db.commit()
        self.path = f"/courses/{self.course.id}/students"

    def request(self, method, path, *, actor="admin", **kwargs):
        return self.client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {self.tokens[actor]}"},
            **kwargs,
        )

    def affiliate(self, name, school_id, role, **overrides):
        return self.request(
            "PATCH",
            f"/admin/users/{self.accounts[name].id}/affiliation",
            json={
                "school_id": str(school_id) if school_id else None,
                "role": role,
                "expected_revision": 2,
                **overrides,
            },
        )

    def enrol(self, name="student", actor="teacher"):
        return self.request(
            "PUT",
            self.path,
            actor=actor,
            json={
                "user_id": str(self.accounts[name].id),
            },
        )

    def course_payload(self, **overrides):
        return {
            "school_id": str(self.school.id),
            "title": "วิทยาศาสตร์",
            "subject": "วิทยาศาสตร์",
            "learning_scope": "ตามเอกสาร",
            **overrides,
        }

    def test_account_school_role_and_admin_are_independent(self):
        result = self.affiliate("unaffiliated", self.school.id, "teacher")
        self.assertEqual(result.status_code, 200, result.text)
        me = self.request("GET", "/me", actor="unaffiliated").json()
        self.assertEqual(me["role"], "teacher")
        self.assertEqual(me["school"]["id"], str(self.school.id))
        self.assertEqual(me["courses"], [])
        self.assertFalse(me["is_admin"])
        self.assertEqual(
            self.request("GET", "/admin/overview", actor="unaffiliated").status_code,
            403,
        )
        users = self.request("GET", "/admin/overview").json()["users"]
        saved = next(
            row for row in users if row["id"] == str(self.accounts["unaffiliated"].id)
        )
        self.assertEqual(saved["membership_revision"], 3)
        self.assertEqual(
            self.affiliate("unaffiliated", None, "student").status_code, 409
        )
        self.assertEqual(
            self.affiliate("student", self.school.id, "admin").status_code, 400
        )
        self.assertEqual(self.affiliate("student", uuid4(), "student").status_code, 404)

    def test_first_course_belongs_only_to_creator(self):
        response = self.request(
            "POST",
            "/courses",
            actor="teacher",
            json=self.course_payload(
                owner_id=str(self.accounts["other_teacher"].id),
            ),
        )
        self.assertEqual(response.status_code, 201, response.text)
        course = response.json()
        self.assertEqual(course["owner_id"], str(self.accounts["teacher"].id))
        self.assertEqual(
            self.request(
                "GET", f"/courses/{course['id']}/students", actor="other_teacher"
            ).status_code,
            403,
        )
        owned = self.request("GET", "/me", actor="teacher").json()["courses"]
        self.assertIn(course["id"], {item["id"] for item in owned})
        self.assertEqual(
            self.request(
                "POST", "/courses", actor="student", json=self.course_payload()
            ).status_code,
            403,
        )
        self.assertEqual(
            self.request(
                "POST",
                "/courses",
                actor="teacher",
                json=self.course_payload(
                    school_id=str(self.other_school.id),
                ),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.request(
                "POST", "/courses", actor="teacher", json=self.course_payload()
            ).status_code,
            409,
        )

    def test_newly_promoted_teacher_can_create_without_existing_course(self):
        self.assertEqual(
            self.affiliate("unaffiliated", self.school.id, "teacher").status_code, 200
        )
        response = self.request(
            "POST", "/courses", actor="unaffiliated", json=self.course_payload()
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(
            response.json()["owner_id"], str(self.accounts["unaffiliated"].id)
        )

    def test_roster_shows_only_eligible_students_and_is_owner_only(self):
        response = self.request("GET", self.path, actor="teacher")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [u["display_name"] for u in response.json()["available"]], ["student"]
        )
        self.assertEqual(
            response.json()["owner"]["id"], str(self.accounts["teacher"].id)
        )
        for name in ["foreign", "unaffiliated", "inactive", "teacher", "other_teacher"]:
            with self.subTest(name=name):
                self.assertEqual(self.enrol(name).status_code, 409)
        self.assertEqual(self.enrol(actor="other_teacher").status_code, 403)
        self.assertEqual(self.enrol(actor="student").status_code, 403)
        self.assertEqual(self.enrol().status_code, 200)
        self.assertEqual(self.enrol().status_code, 200)
        roster = self.request("GET", self.path, actor="teacher").json()
        self.assertEqual(len(roster["students"]), 1)
        self.assertEqual(roster["available"], [])
        self.assertEqual(
            self.request("GET", self.path, actor="student").status_code, 403
        )

    def test_legacy_membership_routes_cannot_grant_roles_or_affiliations(self):
        payload = {
            "course_id": str(self.course.id),
            "user_id": str(self.accounts["foreign"].id),
        }
        self.assertEqual(
            self.request("PUT", "/admin/memberships", json=payload).status_code, 409
        )
        payload["user_id"] = str(self.accounts["student"].id)
        self.assertEqual(
            self.request(
                "PUT", "/admin/memberships", json={**payload, "role": "teacher"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.request("PUT", "/admin/memberships", json=payload).status_code, 200
        )
        response = self.request(
            "DELETE",
            f"/admin/memberships/{self.course.id}/{self.accounts['teacher'].id}",
        )
        self.assertEqual(response.status_code, 404)

    def test_removal_retains_school_and_history_and_cancels_active_quiz(self):
        self.assertEqual(self.enrol().status_code, 200)
        student_id = self.accounts["student"].id
        with Session(self.engine) as db:
            practice = PracticeSession(
                user_id=student_id, course_id=self.course.id, state="line_active"
            )
            db.add(practice)
            db.add(
                UserProfile(
                    user_id=student_id,
                    preferences={
                        "active_course_id": str(self.course.id),
                        "quiet_start": 20,
                    },
                )
            )
            db.commit()
            practice_id = practice.id
        response = self.request("DELETE", f"{self.path}/{student_id}", actor="teacher")
        self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, student_id).school_id, self.school.id)
            member = db.exec(
                select(SchoolMembership).where(SchoolMembership.user_id == student_id)
            ).one()
            self.assertEqual(member.status, "active")
            self.assertEqual(
                db.get(PracticeSession, practice_id).state, "line_cancelled"
            )
            self.assertEqual(
                db.exec(select(UserProfile).where(UserProfile.user_id == student_id))
                .one()
                .preferences,
                {"quiet_start": 20},
            )
        self.assertEqual(
            self.request(
                "GET", f"/courses/{self.course.id}", actor="student"
            ).status_code,
            403,
        )
        self.assertEqual(self.enrol().status_code, 200)

    def test_school_transfer_and_no_affiliation_revoke_access(self):
        self.assertEqual(self.enrol().status_code, 200)
        response = self.affiliate("student", self.other_school.id, "student")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self.request(
                "GET", f"/courses/{self.course.id}", actor="student"
            ).status_code,
            403,
        )
        self.assertEqual(self.enrol().status_code, 409)
        response = self.affiliate("student", None, "student", expected_revision=3)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.request("GET", "/me", actor="student").json()["school"])
        with Session(self.engine) as db:
            member = db.exec(
                select(CourseMembership).where(
                    CourseMembership.user_id == self.accounts["student"].id
                )
            ).one()
            self.assertEqual(member.status, "inactive")

    def test_demoting_owner_revokes_management_without_reassigning_ownership(self):
        self.assertEqual(
            self.affiliate("teacher", self.school.id, "student").status_code, 200
        )
        self.assertEqual(
            self.request("GET", self.path, actor="teacher").status_code, 403
        )
        self.assertEqual(self.enrol("teacher", actor="admin").status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(
                db.get(Course, self.course.id).owner_id, self.accounts["teacher"].id
            )
        self.assertEqual(
            self.affiliate(
                "teacher", self.school.id, "teacher", expected_revision=3
            ).status_code,
            200,
        )
        self.assertEqual(
            self.request("GET", self.path, actor="teacher").status_code, 200
        )

    def test_admin_creation_deletion_and_audit(self):
        response = self.request(
            "POST",
            "/admin/courses",
            json=self.course_payload(school_id=str(self.other_school.id)),
        )
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        self.assertEqual(created["owner_id"], str(self.accounts["admin"].id))
        self.assertEqual(
            self.request("DELETE", f"/admin/courses/{created['id']}").status_code, 200
        )
        self.assertEqual(self.enrol().status_code, 200)
        self.assertEqual(
            self.request("DELETE", f"/admin/courses/{self.course.id}").status_code, 409
        )
        self.assertEqual(
            self.request(
                "DELETE", f"{self.path}/{self.accounts['student'].id}"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.request("DELETE", f"/admin/courses/{self.course.id}").status_code, 200
        )
        with Session(self.engine) as db:
            audit = db.exec(
                select(AuditEvent).where(AuditEvent.action == "admin.course.create")
            ).one()
            self.assertEqual(audit.actor_id, self.accounts["admin"].id)
            self.assertEqual(audit.object_id, UUID(created["id"]))


@unittest.skipUnless(os.getenv("QUIZ_TEST_DATABASE_URL"), "requires PostgreSQL")
class SchoolRosterMigrationTests(unittest.TestCase):
    def test_backfill_prefers_creator_audit_and_does_not_guess_ambiguous_data(self):
        engine = create_engine(os.environ["QUIZ_TEST_DATABASE_URL"])
        self.addCleanup(engine.dispose)
        schema = "roster_migration_" + uuid4().hex
        source = (
            Path(__file__).resolve().parents[1]
            / "alembic/versions/20261107_school_roster.py"
        )
        spec = importlib.util.spec_from_file_location("roster_migration", source)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        school_a, school_b, teacher, student, ambiguous = [uuid4() for _ in range(5)]
        audited, single_teacher, no_owner = [uuid4() for _ in range(3)]
        with engine.connect() as connection, connection.begin():
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(text(f"SET LOCAL search_path = {schema}, public"))
            connection.execute(
                text("""
                CREATE TABLE schools (id uuid PRIMARY KEY);
                CREATE TABLE users (id uuid PRIMARY KEY);
                CREATE TABLE courses (id uuid PRIMARY KEY);
                CREATE TABLE school_memberships (
                    user_id uuid, school_id uuid, role text, status text);
                CREATE TABLE course_memberships (
                    user_id uuid, course_id uuid, role text, status text);
                CREATE TABLE audit_events (
                    id uuid PRIMARY KEY, actor_id uuid, object_id uuid,
                    action text, created_at timestamptz);
            """)
            )
            connection.execute(
                text("INSERT INTO schools VALUES (:a), (:b)"),
                {"a": school_a, "b": school_b},
            )
            connection.execute(
                text("INSERT INTO users VALUES (:id)"),
                [{"id": u} for u in [teacher, student, ambiguous]],
            )
            connection.execute(
                text("INSERT INTO courses VALUES (:id)"),
                [{"id": c} for c in [audited, single_teacher, no_owner]],
            )
            connection.execute(
                text("INSERT INTO school_memberships VALUES (:u, :s, :r, 'active')"),
                [
                    {"u": teacher, "s": school_a, "r": "admin"},
                    {"u": student, "s": school_b, "r": "student"},
                    {"u": ambiguous, "s": school_a, "r": "teacher"},
                    {"u": ambiguous, "s": school_b, "r": "teacher"},
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO course_memberships VALUES (:u, :c, 'teacher', 'active')"
                ),
                [{"u": teacher, "c": c} for c in [audited, single_teacher, no_owner]]
                + [{"u": ambiguous, "c": no_owner}],
            )
            connection.execute(
                text("""
                INSERT INTO audit_events VALUES (:id, :actor, :course, 'course.create', now())
            """),
                {"id": uuid4(), "actor": ambiguous, "course": audited},
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                users = {
                    row.id: row
                    for row in connection.execute(text("SELECT * FROM users"))
                }
                self.assertEqual(users[teacher].school_id, school_a)
                self.assertEqual(users[teacher].role, "teacher")
                self.assertEqual(users[student].school_id, school_b)
                self.assertIsNone(users[ambiguous].school_id)
                owners = dict(
                    connection.execute(text("SELECT id, owner_id FROM courses")).all()
                )
                self.assertEqual(owners[audited], ambiguous)
                self.assertEqual(owners[single_teacher], teacher)
                self.assertIsNone(owners[no_owner])
                self.assertEqual(
                    connection.scalar(
                        text("SELECT role FROM school_memberships WHERE user_id = :id"),
                        {"id": teacher},
                    ),
                    "teacher",
                )
                migration.downgrade()
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM users")), 3
                )
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
