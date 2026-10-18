"""Trusted operator CLI. No public endpoint can grant a teacher role."""
import argparse
from uuid import UUID

from fastapi import UploadFile
from sqlmodel import Session, select

from components.documents import upload_document
from db.database import engine
from db.models import Course, CourseMembership, LineIdentity, School, SchoolMembership, Topic, User


def deletion_ledger(db):
    from db.models import AuditEvent
    rows = db.exec(select(AuditEvent).where(AuditEvent.action.like("data.deleted.%"))).all()
    return [{"user_id": str(r.actor_id), "scope": r.action.removeprefix("data.deleted."),
        "request_id": str(r.request_id)} for r in rows]


def replay_deletions(db, records):
    from components.learning import DeleteRequest, delete_data
    count = 0
    for record in records:
        user = db.get(User, UUID(record["user_id"]))
        if user:
            delete_data(DeleteRequest(deletion_scope=record["scope"]), user=user, db=db)
            count += 1
    return count


def add_membership(db, user, course, role):
    school_member = db.exec(select(SchoolMembership).where(SchoolMembership.user_id == user.id,
        SchoolMembership.school_id == course.school_id)).first()
    if not school_member:
        db.add(SchoolMembership(user_id=user.id, school_id=course.school_id, role=role))
    elif role in {"teacher", "admin"}:
        school_member.role, school_member.status = role, "active"
        db.add(school_member)
    elif school_member.status != "active":
        school_member.status = "active"
        db.add(school_member)
    db.flush()
    member = db.exec(select(CourseMembership).where(CourseMembership.user_id == user.id,
        CourseMembership.course_id == course.id)).first()
    if member:
        member.role, member.status = role, "active"
        db.add(member)
    else:
        db.add(CourseMembership(user_id=user.id, school_id=course.school_id, course_id=course.id, role=role))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--teacher-user-id", type=UUID, required=True)
    bootstrap.add_argument("--school", required=True)
    bootstrap.add_argument("--course", required=True)
    member = sub.add_parser("add-member")
    member.add_argument("--user-id", type=UUID, required=True)
    member.add_argument("--course-id", type=UUID, required=True)
    member.add_argument("--role", choices=["student", "teacher"], default="student")
    upload = sub.add_parser("import-document")
    upload.add_argument("--user-id", type=UUID, required=True)
    upload.add_argument("--course-id", type=UUID, required=True)
    upload.add_argument("--file", required=True)
    upload.add_argument("--title", required=True)
    upload.add_argument("--purpose", choices=["teaching", "evidence"], required=True)
    export = sub.add_parser("export-deletions")
    export.add_argument("--output", required=True)
    replay = sub.add_parser("replay-deletions")
    replay.add_argument("--file", required=True)
    args = parser.parse_args()
    with Session(engine, expire_on_commit=False) as db:
        if args.command in {"export-deletions", "replay-deletions"}:
            import json
            from pathlib import Path
            if args.command == "export-deletions":
                path = Path(args.output)
                path.write_text(json.dumps(deletion_ledger(db), ensure_ascii=False, indent=2))
                path.chmod(0o600)
                print("Deletion ledger exported; keep it outside the database backup")
            else:
                records = json.loads(Path(args.file).read_text())
                print(f"Reapplied {replay_deletions(db, records)} deletion records")
            return
        user_id = args.teacher_user_id if args.command == "bootstrap" else args.user_id
        user = db.get(User, user_id)
        if not user or user.status != "active":
            parser.error("User must sign in with verified LINE login first; use the UUID shown by /me")
        if args.command == "bootstrap":
            school = db.exec(select(School).where(School.name == args.school)).first()
            if not school:
                school = School(name=args.school)
                db.add(school); db.flush()
            course = db.exec(select(Course).where(Course.school_id == school.id, Course.title == args.course)).first()
            if not course:
                course = Course(school_id=school.id, title=args.course)
                db.add(course); db.flush()
                for title in ("โดเมน", "เรนจ์", "การเป็นฟังก์ชัน"):
                    db.add(Topic(course_id=course.id, title=title))
            add_membership(db, user, course, "teacher")
            db.commit()
            print(f"course_id={course.id} school_id={school.id}")
        elif args.command == "add-member":
            course = db.get(Course, args.course_id)
            if not course:
                parser.error("Course not found")
            add_membership(db, user, course, args.role)
            db.commit()
            print("Membership saved")
        else:
            from pathlib import Path
            path = Path(args.file)
            with path.open("rb") as file:
                result = upload_document(course_id=args.course_id, title=args.title,
                    purpose=args.purpose, document_id=None, file=UploadFile(filename=path.name, file=file), user=user, db=db)
            print(result)


if __name__ == "__main__":
    main()
