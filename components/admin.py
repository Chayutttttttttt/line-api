"""Global administration. Every endpoint verifies the fixed admin_users allowlist.

Only the one-time trusted Alembic migration can grant the first admin.
No public route grants global-admin rights.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from components.login import require_admin
from db.database import get_session
from db.models import (
    AuditEvent, AuthSession, Course, CourseMembership, School,
    SchoolMembership, User, utc_now,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class SchoolInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("SCHOOL_NAME_REQUIRED")
        return value


class AdminCourseInput(BaseModel):
    school_id: UUID
    title: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    learning_scope: str = Field(min_length=1, max_length=4000)
    response_language: str = Field(default="ไทย", min_length=1, max_length=64)
    grade_level: str | None = Field(default=None, max_length=32)

    @field_validator("title", "subject", "learning_scope", "response_language")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("EMPTY_FIELD")
        return value.strip()


class MembershipInput(BaseModel):
    user_id: UUID
    course_id: UUID
    role: str = Field(pattern="^(student|teacher)$")


class UserStateInput(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")


def log_admin_action(db: Session, actor: User, action: str, object_id: UUID):
    db.add(AuditEvent(actor_id=actor.id, action=action, object_id=object_id))


def school_role(db: Session, school_id: UUID, user_id: UUID) -> str:
    rows = db.exec(select(CourseMembership).where(
        CourseMembership.school_id == school_id, CourseMembership.user_id == user_id,
        CourseMembership.status == "active",
    )).all()
    return "teacher" if any(r.role in ("teacher", "admin") for r in rows) else "student"


def course_record(course: Course):
    return {
        "id": course.id, "school_id": course.school_id, "title": course.title,
        "subject": course.subject, "grade_level": course.grade_level,
        "learning_scope": course.learning_scope,
        "response_language": course.response_language,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_session)):
    users = db.exec(select(User).order_by(User.created_at)).all()
    schools = db.exec(select(School).order_by(School.name)).all()
    courses = db.exec(select(Course).order_by(Course.title)).all()
    school_members = db.exec(select(SchoolMembership)).all()
    course_members = db.exec(select(CourseMembership)).all()
    members_by_school = {}
    for member in school_members:
        members_by_school.setdefault(str(member.school_id), []).append({
            "user_id": member.user_id, "role": member.role, "status": member.status,
        })
    members_by_course = {}
    for member in course_members:
        members_by_course.setdefault(str(member.course_id), []).append({
            "user_id": member.user_id, "role": member.role, "status": member.status,
        })
    return {
        "counts": {"users": len(users), "schools": len(schools), "courses": len(courses)},
        "users": [
            {"id": user.id, "display_name": user.display_name, "status": user.status}
            for user in users
        ],
        "schools": [
            {"id": school.id, "name": school.name, "members": members_by_school.get(str(school.id), [])}
            for school in schools
        ],
        "courses": [
            {**course_record(course), "members": members_by_course.get(str(course.id), [])}
            for course in courses
        ],
    }


@router.post("/schools", status_code=201)
def add_school(data: SchoolInput, user: User = Depends(require_admin),
               db: Session = Depends(get_session)):
    if db.exec(select(School).where(School.name == data.name)).first():
        raise HTTPException(409, "SCHOOL_ALREADY_EXISTS")
    school = School(name=data.name)
    db.add(school); db.flush()
    log_admin_action(db, user, "admin.school.create", school.id)
    db.commit()
    return {"id": school.id, "name": school.name}


@router.patch("/schools/{school_id}")
def rename_school(school_id: UUID, data: SchoolInput, user: User = Depends(require_admin),
                  db: Session = Depends(get_session)):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "SCHOOL_NOT_FOUND")
    other = db.exec(select(School).where(School.name == data.name, School.id != school_id)).first()
    if other:
        raise HTTPException(409, "SCHOOL_ALREADY_EXISTS")
    school.name = data.name
    db.add(school)
    log_admin_action(db, user, "admin.school.rename", school.id)
    db.commit()
    return {"id": school.id, "name": school.name}


@router.delete("/schools/{school_id}")
def delete_empty_school(school_id: UUID, user: User = Depends(require_admin),
                        db: Session = Depends(get_session)):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "SCHOOL_NOT_FOUND")
    if (db.exec(select(Course.id).where(Course.school_id == school_id)).first()
        or db.exec(select(SchoolMembership.id).where(SchoolMembership.school_id == school_id)).first()):
        raise HTTPException(409, "SCHOOL_NOT_EMPTY")
    db.delete(school)
    log_admin_action(db, user, "admin.school.delete", school_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SCHOOL_HAS_REFERENCES") from None
    return {"deleted": True}


@router.post("/courses", status_code=201)
def add_course(data: AdminCourseInput, user: User = Depends(require_admin),
               db: Session = Depends(get_session)):
    if not db.get(School, data.school_id):
        raise HTTPException(404, "SCHOOL_NOT_FOUND")
    if db.exec(select(Course).where(Course.school_id == data.school_id, Course.title == data.title)).first():
        raise HTTPException(409, "COURSE_ALREADY_EXISTS")
    course = Course(**data.model_dump())
    db.add(course); db.flush()
    log_admin_action(db, user, "admin.course.create", course.id)
    db.commit()
    return course_record(course)


@router.delete("/courses/{course_id}")
def delete_empty_course(course_id: UUID, user: User = Depends(require_admin),
                        db: Session = Depends(get_session)):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "COURSE_NOT_FOUND")
    if db.exec(select(CourseMembership.id).where(CourseMembership.course_id == course_id)).first():
        raise HTTPException(409, "COURSE_HAS_MEMBERS")
    db.delete(course)
    log_admin_action(db, user, "admin.course.delete", course_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "COURSE_HAS_REFERENCES") from None
    return {"deleted": True}


@router.put("/memberships")
def set_membership(data: MembershipInput, user: User = Depends(require_admin),
                   db: Session = Depends(get_session)):
    member_user = db.get(User, data.user_id)
    course = db.get(Course, data.course_id)
    if not member_user or member_user.status != "active":
        raise HTTPException(404, "ACTIVE_USER_NOT_FOUND")
    if not course:
        raise HTTPException(404, "COURSE_NOT_FOUND")
    school_member = db.exec(select(SchoolMembership).where(
        SchoolMembership.user_id == data.user_id,
        SchoolMembership.school_id == course.school_id,
    )).first()
    if not school_member:
        school_member = SchoolMembership(
            school_id=course.school_id, user_id=data.user_id, role=data.role,
        )
        db.add(school_member)
        db.flush()
    course_member = db.exec(select(CourseMembership).where(
        CourseMembership.course_id == course.id,
        CourseMembership.user_id == data.user_id,
    )).first()
    if not course_member:
        course_member = CourseMembership(
            user_id=data.user_id, school_id=course.school_id, course_id=course.id,
            role=data.role,
        )
    else:
        course_member.role = data.role
        course_member.status = "active"
    db.add(course_member)
    db.flush()
    school_member.role = school_role(db, course.school_id, data.user_id)
    school_member.status = "active"
    db.add(school_member)
    log_admin_action(db, user, "admin.membership.upsert", course.id)
    db.commit()
    return {"user_id": data.user_id, "course_id": course.id, "role": data.role}


@router.delete("/memberships/{course_id}/{user_id}")
def remove_membership(course_id: UUID, user_id: UUID, user: User = Depends(require_admin),
                      db: Session = Depends(get_session)):
    cm = db.exec(select(CourseMembership).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
    )).first()
    if not cm:
        raise HTTPException(404, "MEMBERSHIP_NOT_FOUND")
    school_id = cm.school_id
    db.delete(cm)
    db.flush()
    school_member = db.exec(select(SchoolMembership).where(
        SchoolMembership.school_id == school_id,
        SchoolMembership.user_id == user_id,
    )).first()
    remaining = db.exec(select(CourseMembership).where(
        CourseMembership.school_id == school_id,
        CourseMembership.user_id == user_id,
    )).all()
    if school_member:
        if remaining:
            school_member.role = school_role(db, school_id, user_id)
            db.add(school_member)
        else:
            db.delete(school_member)
    log_admin_action(db, user, "admin.membership.remove", course_id)
    db.commit()
    return {"removed": True}


@router.patch("/users/{user_id}/status")
def update_user_status(user_id: UUID, data: UserStateInput,
                       user: User = Depends(require_admin),
                       db: Session = Depends(get_session)):
    if user_id == user.id:
        raise HTTPException(403, "CANNOT_DISABLE_OWN_ADMIN_ACCOUNT")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "USER_NOT_FOUND")
    target.status = data.status
    target.updated_at = utc_now()
    db.add(target)
    if data.status == "inactive":
        for session in db.exec(select(AuthSession).where(AuthSession.user_id == user_id)).all():
            db.delete(session)
    log_admin_action(db, user, "admin.user.status", user_id)
    db.commit()
    return {"user_id": user_id, "status": target.status}
