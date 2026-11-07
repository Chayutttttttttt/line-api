"""Regression tests for the PDF-to-LINE assessment lifecycle."""

import base64
import hashlib
import hmac
import json
import os
import unittest
from io import BytesIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from components import documents, line, pdf_ai, quiz_bank, storage
from components.grading import WrittenMark
from components.learning import (
    AnswerRequest,
    GradeRequest,
    answer,
    review_answer,
)
from components.login import current_user
from components.quiz_bank import GeneratedQuiz
from db.database import get_session
from db.models import (
    Attempt,
    Chunk,
    Course,
    CourseMembership,
    Document,
    DocumentVersion,
    Job,
    LineIdentity,
    MessageOutbox,
    PracticeSession,
    PracticeSessionItem,
    Question,
    School,
    SchoolMembership,
    Topic,
    User,
)
from main import app
from worker import run as worker

EVIDENCE = "น้ำระเหยเมื่อได้รับความร้อน พืชคายน้ำทางปากใบ"
DRAFTS = [
    (
        "น้ำเปลี่ยนสถานะเมื่อใด",
        {
            "kind": "multiple_choice",
            "options": ["ได้รับความร้อน", "ถูกแช่แข็ง"],
            "correct_option": 1,
        },
    ),
    ("พืชคายน้ำทางปากใบ จริงหรือไม่", {"kind": "boolean", "expected": True}),
    (
        "อธิบายการระเหยด้วยคำของตนเอง",
        {
            "kind": "written",
            "criteria": "อธิบายผลของความร้อนต่อน้ำ",
            "reference_answer": "น้ำได้รับความร้อนแล้วระเหย",
        },
    ),
]


def draft(prompt, answer_spec, **kwargs):
    return {
        "prompt": prompt,
        "answer": answer_spec,
        "ordinal": 0,
        "quote": EVIDENCE,
        "hint": "สังเกตสถานะของน้ำ",
        "explanation": "น้ำเปลี่ยนเป็นไอเมื่อได้รับความร้อน",
        **kwargs,
    }


def mock_reader(test, rows):
    test.enterContext(patch.object(quiz_bank, "LLM_API_KEY", "test"))
    parse = test.enterContext(patch.object(quiz_bank, "OpenAI"))
    parse = parse.return_value.__enter__.return_value.responses.parse
    parse.return_value = SimpleNamespace(
        status="completed",
        output_parsed=GeneratedQuiz(questions=rows),
    )
    return parse


class QuizUnitTests(unittest.TestCase):
    def test_rejects_invented_sources_duplicate_prompts_and_choices(self):
        rows = [draft(p, a) for p, a in DRAFTS]
        mock_reader(
            self,
            [
                *rows,
                draft("อื่น", DRAFTS[1][1], ordinal=91),
                draft("อื่น", DRAFTS[1][1], quote="นอกเอกสาร"),
                rows[0],
            ],
        )
        chunk = Chunk(version_id=uuid4(), ordinal=0, text=EVIDENCE)
        valid = quiz_bank.generate_quiz([chunk], {})
        self.assertEqual([d.prompt for d in valid[0]], [p for p, _ in DRAFTS])
        rows[0] = draft(
            "เลือก",
            {
                "kind": "multiple_choice",
                "options": ["a", "A"],
                "correct_option": 1,
            },
        )
        with patch.object(quiz_bank, "OpenAI") as client:
            parse = client.return_value.__enter__.return_value.responses.parse
            parse.return_value = SimpleNamespace(
                status="completed", output_parsed=GeneratedQuiz(questions=rows)
            )
            with self.assertRaisesRegex(
                ValueError, "QUIZ_AI_RESPONSE_INVALID"
            ):
                quiz_bank.generate_quiz([chunk], {})

    def test_quick_replies_follow_the_entire_utf16_question(self):
        text_value = "ก" * 4999 + "🌱" * 2501
        messages = line.text_messages(text_value, ("ถูก", "ผิด"))
        self.assertEqual("".join(m["text"] for m in messages), text_value)
        self.assertTrue(
            all(len(m["text"].encode("utf-16-le")) <= 10000 for m in messages)
        )
        self.assertNotIn("quickReply", messages[0])
        self.assertEqual(
            messages[-1]["quickReply"]["items"][0]["action"]["text"], "ถูก"
        )


@unittest.skipUnless(
    os.getenv("QUIZ_TEST_DATABASE_URL"),
    "requires a PostgreSQL test database with pgvector",
)
class LineQuizIntegrationTests(unittest.TestCase):
    def setUp(self):
        url = os.environ["QUIZ_TEST_DATABASE_URL"]
        self.schema = "quiz_test_" + uuid4().hex
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {self.schema}"))
        self.addCleanup(admin.dispose)

        def cleanup_schema():
            with admin.begin() as conn:
                conn.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))

        self.addCleanup(cleanup_schema)
        self.engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={self.schema},public"},
        )
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine, checkfirst=False)
        self.enterContext(patch.object(worker, "engine", self.engine))
        self.enterContext(patch.object(worker, "LINE_PROVIDER_ID", "provider"))
        self.enterContext(patch.object(line, "LINE_PROVIDER_ID", "provider"))
        self.enterContext(patch.object(line, "LINE_CHANNEL_ID", "channel"))
        self.enterContext(patch.object(line, "CHANNEL_SECRET", "secret"))
        bucket = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(storage, "FILE_STORAGE_ROOT", bucket))
        self.enterContext(patch.object(storage, "STORAGE_BACKEND", "local"))
        self.enterContext(patch.object(pdf_ai, "LLM_API_KEY", "test"))
        reader = self.enterContext(patch.object(pdf_ai, "OpenAI"))
        read = reader.return_value.__enter__.return_value.responses.parse
        read.return_value = SimpleNamespace(
            status="completed",
            output=[],
            output_parsed=pdf_ai.PdfBatchRead(
                pages=[
                    {
                        "page_no": 1,
                        "sections": [
                            {
                                "topic": "วัฏจักรน้ำ",
                                "text": EVIDENCE,
                                "keywords": ["น้ำ"],
                            },
                        ],
                    }
                ]
            ),
        )
        self.parse = mock_reader(self, [draft(p, a) for p, a in DRAFTS])
        self.mark = self.enterContext(patch.object(worker, "mark_written"))
        self.mark.return_value = WrittenMark(
            correct=True, feedback="อธิบายเหตุผลได้"
        )
        self.tutor = self.enterContext(patch.object(worker, "generate_answer"))
        self.tutor.return_value = {"answer": "ข้อความจากผู้ช่วย", "citations": []}

        def session():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        self.enterContext(
            patch.dict(
                app.dependency_overrides,
                {get_session: session, current_user: lambda: self.teacher},
            )
        )
        self.client = self.enterContext(TestClient(app))
        with Session(self.engine, expire_on_commit=False) as db:
            self.student, self.teacher, school = (
                User(),
                User(),
                School(name="โรงเรียน"),
            )
            db.add_all([self.student, self.teacher, school])
            db.flush()
            self.course = Course(school_id=school.id, title="วิทยาศาสตร์")
            db.add(self.course)
            for user, role in [
                (self.student, "student"),
                (self.teacher, "teacher"),
            ]:
                db.add(
                    SchoolMembership(
                        user_id=user.id, school_id=school.id, role=role
                    )
                )
            db.flush()
            for user, role in [
                (self.student, "student"),
                (self.teacher, "teacher"),
            ]:
                db.add(
                    CourseMembership(
                        user_id=user.id,
                        course_id=self.course.id,
                        school_id=school.id,
                        role=role,
                    )
                )
            db.add(
                LineIdentity(
                    user_id=self.student.id,
                    provider_id="provider",
                    line_sub="student",
                )
            )
            db.commit()
        pdf = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(pdf)
        response = self.client.post(
            "/documents",
            data={"course_id": str(self.course.id), "title": "บทเรียน"},
            files={"file": ("lesson.pdf", pdf.getvalue(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 202, response.text)
        with Session(self.engine, expire_on_commit=False) as db:
            self.doc = db.get(Document, UUID(response.json()["document_id"]))
            self.source = db.get(
                DocumentVersion, UUID(response.json()["version_id"])
            )
        self.run_job()

    def run_job(self):
        claim = worker.claim_job()
        self.assertIsNotNone(claim)
        worker.process_job(claim)
        with Session(self.engine) as db:
            job = db.get(Job, claim["id"])
            self.assertEqual(job.state, "done", job.payload)

    def post_event(self, message, event_id=None):
        event = {
            "webhookEventId": event_id or uuid4().hex,
            "type": "message",
            "source": {"type": "user", "userId": "student"},
            "message": {"type": "text", "text": message, "id": uuid4().hex},
        }
        body = json.dumps({"events": [event]}).encode()
        signature = base64.b64encode(
            hmac.digest(b"secret", body, hashlib.sha256)
        ).decode()
        response = self.client.post(
            "/webhooks/line",
            content=body,
            headers={"X-Line-Signature": signature},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["accepted"]

    def chat(self, message, event_id=None):
        self.assertEqual(self.post_event(message, event_id), 1)
        self.run_job()
        with Session(self.engine) as db:
            return (
                db.exec(
                    select(MessageOutbox).order_by(
                        MessageOutbox.created_at.desc()
                    )
                )
                .first()
                .payload
            )

    def approve(self, scope="pilot"):
        with Session(self.engine) as db:
            version = db.get(DocumentVersion, self.source.id)
            review = documents.ReviewRequest(
                version=1,
                expected_revision=version.revision,
                scope=scope,
                decision="approve",
                checklist=dict.fromkeys(documents.CHECKLIST, True),
                rubric=dict.fromkeys(
                    ["correctness", "citations", "teaching", "scope"], 2
                ),
            )
            documents.publish_document(
                self.doc.id, review, user=self.teacher, db=db
            )

    def test_pdf_approval_mixed_chat_answers_and_personal_analysis(self):
        with Session(self.engine) as db:
            self.assertEqual(
                {q.status for q in db.exec(select(Question))},
                {"awaiting_source"},
            )
        self.approve("prototype")
        self.assertIn("ยังไม่มีโจทย์", self.chat("ทำข้อสอบ")["text"])
        self.approve()
        # Include a question authored before automatic generation.
        with Session(self.engine) as db:
            topic = db.exec(select(Topic)).one()
            db.add(
                Question(
                    topic_id=topic.id,
                    source_version_id=self.source.id,
                    status="published",
                    answer_type="numeric",
                    prompt="โจทย์เก่า",
                    grading_spec={"expected": "2"},
                    explanation="เฉลยข้อเก่า",
                )
            )
            db.commit()
        msg = self.chat("ทำข้อสอบ")
        self.assertEqual(msg["text"], self.chat("ทำข้อสอบ")["text"])
        self.assertNotIn("เฉลย", msg["text"])
        hint = self.chat("ขอคำใบ้")
        self.assertIn(msg["text"], hint["text"])
        self.assertEqual(hint["choices"], msg["choices"])
        self.assertEqual(hint["text"], self.chat("คำใบ้")["text"])
        with Session(self.engine) as db:
            self.assertIsNone(db.exec(select(Attempt)).first())
            items = db.exec(select(PracticeSessionItem)).all()
            self.assertEqual(sum(item.hints_used for item in items), 1)
        for n in range(4):
            self.assertIn(f"ข้อ {n + 1}/4", msg["text"])
            if "ส่งรหัสตัวเลือก" in msg["text"]:
                self.assertIn("ยังไม่ได้บันทึก", self.chat("Z")["text"])
                response = "1"
            elif "พิมพ์ ถูก หรือ ผิด" in msg["text"]:
                response = "ผิด"
            elif "พิมพ์อธิบาย" in msg["text"]:
                self.mark.return_value = None
                self.assertIn(
                    "ยังตรวจข้อเขียนไม่ได้", self.chat("น้ำร้อนกลายเป็นไอ")["text"]
                )
                self.mark.return_value = WrittenMark(
                    correct=True, feedback="อธิบายได้"
                )
                response = "น้ำร้อนกลายเป็นไอ"
            else:
                response = "2"
            event_id = uuid4().hex
            msg = self.chat(response, event_id)
            self.assertEqual(self.post_event(response, event_id), 0)
        self.assertIn("ผลสอบชุดนี้ · ตอบถูก 3/4", msg["text"])
        self.assertIn("ใช้คำใบ้ 1 ข้อ", msg["text"])
        self.assertIn("วัฏจักรน้ำ", self.chat("ผลสอบ")["text"])
        with Session(self.engine) as db:
            self.assertEqual(len(db.exec(select(Attempt)).all()), 4)
            self.assertEqual(
                db.exec(select(PracticeSession)).one().state, "line_completed"
            )
        self.tutor.assert_not_called()
        self.assertEqual(self.chat("ช่วยสรุปบทเรียน")["text"], "ข้อความจากผู้ช่วย")

    def add_manual_question(self, *, only=False):
        with Session(self.engine) as db:
            if only:
                for question in db.exec(select(Question)):
                    question.status = "draft"
            question = Question(
                topic_id=db.exec(select(Topic)).one().id,
                source_version_id=self.source.id,
                status="published",
                answer_type="manual",
                prompt="อธิบายผลการทดลอง",
                hint="เริ่มจากสิ่งที่สังเกตเห็น",
                grading_spec={"criteria": "อธิบายสาเหตุและผลที่พบ"},
                explanation="เฉลยสำหรับหลังครูตรวจ",
            )
            db.add(question)
            db.commit()
            return question.id

    def test_line_manual_answer_waits_for_teacher_and_refreshes_result(self):
        self.approve()
        question_id = self.add_manual_question(only=True)
        msg = self.chat("ทำข้อสอบ")
        self.assertIn("ข้อเขียนที่ครูตรวจ", msg["text"])
        self.assertIn("เกณฑ์: อธิบายสาเหตุและผลที่พบ", msg["text"])
        self.assertNotIn("เฉลย", msg["text"])
        hint = self.chat("ขอคำใบ้")
        self.assertIn("เริ่มจากสิ่งที่สังเกตเห็น", hint["text"])
        self.assertIn("ข้อ 1/1", hint["text"])
        event_id = uuid4().hex
        msg = self.chat("น้ำร้อนกลายเป็นไอ", event_id)
        self.assertEqual(self.post_event("น้ำร้อนกลายเป็นไอ", event_id), 0)
        self.assertIn("ส่งคำตอบแล้ว", msg["text"])
        self.assertIn("รอครูตรวจ 1 ข้อ", msg["text"])
        self.assertNotIn("ยังไม่ถูก", msg["text"])
        self.assertNotIn("0/0", msg["text"])
        self.assertNotIn("เฉลย", msg["text"])
        with Session(self.engine) as db:
            attempt = db.exec(select(Attempt)).one()
            self.assertEqual(attempt.question_id, question_id)
            self.assertEqual(attempt.score_status, "pending_review")
            review_answer(
                self.course.id,
                attempt.id,
                GradeRequest(score=0.5, feedback="อธิบายเหตุผลเพิ่ม"),
                user=self.teacher,
                db=db,
            )
        result = self.chat("ผลสอบ")["text"]
        self.assertIn("คะแนนรวมที่ตรวจแล้ว 0.5/1", result)
        self.assertNotIn("รอครูตรวจ", result)
        self.mark.assert_not_called()
        self.tutor.assert_not_called()

    def test_mixed_manual_and_automatic_scores_exclude_pending_answers(self):
        self.approve()
        self.add_manual_question()
        msg = self.chat("ทำข้อสอบ")
        for _ in range(4):
            question_text = msg["text"].split("\n\n")[-1]
            if "ส่งรหัสตัวเลือก" in question_text:
                response = "1"
            elif "พิมพ์ ถูก หรือ ผิด" in question_text:
                response = "ถูก"
            else:
                response = "น้ำได้รับความร้อนแล้วระเหย"
            msg = self.chat(response)
        self.assertIn("ตอบถูก 3/3 ข้อ", msg["text"])
        self.assertIn("รอครูตรวจ 1 ข้อ", msg["text"])
        self.assertNotIn("ตอบถูก 3/4", msg["text"])
        with Session(self.engine) as db:
            self.assertEqual(len(db.exec(select(Attempt)).all()), 4)
            self.assertEqual(
                db.exec(select(PracticeSession)).one().state, "line_completed"
            )

    def test_edit_withdrawal_and_cancelled_delivery(self):
        with Session(self.engine) as db:
            chunk = db.exec(select(Chunk)).one()
            version = db.get(DocumentVersion, self.source.id)
            documents.edit_chunk(
                version.id,
                chunk.id,
                documents.ChunkEdit(
                    text=EVIDENCE + " ข้อมูลเพิ่มเติม",
                    topic="น้ำ",
                    page_no=2,
                    expected_revision=version.revision,
                ),
                user=self.teacher,
                db=db,
            )
            self.assertEqual(db.exec(select(Question)).all(), [])
        self.approve()
        self.run_job()
        self.assertIn("ข้อ 1/3", self.chat("ทำข้อสอบ")["text"])
        with Session(self.engine) as db:
            ver = db.get(DocumentVersion, self.source.id)
            documents.withdraw(
                ver.id,
                documents.RevisionRequest(expected_revision=ver.revision),
                user=self.teacher,
                db=db,
            )
        with patch.object(worker.requests, "post") as push:
            worker.send_outbox()
            push.assert_not_called()
        self.assertIn("เอกสารอ้างอิงเปลี่ยน", self.chat("ถูก")["text"])
        with Session(self.engine) as db:
            self.assertFalse(db.exec(select(Attempt)).first())

    def test_cancel_and_liff_written_replay(self):
        self.approve()
        self.chat("ทำข้อสอบ")
        self.assertIn("ยกเลิกสอบแล้ว", self.chat("ยกเลิกสอบ")["text"])
        with Session(self.engine) as db:
            q = db.exec(
                select(Question).where(Question.answer_type == "written")
            ).one()
            practice = PracticeSession(
                user_id=self.student.id, course_id=self.course.id
            )
            db.add(practice)
            db.flush()
            db.add(
                PracticeSessionItem(
                    session_id=practice.id,
                    question_id=q.id,
                    question_version=q.version,
                )
            )
            db.commit()
            request = AnswerRequest(
                question_id=q.id,
                answer="น้ำร้อนกลายเป็นไอ",
                submission_id=uuid4(),
            )
            with patch(
                "components.learning.mark_written",
                return_value=self.mark.return_value,
            ) as mark:
                result = answer(practice.id, request, user=self.student, db=db)
                self.assertTrue(result["correct"])
                self.assertEqual(
                    answer(practice.id, request, user=self.student, db=db),
                    result,
                )
                mark.assert_called_once()

    def test_quiz_excludes_foreign_sources_and_other_students(self):
        self.approve()
        with Session(self.engine) as db:
            topic = db.exec(select(Topic)).one()
            other = Course(title="ต่างวิชา", school_id=self.course.school_id)
            db.add(other)
            db.flush()
            foreign = Document(
                title="เอกสารส่วนตัว",
                school_id=other.school_id,
                course_id=other.id,
            )
            db.add(foreign)
            db.flush()
            version = DocumentVersion(
                document_id=foreign.id,
                version=1,
                storage_key="foreign",
                checksum="private",
                status="published",
            )
            db.add(version)
            db.flush()
            db.add(
                Question(
                    prompt="อย่าแสดง",
                    topic_id=topic.id,
                    source_version_id=version.id,
                    status="published",
                    answer_type="boolean",
                    grading_spec={"expected": True},
                )
            )
            db.add(
                PracticeSession(
                    user_id=self.teacher.id,
                    course_id=self.course.id,
                    state="line_completed",
                )
            )
            db.commit()
        self.assertIn("ยังไม่มีผลสอบ", self.chat("ผลสอบ")["text"])
        first = self.chat("ทำข้อสอบ")
        self.assertIn("ข้อ 1/3", first["text"])
        self.assertEqual(first["version_ids"], [str(self.source.id)])
        with patch.object(worker, "CHANNEL_ACCESS_TOKEN", "test"):
            with patch.object(worker.requests, "post") as push:
                push.return_value.status_code = 200
                worker.send_outbox()  # Previous score lookup.
                worker.send_outbox()
                body = push.call_args.kwargs["json"]
                self.assertEqual(body["to"], "student")
                self.assertEqual(body["messages"][-1]["text"], first["text"])
                self.assertIn("quickReply", body["messages"][-1])
                self.assertIn(
                    "X-Line-Retry-Key", push.call_args.kwargs["headers"]
                )

    def test_unused_auto_questions_allow_deleting_an_unapproved_pdf(self):
        with Session(self.engine) as db:
            version = db.get(DocumentVersion, self.source.id)
            result = documents.delete_document_version(
                version.id,
                documents.RevisionRequest(expected_revision=version.revision),
                user=self.teacher,
                db=db,
            )
            self.assertTrue(result["object_deleted"])
            self.assertFalse(db.exec(select(Question)).first())

    def test_retried_generation_does_not_duplicate_published_questions(self):
        self.approve()
        with Session(self.engine) as db:
            db.add(
                Job(
                    kind="refresh_quiz",
                    payload={"version_id": str(self.source.id)},
                )
            )
            db.commit()
        self.run_job()
        with Session(self.engine) as db:
            self.assertEqual(len(db.exec(select(Question)).all()), 3)

    def test_quota_and_withdrawal_during_written_grading_do_not_score(self):
        self.approve()
        with Session(self.engine) as db:
            others = db.exec(
                select(Question).where(Question.answer_type != "written")
            ).all()
            for other in others:
                other.status = "draft"
            db.commit()
        self.assertIn("ข้อเขียน", self.chat("ทำข้อสอบ")["text"])
        with patch("components.learning.MAX_DAILY_AI_REQUESTS", 0):
            self.assertIn("ถึงขีดจำกัด AI", self.chat("น้ำกลายเป็นไอ")["text"])
            self.mark.assert_not_called()

        def withdraw_during_mark(_submission):
            with Session(self.engine) as db:
                version = db.get(DocumentVersion, self.source.id)
                documents.withdraw(
                    version.id,
                    documents.RevisionRequest(
                        expected_revision=version.revision
                    ),
                    user=self.teacher,
                    db=db,
                )
            return WrittenMark(correct=True, feedback="ตอบได้")

        self.mark.side_effect = withdraw_during_mark
        self.assertIn("เอกสารอ้างอิงเปลี่ยน", self.chat("น้ำกลายเป็นไอ")["text"])
        with Session(self.engine) as db:
            self.assertFalse(db.exec(select(Attempt)).first())
