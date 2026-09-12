from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)

    line_user_id: str = Field(
        index=True,
        unique=True,
        max_length=64
    )

    display_name: str | None = Field(default=None,max_length=256)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    preferences: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB)
    )

    profile_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)

    conversation_id: int = Field(
        foreign_key="conversations.id",
        index=True
    )

    role: str = Field(max_length=20)

    content: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
