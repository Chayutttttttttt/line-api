"""Student tasks, deterministic practice and explicitly activated study plans."""
from datetime import date, datetime, time, timedelta
import hashlib
import json
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import delete, text
from sqlmodel import Session, select

from components.documents import RevisionRequest
from components.grading import AnswerType, grade, student_answer_config, validate_spec
from components.login import course_access, current_user
from db.database import get_session
from db.models import (Attempt, AuditEvent, AuthSession, Conversation, DocumentVersion, FeedbackReport,
    Course, CourseMembership, SchoolMembership, IdempotencyRecord, Job, LearningPlan, LineIdentity, Message, MessageOutbox, PlanItem,
    PracticeSession, PracticeSessionItem, Question, Reminder, Task, Topic, User, UserProfile, utc_now)

router = APIRouter(tags=["learning"])


class CourseSettings(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    learning_scope: str = Field(min_length=1, max_length=4000)
    response_language: str = Field(default="ไทย", min_length=1, max_length=64)
    grade_level: str | None = Field(default=None, max_length=32)

    @field_validator("title", "subject", "learning_scope", "response_language")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()


class CourseCreate(CourseSettings):
    school_id: UUID


class CourseUpdate(CourseSettings):
    expected_revision: int = Field(ge=1)


def course_info(course):
    return course.model_dump(exclude={"evaluation_overrides"})


@router.post("/courses", status_code=201)
def create_course(data: CourseCreate, user: User = Depends(current_user), db: Session = Depends(get_session)):
    membership = db.exec(select(SchoolMembership).where(SchoolMembership.school_id == data.school_id,
        SchoolMembership.user_id == user.id, SchoolMembership.status == "active",
        SchoolMembership.role.in_(["teacher", "admin"]))).first()
    if not membership:
        raise HTTPException(403, "SCHOOL_TEACHER_REQUIRED")
    course = Course(**data.model_dump())
    db.add(course); db.flush()
    db.add(CourseMembership(school_id=course.school_id, course_id=course.id, user_id=user.id, role="teacher"))
    db.add(AuditEvent(actor_id=user.id, action="course.create", object_id=course.id))
    db.commit()
    return course_info(course)


@router.get("/courses/{course_id}")
def get_course(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    return course_info(course_access(db, user, course_id))


def lock_course(db, user, course_id, expected_revision):
    course_access(db, user, course_id, True)
    course = db.exec(select(Course).where(Course.id == course_id).with_for_update().execution_options(populate_existing=True)).one()
    if course.revision != expected_revision:
        raise HTTPException(409, "REVISION_CONFLICT")
    return course


@router.put("/courses/{course_id}")
def update_course(course_id: UUID, data: CourseUpdate, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course = lock_course(db, user, course_id, data.expected_revision)
    for key, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(course, key, value)
    course.revision += 1
    course.evaluation_profile, course.evaluation_overrides = "general", {}
    db.add(course)
    db.add(AuditEvent(actor_id=user.id, action="course.configure", object_id=course.id))
    db.commit()
    return course_info(course)


class TopicRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    expected_revision: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def title_nonblank(cls, value):
        if not value.strip():
            raise ValueError("Title required")
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def bounded_keywords(cls, value):
        if any(not k.strip() or len(k) > 100 for k in value):
            raise ValueError("Invalid keywords")
        return list(dict.fromkeys(k.strip() for k in value))


@router.post("/courses/{course_id}/topics", status_code=201)
def create_topic(course_id: UUID, data: TopicRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course = lock_course(db, user, course_id, data.expected_revision)
    topic = Topic(course_id=course_id, **data.model_dump(exclude={"expected_revision"}))
    course.revision += 1
    course.evaluation_profile, course.evaluation_overrides = "general", {}
    db.add_all([course, topic]); db.flush()
    db.add(AuditEvent(actor_id=user.id, action="topic.create", object_id=topic.id))
    db.commit()
    return {"topic": topic, "course_revision": course.revision}


@router.put("/courses/{course_id}/topics/{topic_id}")
def update_topic(course_id: UUID, topic_id: UUID, data: TopicRequest,
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    course = lock_course(db, user, course_id, data.expected_revision)
    topic = db.get(Topic, topic_id)
    if not topic or topic.course_id != course_id:
        raise HTTPException(404, "TOPIC_NOT_FOUND")
    topic.title, topic.keywords = data.title, data.keywords
    course.revision += 1
    course.evaluation_profile, course.evaluation_overrides = "general", {}
    db.add_all([topic, course])
    db.add(AuditEvent(actor_id=user.id, action="topic.update", object_id=topic.id))
    db.commit()
    return {"topic": topic, "course_revision": course.revision}


class ActiveCourseRequest(BaseModel):
    course_id: UUID


@router.put("/me/active-course")
def active_course(data: ActiveCourseRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, data.course_id)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": str(user.id)})
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first() or UserProfile(user_id=user.id)
    profile.preferences = {**profile.preferences, "active_course_id": str(data.course_id)}
    db.add(profile); db.commit()
    return {"course_id": data.course_id}


class ChatRequest(BaseModel):
    course_id: UUID
    text: str = Field(min_length=1, max_length=4000)


@router.post("/chat", status_code=202)
def chat(data: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, data.course_id)
    job = Job(user_id=user.id, payload={"text": data.text, "course_id": str(data.course_id)})
    db.add(job)
    db.commit()
    return {"job_id": job.id, "status": job.state}


@router.get("/jobs/{job_id}")
def job_status(job_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    job = owned(db, Job, job_id, user)
    message = None
    if job.payload.get("message_id"):
        message = db.get(Message, UUID(job.payload["message_id"]))
    return {"job_id": job.id, "status": job.state,
        "message_id": message.id if message and message.owner_id == user.id else None,
        "answer": message.text if message and message.owner_id == user.id else None}


def owned(db, model, object_id, user, owner_field="user_id", lock=False):
    query = select(model).where(model.id == object_id, getattr(model, owner_field) == user.id)
    record = db.exec(query.with_for_update() if lock else query).first()
    if not record:
        raise HTTPException(404, "NOT_FOUND")
    return record


def cancel_reminders(db, user_id, task_id=None, plan_item_id=None):
    query = select(Reminder).where(Reminder.user_id == user_id)
    query = query.where(Reminder.task_id == task_id) if task_id else query.where(Reminder.plan_item_id == plan_item_id)
    for reminder in db.exec(query).all():
        reminder.enabled = False
        db.add(reminder)
    # Outbox sender revalidates source revision. Cancel queued messages here too.
    for outbox in db.exec(select(MessageOutbox).where(MessageOutbox.user_id == user_id,
            MessageOutbox.kind == "reminder", MessageOutbox.state.in_(["pending", "sending"]))).all():
        if outbox.payload.get("task_id") == str(task_id) or outbox.payload.get("plan_item_id") == str(plan_item_id):
            outbox.state = "cancelled"
            db.add(outbox)


def reminders_enabled(db, user):
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    return bool(profile and profile.preferences.get("reminders_enabled", False))


class PreferencesRequest(BaseModel):
    reminders_enabled: bool
    quiet_start: int = Field(default=21, ge=0, le=23)
    quiet_end: int = Field(default=7, ge=0, le=23)


@router.get("/me/preferences")
def get_preferences(user: User = Depends(current_user), db: Session = Depends(get_session)):
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    return {"reminders_enabled": profile.preferences.get("reminders_enabled", False) if profile else False,
        "quiet_start": profile.preferences.get("quiet_start", 21) if profile else 21,
        "quiet_end": profile.preferences.get("quiet_end", 7) if profile else 7}


@router.put("/me/preferences")
def preferences(data: PreferencesRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": str(user.id)})
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first() or UserProfile(user_id=user.id)
    profile.preferences = {**profile.preferences, **data.model_dump()}
    db.add(profile)
    if not data.reminders_enabled:
        for reminder in db.exec(select(Reminder).where(Reminder.user_id == user.id)).all():
            reminder.enabled = False
            db.add(reminder)
    db.commit()
    return profile.preferences


class TaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    due_at: AwareDatetime | None = None
    course_id: UUID | None = None


@router.get("/tasks")
def tasks(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return db.exec(select(Task).where(Task.owner_id == user.id).order_by(Task.created_at.desc())).all()


@router.post("/tasks", status_code=201)
def create_task(data: TaskRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    if data.course_id:
        course_access(db, user, data.course_id)
    digest = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": f"task:{user.id}:{idempotency_key}"})
    previous = db.exec(select(IdempotencyRecord).where(IdempotencyRecord.user_id == user.id,
        IdempotencyRecord.scope == "tasks", IdempotencyRecord.key == idempotency_key)).first()
    if previous:
        if previous.payload_hash != digest:
            raise HTTPException(409, "IDEMPOTENCY_PAYLOAD_MISMATCH")
        return previous.result
    if not data.title.strip():
        raise HTTPException(400, "TITLE_REQUIRED")
    task = Task(owner_id=user.id, **data.model_dump())
    db.add(task)
    db.flush()
    if task.due_at and task.due_at > utc_now() and reminders_enabled(db, user):
        db.add(Reminder(user_id=user.id, task_id=task.id, remind_at=task.due_at, source_revision=task.revision))
    result = task.model_dump(mode="json")
    db.add(IdempotencyRecord(user_id=user.id, scope="tasks", key=idempotency_key, payload_hash=digest, result=result))
    db.add(AuditEvent(actor_id=user.id, action="task.create", object_id=task.id))
    db.commit()
    return result


class TaskUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    due_at: AwareDatetime | None = None
    state: Literal["pending", "done", "cancelled"] | None = None


@router.patch("/tasks/{task_id}")
def update_task(task_id: UUID, data: TaskUpdate, user: User = Depends(current_user), db: Session = Depends(get_session)):
    task = owned(db, Task, task_id, user, "owner_id", lock=True)
    if task.revision != data.expected_revision:
        raise HTTPException(409, "REVISION_CONFLICT")
    changes = data.model_dump(exclude_unset=True, exclude={"expected_revision"})
    if ("title" in changes and (not changes["title"] or not changes["title"].strip())) or ("state" in changes and changes["state"] is None):
        raise HTTPException(400, "INVALID_TASK_UPDATE")
    for key, value in changes.items():
        setattr(task, key, value)
    task.revision += 1
    task.updated_at = utc_now()
    cancel_reminders(db, user.id, task_id=task.id)
    if task.state == "pending" and task.due_at and task.due_at > utc_now() and reminders_enabled(db, user):
        db.add(Reminder(user_id=user.id, task_id=task.id, remind_at=task.due_at, source_revision=task.revision))
    db.add(task)
    db.add(AuditEvent(actor_id=user.id, action="task.update", object_id=task.id))
    db.commit()
    return task


class QuestionRequest(BaseModel):
    topic_id: UUID
    prompt: str = Field(min_length=1, max_length=4000)
    hint: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=1, max_length=4000)
    answer_type: AnswerType
    grading_spec: dict
    source_version_id: UUID


@router.post("/questions", status_code=201)
def create_question(data: QuestionRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    topic = db.get(Topic, data.topic_id)
    if not topic:
        raise HTTPException(404, "TOPIC_NOT_FOUND")
    course_access(db, user, topic.course_id, True)
    from components.documents import version_access
    document, _ = version_access(db, user, data.source_version_id, True)
    if document.course_id != topic.course_id or document.purpose != "teaching":
        raise HTTPException(403, "QUESTION_SOURCE_MISMATCH")
    validate_spec(data.answer_type, data.grading_spec)
    question = Question(**data.model_dump())
    db.add(question)
    db.commit()
    return question


@router.get("/questions")
def questions(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id, True)
    return db.exec(select(Question).join(Topic).where(Topic.course_id == course_id)).all()


@router.post("/questions/{question_id}/publish")
def publish_question(question_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "QUESTION_NOT_FOUND")
    topic = db.get(Topic, question.topic_id)
    course_access(db, user, topic.course_id, True)
    source = db.get(DocumentVersion, question.source_version_id)
    if not source or source.status != "published":
        raise HTTPException(400, "PUBLISHED_SOURCE_REQUIRED")
    question.status = "published"
    db.add(question)
    db.add(AuditEvent(actor_id=user.id, action="question.approve", object_id=question.id))
    db.commit()
    return {"id": question.id, "status": question.status}


@router.get("/topics")
def topics(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id)
    return db.exec(select(Topic).where(Topic.course_id == course_id)).all()


class PracticeRequest(BaseModel):
    course_id: UUID
    topic_id: UUID


@router.post("/practice/sessions", status_code=201)
def start_practice(data: PracticeRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, data.course_id)
    topic = db.get(Topic, data.topic_id)
    if not topic or topic.course_id != data.course_id:
        raise HTTPException(404, "TOPIC_NOT_FOUND")
    rows = db.exec(select(Question).join(DocumentVersion, Question.source_version_id == DocumentVersion.id)
        .where(Question.topic_id == data.topic_id, Question.status == "published", DocumentVersion.status == "published")
        .order_by(Question.created_at)).all()
    attempted = {a.question_id for a in db.exec(select(Attempt).where(Attempt.user_id == user.id)).all()}
    question = next((q for q in rows if q.id not in attempted), None)
    if not question:
        raise HTTPException(404, "NO_NEW_APPROVED_QUESTION")
    practice = PracticeSession(user_id=user.id, course_id=data.course_id)
    db.add(practice)
    db.flush()
    db.add(PracticeSessionItem(session_id=practice.id, question_id=question.id, question_version=question.version))
    db.commit()
    return {"session_id": practice.id, "question": {"id": question.id, "version": question.version,
        "prompt": question.prompt, "answer_type": question.answer_type,
        "answer_config": student_answer_config(question.answer_type, question.grading_spec)}}


@router.post("/practice/{session_id}/hint")
def hint(session_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    practice = owned(db, PracticeSession, session_id, user, lock=True)
    course_access(db, user, practice.course_id)
    if practice.state != "active":
        raise HTTPException(409, "SESSION_CLOSED")
    item = db.exec(select(PracticeSessionItem).where(PracticeSessionItem.session_id == session_id)).first()
    question = db.get(Question, item.question_id)
    source = db.get(DocumentVersion, question.source_version_id)
    if not source or source.status != "published":
        raise HTTPException(409, "SOURCE_WITHDRAWN")
    item.hints_used = 1  # One hint in this pilot; repeated reads do not inflate the count.
    db.add(item)
    db.commit()
    return {"hint": question.hint}


class AnswerRequest(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1, max_length=2000)
    submission_id: UUID


@router.post("/practice/{session_id}/answers")
def answer(session_id: UUID, data: AnswerRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    practice = owned(db, PracticeSession, session_id, user, lock=True)
    course_access(db, user, practice.course_id)
    previous = db.exec(select(Attempt).where(Attempt.user_id == user.id, Attempt.submission_id == data.submission_id)).first()
    if previous:
        if previous.session_id != session_id or previous.question_id != data.question_id or previous.answer["text"] != data.answer:
            raise HTTPException(409, "SUBMISSION_PAYLOAD_MISMATCH")
        return previous.answer["result"]
    if practice.state != "active":
        raise HTTPException(409, "SESSION_CLOSED")
    item = db.exec(select(PracticeSessionItem).where(PracticeSessionItem.session_id == session_id,
        PracticeSessionItem.question_id == data.question_id)).first()
    if not item:
        raise HTTPException(403, "QUESTION_NOT_SERVED")
    question = db.get(Question, item.question_id)
    if question.version != item.question_version:
        raise HTTPException(409, "QUESTION_VERSION_CHANGED")
    source = db.get(DocumentVersion, question.source_version_id)
    if not source or source.status != "published":
        raise HTTPException(409, "SOURCE_WITHDRAWN")
    correct = grade(question.answer_type, question.grading_spec, data.answer)
    score_status = "pending_review" if correct is None else "graded"
    result = {"correct": correct, "score": None if correct is None else int(correct), "score_status": score_status,
        "hints_used": item.hints_used, "explanation": "รอครูตรวจคำตอบ" if correct is None else question.explanation,
        "source_version_id": question.source_version_id, "question_version": item.question_version}
    db.add(Attempt(user_id=user.id, session_id=session_id, question_id=question.id,
        question_version=item.question_version, submission_id=data.submission_id,
        answer={"text": data.answer, "result": result | {"source_version_id": str(question.source_version_id)}},
        score=int(bool(correct)), score_status=score_status, hints_used=item.hints_used))
    practice.state = "completed"
    db.add(practice)
    db.commit()
    return result


@router.get("/progress")
def progress(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id)
    attempts = db.exec(select(Attempt).join(PracticeSession).where(Attempt.user_id == user.id,
        PracticeSession.course_id == course_id)).all()
    graded = [a for a in attempts if a.score_status == "graded"]
    independent = [a for a in graded if a.hints_used == 0]
    return {"attempts": len(attempts), "independent_attempts": len(independent),
        "independent_correct": sum(a.score == a.max_score for a in independent),
        "with_hints": sum(a.hints_used > 0 for a in attempts),
        "pending_review": len(attempts) - len(graded), "enough_evidence": len(independent) >= 3,
        "recommendation": "ทบทวนข้อที่ผิดและลองโจทย์ใหม่" if len(independent) >= 3 else "ฝึกทำเองอย่างน้อย 3 ข้อก่อนแนะนำระดับ"}


@router.get("/practice/results")
def practice_results(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id)
    rows = db.exec(select(Attempt, Question).join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id).where(Topic.course_id == course_id, Attempt.user_id == user.id)
        .order_by(Attempt.created_at.desc()).limit(100)).all()
    return [{"id": a.id, "prompt": q.prompt, "answer": a.answer["text"], "result": a.answer["result"]} for a, q in rows]


@router.get("/courses/{course_id}/reviews")
def pending_reviews(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id, True)
    rows = db.exec(select(Attempt, Question, User).join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id).join(User, Attempt.user_id == User.id)
        .where(Topic.course_id == course_id, Attempt.score_status == "pending_review")
        .order_by(Attempt.created_at).limit(100)).all()
    return [{"id": a.id, "student": u.display_name, "prompt": q.prompt, "answer": a.answer["text"],
        "criteria": q.grading_spec.get("criteria"), "explanation": q.explanation,
        "source_version_id": q.source_version_id, "hints_used": a.hints_used} for a, q, u in rows]


class GradeRequest(BaseModel):
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    feedback: str = Field(min_length=1, max_length=4000)


@router.post("/courses/{course_id}/reviews/{attempt_id}")
def review_answer(course_id: UUID, attempt_id: UUID, data: GradeRequest,
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id, True)
    attempt = db.exec(select(Attempt).where(Attempt.id == attempt_id).with_for_update()).first()
    if not attempt:
        raise HTTPException(404, "ATTEMPT_NOT_FOUND")
    question = db.get(Question, attempt.question_id)
    topic = db.get(Topic, question.topic_id)
    if topic.course_id != course_id:
        raise HTTPException(403, "ATTEMPT_COURSE_MISMATCH")
    if question.answer_type != "manual" or attempt.score_status != "pending_review":
        raise HTTPException(409, "ALREADY_GRADED")
    if attempt.user_id == user.id or not data.feedback.strip():
        raise HTTPException(400, "INDEPENDENT_TEACHER_FEEDBACK_REQUIRED")
    source = db.get(DocumentVersion, question.source_version_id)
    if not source or source.status != "published":
        raise HTTPException(409, "SOURCE_WITHDRAWN")
    attempt.score, attempt.score_status = data.score, "graded"
    result = {**attempt.answer["result"], "score": data.score, "correct": data.score == 1,
        "score_status": "graded", "explanation": question.explanation, "feedback": data.feedback.strip(),
        "reviewer_id": str(user.id), "reviewed_at": utc_now().isoformat()}
    attempt.answer = {**attempt.answer, "result": result}
    db.add(attempt)
    db.add(AuditEvent(actor_id=user.id, action="attempt.grade", object_id=attempt.id))
    db.commit()
    return result


class PlanRequest(BaseModel):
    course_id: UUID
    exam_date: date
    minutes_per_day: int = Field(ge=5, le=120)


@router.post("/plans/draft", status_code=201)
def draft_plan(data: PlanRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, data.course_id)
    today = utc_now().astimezone(ZoneInfo(user.timezone)).date()
    days = (data.exam_date - today).days
    if days < 1 or days > 90:
        raise HTTPException(400, "EXAM_MUST_BE_1_TO_90_DAYS_AHEAD")
    topics = db.exec(select(Topic).where(Topic.course_id == data.course_id).order_by(Topic.id)).all()
    if not topics:
        raise HTTPException(400, "NO_TOPICS")
    plan = LearningPlan(user_id=user.id, start_date=today, end_date=data.exam_date)
    db.add(plan)
    db.flush()
    for i in range(days):
        scheduled = datetime.combine(today + timedelta(days=i), time(18), ZoneInfo(user.timezone))
        if scheduled > utc_now():
            db.add(PlanItem(plan_id=plan.id, topic_id=topics[i % len(topics)].id, scheduled_at=scheduled,
                minutes=data.minutes_per_day))
    db.commit()
    return {"plan": plan, "items": db.exec(select(PlanItem).where(PlanItem.plan_id == plan.id).order_by(PlanItem.scheduled_at)).all()}


@router.get("/plans")
def plans(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return [{"plan": p, "items": db.exec(select(PlanItem).where(PlanItem.plan_id == p.id).order_by(PlanItem.scheduled_at)).all()}
        for p in db.exec(select(LearningPlan).where(LearningPlan.user_id == user.id).order_by(LearningPlan.created_at.desc())).all()]


@router.post("/plans/{plan_id}/activate")
def activate(plan_id: UUID, data: RevisionRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    plan = owned(db, LearningPlan, plan_id, user, lock=True)
    if plan.state != "draft" or plan.revision != data.expected_revision:
        raise HTTPException(409, "PLAN_REVISION_CONFLICT")
    items = db.exec(select(PlanItem).where(PlanItem.plan_id == plan.id)).all()
    for item in items:
        course_access(db, user, db.get(Topic, item.topic_id).course_id)
        if item.scheduled_at > utc_now() and reminders_enabled(db, user):
            db.add(Reminder(user_id=user.id, plan_item_id=item.id, remind_at=item.scheduled_at, source_revision=item.revision))
    plan.state, plan.revision = "active", plan.revision + 1
    db.add(plan)
    db.commit()
    return plan


@router.post("/plans/{plan_id}/cancel")
def cancel_plan(plan_id: UUID, data: RevisionRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    plan = owned(db, LearningPlan, plan_id, user, lock=True)
    if plan.revision != data.expected_revision:
        raise HTTPException(409, "PLAN_REVISION_CONFLICT")
    for item in db.exec(select(PlanItem).where(PlanItem.plan_id == plan.id)).all():
        cancel_reminders(db, user.id, plan_item_id=item.id)
        item.state, item.revision = "cancelled", item.revision + 1
        db.add(item)
    plan.state, plan.revision = "cancelled", plan.revision + 1
    db.add(plan)
    db.commit()
    return plan


class FeedbackRequest(BaseModel):
    message_id: UUID
    category: Literal["math_error", "citation", "privacy", "other"]
    detail: str = Field(min_length=1, max_length=5000)


@router.post("/feedback", status_code=201)
def feedback(data: FeedbackRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    owned(db, Message, data.message_id, user, "owner_id")
    report = FeedbackReport(reporter_id=user.id, **data.model_dump())
    db.add(report)
    db.commit()
    return report


@router.get("/feedback/{report_id}")
def get_feedback(report_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    return feedback_access(db, user, report_id)


class DeleteRequest(BaseModel):
    deletion_scope: Literal["conversations", "personal_data"]


@router.delete("/me/data")
def delete_data(data: DeleteRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    # Serialize with a worker's final commit. In-flight generation is discarded afterwards.
    db.exec(select(User).where(User.id == user.id).with_for_update()).one()
    db.exec(delete(FeedbackReport).where(FeedbackReport.reporter_id == user.id))
    db.exec(delete(Message).where(Message.owner_id == user.id))
    db.exec(delete(Conversation).where(Conversation.owner_id == user.id))
    for job in db.exec(select(Job).where(Job.user_id == user.id, Job.kind == "ai_response")).all():
        job.state, job.payload = "cancelled", {}
        db.add(job)
    db.exec(delete(MessageOutbox).where(MessageOutbox.user_id == user.id))
    if data.deletion_scope == "personal_data":
        db.exec(delete(Reminder).where(Reminder.user_id == user.id))
        db.exec(delete(Task).where(Task.owner_id == user.id))
        db.exec(delete(Attempt).where(Attempt.user_id == user.id))
        session_ids = select(PracticeSession.id).where(PracticeSession.user_id == user.id)
        db.exec(delete(PracticeSessionItem).where(PracticeSessionItem.session_id.in_(session_ids)))
        db.exec(delete(PracticeSession).where(PracticeSession.user_id == user.id))
        plan_ids = select(LearningPlan.id).where(LearningPlan.user_id == user.id)
        db.exec(delete(PlanItem).where(PlanItem.plan_id.in_(plan_ids)))
        db.exec(delete(LearningPlan).where(LearningPlan.user_id == user.id))
        for model in (AuthSession, UserProfile, IdempotencyRecord, LineIdentity):
            db.exec(delete(model).where(model.user_id == user.id))
        from db.models import CourseMembership, SchoolMembership
        for model in (CourseMembership, SchoolMembership):
            db.exec(delete(model).where(model.user_id == user.id))
        user.display_name, user.status = None, "deleted"
        db.add(user)
    tombstone = AuditEvent(actor_id=user.id, action=f"data.deleted.{data.deletion_scope}")
    db.add(tombstone)
    db.commit()
    return {"request_id": tombstone.request_id, "status": "deleted_from_live_database",
        "backup_note": "บังคับรายการลบจาก audit_events ซ้ำหลัง restore ตามคู่มือก่อนเปิดบริการ"}


@router.get("/courses/{course_id}/progress")
def course_progress(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id, True)
    rows = db.exec(select(Attempt, Topic).join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id).where(Topic.course_id == course_id)).all()
    summary = {}
    for attempt, topic in rows:
        item = summary.setdefault(str(topic.id), {"topic": topic.title, "attempts": 0, "independent_correct": 0, "with_hints": 0, "pending_review": 0})
        item["attempts"] += 1
        item["independent_correct"] += int(attempt.score_status == "graded" and attempt.hints_used == 0 and attempt.score == attempt.max_score)
        item["with_hints"] += int(attempt.hints_used > 0)
        item["pending_review"] += int(attempt.score_status == "pending_review")
    return list(summary.values())


def feedback_access(db, user, report_id, teacher_only=False):
    report = db.get(FeedbackReport, report_id)
    if not report:
        raise HTTPException(404, "FEEDBACK_NOT_FOUND")
    if report.reporter_id == user.id and not teacher_only:
        return report
    message = db.get(Message, report.message_id)
    conversation = db.get(Conversation, message.conversation_id) if message else None
    if not conversation or not conversation.course_id:
        raise HTTPException(403, "FEEDBACK_FORBIDDEN")
    course_access(db, user, conversation.course_id, True)
    return report


class FeedbackUpdate(BaseModel):
    status: Literal["open", "investigating", "resolved"]


@router.patch("/feedback/{report_id}")
def update_feedback(report_id: UUID, data: FeedbackUpdate, user: User = Depends(current_user), db: Session = Depends(get_session)):
    report = feedback_access(db, user, report_id, teacher_only=True)
    report.status, report.assignee_id = data.status, user.id
    db.add(report)
    db.add(AuditEvent(actor_id=user.id, action=f"feedback.{data.status}", object_id=report.id))
    db.commit()
    return report
