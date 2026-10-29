"""SQL queue, reminder scheduler and retry-safe LINE push sender.

Run `python -m worker.run --once` for one tick, omit --once for a Railway worker.
No transaction is kept open during external AI or LINE requests.
"""
import argparse
from datetime import timedelta
import logging
import time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import requests
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import and_, exists, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from agent.llm import PROMPT_VERSION, generate_answer
from components.documents import TEACHING_READY_STATUSES, ingest, search_materials
from components.embeddings import embed_document_batch
from components.pdf_ai import read_pdf_with_openai
from components.storage import read_file
from components.login import course_access
from config import (CHANNEL_ACCESS_TOKEN, EMBEDDING_MODEL, EMBEDDINGS_ENABLED, JOB_TIMEOUT_SECONDS, LINE_PROVIDER_ID,
    MAX_DAILY_AI_REQUESTS, MAX_JOB_ATTEMPTS)
from db.database import engine
from db.models import (AuditEvent, Chunk, Conversation, CourseMembership, Document, DocumentVersion, Job, LearningPlan,
    LineIdentity, Message, MessageOutbox, PlanItem, Reminder, Task, Topic, User, UserProfile, WebhookEvent, utc_now)

log = logging.getLogger(__name__)


def claim_job():
    now = utc_now()
    with Session(engine, expire_on_commit=False) as db:
        older = aliased(Job)
        # Serialize jobs per user, including retrying work, before loading context.
        preceding = exists(select(older.id).where(older.user_id == Job.user_id,
            older.state.in_(["queued", "retry", "running"]),
            or_(older.created_at < Job.created_at, and_(older.created_at == Job.created_at, older.id < Job.id))))
        job = db.exec(select(Job).where(
            or_(and_(Job.state.in_(["queued", "retry"]), or_(Job.next_run_at == None, Job.next_run_at <= now)),
                and_(Job.state == "running", Job.lease_until <= now)), ~preceding)
            .order_by(Job.created_at, Job.id).with_for_update(skip_locked=True).limit(1)).first()
        if not job:
            return None
        if job.attempts >= MAX_JOB_ATTEMPTS:
            job.state = "failed"
            db.add(job)
            db.commit()
            return None
        job.state, job.attempts = "running", job.attempts + 1
        job.lease_until = now + timedelta(seconds=JOB_TIMEOUT_SECONDS)
        job.updated_at = now
        db.add(job)
        db.commit()
        return job.model_dump()


def create_outbox(db, user_id, key, text, kind="ai", payload=None):
    statement = insert(MessageOutbox).values(user_id=user_id, kind=kind,
        payload={"text": text[:4800], **(payload or {})}, state="pending", attempts=0,
        retry_key=str(uuid4()), logical_message_key=key, created_at=utc_now())
    db.execute(statement.on_conflict_do_nothing(constraint="uq_logical_message"))


def process_job(claim):
    job_id, attempt = claim["id"], claim["attempts"]
    try:
        if claim["kind"] == "ingest":
            version_id = UUID(claim["payload"]["version_id"])
            with Session(engine, expire_on_commit=False) as db:
                job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
                if job.state != "running" or job.attempts != attempt:
                    return
                version = db.get(DocumentVersion, version_id)
                if not version or version.status not in ("uploaded", "processing"):
                    job.state, job.updated_at = "done", utc_now()
                    db.add(job)
                    db.commit()
                    return
                document = db.get(Document, version.document_id)
                is_pdf = version.filename.lower().endswith(".pdf") and document.purpose == "teaching"
                source_key, checksum = version.storage_key, version.checksum
                version.status = "processing"
                db.add(version)
                db.commit()

            # GPT receives private PDF bytes outside any SQL transaction.
            # We do not call PdfReader.extract_text() for PDF documents.
            ai_pages = None
            if is_pdf:
                def renew_lease(page_no: int, total_pages: int):
                    with Session(engine, expire_on_commit=False) as db:
                        current = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
                        if current.state != "running" or current.attempts != attempt:
                            raise RuntimeError("INGEST_LEASE_LOST")
                        current.lease_until = utc_now() + timedelta(seconds=max(90, JOB_TIMEOUT_SECONDS))
                        current.updated_at = utc_now()
                        db.add(current)
                        db.commit()
                ai_pages = read_pdf_with_openai(read_file(source_key, checksum), on_page=renew_lease)
            with Session(engine, expire_on_commit=False) as db:
                job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
                if (job.state != "running" or job.attempts != attempt
                        or job.lease_until <= utc_now()):
                    return
                ingest(db, version_id, ai_pages=ai_pages)
                # Embeddings will be queued only after a teacher approves publication.
                job.state, job.updated_at = "done", utc_now()
                db.add(job)
                db.commit()
            return
        if claim["kind"] == "embed":
            version_id = UUID(claim["payload"]["version_id"])
            start, limit = int(claim["payload"]["start"]), int(claim["payload"]["limit"])
            with Session(engine, expire_on_commit=False) as db:
                version = db.get(DocumentVersion, version_id)
                if not version or version.status not in TEACHING_READY_STATUSES:
                    parts = []
                else:
                    parts = [(c.id, c.text) for c in db.exec(
                        select(Chunk).where(Chunk.version_id == version_id,
                            Chunk.ordinal >= start, Chunk.ordinal < start + limit)
                        .order_by(Chunk.ordinal)).all()]
            vectors = embed_document_batch([text for _, text in parts]) if parts else []
            with Session(engine, expire_on_commit=False) as db:
                job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
                if job.state != "running" or job.attempts != attempt:
                    return
                version = db.get(DocumentVersion, version_id)
                if version and version.status in TEACHING_READY_STATUSES:
                    for (chunk_id, original_text), vector in zip(parts, vectors):
                        chunk = db.get(Chunk, chunk_id)
                        if chunk and chunk.text == original_text:
                            chunk.embedding, chunk.embedding_model = vector, EMBEDDING_MODEL
                            db.add(chunk)
                job.state, job.updated_at = "done", utc_now()
                db.add(job)
                db.commit()
            return
        with Session(engine, expire_on_commit=False) as db:
            user = db.get(User, claim["user_id"])
            if not user or user.status != "active":
                result = {"answer": "บัญชีไม่พร้อมใช้งาน", "citations": []}
                course_id = None
            else:
                memberships = db.exec(select(CourseMembership).where(CourseMembership.user_id == user.id,
                    CourseMembership.status == "active")).all()
                # Require a single selected course for LINE; LIFF can select any authorized course.
                selected = claim["payload"].get("course_id")
                course_id = UUID(selected) if selected else memberships[0].course_id if len(memberships) == 1 else None
                if course_id:
                    course = course_access(db, user, course_id)
                    course_context = {"id": str(course.id), "title": course.title, "subject": course.subject,
                        "grade_level": course.grade_level, "scope": course.learning_scope,
                        "language": course.response_language, "revision": course.revision,
                        "topics": [t.title for t in db.exec(select(Topic).where(Topic.course_id == course_id)).all()]}
                    conversation = db.exec(select(Conversation).where(Conversation.owner_id == user.id,
                        Conversation.course_id == course_id, Conversation.deleted_at == None)
                        .order_by(Conversation.created_at.desc())).first()
                    history = []
                    if conversation:
                        messages = db.exec(select(Message).where(Message.conversation_id == conversation.id,
                            Message.owner_id == user.id, Message.deleted_at == None, Message.role == "user")
                            .order_by(Message.created_at.desc()).limit(6)).all()
                        history = [{"role": m.role, "text": m.text[:2000]} for m in reversed(messages)]
                    retrieval_query = " ".join([claim["payload"]["text"], *[m["text"] for m in history[-2:]]])
                    source_version_id = claim["payload"].get("source_version_id")
                    chunks = search_materials(db, user, course_id, retrieval_query,
                        UUID(source_version_id) if source_version_id else None)
                    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
                    count = len(db.exec(select(Job.id).where(Job.user_id == user.id, Job.kind == "ai_response",
                        Job.created_at >= today, Job.state.in_(["done", "running"]))).all())
                    if count > MAX_DAILY_AI_REQUESTS:
                        result = {"answer": "ถึงขีดจำกัดคำถาม AI วันนี้แล้ว ยังใช้งานงานและแบบฝึกได้", "citations": []}
                    else:
                        result = None
                else:
                    result = {"answer": "กรุณาเปิด LIFF และเลือกวิชาที่ต้องการ หรือติดต่อครูเพื่อลงทะเบียนรายวิชา", "citations": []}
        if result is None:
            result = generate_answer(claim["payload"]["text"], chunks, history, course_context)
        with Session(engine, expire_on_commit=False) as db:
            # Fence stale workers, deletion requests and concurrent document withdrawal.
            user = db.exec(select(User).where(User.id == claim["user_id"]).with_for_update()).one()
            job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
            if job.state != "running" or job.attempts != attempt or job.lease_until <= utc_now() or user.status != "active":
                return
            if course_id:
                current_course = course_access(db, user, course_id)
                if current_course.revision != course_context["revision"]:
                    raise ValueError("COURSE_CHANGED_DURING_GENERATION")
            for citation in result.get("citations", []):
                source = db.get(DocumentVersion, UUID(citation["version_id"]))
                if not source or source.status not in TEACHING_READY_STATUSES:
                    raise ValueError("SOURCE_WITHDRAWN_DURING_GENERATION")
            conversation = db.exec(select(Conversation).where(Conversation.owner_id == user.id,
                Conversation.course_id == course_id, Conversation.deleted_at == None)
                .order_by(Conversation.created_at.desc())).first()
            if not conversation:
                conversation = Conversation(owner_id=user.id, course_id=course_id)
                db.add(conversation)
                db.flush()
            db.add(Message(conversation_id=conversation.id, owner_id=user.id, role="user",
                text=claim["payload"]["text"], line_message_id=claim["payload"].get("line_message_id")))
            references = "\n".join(
                f"{c['document']} รุ่น {c['version']} "
                f"หน้า {c['page_no'] or '-'}"
                f"{'–' + str(c['page_end']) if c.get('page_end') and c['page_end'] != c['page_no'] else ''}"
                f" (รหัสไฟล์: {c['version_id']})"
                for c in result.get("citations", []))
            answer = result["answer"] + (f"\n\nอ้างอิง\n{references}" if references else "")
            message = Message(conversation_id=conversation.id, owner_id=user.id, role="assistant", text=answer)
            db.add(message)
            db.flush()
            if job.webhook_event_id:
                create_outbox(db, user.id, f"job:{job.id}", answer,
                    payload={"course_id": str(course_id) if course_id else None,
                        "course_revision": course_context["revision"] if course_id else None,
                        "version_ids": [c["version_id"] for c in result.get("citations", [])], "message_id": str(message.id)})
            job.payload = {"request_id": claim["payload"].get("request_id"), "message_id": str(message.id),
                "model": result.get("model"), "prompt_version": PROMPT_VERSION,
                "generation_status": result.get("generation_status", "valid"),
                "course_id": str(course_id) if course_id else None,
                "course_revision": course_context["revision"] if course_id else None,
                "usage": result.get("usage", {}), "citations": [
                    {k: c[k] for k in ("chunk_id", "document_id", "version_id", "checksum", "page_no", "page_end")} for c in result.get("citations", [])]}
            job.state, job.updated_at = "done", utc_now()
            db.add(job)
            if job.webhook_event_id:
                event = db.get(WebhookEvent, job.webhook_event_id)
                event.state = "processed"
                db.add(event)
            db.commit()
    except Exception as error:
        # Fail fast for deterministic validation/input errors; transient providers
        # still use bounded retry. Never log user prompts, raw response or tokens.
        permanent = isinstance(error, (ValueError, ValidationError, HTTPException))
        safe_codes = {"INVALID_CITATION", "COURSE_CHANGED_DURING_GENERATION",
            "SOURCE_WITHDRAWN_DURING_GENERATION", "EMBEDDING_DIMENSION_MISMATCH",
            "INVALID_EMBEDDING", "EMBEDDING_COUNT_MISMATCH",
            "NO_SEARCHABLE_TEXT", "EMPTY_OR_TOO_LARGE_TEXT_USE_TEXT_PDF",
            "PDF_AI_REQUIRED", "PDF_AI_KEY_NOT_CONFIGURED", "PDF_AI_RESPONSE_INVALID",
            "PDF_AI_MODEL_NOT_CONFIGURED", "PDF_AI_RESPONSE_INCOMPLETE", "PDF_AI_REFUSAL",
            "LLM_MODEL_REQUIRED",
            "PDF_PAGE_TOO_LONG", "PDF_AI_NO_SEARCHABLE_TEXT", "PDF_AI_TEXT_TOO_LARGE",
            "INVALID_PDF", "ENCRYPTED_OR_TOO_MANY_PAGES", "UNSUPPORTED_FILE"}
        code = str(error) if isinstance(error, ValueError) and str(error) in safe_codes else (
            "MODEL_SCHEMA_INVALID" if isinstance(error, ValidationError)
            else "INVALID_REQUEST" if isinstance(error, HTTPException)
            else "UNEXPECTED_" + type(error).__name__)
        log.warning("job %s failed (kind=%s, code=%s, attempt=%s)",
            job_id, claim["kind"], code, attempt)
        with Session(engine, expire_on_commit=False) as db:
            job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
            if job.state != "running" or job.attempts != attempt:
                return
            job.state = "failed" if permanent or attempt >= MAX_JOB_ATTEMPTS else "retry"
            job.next_run_at = (None if job.state == "failed"
                else utc_now() + timedelta(seconds=min(300, 2 ** attempt * 5)))
            job.payload = {**job.payload, "error_code": code}
            job.updated_at = utc_now()
            db.add(job)
            if job.kind == "ingest" and job.state == "failed":
                version = db.get(DocumentVersion, UUID(job.payload["version_id"]))
                version.status, version.extraction_error = "failed", code
                db.add(version)
            db.commit()


def reminder_valid(db, outbox, user):
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    if not profile or not profile.preferences.get("reminders_enabled") or profile.preferences.get("oa_blocked"):
        return False
    payload = outbox.payload
    if payload.get("task_id"):
        task = db.get(Task, UUID(payload["task_id"]))
        if not task or task.owner_id != user.id or task.state != "pending" or task.revision != payload["source_revision"]:
            return False
        if task.course_id:
            course_access(db, user, task.course_id)
    else:
        item = db.get(PlanItem, UUID(payload["plan_item_id"]))
        plan = db.get(LearningPlan, item.plan_id) if item else None
        if not item or not plan or plan.user_id != user.id or plan.state != "active" or item.state != "pending" or item.revision != payload["source_revision"]:
            return False
        course_access(db, user, db.get(Topic, item.topic_id).course_id)
    return True


def quiet_until(db, user):
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    prefs = profile.preferences if profile else {}
    now = utc_now().astimezone(ZoneInfo(user.timezone))
    start, end = prefs.get("quiet_start", 21), prefs.get("quiet_end", 7)
    quiet = start <= now.hour < end if start < end else now.hour >= start or now.hour < end
    if start == end:
        return None  # Equal hours disable quiet time.
    if not quiet:
        return None
    resume = now.replace(hour=end, minute=0, second=0, microsecond=0)
    return resume if resume > now else resume + timedelta(days=1)


def schedule_reminders():
    with Session(engine, expire_on_commit=False) as db:
        reminders = db.exec(select(Reminder).where(Reminder.enabled == True, Reminder.remind_at <= utc_now())
            .with_for_update(skip_locked=True).limit(100)).all()
        for reminder in reminders:
            user = db.get(User, reminder.user_id)
            if not user or user.status != "active":
                reminder.enabled = False
                db.add(reminder)
                continue
            payload = {"task_id": str(reminder.task_id) if reminder.task_id else None,
                "plan_item_id": str(reminder.plan_item_id) if reminder.plan_item_id else None,
                "source_revision": reminder.source_revision}
            candidate = MessageOutbox(user_id=user.id, kind="reminder", payload=payload,
                retry_key=str(uuid4()), logical_message_key="preview")
            try:
                valid = reminder_valid(db, candidate, user)
            except Exception:
                valid = False
            if valid:
                source = db.get(Task, reminder.task_id) if reminder.task_id else db.get(PlanItem, reminder.plan_item_id)
                title = source.title if reminder.task_id else f"อ่านทบทวน {db.get(Topic, source.topic_id).title} {source.minutes} นาที"
                create_outbox(db, user.id, f"reminder:{reminder.id}:{reminder.source_revision}", title,
                    kind="reminder", payload=payload)
            reminder.enabled = False
            db.add(reminder)
        db.commit()


def send_outbox():
    now = utc_now()
    with Session(engine, expire_on_commit=False) as db:
        outbox = db.exec(select(MessageOutbox).where(or_(
            and_(MessageOutbox.state == "pending", or_(MessageOutbox.next_run_at == None, MessageOutbox.next_run_at <= now)),
            and_(MessageOutbox.state == "sending", MessageOutbox.lease_until <= now)))
            .order_by(MessageOutbox.created_at).with_for_update(skip_locked=True).limit(1)).first()
        if not outbox:
            return
        user = db.get(User, outbox.user_id)
        identity = db.exec(select(LineIdentity).where(LineIdentity.user_id == outbox.user_id,
            LineIdentity.provider_id == LINE_PROVIDER_ID)).first()
        valid = bool(user and user.status == "active" and identity)
        try:
            if valid and outbox.kind == "reminder":
                valid = reminder_valid(db, outbox, user)
                resume = quiet_until(db, user) if valid else None
                if resume:
                    outbox.state, outbox.next_run_at = "pending", resume
                    db.add(outbox)
                    db.commit()
                    return
            if valid and outbox.payload.get("course_id"):
                course = course_access(db, user, UUID(outbox.payload["course_id"]))
                if outbox.payload.get("course_revision") is not None:
                    valid = valid and course.revision == outbox.payload["course_revision"]
            if valid:
                for version_id in outbox.payload.get("version_ids", []):
                    source = db.get(DocumentVersion, UUID(version_id))
                    valid = valid and bool(source and source.status in TEACHING_READY_STATUSES)
        except Exception:
            valid = False
        if not valid:
            outbox.state = "cancelled"
            db.add(outbox)
            db.commit()
            return
        if not CHANNEL_ACCESS_TOKEN:
            return  # Configuration error does not burn retries or pretend delivery.
        if outbox.created_at < now - timedelta(hours=23) or outbox.attempts >= 8:
            outbox.state = "unknown"  # Do not send outside LINE's retry-key validity window.
            db.add(outbox)
            db.commit()
            return
        outbox.state, outbox.attempts = "sending", outbox.attempts + 1
        outbox.lease_until = now + timedelta(seconds=60)
        db.add(outbox)
        db.commit()
        claim = outbox.model_dump()
        recipient = identity.line_sub
    try:
        response = requests.post("https://api.line.me/v2/bot/message/push", headers={
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}", "X-Line-Retry-Key": claim["retry_key"]},
            json={"to": recipient, "messages": [{"type": "text", "text": claim["payload"]["text"]}]}, timeout=15)
        accepted = response.status_code == 200 or (response.status_code == 409 and bool(response.headers.get("x-line-accepted-request-id")))
        retryable = response.status_code == 429 or response.status_code >= 500
        state = "accepted" if accepted else "pending" if retryable else "failed"
    except requests.RequestException:
        state = "pending"  # Same retry key even when first request may have reached LINE.
    with Session(engine, expire_on_commit=False) as db:
        outbox = db.exec(select(MessageOutbox).where(MessageOutbox.id == claim["id"]).with_for_update()).first()
        if not outbox or outbox.attempts != claim["attempts"] or outbox.state != "sending":
            return
        outbox.state = state
        outbox.next_run_at = utc_now() + timedelta(seconds=min(300, 2 ** outbox.attempts * 5))
        if state == "accepted":
            outbox.sent_at = utc_now()  # API accepted, never interpreted as delivered/read.
        db.add(outbox)
        db.commit()


def tick():
    schedule_reminders()
    claim = claim_job()
    if claim:
        process_job(claim)
    send_outbox()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            tick()
        except Exception as error:
            log.error("worker tick failed (%s)", type(error).__name__)
        if args.once:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
