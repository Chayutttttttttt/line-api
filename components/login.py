"""Verify LINE ID tokens and issue revocable, hashed bearer sessions."""

import hashlib
import logging
import secrets
from datetime import timedelta
from uuid import UUID

import requests
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from config import LINE_LOGIN_CHANNEL_ID, LINE_PROVIDER_ID, SESSION_TTL_SECONDS
from db.database import get_session
from db.models import (
    AdminUser,
    AuthSession,
    Course,
    CourseMembership,
    LineIdentity,
    School,
    SchoolMembership,
    User,
    utc_now,
)

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=8192)


def current_user(
    authorization: str | None = Header(None), db: Session = Depends(get_session)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "UNAUTHENTICATED")
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    auth = db.get(AuthSession, digest)
    if not auth or auth.expires_at <= utc_now():
        raise HTTPException(401, "SESSION_EXPIRED")
    user = db.get(User, auth.user_id)
    if not user or user.status != "active":
        raise HTTPException(403, "ACCOUNT_INACTIVE")
    return user


def is_global_admin(db: Session, user_id: UUID) -> bool:
    return db.get(AdminUser, user_id) is not None


def require_admin(
    user: User = Depends(current_user), db: Session = Depends(get_session)
) -> User:
    if not is_global_admin(db, user.id):
        raise HTTPException(403, "ADMIN_REQUIRED")
    return user


def course_access(
    db: Session, user: User, course_id: UUID, teacher: bool = False
) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "COURSE_NOT_FOUND")
    if user.status != "active":
        raise HTTPException(403, "ACCOUNT_INACTIVE")
    if is_global_admin(db, user.id):
        return course
    if user.school_id != course.school_id:
        raise HTTPException(403, "COURSE_FORBIDDEN")
    cm = db.exec(
        select(CourseMembership).where(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user.id,
            CourseMembership.status == "active",
        )
    ).first()
    sm = db.exec(
        select(SchoolMembership).where(
            SchoolMembership.school_id == course.school_id,
            SchoolMembership.user_id == user.id,
            SchoolMembership.status == "active",
        )
    ).first()
    owner = user.role == "teacher" and course.owner_id == user.id
    student = (
        user.role == "student"
        and cm
        and cm.role == "student"
        and cm.school_id == course.school_id
    )
    if not sm or sm.role != user.role or not (owner or student):
        raise HTTPException(403, "COURSE_FORBIDDEN")
    if teacher and not owner:
        raise HTTPException(403, "TEACHER_REQUIRED")
    return course


@router.post("/auth/line")
def line_login(data: LoginRequest, db: Session = Depends(get_session)):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_PROVIDER_ID:
        raise HTTPException(503, "LINE_LOGIN_NOT_CONFIGURED")
    try:
        response = requests.post(
            "https://api.line.me/oauth2/v2.1/verify",
            data={"id_token": data.id_token, "client_id": LINE_LOGIN_CHANNEL_ID},
            timeout=10,
        )
        if response.status_code != 200:
            details = response.json()
            logging.warning(
                "LINE verify failed: status=%s reason=%s",
                response.status_code,
                details.get("error_description", "Unknown"),
            )
            raise HTTPException(401, "INVALID_LINE_TOKEN")
        claims = response.json()
        if (
            claims.get("iss") != "https://access.line.me"
            or str(claims.get("aud")) != LINE_LOGIN_CHANNEL_ID
            or not isinstance(claims.get("exp"), (int, float))
            or claims["exp"] <= utc_now().timestamp()
            or not claims.get("sub")
        ):
            details = response.json()
            logging.warning(
                "LINE verify failed: status=%s reason=%s",
                response.status_code,
                details.get("error_description", "Unknown"),
            )
            raise HTTPException(401, "INVALID_LINE_TOKEN")
    except (requests.RequestException, ValueError):
        raise HTTPException(503, "LINE_TEMPORARILY_UNAVAILABLE") from None
    # Serialize first login for this identity without exposing tokens in logs.
    from sqlalchemy import text

    identity_key = f"{LINE_PROVIDER_ID}:{claims['sub']}"
    db.exec(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        params={"key": identity_key},
    )
    identity = db.exec(
        select(LineIdentity).where(
            LineIdentity.provider_id == LINE_PROVIDER_ID,
            LineIdentity.line_sub == claims["sub"],
        )
    ).first()
    if identity:
        user = db.get(User, identity.user_id)
    else:
        user = User(display_name=str(claims.get("name", ""))[:255])
        db.add(user)
        db.flush()
        db.add(
            LineIdentity(
                user_id=user.id, provider_id=LINE_PROVIDER_ID, line_sub=claims["sub"]
            )
        )
    if user.status != "active":
        raise HTTPException(403, "ACCOUNT_INACTIVE")
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=utc_now() + timedelta(seconds=SESSION_TTL_SECONDS),
        )
    )
    db.commit()
    return {
        "received": True,
        "access_token": token,
        "token_type": "bearer",
        "expires_in": SESSION_TTL_SECONDS,
    }


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_session)):
    admin = is_global_admin(db, user.id)
    memberships = (
        db.exec(
            select(CourseMembership).where(
                CourseMembership.user_id == user.id, CourseMembership.status == "active"
            )
        ).all()
        if not admin
        else []
    )
    courses = []
    if admin:
        for course in db.exec(select(Course).order_by(Course.title)).all():
            courses.append(
                {
                    "id": course.id,
                    "title": course.title,
                    "role": "admin",
                    "school_id": course.school_id,
                    "subject": course.subject,
                }
            )
    course_ids = {membership.course_id for membership in memberships}
    if not admin and user.role == "teacher":
        course_ids.update(
            db.exec(select(Course.id).where(Course.owner_id == user.id)).all()
        )
    for course_id in course_ids:
        try:
            course = course_access(db, user, course_id)
        except HTTPException:
            continue
        courses.append(
            {
                "id": course.id,
                "title": course.title,
                "role": user.role,
                "school_id": course.school_id,
                "subject": course.subject,
            }
        )
    courses.sort(key=lambda course: (course["title"], str(course["id"])))
    school = db.get(School, user.school_id) if user.school_id else None
    from db.models import UserProfile

    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    selected = profile.preferences.get("active_course_id") if profile else None
    if selected not in {str(c["id"]) for c in courses}:
        selected = None
    return {
        "id": user.id,
        "display_name": user.display_name,
        "timezone": user.timezone,
        "courses": courses,
        "active_course_id": selected,
        "is_admin": admin,
        "role": user.role,
        "school": {"id": school.id, "name": school.name} if school else None,
    }


@router.post("/auth/logout")
def logout(
    user: User = Depends(current_user),
    authorization: str = Header(),
    db: Session = Depends(get_session),
):
    auth = db.get(AuthSession, hashlib.sha256(authorization[7:].encode()).hexdigest())
    db.delete(auth)
    db.commit()
    return {"logged_out": True}
