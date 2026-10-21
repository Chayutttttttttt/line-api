"""Multi-subject flows against disposable PostgreSQL and private local storage."""
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from agent import gemini
from components.documents import CHECKLIST
from components.grading import grade, validate_spec
from db.database import engine
from db.models import Course, Job, MessageOutbox, User
from manage import add_membership
from worker import run as worker
from test_pilot import signed_event


def new_course(ctx, subject="วิทยาศาสตร์"):
    response = ctx["client"].post("/courses", headers=ctx["teacher_headers"], json={
        "school_id": str(ctx["school"]), "title": subject + " ม.4", "subject": subject,
        "learning_scope": "แรง การเคลื่อนที่ และพลังงาน" if subject == "วิทยาศาสตร์" else "คำศัพท์และการใช้ภาษา",
        "response_language": "ไทย", "grade_level": "ม.4"})
    assert response.status_code == 201, response.text
    course = response.json()
    with Session(engine) as db:
        add_membership(db, db.get(User, ctx["student"]), db.get(Course, UUID(course["id"])), "student")
        db.commit()
    return course


def lesson(ctx, course, topic="แรง", text="แรงคือปริมาณที่ทำให้วัตถุเปลี่ยนการเคลื่อนที่ หน่วยของแรงคือนิวตัน force"):
    client, headers = ctx["client"], ctx["teacher_headers"]
    response = client.post(f"/courses/{course['id']}/topics", headers=headers,
        json={"title": topic, "keywords": ["force", "แรง"], "expected_revision": course["revision"]})
    assert response.status_code == 201, response.text
    course["revision"] = response.json()["course_revision"]
    topic_id = response.json()["topic"]["id"]
    response = client.post("/documents", headers=headers, data={"course_id": course["id"], "title": topic, "purpose": "teaching"},
        files={"file": ("lesson.txt", text.encode(), "text/plain")})
    assert response.status_code == 202, response.text
    version = response.json()
    worker.process_job(worker.claim_job())
    detail = client.get(f"/documents/versions/{version['version_id']}", headers=headers).json()
    for chunk in detail["chunks"]:
        updated = client.patch(f"/documents/versions/{version['version_id']}/chunks/{chunk['id']}", headers=headers,
            json={"text": chunk["text"], "page_no": 1, "expected_revision": detail["version"]["revision"]})
        assert updated.status_code == 200, updated.text
        detail["version"]["revision"] = updated.json()["revision"]
    response = client.post(f"/documents/{version['document_id']}/publish", headers=headers, json={
        "version": 1, "expected_revision": detail["version"]["revision"], "decision": "approve", "scope": "pilot",
        "checklist": {k: True for k in CHECKLIST}, "rubric": {k: 2 for k in ("correctness", "citations", "teaching", "scope")}})
    assert response.status_code == 200, response.text
    return topic_id, version["version_id"]


@pytest.mark.parametrize("kind,spec,answer,expected", [
    ("multiple_choice", {"options": [{"id": "a", "text": "มวล"}, {"id": "b", "text": "แรง"}], "expected": "b"}, "b", True),
    ("numeric", {"expected": "9.81", "tolerance": ".01", "unit": "m/s²"}, "9.80", True),
    ("numeric", {"expected": "9.81", "tolerance": ".01"}, "9.79", False),
    ("numeric", {"expected": "100", "tolerance": "0"}, "1e2", True),
    ("short_text", {"accepted": ["Bangkok", "กรุงเทพฯ"]}, " BANGKOK ", True),
    ("short_text", {"accepted": ["US"], "case_sensitive": True}, "us", False),
    ("short_text", {"accepted": ["café"]}, "cafe\u0301", True),
    ("boolean", {"expected": False}, "เท็จ", True),
    ("manual", {"criteria": "ให้เหตุผลพร้อมหลักฐาน"}, "วิเคราะห์หลักฐาน", None),
])
def test_grading_across_subjects(kind, spec, answer, expected):
    validate_spec(kind, spec)
    assert grade(kind, spec, answer) is expected


@pytest.mark.parametrize("kind,spec", [
    ("numeric", {"expected": "NaN"}), ("numeric", {"expected": "Infinity"}),
    ("numeric", {"expected": 1, "tolerance": -1}), ("numeric", {"expected": True}),
    ("numeric", {"expected": "1e99999"}), ("short_text", {"accepted": [""]}),
    ("short_text", {"accepted": ["yes"], "case_sensitive": "false"}),
    ("manual", {"criteria": " "}),
    ("multiple_choice", {"options": [{"id": "a", "text": "A"}, {"id": "a", "text": "B"}], "expected": "a"}),
    ("multiple_choice", {"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], "expected": "c"}),
])
def test_invalid_specs_rejected(kind, spec):
    with pytest.raises(HTTPException):
        validate_spec(kind, spec)


def test_numeric_input_never_executes_expressions():
    for value in ["1/2", "9.81 m/s", "float('nan')", "1e99999", "__import__('os')"]:
        with pytest.raises(HTTPException):
            grade("numeric", {"expected": 1}, value)


def test_course_permissions_topics_and_revisions(context):
    c = new_course(context)
    client = context["client"]
    payload = {"title": "English", "subject": "ภาษาอังกฤษ", "learning_scope": "Vocabulary", "response_language": "English", "expected_revision": 1}
    assert client.put(f"/courses/{c['id']}", headers=context["student_headers"], json=payload).status_code == 403
    assert client.get(f"/courses/{c['id']}", headers=context["outsider_headers"]).status_code == 403
    response = client.put(f"/courses/{c['id']}", headers=context["teacher_headers"], json=payload)
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["evaluation_profile"] == "general"
    assert client.put(f"/courses/{c['id']}", headers=context["teacher_headers"], json=payload).status_code == 409
    payload = {"school_id": str(context["school"]), "title": "Other", "subject": "Other", "learning_scope": "scope"}
    assert client.post("/courses", headers=context["student_headers"], json=payload).status_code == 403
    assert client.post("/courses", headers=context["outsider_headers"], json=payload).status_code == 403
    assert client.get(f"/topics?course_id={c['id']}", headers=context["teacher_headers"]).json() == []


@pytest.mark.parametrize("kind,spec,answer", [
    ("multiple_choice", {"options": [{"id": "a", "text": "นิวตัน"}, {"id": "b", "text": "กิโลกรัม"}], "expected": "a"}, "a"),
    ("numeric", {"expected": 10, "tolerance": .1, "unit": "N"}, "10.05"),
    ("short_text", {"accepted": ["นิวตัน", "Newton"]}, "NEWTON"),
    ("manual", {"criteria": "แสดงเหตุผลและหน่วย"}, "แรงเป็นปริมาณเวกเตอร์ หน่วยนิวตัน"),
])
def test_practice_new_formats_and_manual_review(context, kind, spec, answer):
    c = new_course(context)
    topic_id, version_id = lesson(context, c)
    client, teacher, student = context["client"], context["teacher_headers"], context["student_headers"]
    response = client.post("/questions", headers=teacher, json={"topic_id": topic_id, "source_version_id": version_id,
        "prompt": "อธิบายแรง", "hint": "ทบทวนเรื่องหน่วย", "explanation": "แรงมีหน่วยนิวตัน", "answer_type": kind, "grading_spec": spec})
    assert response.status_code == 201, response.text
    q = response.json()
    assert client.post(f"/questions/{q['id']}/publish", headers=teacher).status_code == 200
    response = client.post("/practice/sessions", headers=student, json={"course_id": c["id"], "topic_id": topic_id})
    assert response.status_code == 201, response.text
    practice = response.json()
    assert "expected" not in practice["question"]["answer_config"]
    assert "accepted" not in practice["question"]["answer_config"]
    assert "explanation" not in practice["question"]
    submission = {"question_id": q["id"], "answer": answer, "submission_id": str(uuid4())}
    path = f"/practice/{practice['session_id']}/answers"
    response = client.post(path, headers=student, json=submission)
    assert response.status_code == 200, response.text
    result = response.json()
    if kind == "manual":
        assert result["score_status"] == "pending_review" and result["score"] is None and result["correct"] is None
        progress = client.get(f"/progress?course_id={c['id']}", headers=student).json()
        assert progress["pending_review"] == 1 and progress["independent_attempts"] == 0
        reviews = client.get(f"/courses/{c['id']}/reviews", headers=teacher).json()
        assert len(reviews) == 1
        review_path = f"/courses/{c['id']}/reviews/{reviews[0]['id']}"
        score = {"score": .8, "feedback": "เพิ่มการอธิบายทิศทางของแรง"}
        assert client.post(review_path, headers=student, json=score).status_code == 403
        wrong_course = new_course(context, "ภาษาอังกฤษ")
        assert client.post(f"/courses/{wrong_course['id']}/reviews/{reviews[0]['id']}", headers=teacher, json=score).status_code == 403
        assert client.post(review_path, headers=teacher, json=score).status_code == 200
        assert client.post(review_path, headers=teacher, json=score).status_code == 409
        replay = client.post(path, headers=student, json=submission).json()
        assert replay["score"] == .8 and replay["feedback"] == score["feedback"]
        progress = client.get(f"/progress?course_id={c['id']}", headers=student).json()
        assert progress["pending_review"] == 0 and progress["independent_attempts"] == 1
    else:
        assert result["correct"] is True
    results = client.get(f"/practice/results?course_id={c['id']}", headers=student).json()
    assert len(results) == 1 and results[0]["answer"] == answer
    assert client.get(f"/practice/results?course_id={c['id']}", headers=context["peer_headers"]).status_code == 403


def test_retrieval_and_worker_receive_selected_subject(context, monkeypatch):
    c = new_course(context)
    lesson(context, c)
    client, student = context["client"], context["student_headers"]
    chunks = client.get(f"/materials/search?course_id={c['id']}&query=ช่วยอธิบายแรงให้หน่อย", headers=student).json()
    assert chunks and "นิวตัน" in chunks[0]["text"]
    # General English vocabulary and Thai no-space queries use the same retrieval path.
    assert client.get(f"/materials/search?course_id={c['id']}&query=force", headers=student).json()
    assert not client.get(f"/materials/search?course_id={context['course']}&query=force", headers=student).json()
    captured = []
    def tutor(question, chunks, history, course):
        captured.append(course)
        assert course["subject"] == "วิทยาศาสตร์"
        return {"answer": "แรงมีหน่วยนิวตัน", "citations": chunks}
    monkeypatch.setattr(worker, "generate_answer", tutor)
    assert client.put("/me/active-course", headers=student, json={"course_id": c["id"]}).status_code == 200
    body, headers = signed_event("science", "แรงคืออะไร")
    assert client.post("/webhooks/line", content=body, headers=headers).status_code == 200
    # Changing selection after webhook receipt cannot silently reroute the queued question.
    client.put("/me/active-course", headers=student, json={"course_id": str(context["course"])})
    worker.process_job(worker.claim_job())
    assert captured[0]["id"] == c["id"]
    with Session(engine) as db:
        outbox = db.exec(select(MessageOutbox)).one()
        assert outbox.payload["course_id"] == c["id"]
        jobs = db.exec(select(Job).where(Job.kind == "ai_response")).all()
        assert jobs[-1].state == "done"
    assert client.put("/me/active-course", headers=context["outsider_headers"], json={"course_id": c["id"]}).status_code == 403


def test_general_suite_requires_subject_cases_and_current_revision(context):
    c = new_course(context, "ภาษาอังกฤษ")
    client, headers = context["client"], context["teacher_headers"]
    suite = client.get(f"/evaluation/cases?course_id={c['id']}", headers=headers).json()
    assert len(suite["cases"]) == 80
    assert all(case["needs_customization"] for case in suite["cases"])
    assert "โดเมน" not in json.dumps(suite, ensure_ascii=False)
    assert client.get(f"/evaluation/cases?course_id={c['id']}", headers=context["student_headers"]).status_code == 403
    evidence = client.post(f"/courses/{c['id']}/evidence", headers=headers, json={"requirement": "T12", "result": "pass",
        "detail": "review", "build_ref": "abcdef0", "expected": "English", "actual": "English"}).json()
    payload = {"expected_course_revision": 1, "run_id": str(uuid4()), "case_id": "content-01", "evidence_id": evidence["id"],
        "scores": {"correctness": 3, "citations": 3, "teaching": 3, "uncertainty": 3}, "model": "stub", "prompt_version": "course-tutor-v2"}
    assert client.post(f"/courses/{c['id']}/evaluations", headers=headers, json=payload).status_code == 400
    case = {"expected_revision": 1, "input": "Translate apple into Thai", "expected": "แอปเปิล อ้างหน้าที่ถูกต้อง", "failure": "แปลเป็นผลไม้อื่น"}
    assert client.put(f"/courses/{c['id']}/evaluation-cases/content-01", headers=headers, json=case).status_code == 200
    assert client.post(f"/courses/{c['id']}/evaluations", headers=headers, json=payload).status_code == 409
    payload["expected_course_revision"] = 2
    assert client.post(f"/courses/{c['id']}/evaluations", headers=headers, json=payload).status_code == 201
    case["expected_revision"] = 2
    client.put(f"/courses/{c['id']}/evaluation-cases/content-02", headers=headers, json=case)
    payload.update(expected_course_revision=3, case_id="content-02")
    assert client.post(f"/courses/{c['id']}/evaluations", headers=headers, json=payload).status_code == 409
    report = client.get(f"/courses/{c['id']}/acceptance?build_ref=abcdef0&run_id={payload['run_id']}", headers=headers).json()
    assert report["readiness"] == "not_ready"
    assert any("รุ่นเก่า" in b for b in report["blockers"])
    assert report["metrics"]["correctness"]["count"] == 0
    assert len(report["evaluations"]) == 1


def test_adapter_uses_course_context_and_validates_citations(monkeypatch):
    captured = {}
    class FakeClient:
        def __init__(self, **kwargs):
            self.models = self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps({"intent": "tutor", "answer": "Apple means แอปเปิล", "citations": ["chunk-1"],
                "next_action": "practice", "needs_clarification": False}), usage_metadata=None)
    monkeypatch.setattr(gemini, "AI_ENABLED", True)
    monkeypatch.setattr(gemini, "LLM_API_KEY", "test")
    monkeypatch.setattr(gemini.genai, "Client", FakeClient)
    chunks = [{"chunk_id": "chunk-1", "text": "apple = แอปเปิล"}]
    result = gemini.generate_answer("apple แปลว่าอะไร", chunks, [], {"subject": "English", "scope": "Vocabulary", "language": "English"})
    assert result["citations"] == chunks
    assert json.loads(captured["contents"])["course_context"]["subject"] == "English"
    assert "ขอบเขตมีเพียงโดเมน" not in captured["config"].system_instruction
    with pytest.raises(ValueError, match="INVALID_CITATION"):
        gemini.generate_answer("question", [{"chunk_id": "different", "text": "other"}], [], {"subject": "English"})


def test_course_edits_are_serialized(context):
    from concurrent.futures import ThreadPoolExecutor
    c = new_course(context)
    payload = {"title": c["title"], "subject": c["subject"], "learning_scope": "พลังงาน", "expected_revision": 1}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: context["client"].put(f"/courses/{c['id']}",
            headers=context["teacher_headers"], json=payload).status_code, range(2)))
    assert sorted(results) == [200, 409]


def test_course_change_fences_inflight_and_queued_answers(context, monkeypatch):
    c = new_course(context)
    lesson(context, c)
    client = context["client"]
    client.put("/me/active-course", headers=context["student_headers"], json={"course_id": c["id"]})
    def change_during_generation(question, chunks, history, course):
        with Session(engine) as db:
            current = db.get(Course, UUID(c["id"]))
            current.revision += 1
            db.add(current); db.commit()
        return {"answer": "answer from obsolete scope", "citations": chunks}
    monkeypatch.setattr(worker, "generate_answer", change_during_generation)
    body, headers = signed_event("scope-change", "แรง")
    client.post("/webhooks/line", content=body, headers=headers)
    worker.process_job(worker.claim_job())
    with Session(engine) as db:
        job = db.exec(select(Job).where(Job.kind == "ai_response")).one()
        assert job.state == "retry"
        assert not db.exec(select(MessageOutbox)).all()
        worker.create_outbox(db, context["student"], "old-scope", "old answer", payload={"course_id": c["id"], "course_revision": c["revision"]})
        db.commit()
    monkeypatch.setattr(worker.requests, "post", lambda *args, **kwargs: pytest.fail("Must not push an obsolete answer"))
    worker.send_outbox()
    with Session(engine) as db:
        assert db.exec(select(MessageOutbox)).one().state == "cancelled"


def test_migration_keeps_existing_documents_and_memberships(context):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from test_pilot import publish
    document, _ = publish(context)
    with engine.connect() as connection:
        checksum = connection.execute(text("SELECT checksum FROM document_versions WHERE id=:id"), {"id": document["version_id"]}).scalar_one()
        count = connection.execute(text("SELECT count(*) FROM course_memberships")).scalar_one()
    config = Config("alembic.ini")
    command.downgrade(config, "20261018_acceptance")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT checksum FROM document_versions WHERE id=:id"), {"id": document["version_id"]}).scalar_one() == checksum
        assert connection.execute(text("SELECT count(*) FROM course_memberships")).scalar_one() == count
    with Session(engine) as db:
        course = db.get(Course, context["course"])
        assert course.evaluation_profile == "relations-pilot"
        assert "โดเมน" in course.learning_scope
