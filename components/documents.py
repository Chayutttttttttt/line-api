"""Course-scoped document ingestion, direct source-ID retrieval and private downloads."""
import hashlib
import logging
import io
import re
import unicodedata
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
import xml.etree.ElementTree as ET
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Response, Query
from pydantic import BaseModel, Field, StrictInt
from pypdf import PdfReader
from sqlalchemy import delete
from sqlmodel import Session, select

from components.chunking import chunk_page
from components.embeddings import embed_query
from components.login import course_access, current_user
from components.storage import put_file, read_file
from config import EMBEDDINGS_ENABLED, EMBEDDING_MODEL, MAX_UPLOAD_BYTES
from db.database import get_session
from db.models import (AuditEvent, Chunk, ContentReview, Document, DocumentVersion, Job, Topic, User, utc_now)

router = APIRouter(tags=["documents"])
log = logging.getLogger(__name__)
# Only teacher-approved documents are visible to students and retrievable by AI.
TEACHING_READY_STATUSES = ("published",)
MATERIAL_TYPES = ("lesson", "textbook", "worksheet", "solution", "slides", "reference")
CHECKLIST = {
    "scope": "ขอบเขตและรายวิชาถูกต้อง",
    "definitions": "นิยาม แนวคิด และข้อเท็จจริงของรายวิชาถูกต้อง",
    "notation": "ศัพท์ สัญลักษณ์ หน่วย และรูปแบบภาษาถูกต้องตามรายวิชา",
    "examples": "ตัวอย่างตรวจย้อนกลับได้",
    "solutions": "เฉลยและเหตุผลถูกต้อง",
    "hints": "คำใบ้ช่วยให้ลองต่อ",
    "language": "ภาษาเหมาะกับระดับชั้น",
    "misconceptions": "ครอบคลุมความเข้าใจผิด",
    "grading": "ทักษะและเกณฑ์ตรวจชัดเจน",
    "boundaries": "ระบุเนื้อหานอกขอบเขต",
    "citations": "ชื่อไฟล์ หน้า และรุ่นถูกต้อง",
    "rights": "ยืนยันสิทธิ์การใช้เอกสาร",
    "extraction": "ตรวจข้อความ สมการ ตาราง และเลขหน้าที่สกัดแล้ว",
}


def version_access(db: Session, user: User, version_id: UUID, teacher=False, lock=False):
    query = select(DocumentVersion).where(DocumentVersion.id == version_id)
    if lock:
        query = query.with_for_update()
    version = db.exec(query).first()
    if not version:
        raise HTTPException(404, "VERSION_NOT_FOUND")
    document = db.get(Document, version.document_id)
    course_access(db, user, document.course_id, teacher)
    if not teacher:
        # Only course members may access extracted teaching documents.
        # Evidence, uploads still processing, failed and withdrawn versions stay private.
        if document.purpose != "teaching" or version.status not in TEACHING_READY_STATUSES:
            raise HTTPException(403, "DOCUMENT_NOT_PUBLISHED")
    return document, version


def extract_pages(data: bytes, filename: str) -> list[tuple[int, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("INVALID_PDF")
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 200:
            raise ValueError("ENCRYPTED_OR_TOO_MANY_PAGES")
        pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    elif suffix == ".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 20_000_000:
                raise ValueError("DOCX_EXPANSION_TOO_LARGE")
            root = ET.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            text = "\n".join("".join(t.text or "" for t in p.findall(".//w:t", ns))
                for p in root.findall(".//w:p", ns))
            # DOCX has no trustworthy physical page numbers. Teacher sets them in review.
            pages = [(None, text)]
    elif suffix == ".txt":
        pages = [(None, data.decode("utf-8"))]
    else:
        raise ValueError("UNSUPPORTED_FILE")
    if sum(len(t) for _, t in pages) > 1_000_000 or not any(t.strip() for _, t in pages):
        raise ValueError("EMPTY_OR_TOO_LARGE_TEXT_USE_TEXT_PDF")
    return pages


def ingest(db: Session, version_id: UUID, ai_pages: list[tuple[int, str, list[str], str | None]] | None = None):
    version = db.exec(select(DocumentVersion).where(DocumentVersion.id == version_id).with_for_update()).first()
    if not version or version.status not in {"uploaded", "processing"}:
        return
    if version.filename.lower().endswith(".pdf"):
        if ai_pages is None:
            raise ValueError("PDF_AI_REQUIRED")
        pages = ai_pages
    else:
        data = read_file(version.storage_key, version.checksum)
        pages = [(n, content, [], None) for n, content in extract_pages(data, version.filename)]
    # Prepare all metadata before changing database state.
    prepared = []
    blank = []
    warnings = []
    for page_no, page_text, keywords, note in pages:
        if not page_text.strip():
            blank.append(page_no)
        if note:
            warnings.append(f"หน้า {page_no}: {note}")
        for part in chunk_page(page_text):
            # Keywords are context for matching, not a replacement for the source text.
            related = [k for k in keywords if k.casefold() in part.casefold()]
            prepared.append((page_no, part, related or keywords[:8]))
    if not prepared:
        raise ValueError("NO_SEARCHABLE_TEXT")
    db.exec(delete(Chunk).where(Chunk.version_id == version.id))
    for ordinal, (page_no, part, keywords) in enumerate(prepared):
        db.add(Chunk(version_id=version.id, ordinal=ordinal, page_no=page_no,
            text=part, keywords=keywords))
    messages = ([f"หน้าไม่มีข้อความ: {', '.join(map(str, blank[:30]))}"] if blank else []) + warnings[:20]
    version.extraction_warning = " | ".join(messages)[:4000] or None
    # Mandatory teacher checklist + approval; never auto-publish.
    version.status = "review"
    version.revision += 1
    db.add(version)


@router.get("/documents/checklist")
def checklist(user: User = Depends(current_user)):
    return CHECKLIST


@router.post("/documents", status_code=202)
def upload_document(course_id: UUID = Form(), title: str = Form(min_length=1, max_length=255),
    purpose: Literal["teaching", "evidence"] = Form("teaching"),
    material_type: Literal["lesson", "textbook", "worksheet", "solution", "slides", "reference"] = Form("lesson"),
    topic_id: UUID | None = Form(None),
    document_id: UUID | None = Form(None), file: UploadFile = File(),
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    course = course_access(db, user, course_id, teacher=True)
    filename = Path((file.filename or "").replace("\\", "/")).name
    suffix = Path(filename).suffix.lower()
    mime_types = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain"}
    if suffix not in mime_types or len(filename) > 255:
        raise HTTPException(400, "PDF_DOCX_TXT_ONLY")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "EMPTY_OR_TOO_LARGE_FILE")
    if purpose == "evidence" and topic_id is not None:
        raise HTTPException(400, "EVIDENCE_HAS_NO_TEACHING_TOPIC")
    if topic_id is not None:
        topic = db.get(Topic, topic_id)
        if not topic or topic.course_id != course_id:
            raise HTTPException(400, "TOPIC_NOT_IN_COURSE")
    # Reject disguised files before storing; full extraction runs in worker.
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(400, "INVALID_PDF")
    if suffix == ".docx" and not zipfile.is_zipfile(io.BytesIO(data)):
        raise HTTPException(400, "INVALID_DOCX")
    if document_id:
        document = db.exec(select(Document).where(Document.id == document_id).with_for_update()).first()
        if not document or document.course_id != course_id or document.purpose != purpose:
            raise HTTPException(404, "DOCUMENT_NOT_FOUND")
        if document.material_type != material_type or document.topic_id != topic_id:
            raise HTTPException(409, "DOCUMENT_METADATA_MISMATCH")
        latest = db.exec(select(DocumentVersion).where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version.desc())).first()
        number = latest.version + 1 if latest else 1
    else:
        document = Document(school_id=course.school_id, course_id=course_id,
            title=title.strip(), purpose=purpose, material_type=material_type, topic_id=topic_id)
        db.add(document)
        db.flush()
        number = 1
    version = DocumentVersion(document_id=document.id, version=number, filename=filename,
        content_type=mime_types[suffix], size_bytes=len(data), storage_key=f"{course.school_id}/{course.id}/{uuid4()}{suffix}",
        checksum=hashlib.sha256(data).hexdigest())
    put_file(version.storage_key, data)
    db.add(version)
    db.flush()
    job = Job(kind="ingest", user_id=user.id, payload={"version_id": str(version.id)})
    db.add(job)
    db.add(AuditEvent(actor_id=user.id, action="document.upload", object_id=version.id))
    db.commit()
    return {"document_id": document.id, "version_id": version.id, "ingestion_job_id": job.id, "revision": version.revision}


@router.get("/documents")
def list_documents(course_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    course_access(db, user, course_id)
    try:
        course_access(db, user, course_id, True)
        teacher = True
    except HTTPException:
        teacher = False
    rows = db.exec(select(Document, DocumentVersion).join(DocumentVersion)
        .where(Document.course_id == course_id).order_by(DocumentVersion.created_at.desc())).all()
    return [{"document_id": d.id, "title": d.title, "purpose": d.purpose,
        "material_type": d.material_type, "topic_id": d.topic_id,
        **v.model_dump(exclude={"storage_key"})} for d, v in rows
        if teacher or (d.purpose == "teaching" and v.status in TEACHING_READY_STATUSES)]


@router.get("/documents/versions/{version_id}")
def document_detail(version_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    document, version = version_access(db, user, version_id, teacher=True)
    return {"document": document, "version": version.model_dump(exclude={"storage_key"}),
        "chunks": db.exec(select(Chunk).where(Chunk.version_id == version_id).order_by(Chunk.ordinal)).all(),
        "reviews": db.exec(select(ContentReview).where(ContentReview.version_id == version_id).order_by(ContentReview.created_at)).all()}


class ChunkEdit(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    page_no: int = Field(ge=1, le=1000)
    keywords: list[str] = Field(default_factory=list, max_length=12)
    expected_revision: int = Field(ge=1)


@router.patch("/documents/versions/{version_id}/chunks/{chunk_id}")
def edit_chunk(version_id: UUID, chunk_id: UUID, data: ChunkEdit,
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    _, version = version_access(db, user, version_id, teacher=True, lock=True)
    if version.status != "review" or version.revision != data.expected_revision:
        raise HTTPException(409, "VERSION_CONFLICT")
    chunk = db.get(Chunk, chunk_id)
    if not chunk or chunk.version_id != version_id:
        raise HTTPException(404, "CHUNK_NOT_FOUND")
    chunk.text, chunk.page_no, chunk.embedding, chunk.embedding_model = data.text, data.page_no, None, None
    chunk.keywords = list(dict.fromkeys(k.strip()[:80] for k in data.keywords if k.strip()))[:12]
    version.revision += 1
    db.add(chunk)
    db.add(version)
    db.add(AuditEvent(actor_id=user.id, action="chunk.correct", object_id=chunk.id))
    db.commit()
    return {"revision": version.revision}


@router.post("/documents/versions/{version_id}/index")
def reindex_embeddings(version_id: UUID, user: User = Depends(current_user),
    db: Session = Depends(get_session)):
    """Queue embeddings for already uploaded teaching files (without re-upload)."""
    if not EMBEDDINGS_ENABLED:
        raise HTTPException(409, "EMBEDDINGS_DISABLED")
    document, version = version_access(db, user, version_id, teacher=True, lock=True)
    if document.purpose != "teaching" or version.status not in TEACHING_READY_STATUSES:
        raise HTTPException(409, "DOCUMENT_NOT_READY_FOR_INDEXING")
    pending = db.exec(select(Job).where(Job.kind == "embed",
        Job.state.in_(["queued", "retry", "running"]))).all()
    if any(job.payload.get("version_id") == str(version_id) for job in pending):
        raise HTTPException(409, "DOCUMENT_INDEXING_ALREADY_QUEUED")
    # Only enqueue chunks that are not indexed with the configured model.
    chunks = db.exec(select(Chunk).where(Chunk.version_id == version_id)
        .order_by(Chunk.ordinal)).all()
    batches = sorted({c.ordinal // 8 for c in chunks
        if c.embedding is None or c.embedding_model != EMBEDDING_MODEL})
    for batch in batches:
        db.add(Job(kind="embed", user_id=None,
            payload={"version_id": str(version_id), "start": batch * 8, "limit": 8}))
    db.add(AuditEvent(actor_id=user.id, action="document.index", object_id=version_id))
    db.commit()
    return {"version_id": version_id, "queued_batches": len(batches)}


class ReviewRequest(BaseModel):
    version: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    scope: Literal["prototype", "pilot"]
    decision: Literal["approve", "revise", "reject"]
    checklist: dict[str, bool]
    rubric: dict[str, StrictInt] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=5000)


@router.post("/documents/{document_id}/publish")
def publish_document(document_id: UUID, data: ReviewRequest,
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    version = db.exec(select(DocumentVersion).where(DocumentVersion.document_id == document_id,
        DocumentVersion.version == data.version).with_for_update()).first()
    if not version:
        raise HTTPException(404, "VERSION_NOT_FOUND")
    document, version = version_access(db, user, version.id, teacher=True)
    if version.revision != data.expected_revision or version.status != "review":
        raise HTTPException(409, "VERSION_CONFLICT")
    if data.decision == "approve" and document.purpose == "teaching":
        if set(data.checklist) != set(CHECKLIST) or not all(data.checklist.values()):
            raise HTTPException(400, "ALL_CONTENT_CHECKS_REQUIRED")
        if set(data.rubric) != {"correctness", "citations", "teaching", "scope"} or any(v != 2 for v in data.rubric.values()):
            raise HTTPException(400, "CONTENT_RUBRIC_MUST_PASS_0_TO_2_SCALE")
        chunks = db.exec(select(Chunk).where(Chunk.version_id == version.id)).all()
        if not chunks or any(c.page_no is None for c in chunks):
            raise HTTPException(400, "REVIEW_PAGE_NUMBERS_REQUIRED")
        if version.extraction_warning and not data.notes.strip():
            raise HTTPException(400, "REVIEW_EXTRACTION_WARNING_IN_NOTES")
    review = ContentReview(version_id=version.id, reviewer_id=user.id,
        decision=data.decision, scope=data.scope, checklist=data.checklist, rubric=data.rubric, notes=data.notes)
    db.add(review)
    version.revision += 1
    if data.decision == "approve":
        # Prototype approval is recorded but never exposes content to students.
        version.status = "published" if data.scope == "pilot" else "review"
        version.approved_by, version.approved_at = user.id, utc_now()
    elif data.decision == "reject":
        version.status = "withdrawn"
    db.add(version)
    db.add(AuditEvent(actor_id=user.id, action=f"document.{data.decision}.{data.scope}", object_id=version.id))
    db.commit()
    return {"version_id": version.id, "status": version.status, "revision": version.revision, "review_id": review.id}


class RevisionRequest(BaseModel):
    expected_revision: int = Field(ge=1)


@router.post("/documents/versions/{version_id}/withdraw")
def withdraw(version_id: UUID, data: RevisionRequest, user: User = Depends(current_user), db: Session = Depends(get_session)):
    _, version = version_access(db, user, version_id, teacher=True, lock=True)
    if version.revision != data.expected_revision:
        raise HTTPException(409, "VERSION_CONFLICT")
    version.status, version.revision = "withdrawn", version.revision + 1
    db.add(version)
    db.add(ContentReview(version_id=version.id, reviewer_id=user.id, decision="withdraw", scope="pilot", checklist={}, notes="ถอนการใช้เอกสาร"))
    db.add(AuditEvent(actor_id=user.id, action="document.withdraw", object_id=version.id))
    db.commit()
    return {"status": version.status, "revision": version.revision}


@router.get("/documents/versions/{version_id}/file")
def download(version_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_session)):
    try:
        document, version = version_access(db, user, version_id)
    except HTTPException as error:
        if error.status_code != 403:
            raise
        document, version = version_access(db, user, version_id, teacher=True)
    data = read_file(version.storage_key, version.checksum)
    db.add(AuditEvent(actor_id=user.id, action="document.download", object_id=version.id))
    db.commit()
    from urllib.parse import quote
    return Response(data, media_type=version.content_type, headers={"Cache-Control": "no-store",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(version.filename)}", "X-Content-Type-Options": "nosniff"})


def search_materials(db: Session, user: User, course_id: UUID, query: str,
                     source_version_id: UUID | None = None):
    course_access(db, user, course_id)
    # A caller-supplied PDF ID is never trusted: validate course, purpose and state.
    if source_version_id is not None:
        source = db.get(DocumentVersion, source_version_id)
        document = db.get(Document, source.document_id) if source else None
        if (not source or not document or document.course_id != course_id
                or document.purpose != "teaching" or source.status not in TEACHING_READY_STATUSES):
            raise HTTPException(404, "TEACHING_FILE_NOT_AVAILABLE")
    # Read extracted text, not raw PDF bytes; never retrieve evidence/other courses.
    statement = (select(Chunk, DocumentVersion, Document)
        .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.course_id == course_id, Document.purpose == "teaching",
               DocumentVersion.status.in_(TEACHING_READY_STATUSES)))
    if source_version_id is not None:
        statement = statement.where(DocumentVersion.id == source_version_id)
    rows = db.exec(statement).all()
    semantic_scores = {}
    if EMBEDDINGS_ENABLED and rows:
        try:
            vector = embed_query(query)
            if vector is not None:
                distance = Chunk.embedding.cosine_distance(vector)
                similar = (select(Chunk.id, distance)
                    .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
                    .join(Document, DocumentVersion.document_id == Document.id)
                    .where(Document.course_id == course_id, Document.purpose == "teaching",
                        DocumentVersion.status.in_(TEACHING_READY_STATUSES),
                        Chunk.embedding_model == EMBEDDING_MODEL, Chunk.embedding.is_not(None)))
                if source_version_id is not None:
                    similar = similar.where(DocumentVersion.id == source_version_id)
                for chunk_id, value in db.exec(similar.order_by(distance).limit(30)).all():
                    semantic_scores[chunk_id] = 5.0 * max(0.0, 1.0 - float(value))
        except Exception as error:
            # Optional vector retrieval must never block safe lexical search.
            log.warning("vector retrieval unavailable (%s)", type(error).__name__)
    def normalize(value):
        return unicodedata.normalize("NFC", value).casefold()

    query = normalize(query[:8000])
    terms = set(re.findall(r"[^\W_]{2,}", query))
    # Thai text often has no spaces. Character grams avoid a subject-specific dictionary.
    grams = {word[i:i+3] for word in re.findall(r"[\u0e00-\u0e7f]+", query)
        for i in range(len(word) - 2)}
    keywords = set()
    for topic in db.exec(select(Topic).where(Topic.course_id == course_id)).all():
        vocabulary = [normalize(topic.title), *[normalize(k) for k in topic.keywords]]
        if any(k in query for k in vocabulary):
            keywords.update(vocabulary)
    scored = []
    for chunk, version, document in rows:
        text = normalize(chunk.text)
        direct = sum(term in text for term in terms)
        topic_match = sum(term in text for term in keywords)
        shared = sum(g in text for g in grams)
        gram_score = shared / max(len(grams), 1) if shared >= 3 else 0
        score = direct * 3 + topic_match * 4 + (gram_score if gram_score >= .2 else 0)
        score += semantic_scores.get(chunk.id, 0)
        # AI-derived, teacher-reviewed keywords connect questions with source chunks.
        aliases = [normalize(k) for k in (chunk.keywords or [])]
        score += sum(5 for keyword in aliases if keyword in query or query in keyword) if query else 0
        score += sum(2 for keyword in aliases if any(term in keyword for term in terms))
        scored.append((score, chunk, version, document))
    # For a selected PDF, permit general prompts (e.g. "สรุปไฟล์นี้")
    # to fall back to its first pages if no exact keyword matches were found.
    if source_version_id is not None and not any(score > 0 for score, *_ in scored):
        scored.sort(key=lambda row: row[1].ordinal)
    else:
        scored.sort(key=lambda row: (-row[0], str(row[1].id)))
    return [{"chunk_id": str(c.id), "document_id": str(d.id), "version_id": str(v.id),
             "document": d.title, "filename": v.filename, "version": v.version,
             "page_no": c.page_no, "checksum": v.checksum, "text": c.text,
             "keywords": c.keywords}
        for score, c, v, d in scored[:5] if score > 0 or source_version_id is not None]


@router.get("/materials/search")
def search(course_id: UUID, query: str = Query(min_length=1, max_length=2000),
    source_version_id: UUID | None = None,
    user: User = Depends(current_user), db: Session = Depends(get_session)):
    return search_materials(db, user, course_id, query, source_version_id)
