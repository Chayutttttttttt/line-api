"use client";

import { useEffect, useState } from "react";
import { api, saveBlob } from "@/lib/api";

type MaterialType = "lesson" | "textbook" | "worksheet" | "solution" | "slides" | "reference";
const materialNames: Record<MaterialType, string> = {
  lesson: "ใบความรู้/บทเรียน", textbook: "หนังสือเรียน", worksheet: "ใบงาน/แบบฝึก",
  solution: "เฉลย", slides: "สไลด์", reference: "เอกสารอ้างอิงเสริม",
};
type Version = { id: string; document_id: string; title: string; purpose: string; material_type: MaterialType; topic_id: string | null; version: number; revision: number; status: string; filename: string; checksum: string; extraction_error: string | null; extraction_warning: string | null };
type Chunk = { id: string; text: string; page_no: number | null };
type Detail = { document: { purpose: string; material_type: MaterialType; topic_id: string | null }; version: Version; chunks: Chunk[]; reviews: { id: string; reviewer_id: string; decision: string; scope: string; notes: string; rubric: Record<string, number>; created_at: string }[] };
type Report = { readiness: string; blockers: string[] };
type Question = { id: string; prompt: string; status: string };
type EvaluationCase = { id: string; input: string; expected: string; failure: string; needs_customization: boolean };
const value = (form: FormData, key: string) => String(form.get(key) ?? "");

export default function TeacherPanel({ courseId, mode }: { courseId: string; mode: "documents" | "acceptance" }) {
  const [versions, setVersions] = useState<Version[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [uploadDocId, setUploadDocId] = useState("");
  const [uploadPurpose, setUploadPurpose] = useState("teaching");
  const [uploadType, setUploadType] = useState<MaterialType>("lesson");
  const [uploadTopic, setUploadTopic] = useState("");
  const [documentTab, setDocumentTab] = useState<"upload" | "library" | "questions">("upload");
  const [acceptanceTab, setAcceptanceTab] = useState<"evidence" | "cases" | "scoring" | "report">("evidence");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [topics, setTopics] = useState<{ id: string; title: string }[]>([]);
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [courseRevision, setCourseRevision] = useState(1);
  const [editingCase, setEditingCase] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([api<Version[]>(`/documents?course_id=${courseId}`),
      api<Question[]>(`/questions?course_id=${courseId}`), api<{id: string; title: string}[]>(`/topics?course_id=${courseId}`),
      api<{cases: EvaluationCase[]; course_revision: number}>(`/evaluation/cases?course_id=${courseId}`)])
      .then(([v, q, t, e]) => { if (active) { setVersions(v); setQuestions(q); setTopics(t); setCases(e.cases); setCourseRevision(e.course_revision); } })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [courseId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    api<Detail>(`/documents/versions/${selectedId}`).then((d) => { if (active) setDetail(d); }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [selectedId]);

  async function refresh() {
    setVersions(await api<Version[]>(`/documents?course_id=${courseId}`));
    if (selectedId) setDetail(await api<Detail>(`/documents/versions/${selectedId}`));
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return <div className="space-y-5" aria-busy={busy}>
    <h2 className="pilot-heading">{mode === "documents" ? "สื่อการสอนและแบบฝึกหัด" : "ตรวจความพร้อมก่อนใช้งานจริง"}</h2>
    {mode === "documents" && <nav aria-label="เมนูสื่อการสอน" className="grid gap-2 sm:grid-cols-3">
      {([["upload", "อัปโหลดไฟล์"], ["library", "ดูและแก้ไฟล์"], ["questions", "สร้างแบบฝึกหัด"]] as const).map(([id, title]) =>
        <button key={id} type="button" className={documentTab === id ? "pilot-button" : "pilot-secondary"}
          aria-current={documentTab === id ? "page" : undefined}
          onClick={() => {setDocumentTab(id);setError("");setMessage("");}}>{title}</button>)}
    </nav>}
    {mode === "acceptance" && <nav aria-label="ขั้นตอนตรวจรับระบบ" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {([["evidence","1. บันทึกหลักฐาน"],["cases","2. จัดชุดทดสอบ"],["scoring","3. ประเมิน AI"],["report","4. สรุปผล"]] as const).map(([id,title]) =>
        <button key={id} type="button" className={acceptanceTab === id ? "pilot-button" : "pilot-secondary"}
          aria-current={acceptanceTab === id ? "page" : undefined}
          onClick={() => {setAcceptanceTab(id);setError("");setMessage("");}}>{title}</button>)}
    </nav>}
    {error && <p role="alert" className="rounded-xl border border-danger p-3 text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl bg-brand-mint p-3 break-all">{message}</p>}
    {mode === "documents" && <>
      <p className="text-sm text-secondary">เพิ่มสื่อการสอนให้ผู้เรียนใช้ในรายวิชานี้ ไฟล์สอนพร้อมใช้กับ AI ใน LINE หลังอ่านไฟล์สำเร็จ ส่วนไฟล์หลักฐานจะไม่ถูกนำไปตอบ AI</p>
      {documentTab === "upload" && <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); const target = e.currentTarget; form.set("course_id", courseId);
        if (!value(form, "document_id")) form.delete("document_id");
        if (!value(form, "topic_id")) form.delete("topic_id");
        void run(async () => { const uploaded = await api<{ingestion_job_id: string; version_id: string}>("/documents", { method: "POST", body: form }); setMessage("รับไฟล์แล้ว กด ‘ดูและแก้ไฟล์’ เพื่อตรวจว่าอ่านข้อความสำเร็จหรือไม่"); target.reset(); setUploadDocId(""); setUploadPurpose("teaching"); setUploadType("lesson"); setUploadTopic(""); await refresh(); }); }}>
        <label>ชื่อเอกสาร<input name="title" required maxLength={255} className="pilot-input" /></label>
        <label>การใช้เอกสาร<select name="purpose" className="pilot-input" value={uploadPurpose} onChange={(e) => { setUploadPurpose(e.target.value); if (e.target.value === "evidence") setUploadTopic(""); }}><option value="teaching">เอกสารสอน (ใช้ตอบ AI)</option><option value="evidence">หลักฐานและเอกสารโครงการ (ไม่ใช้ตอบ AI)</option></select></label>
        {uploadPurpose === "teaching" && <>
          <label>รูปแบบสื่อ<select name="material_type" className="pilot-input" value={uploadType} onChange={(e) => setUploadType(e.target.value as MaterialType)}>{Object.entries(materialNames).map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select></label>
          <label>หัวข้อในรายวิชา (ไม่บังคับ)<select name="topic_id" className="pilot-input" value={uploadTopic} onChange={(e) => setUploadTopic(e.target.value)}><option value="">ไม่ระบุหัวข้อ</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.title}</option>)}</select></label>
        </>}
        {uploadPurpose === "evidence" && <input type="hidden" name="material_type" value="lesson" />}
        <details className="rounded-xl border border-border p-3"><summary className="cursor-pointer font-medium">เพิ่มรุ่นให้เอกสารเดิม (ถ้าต้องการ)</summary><label>เลือกไฟล์เดิม<select name="document_id" className="pilot-input" value={uploadDocId} onChange={(e) => { const id = e.target.value; const existing = versions.find((v) => v.document_id === id); setUploadDocId(id); if (existing) { setUploadPurpose(existing.purpose); setUploadType(existing.material_type); setUploadTopic(existing.topic_id ?? ""); } }}><option value="">สร้างเอกสารใหม่</option>{versions.filter((v, i, all) => all.findIndex((x) => x.document_id === v.document_id) === i).map((v) => <option key={v.document_id} value={v.document_id}>{v.title}</option>)}</select></label></details>
        <label>ไฟล์ PDF, DOCX หรือ TXT ไม่เกิน 10 MB<input type="file" name="file" required accept=".pdf,.docx,.txt" className="pilot-input" /></label>
        <button disabled={busy} className="pilot-button">เพิ่มไฟล์สอนในรายวิชา</button>
      </form>}
      {documentTab === "library" && <><div className="flex flex-wrap gap-2"><select aria-label="รุ่นเอกสารที่ต้องตรวจ" className="pilot-input flex-1" value={selectedId} onChange={(e) => { setSelectedId(e.target.value); setDetail(null); }}><option value="">เลือกรุ่นเอกสาร</option>{versions.map((v) => <option key={v.id} value={v.id}>{v.title} · รุ่น {v.version} · {v.status}</option>)}</select><button disabled={busy} className="pilot-secondary" onClick={() => void run(refresh)}>รีเฟรชสถานะ</button></div>
      {detail && <article className="space-y-4">
        <p className="text-sm font-medium">{detail.version.filename} · {detail.version.status} · {materialNames[detail.document.material_type] ?? detail.document.material_type}</p>
        <details className="rounded-xl bg-surface-soft p-3"><summary className="cursor-pointer text-sm">รายละเอียดไฟล์สำหรับตรวจสอบ</summary>
          <p className="mt-2 break-all text-xs">รหัสไฟล์: {detail.version.id}<br />SHA256: {detail.version.checksum}</p>
        </details>
        <p className="text-sm">{detail.document.purpose === "teaching" && ["review", "published"].includes(detail.version.status) ? "พร้อมใช้ถาม AI แล้ว" : "ไฟล์นี้ยังไม่พร้อมใช้ตอบ AI"}</p>
        {detail.version.extraction_error && <p role="alert">สกัดข้อความไม่สำเร็จ: {detail.version.extraction_error} โปรดใช้ PDF ที่มีข้อความหรืออัปโหลดรุ่นใหม่</p>}
        {detail.version.extraction_warning && <p role="alert" className="rounded-xl border border-border p-3 text-sm">บางหน้าไม่มีข้อความที่สกัดได้: {detail.version.extraction_warning} · หากเป็นภาพสแกนต้องใช้ OCR หรือตรวจไฟล์ต้นฉบับ</p>}
        <button className="pilot-secondary" disabled={busy} onClick={() => void run(async () => saveBlob(await api<Blob>(`/documents/versions/${selectedId}/file`), detail.version.filename))}>ดาวน์โหลดต้นฉบับเพื่อตรวจเทียบ</button>
        {detail.document.purpose === "teaching" && ["review", "published"].includes(detail.version.status) && <button className="pilot-secondary ml-2" disabled={busy} onClick={() => void run(async () => {
          const result = await api<{queued_batches: number}>(`/documents/versions/${selectedId}/index`, {method: "POST"});
          setMessage(`ส่งสร้างดัชนีค้นหาแล้ว ${result.queued_batches} ชุด`);
        })}>สร้าง/อัปเดต Vector ของไฟล์นี้</button>}

        <details className="rounded-xl border border-border p-3"><summary className="cursor-pointer font-semibold">ตรวจหรือแก้ข้อความที่อ่านจากไฟล์ ({detail.chunks.length} ส่วน)</summary>
          <div className="mt-3 space-y-3">{detail.chunks.map((chunk) => <form key={`${chunk.id}-${detail.version.revision}`} className="space-y-2 rounded-xl border border-border p-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { await api(`/documents/versions/${selectedId}/chunks/${chunk.id}`, { method: "PATCH", body: JSON.stringify({ text: value(form, "text"), page_no: Number(value(form, "page")), expected_revision: detail.version.revision }) }); await refresh(); }); }}>
          <label>หน้าเอกสารที่ตรวจยืนยันแล้ว<input name="page" type="number" min={1} max={1000} required defaultValue={chunk.page_no ?? ""} className="pilot-input" disabled={!["review", "published"].includes(detail.version.status)} /></label>
          <label>ข้อความที่สกัด<textarea name="text" required maxLength={10000} rows={7} defaultValue={chunk.text} className="pilot-input" disabled={!["review", "published"].includes(detail.version.status)} /></label>
          {["review", "published"].includes(detail.version.status) && <button className="pilot-secondary" disabled={busy}>บันทึกข้อความและเลขหน้า</button>}
        </form>)}</div></details>
        {["review", "published"].includes(detail.version.status) && <button disabled={busy} className="pilot-secondary" onClick={() => void run(async () => { await api(`/documents/versions/${selectedId}/withdraw`, { method: "POST", body: JSON.stringify({ expected_revision: detail.version.revision }) }); await refresh(); setMessage("ถอนการใช้รุ่นนี้แล้ว"); })}>ถอนการใช้เอกสารรุ่นนี้</button>}
        <h3 className="font-semibold">ประวัติผลตรวจ</h3>{detail.reviews.map((r) => <p key={r.id} className="rounded-xl bg-surface-soft p-3 text-sm break-all">{r.decision} · {r.scope} · {new Date(r.created_at).toLocaleString("th-TH")}<br />ผู้ตรวจ {r.reviewer_id}<br />{r.notes}<br />คะแนน 0–2: {Object.entries(r.rubric).map(([key, score]) => `${key} ${score}`).join(" · ")}</p>)}
      </article>}</>}
      {documentTab === "questions" && <section className="rounded-xl border border-border p-4">
        <h3 className="text-lg font-semibold">สร้างโจทย์และเฉลย</h3>
        <p className="mt-1 text-sm text-secondary">เลือกหัวข้อ ใส่โจทย์และคำตอบ แล้วกดรับรองโจทย์ก่อนให้นักเรียนฝึก</p><QuestionForm topics={topics} versions={versions} busy={busy} onSave={(data) => run(async () => {
        await api("/questions", { method: "POST", body: JSON.stringify(data) });
        setQuestions(await api<Question[]>(`/questions?course_id=${courseId}`)); setMessage("สร้างโจทย์ร่างแล้ว ตรวจเฉลยก่อนอนุมัติ");
      })} /><ul className="mt-4 space-y-3">{questions.map((q) => <li key={q.id} className="rounded-xl bg-surface-soft p-3">{q.prompt} · {q.status}{q.status === "draft" && <button className="pilot-secondary ml-2" disabled={busy} onClick={() => void run(async () => { await api(`/questions/${q.id}/publish`, { method: "POST" }); setQuestions(await api<Question[]>(`/questions?course_id=${courseId}`)); })}>รับรองโจทย์และเฉลย</button>}</li>)}</ul></section>}
    </>}
    {mode === "acceptance" && <>
      <p className="text-sm text-secondary">บันทึกผลจริงพร้อมรุ่นโปรแกรม ทุกกรณีเริ่มเป็น “ยังไม่ทดสอบ” ต้องตรวจโดยครูและโรงเรียนก่อนเริ่มนำร่อง</p>
      {acceptanceTab === "evidence" && <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { const result = await api<{id: string}>(`/courses/${courseId}/evidence`, { method: "POST", body: JSON.stringify({ requirement: value(form, "requirement"), result: value(form, "result"), detail: value(form, "detail"), build_ref: value(form, "build"), expected: value(form, "expected"), actual: value(form, "actual"), artifact_version_id: value(form, "artifact") || null }) }); setMessage(`บันทึกหลักฐานแล้ว รหัส ${result.id}`); }); }}>
        <label className="block">กรณีทดสอบ<select name="requirement" className="pilot-input">{[...Array.from({length: 12}, (_, i) => `T${String(i + 1).padStart(2, "0")}`), "BACKUP_RESTORE", "SCHOOL_APPROVAL", "USER_GUIDE", "LOAD_30"].map((id) => <option key={id}>{id}</option>)}</select></label>
        <label className="block">ผล<select name="result" className="pilot-input"><option value="not_tested">ยังไม่ทดสอบ</option><option value="pass">ผ่าน</option><option value="fail">ไม่ผ่าน</option></select></label>
        {[["build", "Commit หรือรุ่นโปรแกรม"], ["expected", "ผลที่คาดหวัง"], ["actual", "ผลที่เกิดขึ้นจริง"], ["detail", "วิธีทดสอบ สภาพแวดล้อม และรายละเอียดหลักฐาน"]].map(([name, label]) => <label key={name} className="block">{label}<textarea required name={name} minLength={name === "build" ? 7 : 1} maxLength={5000} className="pilot-input" /></label>)}
        <label className="block">แนบไฟล์หลักฐานรุ่นที่เก็บไว้<select name="artifact" className="pilot-input"><option value="">ไม่แนบไฟล์</option>{versions.filter((v) => v.purpose === "evidence").map((v) => <option key={v.id} value={v.id}>{v.title} รุ่น {v.version}</option>)}</select></label><button disabled={busy} className="pilot-button">บันทึกหลักฐานจริง</button>
      </form>}
      {acceptanceTab === "cases" && <details open className="rounded-xl border border-border p-4"><summary className="cursor-pointer font-semibold">จัดชุดทดสอบให้ตรงรายวิชา</summary>
        <p className="my-3 text-sm">กำหนดโจทย์ ผลคาดหวัง และสิ่งที่ถือว่าผิดให้ครบก่อนเริ่มให้คะแนน การแก้ชุดทดสอบจะต้องประเมินรอบใหม่ เหลือ {cases.filter((c) => c.needs_customization).length} กรณีที่ต้องกำหนด</p>
        <label className="block">กรณีทดสอบ<select value={editingCase} onChange={(e) => setEditingCase(e.target.value)} className="pilot-input"><option value="">เลือกกรณี</option>{cases.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.needs_customization ? "ยังไม่กำหนด" : "กำหนดแล้ว"}</option>)}</select></label>
        {cases.filter((c) => c.id === editingCase).map((c) => <form key={`${c.id}-${courseRevision}`} className="mt-3 space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => {
          await api(`/courses/${courseId}/evaluation-cases/${c.id}`, { method: "PUT", body: JSON.stringify({ expected_revision: courseRevision, input: value(form, "input"), expected: value(form, "expected"), failure: value(form, "failure") }) });
          const suite = await api<{cases: EvaluationCase[]; course_revision: number}>(`/evaluation/cases?course_id=${courseId}`);
          setCases(suite.cases); setCourseRevision(suite.course_revision); setReport(null); setMessage("บันทึกกรณีทดสอบแล้ว");
        }); }}>
          <label className="block">โจทย์ / ลำดับการทดสอบ<textarea required name="input" maxLength={4000} defaultValue={c.input} className="pilot-input" /></label>
          <label className="block">คำตอบและพฤติกรรมที่คาดหวัง<textarea required name="expected" maxLength={4000} defaultValue={c.expected} className="pilot-input" /></label>
          <label className="block">ข้อผิดพลาดที่ต้องจับ<textarea required name="failure" maxLength={4000} defaultValue={c.failure} className="pilot-input" /></label>
          <button disabled={busy} className="pilot-button">ยืนยันกรณีสำหรับวิชานี้</button>
        </form>)}
      </details>}
      {acceptanceTab === "scoring" && <details open className="rounded-xl border border-border p-4"><summary className="cursor-pointer font-semibold">ให้คะแนนชุดประเมิน AI จำนวน 80 กรณี</summary><p className="my-3 text-sm">คะแนน roadmap ใช้ 0–3; ช่องว่างคือ N/A แยกจาก rubric 0–2 ในแบบตรวจเนื้อหา</p><form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { await api(`/courses/${courseId}/evaluations`, { method: "POST", body: JSON.stringify({ expected_course_revision: courseRevision, run_id: value(form, "run"), case_id: value(form, "case"), evidence_id: value(form, "evidence"), scores: Object.fromEntries(["correctness", "citations", "teaching", "uncertainty"].map((key) => [key, value(form, key) === "" ? null : Number(value(form, key))])), critical: form.has("critical"), model: value(form, "model"), prompt_version: value(form, "prompt") }) }); setMessage("บันทึกคะแนนแล้ว"); }); }}>
        {[["run", "UUID ของรอบประเมิน"], ["evidence", "UUID หลักฐานที่บันทึกไว้"], ["model", "รุ่นโมเดล"], ["prompt", "รุ่น prompt"]].map(([name, label]) => <label className="block" key={name}>{label}<input required name={name} className="pilot-input" /></label>)}<label className="block">กรณี<select name="case" className="pilot-input">{cases.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.input}</option>)}</select></label>{["correctness", "citations", "teaching", "uncertainty"].map((key) => <label className="block" key={key}>{key}<input name={key} type="number" min={0} max={3} className="pilot-input" /></label>)}<label className="flex gap-3"><input type="checkbox" name="critical" /> พบข้อผิดพลาดวิกฤต</label><button className="pilot-button" disabled={busy}>บันทึกคะแนนกรณีนี้</button>
      </form><button className="pilot-secondary mt-3" onClick={() => saveBlob(new Blob([JSON.stringify(cases, null, 2)], {type: "application/json"}), "ai-evaluation-80-cases.json")}>ดาวน์โหลดรายการ 80 กรณี</button></details>}
      {acceptanceTab === "report" && <><form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { const params = new URLSearchParams({build_ref: value(form, "build")}); if (value(form, "run")) params.set("run_id", value(form, "run")); const result = await api<Report>(`/courses/${courseId}/acceptance?${params}`); setReport(result); saveBlob(new Blob([JSON.stringify(result, null, 2)], {type: "application/json"}), "pre-pilot-acceptance.json"); }); }}><label className="block">รุ่นโปรแกรมที่ต้องตรวจ<input required minLength={7} name="build" className="pilot-input" /></label><label className="block">UUID รอบประเมิน AI (หากมี)<input name="run" className="pilot-input" /></label><button className="pilot-button" disabled={busy}>ตรวจความพร้อมและส่งออกหลักฐาน JSON</button></form>
      {report && <div role="status"><p className="font-semibold">{report.readiness === "not_ready" ? "ยังไม่พร้อมนำร่อง" : "หลักฐานครบ รอการตัดสินจากโรงเรียน"}</p><ul className="mt-3 list-disc space-y-2 pl-5">{report.blockers.map((b) => <li key={b}>{b}</li>)}</ul></div>}</>}
    </>}
  </div>;
}


type QuestionDraft = { topic_id: string; source_version_id: string; prompt: string; hint: string; explanation: string; answer_type: string; grading_spec: Record<string, unknown> };
function QuestionForm({ topics, versions, busy, onSave }: { topics: {id: string; title: string}[]; versions: Version[]; busy: boolean; onSave: (data: QuestionDraft) => Promise<void> }) {
  const [type, setType] = useState("multiple_choice");
  return <form className="mt-4 space-y-3" onSubmit={(e) => {
    e.preventDefault(); const form = new FormData(e.currentTarget);
    let spec: Record<string, unknown>;
    if (type === "multiple_choice") spec = { options: value(form, "options").split("\n").map((t) => t.trim()).filter(Boolean).map((text, i) => ({ id: String(i + 1), text })), expected: value(form, "choice") };
    else if (type === "boolean") spec = { expected: value(form, "boolean") === "true" };
    else if (type === "numeric") spec = { expected: value(form, "number"), tolerance: value(form, "tolerance"), unit: value(form, "unit") };
    else if (type === "short_text") spec = { accepted: value(form, "accepted").split("\n").map((t) => t.trim()).filter(Boolean), case_sensitive: form.has("case_sensitive") };
    else if (type === "manual") spec = { criteria: value(form, "criteria") };
    else spec = { expected: value(form, "set").trim() ? value(form, "set").split(",").map((n) => /^[-+]?\d+$/.test(n.trim()) ? Number(n) : null) : [] };
    void onSave({ topic_id: value(form, "topic"), source_version_id: value(form, "source"), prompt: value(form, "prompt"), hint: value(form, "hint"), explanation: value(form, "explanation"), answer_type: type, grading_spec: spec });
  }}>
    <label className="block">หัวข้อ<select name="topic" required className="pilot-input">{topics.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
    <label className="block">แหล่งเอกสาร<select name="source" required className="pilot-input">{versions.filter((v) => v.purpose === "teaching" && ["review", "published"].includes(v.status)).map((v) => <option key={v.id} value={v.id}>{v.title} รุ่น {v.version}</option>)}</select></label>
    {[["prompt", "โจทย์"], ["hint", "คำใบ้"], ["explanation", "เฉลย / แนวคำตอบสำหรับครู"]].map(([name, label]) => <label className="block" key={name}>{label}<textarea required name={name} maxLength={2000} className="pilot-input" /></label>)}
    <label className="block">รูปแบบคำตอบ<select value={type} onChange={(e) => setType(e.target.value)} className="pilot-input">
      {[["multiple_choice", "ปรนัย"], ["boolean", "จริง / เท็จ"], ["numeric", "ตัวเลข"], ["short_text", "คำตอบสั้นตรงตามรายการ"], ["manual", "คำตอบอธิบาย — ครูตรวจ"], ["integer_set", "เซตจำนวนเต็ม"]].map(([id, label]) => <option key={id} value={id}>{label}</option>)}
    </select></label>
    {type === "multiple_choice" && <><label className="block">ตัวเลือก 2–8 ข้อ (หนึ่งตัวเลือกต่อบรรทัด)<textarea required name="options" rows={4} className="pilot-input" /></label><label className="block">ลำดับตัวเลือกที่ถูก<input name="choice" required type="number" min={1} max={8} className="pilot-input" /></label></>}
    {type === "boolean" && <label className="block">คำตอบที่ถูก<select name="boolean" className="pilot-input"><option value="true">จริง / ใช่</option><option value="false">เท็จ / ไม่ใช่</option></select></label>}
    {type === "numeric" && <><label className="block">คำตอบตัวเลข<input name="number" required className="pilot-input" /></label><label className="block">ค่าคลาดเคลื่อนสัมบูรณ์ที่ยอมรับ<input name="tolerance" required defaultValue="0" className="pilot-input" /></label><label className="block">หน่วยที่ผู้เรียนต้องใช้<input name="unit" maxLength={64} className="pilot-input" /></label></>}
    {type === "short_text" && <><label className="block">คำตอบที่ยอมรับ (หนึ่งคำตอบต่อบรรทัด)<textarea name="accepted" required className="pilot-input" /></label><label className="flex gap-2"><input name="case_sensitive" type="checkbox" /> แยกตัวพิมพ์เล็กและใหญ่</label><p className="text-sm">ตรวจตามรายการที่กำหนด หากต้องประเมินความหมายหรือเหตุผล ให้เลือกคำตอบอธิบาย</p></>}
    {type === "manual" && <label className="block">เกณฑ์ให้คะแนนที่แสดงให้ผู้เรียนทราบ<textarea name="criteria" required maxLength={4000} className="pilot-input" /></label>}
    {type === "integer_set" && <label className="block">สมาชิกเซตคั่นด้วยจุลภาค เช่น -2,0,3 (เว้นว่างสำหรับเซตว่าง)<input name="set" className="pilot-input" /></label>}
    <button disabled={busy || !topics.length} className="pilot-button">สร้างโจทย์ร่าง</button>
  </form>;
}
