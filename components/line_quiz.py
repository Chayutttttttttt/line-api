"""Run private LINE quizzes against the shared course question bank."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from components.grading import WrittenSubmission
from components.learning import (
    practice_source,
    published_questions,
    record_answer,
)
from components.quiz_bank import QUIZ_ORIGIN
from db.models import (
    Attempt,
    Chunk,
    PracticeSession,
    PracticeSessionItem,
    Question,
    Topic,
    utc_now,
)

START = {"ทำข้อสอบ", "ทำแบบทดสอบ", "เริ่มสอบ", "เริ่มแบบทดสอบ", "แบบทดสอบ", "quiz"}
RESULTS = {"ผลสอบ", "ดูผลสอบ"}
CANCEL = {"ยกเลิกสอบ", "ยกเลิกแบบทดสอบ"}
HINT = {"คำใบ้", "ขอคำใบ้"}
QUIZ_SIZE = 5
FORMATS = {
    "multiple_choice": "ปรนัย",
    "boolean": "ถูกหรือผิด",
    "written": "ข้อเขียน",
    "short_text": "คำตอบสั้น",
    "numeric": "ตัวเลข",
    "integer_set": "เซตจำนวนเต็ม",
    "manual": "ข้อเขียนที่ครูตรวจ",
}
ANSWER_HELP = {
    "multiple_choice": "ส่งรหัสตัวเลือกที่ต้องการ",
    "boolean": "พิมพ์ ถูก หรือ ผิด",
    "written": "พิมพ์อธิบายด้วยคำของตนเอง",
    "short_text": "พิมพ์คำหรือวลีสั้น ๆ",
    "numeric": "พิมพ์เฉพาะตัวเลขในหน่วยที่โจทย์กำหนด",
    "integer_set": "พิมพ์เซต เช่น {-2, 0, 3}",
    "manual": "พิมพ์คำตอบในแชต ระบบส่งให้ครูตรวจ",
}


@dataclass(frozen=True)
class QuizReply:
    text: str
    version_ids: tuple[UUID, ...] = ()
    choices: tuple[str, ...] = ()


def is_quiz_message(db, user_id, course_id, text):
    if text.strip().casefold() in START | RESULTS | CANCEL | HINT:
        return True
    return (
        db.exec(
            select(PracticeSession.id)
            .where(
                PracticeSession.user_id == user_id,
                PracticeSession.course_id == course_id,
                PracticeSession.state == "line_active",
            )
            .limit(1)
        ).first()
        is not None
    )


def select_quiz(db, user_id, course_id):
    """Interleave answer formats, preferring the least recently attempted."""
    history = (
        select(Attempt.question_id, func.max(Attempt.created_at).label("seen"))
        .where(Attempt.user_id == user_id)
        .group_by(Attempt.question_id)
        .subquery()
    )
    pool = (
        published_questions(course_id)
        .outerjoin(history, history.c.question_id == Question.id)
        .where(Question.answer_type.in_(list(FORMATS)))
        .with_only_columns(Question.id, Question.answer_type, history.c.seen)
        .subquery()
    )
    position = func.row_number().over(
        partition_by=pool.c.answer_type,
        order_by=(pool.c.seen.asc().nulls_first(), pool.c.id),
    )
    ranked = select(pool.c.id, pool.c.seen, position.label("pos")).subquery()
    return db.exec(
        select(Question)
        .join(ranked, ranked.c.id == Question.id)
        .order_by(ranked.c.pos, ranked.c.seen.asc().nulls_first(), Question.id)
        .limit(QUIZ_SIZE)
    ).all()


def start_quiz(db, user, course):
    questions = select_quiz(db, user.id, course.id)
    if not questions:
        return None
    practice = PracticeSession(
        user_id=user.id,
        course_id=course.id,
        state="line_active",
    )
    db.add(practice)
    db.flush()
    start = utc_now()
    for index, question in enumerate(questions):
        db.add(
            PracticeSessionItem(
                session_id=practice.id,
                question_id=question.id,
                question_version=question.version,
                served_at=start + timedelta(microseconds=index),
            )
        )
    return practice


def show_question(question, number, total):
    kind = question.answer_type
    lines = [f"ข้อ {number}/{total} · {FORMATS[kind]}", question.prompt]
    choices = ()
    if kind == "multiple_choice":
        choices = tuple(o["id"] for o in question.grading_spec["options"])
        lines.extend(
            f"{option['id']}. {option['text']}"
            for option in question.grading_spec["options"]
        )
    elif kind == "boolean":
        choices = ("ถูก", "ผิด")
    if kind == "numeric" and question.grading_spec.get("unit"):
        lines.append(f"หน่วย {question.grading_spec['unit']}")
    if kind == "manual":
        lines.append(f"เกณฑ์: {question.grading_spec['criteria']}")
    lines.extend([ANSWER_HELP[kind], "พิมพ์ “คำใบ้” หรือ “ยกเลิกสอบ” ได้"])
    return QuizReply(
        "\n".join(lines),
        (question.source_version_id,),
        (*choices, "คำใบ้"),
    )


def quiz_result(db, practice):
    rows = db.exec(
        select(Attempt, Question, Topic)
        .join(Question, Question.id == Attempt.question_id)
        .join(Topic, Topic.id == Question.topic_id)
        .where(
            Attempt.session_id == practice.id,
            Attempt.user_id == practice.user_id,
            Topic.course_id == practice.course_id,
        )
        .order_by(Attempt.created_at)
    ).all()
    pending_count = sum(a.score_status == "pending_review" for a, _, _ in rows)
    rows = [row for row in rows if row[0].score_status == "graded"]
    if not rows:
        return QuizReply(
            f"ส่งคำตอบครบชุดแล้ว · รอครูตรวจ {pending_count} ข้อ\n"
            "พิมพ์ “ผลสอบ” เพื่อดูผลหลังครูตรวจ",
            choices=("ผลสอบ", "ทำข้อสอบ"),
        )
    by_topic = defaultdict(Counter)
    by_format = defaultdict(Counter)
    independent = correct = hints = 0
    for attempt, question, topic in rows:
        right = attempt.score == attempt.max_score
        helped = attempt.hints_used > 0
        name = (
            question.rubric.get("topic", topic.title)
            if question.rubric.get("origin") == QUIZ_ORIGIN
            else topic.title
        )
        by_topic[name][
            "independent" if right and not helped else "review"
        ] += 1
        by_format[FORMATS[question.answer_type]]["total"] += 1
        by_format[FORMATS[question.answer_type]]["right"] += int(right)
        independent += int(right and not helped)
        correct += int(right)
        hints += int(helped)
    lines = [
        f"ผลสอบชุดนี้ · ตอบถูก {correct}/{len(rows)} ข้อ",
        f"ตอบถูกด้วยตนเอง {independent} ข้อ · ใช้คำใบ้ {hints} ข้อ",
        "ผลตามรูปแบบโจทย์",
        *(
            f"• {kind} {counts['right']}/{counts['total']}"
            for kind, counts in by_format.items()
        ),
    ]
    if pending_count:
        lines.append(
            f"รอครูตรวจ {pending_count} ข้อ · คะแนนข้างต้นนับเฉพาะข้อที่ตรวจแล้ว"
        )
    if any(q.answer_type == "manual" for _, q, _ in rows):
        score = sum(a.score for a, _, _ in rows)
        maximum = sum(a.max_score for a, _, _ in rows)
        lines.append(f"คะแนนรวมที่ตรวจแล้ว {score:g}/{maximum:g}")
    strengths = [
        name for name, counts in by_topic.items() if counts["independent"]
    ]
    review = [name for name, counts in by_topic.items() if counts["review"]]
    if strengths:
        lines.append("หัวข้อที่ตอบถูกด้วยตนเอง · " + ", ".join(strengths))
    if review:
        lines.append("ลองทบทวนข้อที่ผิดหรือใช้คำใบ้ · " + ", ".join(review))
    else:
        lines.append("ลองโจทย์ชุดถัดไปเพื่อฝึกใช้ความรู้กับคำถามใหม่")
    if len(rows) - hints < 3:
        lines.append("ยังมีข้อที่ทำโดยไม่ใช้คำใบ้น้อยกว่า 3 ข้อ ควรฝึกเพิ่มก่อนสรุประดับ")
    if pending_count:
        lines.append("พิมพ์ “ผลสอบ” เพื่อดูผลหลังครูตรวจ")
    lines.append("พิมพ์ “ทำข้อสอบ” เพื่อเริ่มชุดใหม่")
    choices = ("ผลสอบ", "ทำข้อสอบ") if pending_count else ("ทำข้อสอบ",)
    return QuizReply("\n".join(lines), choices=choices)


def source_note(db, question, source):
    label = f"อ้างอิง {source.filename} รุ่น {source.version}"
    if question.rubric.get("origin") != QUIZ_ORIGIN:
        return label
    chunk_id = question.rubric.get("source_chunk_id")
    chunk = db.get(Chunk, UUID(chunk_id)) if chunk_id else None
    if chunk and chunk.version_id == source.id and chunk.page_no:
        label += f" หน้า {chunk.page_no}"
        if chunk.page_end and chunk.page_end != chunk.page_no:
            label += f"–{chunk.page_end}"
    return label


def checked_source(db, practice, item, question):
    try:
        return practice_source(db, practice, item, question)
    except HTTPException:
        practice.state = "line_cancelled"
        return None


SOURCE_CHANGED = "โจทย์หรือเอกสารอ้างอิงเปลี่ยนแล้ว พิมพ์ “ทำข้อสอบ” เพื่อเริ่มชุดใหม่"


def handle_quiz(
    db: Session,
    user,
    course,
    text: str,
    submission_id: UUID,
    assessment=None,
) -> QuizReply | WrittenSubmission | None:
    """Return the reply to commit together with the learner's attempt."""
    command = text.strip().casefold()
    sessions = select(PracticeSession).where(
        PracticeSession.user_id == user.id,
        PracticeSession.course_id == course.id,
    )
    if command in RESULTS:
        last = db.exec(
            sessions.where(PracticeSession.state == "line_completed")
            .order_by(PracticeSession.created_at.desc())
            .limit(1)
        ).first()
        return (
            quiz_result(db, last)
            if last
            else QuizReply("ยังไม่มีผลสอบที่ทำจบในวิชานี้ พิมพ์ “ทำข้อสอบ” เพื่อเริ่ม")
        )
    practice = db.exec(
        sessions.where(
            PracticeSession.state == "line_active"
        ).with_for_update()
    ).first()
    if command in CANCEL:
        if practice:
            practice.state = "line_cancelled"
            return QuizReply("ยกเลิกสอบแล้ว เก็บผลข้อที่ส่งแล้วในความก้าวหน้าของคุณ")
        return QuizReply("ไม่มีแบบทดสอบที่กำลังทำในวิชานี้")
    if not practice:
        if command in HINT:
            return QuizReply("พิมพ์ “ทำข้อสอบ” เพื่อเริ่มก่อนขอคำใบ้")
        if command not in START:
            return None
        practice = start_quiz(db, user, course)
        if not practice:
            return QuizReply("วิชานี้ยังไม่มีโจทย์พร้อมใช้จากเอกสารที่อนุมัติแล้ว")

    return take_question(db, practice, text, submission_id, assessment)


def take_question(db, practice, text, submission_id, assessment):
    command = text.strip().casefold()
    items = db.exec(
        select(PracticeSessionItem, Question)
        .join(Question, Question.id == PracticeSessionItem.question_id)
        .where(PracticeSessionItem.session_id == practice.id)
        .order_by(PracticeSessionItem.served_at, PracticeSessionItem.id)
    ).all()
    answered = set(
        db.exec(
            select(Attempt.question_id).where(
                Attempt.session_id == practice.id,
                Attempt.user_id == practice.user_id,
            )
        ).all()
    )
    pending = [(item, q) for item, q in items if q.id not in answered]
    if not pending:
        practice.state = "line_completed"
        return quiz_result(db, practice)
    (item, question), *remaining = pending
    source = checked_source(db, practice, item, question)
    if not source:
        return QuizReply(SOURCE_CHANGED)
    if command in START:
        return show_question(question, len(answered) + 1, len(items))
    if command in HINT:
        item.hints_used = 1
        shown = show_question(question, len(answered) + 1, len(items))
        return QuizReply(
            f"คำใบ้ · {question.hint}\n\n{shown.text}",
            shown.version_ids,
            shown.choices,
        )
    answer = text.strip().removeprefix("ตอบ ").strip()
    if not answer or len(answer) > 2000:
        return QuizReply("กรุณาส่งคำตอบ 1–2,000 ตัวอักษรสำหรับข้อเดิม")
    try:
        result = record_answer(
            db,
            practice,
            item,
            question,
            answer,
            submission_id,
            assessment=assessment,
        )
    except HTTPException as error:
        if error.detail == "WRITTEN_GRADING_UNAVAILABLE":
            return QuizReply("ยังตรวจข้อเขียนไม่ได้ กรุณาส่งคำตอบข้อนี้อีกครั้ง")
        if error.detail == "WRITTEN_MARK_UNCERTAIN":
            return QuizReply("ยังให้คะแนนข้อนี้ไม่ได้ ลองอธิบายเหตุผลเพิ่มหรือขอคำใบ้")
        if error.status_code == 400:
            return QuizReply(
                "ยังไม่ได้บันทึกคำตอบ · " + ANSWER_HELP[question.answer_type]
            )
        raise
    if isinstance(result, WrittenSubmission):
        return result
    verdict = (
        "ส่งคำตอบแล้ว"
        if result["score_status"] == "pending_review"
        else "ตอบถูก" if result["correct"] else "ยังไม่ถูก"
    )
    feedback = (
        f"{verdict} · {result['explanation']}\n"
        f"{source_note(db, question, source)}"
    )
    if remaining:
        next_item, next_question = remaining[0]
        if checked_source(db, practice, next_item, next_question):
            followup = show_question(
                next_question, len(answered) + 2, len(items)
            )
        else:
            followup = QuizReply(SOURCE_CHANGED)
    else:
        practice.state = "line_completed"
        followup = quiz_result(db, practice)
    return QuizReply(
        f"{feedback}\n\n{followup.text}",
        (source.id, *followup.version_ids),
        followup.choices,
    )
