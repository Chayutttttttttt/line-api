import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import hmac
import json
from uuid import UUID, uuid4

import pytest
import requests
from sqlalchemy import text
from sqlmodel import Session, select

from components.documents import CHECKLIST, extract_pages
from components.grading import grade, integer_set
from components.acceptance import evaluation_cases
from db.database import engine
from db.models import (Attempt, AuthSession, Chunk, ContentReview, CourseMembership, DocumentVersion, Job,
    MessageOutbox, Question, Reminder, Task, UserProfile, utc_now)
from worker import run as worker


def signed_event(event_id="e1", message="โดเมน", user="student"):
    body = json.dumps({"events": [{"webhookEventId": event_id, "type": "message",
        "source": {"type": "user", "userId": f"line-{user}"},
        "message": {"type": "text", "text": message, "id": "m1"}}]}).encode()
    signature = base64.b64encode(hmac.new(b"test-channel-secret", body, hashlib.sha256).digest()).decode()
    return body, {"X-Line-Signature": signature, "Content-Type": "application/json"}


def upload(context, purpose="teaching"):
    response = context["client"].post("/documents", headers=context["teacher_headers"],
        data={"course_id": str(context["course"]), "title": "โดเมน", "purpose": purpose},
        files={"file": ("lesson.txt", "โดเมนคือเซตของสมาชิกตัวหน้า เช่น {(1,2),(3,4)} มีโดเมน {1,3}".encode(), "text/plain")})
    assert response.status_code == 202, response.text
    result = response.json()
    worker.process_job(worker.claim_job())
    detail = context["client"].get(f"/documents/versions/{result['version_id']}", headers=context["teacher_headers"]).json()
    assert detail["version"]["status"] == "review", detail
    for chunk in detail["chunks"]:
        response = context["client"].patch(f"/documents/versions/{result['version_id']}/chunks/{chunk['id']}",
            headers=context["teacher_headers"], json={"text": chunk["text"], "page_no": 22,
                "expected_revision": detail["version"]["revision"]})
        assert response.status_code == 200, response.text
        detail["version"]["revision"] = response.json()["revision"]
    return result, detail


def publish(context, scope="pilot", purpose="teaching"):
    result, detail = upload(context, purpose)
    response = context["client"].post(f"/documents/{result['document_id']}/publish", headers=context["teacher_headers"],
        json={"version": 1, "expected_revision": detail["version"]["revision"], "scope": scope,
            "decision": "approve", "checklist": {key: True for key in CHECKLIST},
            "rubric": {key: 2 for key in ("correctness", "citations", "teaching", "scope")}})
    assert response.status_code == 200, response.text
    return result, response.json()


@pytest.mark.parametrize("answer", ["{1,3}", "{3,1,1}", "{+1, 3}"])
def test_set_equivalence(answer):
    assert grade("integer_set", {"expected": [1,3]}, answer)


@pytest.mark.parametrize("answer", ["__import__('os').system('id')", "{1, 2.0}", "[1,3]", "{1,}", "{1e2}"])
def test_reject_code_and_unsupported_answers(answer):
    with pytest.raises(Exception):
        integer_set(answer)


def test_negative_zero_empty_and_boolean():
    assert grade("integer_set", {"expected": [-2,0]}, "{0,−2,-2}")
    assert grade("integer_set", {"expected": []}, "∅")
    assert grade("boolean", {"expected": False}, "ไม่ใช่")
    assert not grade("boolean", {"expected": True}, "ไม่ใช่")


def test_forged_signature_and_bounded_body(context):
    client = context["client"]
    body, headers = signed_event()
    response = client.post("/webhooks/line", content=body + b" ", headers=headers)
    assert response.status_code == 400
    assert response.json()["request_id"]
    assert client.post("/chat", headers=context["student_headers"], content=b"x" * 70000).status_code == 413
    with Session(engine) as db:
        assert not db.exec(select(Job)).all()


def test_empty_events_and_concurrent_redelivery(context):
    client = context["client"]
    body = b'{"events": []}'
    signature = base64.b64encode(hmac.new(b"test-channel-secret", body, hashlib.sha256).digest()).decode()
    assert client.post("/webhook", content=body, headers={"X-Line-Signature": signature}).status_code == 200
    body, headers = signed_event()
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: client.post("/webhooks/line", content=body, headers=headers), range(10)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert sum(r.json()["accepted"] for r in results) == 1
    with Session(engine) as db:
        assert len(db.exec(select(Job)).all()) == 1


def test_verified_login_no_token_logging_and_revocation(context, monkeypatch, capsys):
    from components import login
    class Response:
        status_code = 200
        def json(self):
            return {"iss": "https://access.line.me", "aud": "test-login-channel", "sub": "new-line-user",
                "exp": (utc_now() + timedelta(hours=1)).timestamp(), "name": "Learner"}
    monkeypatch.setattr(login.requests, "post", lambda *args, **kwargs: Response())
    client = context["client"]
    result = client.post("/auth/line", json={"id_token": "private-test-id-token"})
    assert result.status_code == 200, result.text
    token = result.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/me", headers=headers).json()["courses"] == []
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/me", headers=headers).status_code == 401
    assert "private-test-id-token" not in capsys.readouterr().out


@pytest.mark.parametrize("claims", [{"aud": "wrong-channel"}, {"exp": 1}, {"iss": "https://evil.test"}, {"sub": ""}])
def test_bad_claims_are_rejected(context, monkeypatch, claims):
    from components import login
    class Response:
        status_code = 200
        def json(self):
            return {"iss": "https://access.line.me", "aud": "test-login-channel", "sub": "new-line-user",
                "exp": (utc_now() + timedelta(hours=1)).timestamp(), **claims}
    monkeypatch.setattr(login.requests, "post", lambda *args, **kwargs: Response())
    assert context["client"].post("/auth/line", json={"id_token": "bad"}).status_code == 401


def test_expired_session_and_unauthenticated(context):
    assert context["client"].get("/me").status_code == 401
    with Session(engine) as db:
        auth = db.get(AuthSession, hashlib.sha256(b"session-student").hexdigest())
        auth.expires_at = utc_now() - timedelta(seconds=1)
        db.add(auth); db.commit()
    assert context["client"].get("/me", headers=context["student_headers"]).status_code == 401


def test_document_permissions_approval_withdraw_and_checksum(context):
    client = context["client"]
    result, state = publish(context)
    path = f"/documents/versions/{result['version_id']}/file"
    assert client.get(path, headers=context["student_headers"]).status_code == 200
    assert client.get(path, headers=context["outsider_headers"]).status_code == 403
    assert client.get(f"/documents/versions/{result['version_id']}", headers=context["student_headers"]).status_code == 403
    response = client.get("/materials/search", params={"course_id": str(context["course"]), "query": "โดเมน"}, headers=context["student_headers"])
    assert len(response.json()) == 1, response.text
    assert response.json()[0]["page_no"] == 22
    assert client.post(f"/documents/versions/{result['version_id']}/withdraw", headers=context["student_headers"], json={"expected_revision": state["revision"]}).status_code == 403
    response = client.post(f"/documents/versions/{result['version_id']}/withdraw", headers=context["teacher_headers"], json={"expected_revision": state["revision"]})
    assert response.status_code == 200
    assert client.get(path, headers=context["student_headers"]).status_code == 403
    assert client.get("/materials/search", params={"course_id": str(context["course"]), "query": "โดเมน"}, headers=context["student_headers"]).json() == []
    with Session(engine) as db:
        source = db.get(DocumentVersion, UUID(result["version_id"]))
        source.checksum = "bad"
        db.add(source); db.commit()
    assert client.get(path, headers=context["teacher_headers"]).status_code == 409


def test_prototype_and_evidence_never_enter_student_retrieval(context):
    result, state = publish(context, scope="prototype")
    assert state["status"] == "review"
    assert context["client"].get(f"/documents/versions/{result['version_id']}/file", headers=context["student_headers"]).status_code == 403
    publish(context, purpose="evidence")
    assert context["client"].get("/materials/search", params={"course_id": str(context["course"]), "query": "โดเมน"}, headers=context["student_headers"]).json() == []


def test_unreviewed_pages_and_missing_checklist_block_publication(context):
    result, detail = upload(context)
    body = {"version": 1, "expected_revision": detail["version"]["revision"], "scope": "pilot", "decision": "approve", "checklist": {}}
    assert context["client"].post(f"/documents/{result['document_id']}/publish", headers=context["teacher_headers"], json=body).status_code == 400
    body["checklist"] = {key: True for key in CHECKLIST}
    body["rubric"] = {key: 2 for key in ("correctness", "citations", "teaching", "scope")}
    with Session(engine) as db:
        chunk = db.exec(select(Chunk)).first()
        chunk.page_no = None
        db.add(chunk); db.commit()
    assert context["client"].post(f"/documents/{result['document_id']}/publish", headers=context["teacher_headers"], json=body).status_code == 400


def test_document_revision_and_disguised_upload(context):
    result, detail = upload(context)
    chunk = detail["chunks"][0]
    response = context["client"].patch(f"/documents/versions/{result['version_id']}/chunks/{chunk['id']}",
        headers=context["teacher_headers"], json={"text": "wrong", "page_no": 1, "expected_revision": 1})
    assert response.status_code == 409
    response = context["client"].post("/documents", headers=context["teacher_headers"], data={"course_id": str(context["course"]), "title": "fake"}, files={"file": ("fake.pdf", b"not pdf", "application/pdf")})
    assert response.status_code == 400


def test_tasks_idempotency_revision_and_cross_user(context):
    client, headers = context["client"], context["student_headers"] | {"Idempotency-Key": "same-key"}
    body = {"title": "อ่านบทเรียน", "due_at": "2030-01-01T18:00:00+07:00"}
    first = client.post("/tasks", headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert client.post("/tasks", headers=headers, json=body).json() == first.json()
    assert client.post("/tasks", headers=headers, json={**body, "title": "changed"}).status_code == 409
    task_id = first.json()["id"]
    assert client.patch(f"/tasks/{task_id}", headers=context["peer_headers"], json={"expected_revision": 1, "state": "done"}).status_code == 404
    assert client.patch(f"/tasks/{task_id}", headers=headers, json={"expected_revision": 1, "state": "done"}).status_code == 200
    assert client.patch(f"/tasks/{task_id}", headers=headers, json={"expected_revision": 1, "state": "done"}).status_code == 409
    assert client.post("/tasks", headers=headers, json={"title": "naive", "due_at": "2030-01-01T18:00:00"}).status_code == 400


def test_practice_no_solution_leak_hints_submission_and_ownership(context):
    client = context["client"]
    result, _ = publish(context)
    question = client.post("/questions", headers=context["teacher_headers"], json={"topic_id": str(context["topic"]),
        "prompt": "หาโดเมน {(1,2),(3,4)}", "hint": "ดูสมาชิกตัวหน้า", "explanation": "สมาชิกตัวหน้าคือ 1 และ 3", "answer_type": "integer_set", "grading_spec": {"expected": [1,3]}, "source_version_id": result["version_id"]})
    assert question.status_code == 201, question.text
    qid = question.json()["id"]
    assert client.post(f"/questions/{qid}/publish", headers=context["student_headers"]).status_code == 403
    assert client.post(f"/questions/{qid}/publish", headers=context["teacher_headers"]).status_code == 200
    practice = client.post("/practice/sessions", headers=context["student_headers"], json={"course_id": str(context["course"]), "topic_id": str(context["topic"])})
    assert practice.status_code == 201, practice.text
    assert "grading_spec" not in practice.text and "explanation" not in practice.text and "expected" not in practice.text
    sid = practice.json()["session_id"]
    submission = {"question_id": qid, "answer": "{3,1,1}", "submission_id": str(uuid4())}
    assert client.post(f"/practice/{sid}/answers", headers=context["peer_headers"], json=submission).status_code == 404
    assert client.post(f"/practice/{sid}/hint", headers=context["student_headers"]).status_code == 200
    response = client.post(f"/practice/{sid}/answers", headers=context["student_headers"], json=submission)
    assert response.status_code == 200, response.text
    assert response.json()["correct"] and response.json()["hints_used"] == 1
    assert client.post(f"/practice/{sid}/answers", headers=context["student_headers"], json=submission).json() == response.json()
    assert client.post(f"/practice/{sid}/answers", headers=context["student_headers"], json={**submission, "answer": "{2}"}).status_code == 409
    progress = client.get("/progress", headers=context["student_headers"], params={"course_id": str(context["course"])}).json()
    assert progress["attempts"] == 1 and progress["independent_attempts"] == 0 and not progress["enough_evidence"]


def test_worker_crash_lease_fencing_and_atomic_outbox(context, monkeypatch):
    publish(context)
    body, headers = signed_event()
    context["client"].post("/webhook", content=body, headers=headers)
    first_claim = worker.claim_job()
    assert first_claim and worker.claim_job() is None
    with Session(engine) as db:
        job = db.get(Job, first_claim["id"])
        job.lease_until = utc_now() - timedelta(seconds=1)
        db.add(job); db.commit()
    reclaimed = worker.claim_job()
    assert reclaimed["attempts"] == 2
    monkeypatch.setattr(worker, "generate_answer", lambda prompt, chunks, history: {"answer": "ดูสมาชิกตัวหน้า", "citations": chunks, "model": "stub", "usage": {}})
    worker.process_job(first_claim)
    with Session(engine) as db:
        assert not db.exec(select(MessageOutbox)).all()
    worker.process_job(reclaimed)
    worker.process_job(reclaimed)
    with Session(engine) as db:
        assert len(db.exec(select(MessageOutbox)).all()) == 1
        assert db.get(Job, reclaimed["id"]).state == "done"


def test_line_timeout_retry_key_and_accepted_is_not_delivered(context, monkeypatch):
    with Session(engine) as db:
        worker.create_outbox(db, context["student"], "test-push", "message")
        db.commit()
    calls = []
    def send(*args, **kwargs):
        calls.append(kwargs["headers"]["X-Line-Retry-Key"])
        if len(calls) == 1:
            raise requests.Timeout()
        class Response:
            status_code = 409
            headers = {"x-line-accepted-request-id": "previous-request"}
        return Response()
    monkeypatch.setattr(worker.requests, "post", send)
    worker.send_outbox()
    with Session(engine) as db:
        outbox = db.exec(select(MessageOutbox)).one()
        outbox.next_run_at = utc_now() - timedelta(seconds=1)
        assert outbox.state == "pending"
        db.add(outbox); db.commit()
    worker.send_outbox()
    assert calls[0] == calls[1]
    with Session(engine) as db:
        assert db.exec(select(MessageOutbox)).one().state == "accepted"


def test_reminder_opt_in_revision_and_quiet_time(context):
    client = context["client"]
    with Session(engine) as db:
        task = Task(owner_id=context["student"], title="due", due_at=utc_now() - timedelta(minutes=1))
        db.add(task); db.flush()
        reminder = Reminder(user_id=context["student"], task_id=task.id, remind_at=task.due_at)
        db.add(reminder); db.commit()
    worker.schedule_reminders()
    with Session(engine) as db:
        assert not db.exec(select(MessageOutbox)).all()
        profile = UserProfile(user_id=context["student"], preferences={"reminders_enabled": True, "quiet_start": 0, "quiet_end": 23})
        db.add(profile)
        task = db.exec(select(Task)).one()
        reminder = Reminder(user_id=context["student"], task_id=task.id, remind_at=task.due_at)
        db.add(reminder); db.commit()
    worker.schedule_reminders()
    with Session(engine) as db:
        outbox = db.exec(select(MessageOutbox)).one()
        task_id = outbox.payload["task_id"]
    response = client.patch(f"/tasks/{task_id}", headers=context["student_headers"], json={"expected_revision": 1, "state": "done"})
    assert response.status_code == 200
    with Session(engine) as db:
        assert db.exec(select(MessageOutbox)).one().state == "cancelled"


def test_draft_plan_no_reminders_until_activate_and_cancel(context):
    client = context["client"]
    client.put("/me/preferences", headers=context["student_headers"], json={"reminders_enabled": True})
    result = client.post("/plans/draft", headers=context["student_headers"], json={"course_id": str(context["course"]), "exam_date": str((utc_now() + timedelta(days=4)).date()), "minutes_per_day": 20})
    assert result.status_code == 201, result.text
    with Session(engine) as db:
        assert not db.exec(select(Reminder)).all()
    plan_id = result.json()["plan"]["id"]
    response = client.post(f"/plans/{plan_id}/activate", headers=context["student_headers"], json={"expected_revision": 1})
    assert response.status_code == 200, response.text
    with Session(engine) as db:
        assert db.exec(select(Reminder)).all()
    response = client.post(f"/plans/{plan_id}/cancel", headers=context["student_headers"], json={"expected_revision": 2})
    assert response.status_code == 200
    with Session(engine) as db:
        assert all(not r.enabled for r in db.exec(select(Reminder)).all())


def test_acceptance_never_invents_results_and_has_80_cases(context):
    cases = evaluation_cases()
    assert len(cases) == 80 and len({c["id"] for c in cases}) == 80
    client = context["client"]
    response = client.get(f"/courses/{context['course']}/acceptance", headers=context["teacher_headers"], params={"build_ref": "abcdef1"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["readiness"] == "not_ready" and report["metrics"]["correctness"]["rate"] is None
    assert len(report["blockers"]) >= 16 and report["evidence"] == []
    assert client.get(f"/courses/{context['course']}/acceptance", headers=context["student_headers"], params={"build_ref": "abcdef1"}).status_code == 403


def test_personal_deletion_cancels_pending_work(context):
    client = context["client"]
    client.post("/chat", headers=context["student_headers"], json={"course_id": str(context["course"]), "text": "โดเมน"})
    client.post("/tasks", headers=context["student_headers"] | {"Idempotency-Key": "delete-test"}, json={"title": "private"})
    response = client.request("DELETE", "/me/data", headers=context["student_headers"], json={"deletion_scope": "personal_data"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted_from_live_database"
    assert client.get("/me", headers=context["student_headers"]).status_code == 401
    with Session(engine) as db:
        assert not db.exec(select(Task)).all()
        job = db.exec(select(Job)).one()
        assert job.state == "cancelled" and job.payload == {}


def test_database_failure_never_acknowledges_uncommitted_webhook(context, monkeypatch):
    from sqlalchemy.exc import OperationalError
    body, headers = signed_event()
    with monkeypatch.context() as patch:
        def fail_commit(self):
            raise OperationalError("test-statement", {}, RuntimeError("simulated offline database"))
        patch.setattr(Session, "commit", fail_commit)
        response = context["client"].post("/webhook", content=body, headers=headers)
        assert response.status_code == 503
        assert response.json()["code"] == "DATABASE_UNAVAILABLE"
    with Session(engine) as db:
        assert not db.exec(select(Job)).all()


def test_s3_private_roundtrip_and_checksum(monkeypatch):
    import io
    import boto3
    from botocore.response import StreamingBody
    from botocore.stub import Stubber
    from components import storage
    payload = b"private evidence"
    key = "school/course/file.pdf"
    client = boto3.client("s3", endpoint_url="https://storage.invalid", aws_access_key_id="test", aws_secret_access_key="test")
    stubber = Stubber(client)
    stubber.add_response("put_object", {}, {"Bucket": "test-bucket", "Key": key,
        "Body": payload, "ContentType": "application/octet-stream"})
    stubber.add_response("get_object", {"Body": StreamingBody(io.BytesIO(payload), len(payload))}, {"Bucket": "test-bucket", "Key": key})
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage, "s3_client", lambda: client)
    with stubber:
        storage.put_file(key, payload)
        assert storage.read_file(key, hashlib.sha256(payload).hexdigest()) == payload
        stubber.assert_no_pending_responses()
    with pytest.raises(Exception):
        storage.object_path("../escape.pdf")


def test_withdrawal_cancels_already_queued_ai_push(context, monkeypatch):
    result, state = publish(context)
    with Session(engine) as db:
        worker.create_outbox(db, context["student"], "old-source", "old answer",
            payload={"course_id": str(context["course"]), "version_ids": [result["version_id"]]})
        db.commit()
    context["client"].post(f"/documents/versions/{result['version_id']}/withdraw", headers=context["teacher_headers"], json={"expected_revision": state["revision"]})
    monkeypatch.setattr(worker.requests, "post", lambda *a, **k: pytest.fail("must not send withdrawn source"))
    worker.send_outbox()
    with Session(engine) as db:
        assert db.exec(select(MessageOutbox)).one().state == "cancelled"


def test_chat_context_scoped_to_course_and_user(context, monkeypatch):
    publish(context)
    histories = []
    def answer(prompt, chunks, history):
        histories.append(history)
        assert chunks
        return {"answer": "ดูสมาชิกตัวหน้า", "citations": chunks, "model": "stub", "usage": {}}
    monkeypatch.setattr(worker, "generate_answer", answer)
    for question in ["โดเมนคืออะไร", "ขอคำใบ้"]:
        response = context["client"].post("/chat", headers=context["student_headers"], json={"course_id": str(context["course"]), "text": question})
        assert response.status_code == 202
        worker.process_job(worker.claim_job())
        status = context["client"].get(f"/jobs/{response.json()['job_id']}", headers=context["student_headers"])
        assert status.json()["status"] == "done", status.text
        assert context["client"].get(f"/jobs/{response.json()['job_id']}", headers=context["peer_headers"]).status_code == 404
    assert histories[0] == [] and histories[1][0]["text"] == "โดเมนคืออะไร"
    assert all(h["role"] == "user" for h in histories[1])
    with Session(engine) as db:
        assert not db.exec(select(MessageOutbox)).all()  # LIFF answers are polled, not pushed twice.


def test_deletion_ledger_replayed_after_restore(context):
    from manage import deletion_ledger, replay_deletions
    response = context["client"].request("DELETE", "/me/data", headers=context["student_headers"], json={"deletion_scope": "personal_data"})
    assert response.status_code == 200
    with Session(engine) as db:
        ledger = deletion_ledger(db)
        assert len(ledger) == 1 and ledger[0]["scope"] == "personal_data"
        # Simulate restoring old personal rows, then enforce the independent latest ledger.
        db.add(Task(owner_id=context["student"], title="restored private task"))
        db.commit()
        assert replay_deletions(db, ledger) == 1
        assert not db.exec(select(Task).where(Task.owner_id == context["student"])).all()


def test_evidence_export_version_and_evaluation_scores(context):
    client = context["client"]
    artifact, _ = publish(context, purpose="evidence")
    body = {"requirement": "T01", "result": "pass", "detail": "Signature rejected before any job",
        "build_ref": "abcdef1", "expected": "400 with zero jobs", "actual": "400 with zero jobs", "artifact_version_id": artifact["version_id"]}
    response = client.post(f"/courses/{context['course']}/evidence", headers=context["teacher_headers"], json=body)
    assert response.status_code == 201, response.text
    evidence_id = response.json()["id"]
    params = {"build_ref": "different-build"}
    report = client.get(f"/courses/{context['course']}/acceptance", headers=context["teacher_headers"], params=params).json()
    assert report["evidence"] == []
    result = client.get(f"/courses/{context['course']}/acceptance", headers=context["teacher_headers"], params={"build_ref": "abcdef1"}).json()
    assert result["artifact_inventory"][0]["checksum"]
    scores = {"correctness": 3, "citations": None, "teaching": 3, "uncertainty": None}
    evaluation = {"run_id": str(uuid4()), "case_id": "content-01", "evidence_id": evidence_id,
        "scores": scores, "model": "stub", "prompt_version": "v1"}
    assert client.post(f"/courses/{context['course']}/evaluations", headers=context["teacher_headers"], json=evaluation).status_code == 201
    assert client.post(f"/courses/{context['course']}/evaluations", headers=context["teacher_headers"], json=evaluation).status_code == 409
    evaluation["case_id"] = "content-02"
    evaluation["scores"]["correctness"] = None
    assert client.post(f"/courses/{context['course']}/evaluations", headers=context["teacher_headers"], json=evaluation).status_code == 400


def test_cross_school_constraint_is_enforced_by_postgres(context):
    from db.models import Course, CourseMembership, School
    from sqlalchemy.exc import IntegrityError
    with Session(engine) as db:
        other = db.exec(select(School).where(School.id != context["school"])).one()
        db.add(CourseMembership(user_id=context["student"], school_id=other.id, course_id=context["course"], role="teacher"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_migration_downgrade_then_upgrade_preserves_initial(context):
    from alembic import command
    from alembic.config import Config
    config = Config("alembic.ini")
    command.downgrade(config, "9bce9b6e09b4")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261018_acceptance"


def test_saved_preferences_feedback_and_teacher_progress(context, monkeypatch):
    client = context["client"]
    defaults = client.get("/me/preferences", headers=context["student_headers"])
    assert defaults.json()["reminders_enabled"] is False
    client.put("/me/preferences", headers=context["student_headers"], json={"reminders_enabled": True, "quiet_start": 20, "quiet_end": 6})
    assert client.get("/me/preferences", headers=context["student_headers"]).json()["quiet_start"] == 20
    request = client.post("/chat", headers=context["student_headers"], json={"course_id": str(context["course"]), "text": "โดเมน"})
    worker.process_job(worker.claim_job())
    message = client.get(f"/jobs/{request.json()['job_id']}", headers=context["student_headers"]).json()["message_id"]
    response = client.post("/feedback", headers=context["student_headers"], json={"message_id": message, "category": "citation", "detail": "Need reviewed teaching materials"})
    assert response.status_code == 201
    report_id = response.json()["id"]
    assert client.get(f"/feedback/{report_id}", headers=context["teacher_headers"]).status_code == 200
    assert client.get(f"/feedback/{report_id}", headers=context["peer_headers"]).status_code == 403
    assert client.patch(f"/feedback/{report_id}", headers=context["teacher_headers"], json={"status": "investigating"}).status_code == 200
    assert client.patch(f"/feedback/{report_id}", headers=context["student_headers"], json={"status": "resolved"}).status_code == 403
    assert client.get(f"/courses/{context['course']}/progress", headers=context["teacher_headers"]).json() == []
    assert client.get(f"/courses/{context['course']}/progress", headers=context["student_headers"]).status_code == 403


def test_classroom_login_burst_under_shared_ip(context, monkeypatch):
    from components import login
    class Response:
        status_code = 200
        def json(self):
            return {"iss": "https://access.line.me", "aud": "test-login-channel", "sub": "line-student",
                "exp": (utc_now() + timedelta(hours=1)).timestamp()}
    monkeypatch.setattr(login.requests, "post", lambda *args, **kwargs: Response())
    responses = [context["client"].post("/auth/line", json={"id_token": "test-classroom-token"}) for _ in range(30)]
    assert all(r.status_code == 200 for r in responses)
