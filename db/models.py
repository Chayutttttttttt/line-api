# db/models.py

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field

# ถ้าจะใช้ RAG + pgvector
from pgvector.sqlalchemy import Vector


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# USER
# =========================================================

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    display_name: str | None = Field(
        default=None,
        max_length=255
    )

    timezone: str = Field(
        default="Asia/Bangkok",
        max_length=64
    )

    status: str = Field(
        default="active",
        max_length=32
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# USER PROFILE
# =========================================================

class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        unique=True,
        index=True
    )

    preferences: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    profile_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# LINE IDENTITY
# =========================================================

class LineIdentity(SQLModel, table=True):
    __tablename__ = "line_identities"

    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "line_sub",
            name="uq_line_provider_sub"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    provider_id: str = Field(
        max_length=255
    )

    line_sub: str = Field(
        max_length=255
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# SCHOOL
# =========================================================

class School(SQLModel, table=True):
    __tablename__ = "schools"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    name: str = Field(
        max_length=255
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class SchoolMembership(SQLModel, table=True):
    __tablename__ = "school_memberships"

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "user_id",
            name="uq_school_user"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    school_id: UUID = Field(
        foreign_key="schools.id",
        index=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    role: str = Field(
        max_length=32
    )

    status: str = Field(
        default="active",
        max_length=32
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# COURSE
# =========================================================

class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    school_id: UUID = Field(
        foreign_key="schools.id",
        index=True
    )

    title: str = Field(
        max_length=255
    )

    grade_level: str | None = Field(
        default=None,
        max_length=32
    )

    term: str | None = Field(
        default=None,
        max_length=32
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CourseMembership(SQLModel, table=True):
    __tablename__ = "course_memberships"

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "user_id",
            name="uq_course_user"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    school_id: UUID = Field(
        foreign_key="schools.id"
    )

    course_id: UUID = Field(
        foreign_key="courses.id",
        index=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    role: str = Field(
        max_length=32
    )

    status: str = Field(
        default="active",
        max_length=32
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# TOPIC
# =========================================================

class Topic(SQLModel, table=True):
    __tablename__ = "topics"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    course_id: UUID = Field(
        foreign_key="courses.id",
        index=True
    )

    title: str = Field(
        max_length=255
    )

    prerequisite_id: UUID | None = Field(
        default=None,
        foreign_key="topics.id"
    )


# =========================================================
# DOCUMENT / RAG
# =========================================================

class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    school_id: UUID = Field(
        foreign_key="schools.id"
    )

    course_id: UUID = Field(
        foreign_key="courses.id",
        index=True
    )

    title: str = Field(
        max_length=255
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class DocumentVersion(SQLModel, table=True):
    __tablename__ = "document_versions"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version",
            name="uq_document_version"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    document_id: UUID = Field(
        foreign_key="documents.id",
        index=True
    )

    version: int

    status: str = Field(
        default="uploaded",
        max_length=32
    )

    storage_key: str

    checksum: str = Field(
        max_length=128
    )

    approved_by: UUID | None = Field(
        default=None,
        foreign_key="users.id"
    )

    approved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "ordinal",
            name="uq_version_chunk"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    version_id: UUID = Field(
        foreign_key="document_versions.id",
        index=True
    )

    ordinal: int

    page_no: int | None = None

    text: str

    # เปลี่ยน dimension ให้ตรงกับ embedding model ที่ใช้จริง
    embedding: Any | None = Field(
        default=None,
        sa_column=Column(Vector(768))
    )

    embedding_model: str | None = Field(
        default=None,
        max_length=255
    )


# =========================================================
# QUESTIONS
# =========================================================

class Question(SQLModel, table=True):
    __tablename__ = "questions"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "version",
            name="uq_question_version"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    topic_id: UUID = Field(
        foreign_key="topics.id",
        index=True
    )

    version: int = 1

    answer_type: str = Field(
        max_length=64
    )

    grading_spec: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    rubric: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    status: str = Field(
        default="draft",
        max_length=32
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# PRACTICE
# =========================================================

class PracticeSession(SQLModel, table=True):
    __tablename__ = "practice_sessions"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    course_id: UUID = Field(
        foreign_key="courses.id",
        index=True
    )

    state: str = Field(
        default="active",
        max_length=32
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PracticeSessionItem(SQLModel, table=True):
    __tablename__ = "practice_session_items"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    session_id: UUID = Field(
        foreign_key="practice_sessions.id",
        index=True
    )

    question_id: UUID = Field(
        foreign_key="questions.id"
    )

    question_version: int

    served_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "submission_id",
            name="uq_user_submission"
        ),
        CheckConstraint(
            "score >= 0",
            name="ck_attempt_score_min"
        ),
        CheckConstraint(
            "max_score >= 0",
            name="ck_attempt_max_score"
        ),
        CheckConstraint(
            "score <= max_score",
            name="ck_attempt_score_max"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    session_id: UUID = Field(
        foreign_key="practice_sessions.id",
        index=True
    )

    question_id: UUID = Field(
        foreign_key="questions.id"
    )

    question_version: int

    answer: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    score: float = 0

    max_score: float = 1

    hints_used: int = 0

    submission_id: UUID = Field(
        default_factory=uuid4
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# TASK
# =========================================================

class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    owner_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    course_id: UUID | None = Field(
        default=None,
        foreign_key="courses.id"
    )

    title: str = Field(
        max_length=255
    )

    due_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    state: str = Field(
        default="pending",
        max_length=32
    )

    revision: int = 1

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# LEARNING PLAN
# =========================================================

class LearningPlan(SQLModel, table=True):
    __tablename__ = "learning_plans"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    start_date: date

    end_date: date

    state: str = Field(
        default="draft",
        max_length=32
    )

    revision: int = 1

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PlanItem(SQLModel, table=True):
    __tablename__ = "plan_items"

    __table_args__ = (
        CheckConstraint(
            "minutes > 0",
            name="ck_plan_minutes_positive"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    plan_id: UUID = Field(
        foreign_key="learning_plans.id",
        index=True
    )

    topic_id: UUID = Field(
        foreign_key="topics.id"
    )

    scheduled_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    minutes: int

    state: str = Field(
        default="pending",
        max_length=32
    )

    revision: int = 1


# =========================================================
# REMINDER
# =========================================================

class Reminder(SQLModel, table=True):
    __tablename__ = "reminders"

    __table_args__ = (
        CheckConstraint(
            """
            (task_id IS NOT NULL AND plan_item_id IS NULL)
            OR
            (task_id IS NULL AND plan_item_id IS NOT NULL)
            """,
            name="ck_reminder_source"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    task_id: UUID | None = Field(
        default=None,
        foreign_key="tasks.id"
    )

    plan_item_id: UUID | None = Field(
        default=None,
        foreign_key="plan_items.id"
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    remind_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    enabled: bool = True

    source_revision: int = 1

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# CONVERSATION
# =========================================================

class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    owner_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    conversation_id: UUID = Field(
        foreign_key="conversations.id",
        index=True
    )

    owner_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    role: str = Field(
        max_length=32
    )

    text: str

    line_message_id: str | None = Field(
        default=None,
        max_length=255
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )


# =========================================================
# WEBHOOK
# =========================================================

class WebhookEvent(SQLModel, table=True):
    __tablename__ = "webhook_events"

    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "event_id",
            name="uq_channel_event"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    channel_id: str = Field(
        max_length=255
    )

    event_id: str = Field(
        max_length=255
    )

    state: str = Field(
        default="received",
        max_length=32
    )

    attempts: int = 0

    lease_until: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    next_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# JOB
# =========================================================

class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    webhook_event_id: UUID | None = Field(
        default=None,
        foreign_key="webhook_events.id",
        index=True
    )

    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id"
    )

    kind: str = Field(
        default="ai_response",
        max_length=64
    )

    state: str = Field(
        default="queued",
        max_length=32
    )

    attempts: int = 0

    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    lease_until: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    next_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# MESSAGE OUTBOX
# =========================================================

class MessageOutbox(SQLModel, table=True):
    __tablename__ = "message_outbox"

    __table_args__ = (
        UniqueConstraint(
            "retry_key",
            name="uq_outbox_retry_key"
        ),
        UniqueConstraint(
            "logical_message_key",
            name="uq_logical_message"
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    kind: str = Field(
        max_length=32
    )

    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    state: str = Field(
        default="pending",
        max_length=32
    )

    retry_key: str = Field(
        max_length=255
    )

    logical_message_key: str = Field(
        max_length=255
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    sent_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )


# =========================================================
# AUDIT
# =========================================================

class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    actor_id: UUID | None = Field(
        default=None,
        foreign_key="users.id"
    )

    action: str = Field(
        max_length=128
    )

    object_id: UUID | None = None

    request_id: UUID = Field(
        default_factory=uuid4,
        index=True
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


# =========================================================
# FEEDBACK
# =========================================================

class FeedbackReport(SQLModel, table=True):
    __tablename__ = "feedback_reports"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    reporter_id: UUID = Field(
        foreign_key="users.id",
        index=True
    )

    message_id: UUID = Field(
        foreign_key="messages.id"
    )

    category: str = Field(
        max_length=64
    )

    detail: str

    status: str = Field(
        default="open",
        max_length=32
    )

    assignee_id: UUID | None = Field(
        default=None,
        foreign_key="users.id"
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )