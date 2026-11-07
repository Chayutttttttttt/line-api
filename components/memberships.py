"""Account affiliation and student enrolment shared by admin, teachers and CLI."""

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from db.models import (
    Course,
    CourseMembership,
    PracticeSession,
    School,
    SchoolMembership,
    User,
    UserProfile,
    utc_now,
)


def lock_user(db: Session, user_id: UUID) -> User:
    """Serialize affiliation changes with enrolment and worker final commits."""
    user = db.exec(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if not user or user.status == "deleted":
        raise HTTPException(404, "USER_NOT_FOUND")
    return user


def school_membership(db: Session, user: User) -> SchoolMembership:
    member = db.exec(
        select(SchoolMembership).where(
            SchoolMembership.school_id == user.school_id,
            SchoolMembership.user_id == user.id,
        )
    ).first()
    if not member:
        member = SchoolMembership(
            school_id=user.school_id,
            user_id=user.id,
            role=user.role,
        )
    member.role, member.status = user.role, "active"
    db.add(member)
    db.flush()
    return member


def enrol(db: Session, user: User, course: Course, role: str):
    member = db.exec(
        select(CourseMembership).where(
            CourseMembership.course_id == course.id,
            CourseMembership.user_id == user.id,
        )
    ).first()
    if not member:
        member = CourseMembership(
            user_id=user.id,
            course_id=course.id,
            school_id=course.school_id,
            role=role,
        )
    member.role, member.status = role, "active"
    db.add(member)


def clear_course_activity(db: Session, user_id: UUID, course_ids: set[UUID]):
    if not course_ids:
        return
    for practice in db.exec(
        select(PracticeSession).where(
            PracticeSession.user_id == user_id,
            PracticeSession.course_id.in_(course_ids),
            PracticeSession.state == "line_active",
        )
    ).all():
        practice.state = "line_cancelled"
        db.add(practice)
    profile = db.exec(
        select(UserProfile).where(
            UserProfile.user_id == user_id,
        )
    ).first()
    if profile and profile.preferences.get("active_course_id") in {
        str(course_id) for course_id in course_ids
    }:
        profile.preferences = {
            key: value
            for key, value in profile.preferences.items()
            if key != "active_course_id"
        }
        db.add(profile)


def set_affiliation(db: Session, user: User, school_id: UUID | None, role: str):
    """Caller must lock the user; history is retained when access is revoked."""
    if role not in {"student", "teacher"}:
        raise HTTPException(400, "INVALID_ROLE")
    if school_id and not db.get(School, school_id):
        raise HTTPException(404, "SCHOOL_NOT_FOUND")
    user.school_id, user.role = school_id, role
    user.membership_revision += 1
    user.updated_at = utc_now()
    db.add(user)
    for member in db.exec(
        select(SchoolMembership).where(
            SchoolMembership.user_id == user.id,
        )
    ).all():
        member.status = "inactive"
        db.add(member)
    if school_id:
        school_membership(db, user)
    owned = db.exec(select(Course).where(Course.owner_id == user.id)).all()
    owner_ids = {course.id for course in owned}
    revoked = set()
    for member in db.exec(
        select(CourseMembership).where(
            CourseMembership.user_id == user.id,
            CourseMembership.status == "active",
        )
    ).all():
        allowed = member.school_id == school_id and (
            (
                role == "student"
                and member.role == "student"
                and member.course_id not in owner_ids
            )
            or (role == "teacher" and member.course_id in owner_ids)
        )
        if not allowed:
            member.status = "inactive"
            revoked.add(member.course_id)
            db.add(member)
    if role == "teacher" and school_id:
        for course in owned:
            if course.school_id == school_id:
                enrol(db, user, course, "teacher")
    clear_course_activity(db, user.id, revoked)


def add_student(db: Session, course: Course, user_id: UUID) -> User:
    user = lock_user(db, user_id)
    if (
        user.status != "active"
        or user.role != "student"
        or user.school_id != course.school_id
        or user.id == course.owner_id
    ):
        raise HTTPException(409, "STUDENT_SCHOOL_REQUIRED")
    school_membership(db, user)
    enrol(db, user, course, "student")
    return user


def remove_student(db: Session, course: Course, user_id: UUID):
    lock_user(db, user_id)
    member = db.exec(
        select(CourseMembership).where(
            CourseMembership.course_id == course.id,
            CourseMembership.user_id == user_id,
        )
    ).first()
    if not member or member.role != "student" or user_id == course.owner_id:
        raise HTTPException(404, "STUDENT_MEMBERSHIP_NOT_FOUND")
    db.delete(member)
    clear_course_activity(db, user_id, {course.id})


def assign_creator(db: Session, course: Course, user: User):
    course.owner_id = user.id
    db.add(course)
    db.flush()
    # Global admins may create outside their own school without changing it.
    if user.school_id == course.school_id and user.role == "teacher":
        school_membership(db, user)
        enrol(db, user, course, "teacher")
