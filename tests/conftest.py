"""Disposable PostgreSQL/pgvector only. Never use DATABASE_URL from the user's .env."""
import hashlib
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import pgserver
import pytest

_test_root = Path(tempfile.mkdtemp(prefix="line-math-tests-"))
_server = pgserver.get_server(_test_root / "pgdata")
os.environ["DATABASE_URL"] = _server.get_uri()
os.environ["STORAGE_BACKEND"] = "local"
os.environ["FILE_STORAGE_ROOT"] = str(_test_root / "files")
os.environ["AI_ENABLED"] = "false"
os.environ["CHANNEL_SECRET"] = "test-channel-secret"
os.environ["LINE_CHANNEL_ID"] = "test-channel"
os.environ["LINE_PROVIDER_ID"] = "test-provider"
os.environ["LINE_LOGIN_CHANNEL_ID"] = "test-login-channel"
os.environ["CHANNEL_ACCESS_TOKEN"] = "test-access-token"

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session
from db.database import engine
from db.migrate import main as migrate
from db.models import (AuthSession, Course, CourseMembership, LineIdentity, School, SchoolMembership,
    Topic, User, utc_now)
from main import app, recent
from datetime import timedelta


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    migrate()
    yield
    engine.dispose()


@pytest.fixture()
def context(migrated_database):
    with engine.begin() as connection:
        tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename != 'alembic_version'"))
        names = [row[0] for row in tables]
        connection.execute(text("TRUNCATE " + ", ".join('"' + n + '"' for n in names) + " CASCADE"))
    recent.clear()
    with Session(engine) as db:
        school, other_school = School(name="Test school"), School(name="Other school")
        db.add_all([school, other_school]); db.flush()
        course = Course(school_id=school.id, title="ความสัมพันธ์และฟังก์ชัน", subject="คณิตศาสตร์",
            learning_scope="โดเมน เรนจ์ และการเป็นฟังก์ชันจากเซตคู่อันดับจำนวนเต็ม", evaluation_profile="relations-pilot")
        db.add(course); db.flush()
        topic = Topic(course_id=course.id, title="โดเมน")
        db.add(topic)
        result = {"course": course.id, "school": school.id, "topic": topic.id}
        for name, role, school_id in [("teacher", "teacher", school.id), ("student", "student", school.id),
                ("peer", "student", school.id), ("outsider", "teacher", other_school.id)]:
            user = User(display_name=name)
            db.add(user); db.flush()
            db.add(SchoolMembership(school_id=school_id, user_id=user.id, role=role))
            db.flush()
            if name != "outsider":
                db.add(CourseMembership(school_id=school.id, course_id=course.id, user_id=user.id, role=role))
            token = f"session-{name}"
            db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                expires_at=utc_now() + timedelta(hours=1)))
            db.add(LineIdentity(user_id=user.id, provider_id="test-provider", line_sub=f"line-{name}"))
            result[name] = user.id
            result[f"{name}_headers"] = {"Authorization": f"Bearer {token}"}
        db.commit()
    with TestClient(app) as client:
        result["client"] = client
        yield result
