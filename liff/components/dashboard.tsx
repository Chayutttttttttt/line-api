"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, saveBlob } from "@/lib/api";
import { initliff } from "@/lib/liff";
import { getRequestedDashboardView, type DashboardView } from "@/lib/dashboardView";
import TeacherPanel from "./teacherPanel";
import CoursePanel from "./coursePanel";
import AdminPanel from "./adminPanel";

type Course = { id: string; title: string; role: string };
type Me = { id: string; display_name: string; courses: Course[]; active_course_id: string | null; is_admin: boolean };
type Task = { id: string; title: string; state: string; revision: number; due_at: string | null };
type Topic = { id: string; title: string };
type Practice = { session_id: string; question: { id: string; prompt: string; answer_type: string; answer_config: { options?: {id: string; text: string}[]; unit?: string; criteria?: string } } };
type Plan = { plan: { id: string; state: string; revision: number; end_date: string }; items: { id: string; scheduled_at: string; minutes: number }[] };
type Progress = { attempts: number; independent_attempts: number; independent_correct: number; with_hints: number; pending_review: number; recommendation: string };
type Preferences = { reminders_enabled: boolean; quiet_start: number; quiet_end: number };
type View = DashboardView;
const tabs: [View, string][] = [["ask", "ถามบทเรียน"], ["tasks", "งานของฉัน"], ["practice", "ฝึกโจทย์"], ["plans", "แผนอ่านสอบ"], ["progress", "ความก้าวหน้า"], ["documents", "เอกสารบทเรียน"], ["settings", "ตั้งค่า"]];
const dateTime = (value: string) => new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(value));
const field = (form: FormData, name: string) => String(form.get(name) ?? "");
const json = (value: unknown) => JSON.stringify(value);

export default function Dashboard() {
  const [me, setMe] = useState<Me | null>(null);
  const [courseId, setCourseId] = useState("");
  const [view, setView] = useState<View>("home");
  const [requestedView, setRequestedView] = useState<View | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [practice, setPractice] = useState<Practice | null>(null);
  const [submissionId, setSubmissionId] = useState("");
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    let active = true;
    const loadAccount = async () => {
      try {
        // LINE carries Rich Menu parameters in liff.state until init resolves.
        await initliff();
        if (!active) return;
        const requested = getRequestedDashboardView(window.location.search);
        setRequestedView(requested);
        const user = await api<Me>("/me");
        if (!active) return;
        const initialCourseId = user.active_course_id ?? user.courses[0]?.id ?? "";
        const initialCourse = user.courses.find((c) => c.id === initialCourseId);
        const restricted = requested === "course" || requested === "acceptance";
        const isTeacher = initialCourse?.role === "teacher" || initialCourse?.role === "admin";
        setMe(user);
        setCourseId(initialCourseId);
        // Deep links are navigation only; teacher views still require membership.
        setView(requested === "admin" && !user.is_admin ? "home" : requested && (!restricted || isTeacher || user.is_admin) ? requested : "home");
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void loadAccount();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!me) return;
    let active = true;
    Promise.all([api<Task[]>("/tasks"), api<Plan[]>("/plans"), api<Preferences>("/me/preferences"), courseId ? api<Topic[]>(`/topics?course_id=${courseId}`) : Promise.resolve([])])
      .then(([nextTasks, nextPlans, nextPreferences, nextTopics]) => { if (active) { setTasks(nextTasks); setPlans(nextPlans); setPreferences(nextPreferences); setTopics(nextTopics); } })
      .catch((e: Error) => { if (active) setError(e.message); });
    if (courseId) api<Progress>(`/progress?course_id=${courseId}`).then((value) => { if (active) setProgress(value); }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [me, courseId, view]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const course = me?.courses.find((c) => c.id === courseId);
  const teacher = course?.role === "teacher" || course?.role === "admin";

  if (!me) return <main className="mx-auto w-full max-w-xl p-8"><h1 className="text-2xl font-bold text-brand-navy">ผู้ช่วยเรียน</h1><p className="my-4" role="status">{error || "กำลังตรวจสอบบัญชี LINE…"}</p><Link className="text-brand-blue underline" href={requestedView ? `/login?view=${requestedView}` : "/login"}>เข้าสู่ระบบด้วย LINE</Link></main>;

  return <main className="mx-auto w-full max-w-5xl p-4 pb-16 sm:p-8">
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm text-secondary">LINE Learning · เตรียมความพร้อมก่อนนำร่อง</p><h1 className="text-2xl font-bold text-brand-navy">สวัสดี {me.display_name || "ผู้เรียน"}</h1></div><Link href="/login" className="text-sm text-brand-blue underline">บัญชี LINE</Link></header>
    <p className="mb-4 rounded-xl bg-brand-mint/50 p-3 text-sm">เรียนและฝึกตามรายวิชาที่เลือก AI ใช้ไฟล์บทเรียนที่สกัดข้อความสำเร็จโดยไม่ต้องอนุมัติไฟล์ คำตอบอธิบายในแบบฝึกยังส่งให้ครูตรวจ</p>
    <label className="mb-5 block">รายวิชา<select value={courseId} disabled={busy} className="pilot-input mt-1" onChange={(e) => { setCourseId(e.target.value); setView("ask"); setPractice(null); setFeedback(""); setProgress(null); setError(""); setNotice(""); }}><option value="">เลือกรายวิชา</option>{me.courses.map((c) => <option key={c.id} value={c.id}>{c.title} ({c.role})</option>)}</select></label>
    {courseId && <div className="mb-4 flex flex-wrap items-center gap-3"><button className="pilot-secondary" disabled={busy} onClick={() => void run(async () => {
      await api("/me/active-course", { method: "PUT", body: json({ course_id: courseId }) });
      setMe(await api<Me>("/me")); setNotice("ตั้งวิชาสำหรับข้อความ LINE ถัดไปแล้ว");
    })}>ใช้วิชานี้ในแชต LINE</button><p className="text-sm">วิชาใน LINE: {me.courses.find((c) => c.id === me.active_course_id)?.title ?? (me.courses.length === 1 ? me.courses[0].title : "ยังไม่ได้เลือก")}</p></div>}
    {!me.courses.length && <p className="mb-4 rounded-xl border border-border p-4">ยังไม่มีรายวิชา กรุณาแจ้งรหัสบัญชีจาก /me ให้ผู้ดูแลเพิ่มสมาชิก ไม่มีการให้สิทธิ์ครูจากการเลือกบทบาทเอง</p>}
    <nav aria-label="เมนูหลัก" className="mb-6 flex flex-wrap gap-2">{[...tabs, ...(teacher ? [["course", "จัดการวิชา / ตรวจคำตอบ"], ["acceptance", "หลักฐานตรวจรับ"]] as [View, string][] : []), ...(me.is_admin ? [["admin", "ผู้ดูแลระบบ"]] as [View, string][] : [])].map(([id, title]) => <button type="button" key={id} aria-current={view === id ? "page" : undefined} className={view === id ? "pilot-button" : "pilot-secondary"} onClick={() => { setView(id); setError(""); setNotice(""); }}>{title}</button>)}</nav>
    {error && <p role="alert" className="mb-4 rounded-xl border border-danger p-3 text-red-800">{error}</p>}
    {notice && <p role="status" className="mb-4 rounded-xl bg-brand-mint p-3">{notice}</p>}
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm" aria-busy={busy}>
      {(view === "home" || view === "ask") && <div className="space-y-5">
        <section className="rounded-2xl bg-brand-mint/40 p-5">
          <h2 className="text-xl font-bold text-brand-navy">ถาม AI ในแชต LINE</h2>
          <p className="mt-2">กลับไปที่แชต LINE Learning แล้วพิมพ์คำถามได้เลย AI จะใช้รายวิชาที่คุณตั้งไว้</p>
          <p className="mt-2 text-sm text-secondary">ตัวอย่าง “อธิบายกฎของนิวตันข้อที่ 2” · การถาม AI ใช้ใน LINE เท่านั้น</p>
          {!me.active_course_id && !!courseId && <p className="mt-3 font-medium">กด “ใช้วิชานี้ในแชต LINE” ด้านบนก่อนถาม</p>}
        </section>
        <h2 className="text-lg font-bold">เมนูที่ใช้บ่อย</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {([
            ["practice", "ฝึกทำโจทย์", "เลือกหัวข้อและลองทำด้วยตัวเอง"],
            ["tasks", "งานที่ต้องทำ", `ยังไม่เสร็จ ${tasks.filter((task) => task.state === "pending").length} งาน`],
            ["plans", "แผนอ่านสอบ", "วางเวลาอ่านหนังสือ"],
            ["progress", "ผลการเรียน", `ฝึกไปแล้ว ${progress?.attempts ?? 0} ครั้ง`],
            ["documents", teacher ? "ไฟล์สอนและโจทย์" : "เอกสารบทเรียน", teacher ? "เพิ่มไฟล์และแบบฝึกหัด" : "เปิดเอกสารที่ครูให้"],
            ...(teacher ? [["course", "งานของครู", "ตรวจคำตอบและจัดรายวิชา"]] : []),
          ] as [View, string, string][]).map(([id, title, desc]) => <button key={id} type="button"
            onClick={() => {setView(id); setError(""); setNotice("");}}
            className="rounded-2xl border border-border bg-white p-4 text-left hover:border-brand-blue focus-visible:outline-2 focus-visible:outline-brand-blue">
            <span className="block font-semibold text-brand-navy">{title}</span>
            <span className="mt-1 block text-sm text-secondary">{desc}</span>
          </button>)}
        </div>
      </div> 
      {view === "tasks" && <><h2 className="pilot-heading">งานของฉัน</h2><form className="mb-5 grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); const target = e.currentTarget; void run(async () => { const due = field(form, "due"); await api("/tasks", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: json({ title: field(form, "title"), due_at: due ? new Date(due).toISOString() : null, course_id: courseId || null }) }); setTasks(await api<Task[]>("/tasks")); target.reset(); }); }}><label>ชื่องาน<input className="pilot-input" name="title" required maxLength={255} /></label><label>กำหนดส่ง (เวลาบนอุปกรณ์)<input className="pilot-input" name="due" type="datetime-local" /></label><button disabled={busy} className="pilot-button sm:col-span-2">บันทึกงาน</button></form><ul className="space-y-3">{tasks.map((task) => <li key={task.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3"><div><strong>{task.title}</strong><p className="text-sm text-secondary">{task.due_at ? dateTime(task.due_at) : "ไม่มีกำหนดส่ง"} · {task.state}</p></div>{task.state === "pending" && <button disabled={busy} className="pilot-secondary" onClick={() => void run(async () => { await api(`/tasks/${task.id}`, { method: "PATCH", body: json({ expected_revision: task.revision, state: "done" }) }); setTasks(await api<Task[]>("/tasks")); })}>ทำเสร็จแล้ว</button>}</li>)}</ul>{!tasks.length && <p>ยังไม่มีงาน</p>}</>}
      {view === "practice" && <><h2 className="pilot-heading">ลองทำโจทย์ด้วยตัวเอง</h2><form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { const result = await api<Practice>("/practice/sessions", { method: "POST", body: json({ course_id: courseId, topic_id: field(form, "topic") }) }); setPractice(result); setSubmissionId(crypto.randomUUID()); setFeedback(""); }); }}><label>หัวข้อ<select required name="topic" className="pilot-input">{topics.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label><button disabled={busy || !courseId || !topics.length} className="pilot-button">รับโจทย์ใหม่</button></form>{practice && <div key={practice.session_id} className="mt-5"><p className="mb-4 text-lg">{practice.question.prompt}</p><form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { const result = await api<{correct: boolean | null; score_status: string; explanation: string; hints_used: number}>(`/practice/${practice.session_id}/answers`, { method: "POST", body: json({ question_id: practice.question.id, answer: field(form, "answer"), submission_id: submissionId }) }); setFeedback(`${result.score_status === "pending_review" ? "ส่งคำตอบแล้ว รอครูตรวจ" : result.correct ? "ถูกต้อง" : "ลองทบทวนอีกครั้ง"} · ${result.hints_used ? "ใช้คำใบ้" : "ทำเอง"}\n${result.explanation}`); setProgress(await api<Progress>(`/progress?course_id=${courseId}`)); }); }}><PracticeAnswer question={practice.question} /><button className="pilot-button" disabled={busy}>ส่งคำตอบ</button><button type="button" disabled={busy} className="pilot-secondary ml-2" onClick={() => void run(async () => { const result = await api<{hint: string}>(`/practice/${practice.session_id}/hint`, { method: "POST" }); setFeedback(`คำใบ้: ${result.hint}`); })}>ขอคำใบ้</button></form></div>}{feedback && <p role="status" className="mt-4 whitespace-pre-wrap rounded-xl bg-surface-soft p-4">{feedback}</p>}</>}
      {view === "plans" && <><h2 className="pilot-heading">ร่างแผนอ่านสอบ</h2><form className="mb-5 space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { await api("/plans/draft", { method: "POST", body: json({ course_id: courseId, exam_date: field(form, "exam"), minutes_per_day: Number(field(form, "minutes")) }) }); setPlans(await api<Plan[]>("/plans")); }); }}><label className="block">วันสอบที่ยืนยันแล้ว<input type="date" name="exam" required className="pilot-input" /></label><label className="block">นาทีต่อวัน<input type="number" name="minutes" min={5} max={120} defaultValue={20} required className="pilot-input" /></label><p className="text-sm text-secondary">เสนอเวลาอ่าน 18:00 น. ตามเขตเวลาบัญชี ตรวจวันจริงก่อนเปิดแผน</p><button className="pilot-button" disabled={busy || !courseId}>สร้างแผนร่าง</button></form>{plans.map(({plan, items}) => <article key={plan.id} className="mb-4 rounded-xl border border-border p-4"><h3 className="font-semibold">สอบ {plan.end_date} · {plan.state}</h3><ul className="my-3 max-h-52 overflow-auto text-sm">{items.map((item) => <li className="py-1" key={item.id}>{dateTime(item.scheduled_at)} · {item.minutes} นาที</li>)}</ul>{plan.state === "draft" && <button disabled={busy} className="pilot-button" onClick={() => void run(async () => { await api(`/plans/${plan.id}/activate`, { method: "POST", body: json({ expected_revision: plan.revision }) }); setPlans(await api<Plan[]>("/plans")); })}>ยืนยันวันและเปิดแผน</button>}{plan.state !== "cancelled" && <button disabled={busy} className="pilot-secondary ml-2" onClick={() => void run(async () => { await api(`/plans/${plan.id}/cancel`, { method: "POST", body: json({ expected_revision: plan.revision }) }); setPlans(await api<Plan[]>("/plans")); })}>ยกเลิกแผน</button>}</article>)}</>}
      {view === "progress" && <><h2 className="pilot-heading">ความก้าวหน้าของฉัน</h2>{progress ? <><dl className="grid grid-cols-2 gap-3">{[["ฝึกทั้งหมด", progress.attempts], ["ทำเอง", progress.independent_attempts], ["ทำเองถูก", progress.independent_correct], ["ใช้คำใบ้", progress.with_hints], ["รอครูตรวจ", progress.pending_review]].map(([label, value]) => <div key={label} className="rounded-xl bg-surface-soft p-4"><dt>{label}</dt><dd className="text-3xl font-bold text-brand-navy">{value}</dd></div>)}</dl><p className="mt-4">{progress.recommendation}</p></> : <p>เลือกรายวิชาเพื่อดูผล</p>}{courseId && <PracticeResults key={courseId} courseId={courseId} />}</>}
      {view === "admin" && me.is_admin && <AdminPanel onChanged={async () => { setMe(await api<Me>("/me")); }} />}
      {view === "course" && teacher && courseId && <CoursePanel key={courseId} courseId={courseId} onChanged={async () => { setMe(await api<Me>("/me")); }} />}
      {(view === "documents" || view === "acceptance") && teacher && courseId && <TeacherPanel key={`${courseId}-${view}`} courseId={courseId} mode={view} />}
      {view === "documents" && !teacher && courseId && <StudentMaterials key={courseId} courseId={courseId} />}
      {view === "settings" && <><h2 className="pilot-heading">การแจ้งเตือนและข้อมูล</h2><p className="mb-4 break-all text-sm">รหัสบัญชีสำหรับแจ้งผู้ดูแล: {me.id}</p><form key={JSON.stringify(preferences)} className="space-y-4" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { setPreferences(await api<Preferences>("/me/preferences", { method: "PUT", body: json({ reminders_enabled: form.has("enabled"), quiet_start: Number(field(form, "start")), quiet_end: Number(field(form, "end")) }) })); setNotice("บันทึกการตั้งค่าแล้ว ใช้กับงานและแผนที่สร้างหรือเปิดใช้หลังจากนี้"); }); }}><label className="flex gap-3"><input type="checkbox" name="enabled" defaultChecked={preferences?.reminders_enabled ?? false} /> เปิดการเตือนผ่าน LINE โดยสมัครใจ</label><label className="block">เวลาเงียบเริ่ม (ชั่วโมง)<input className="pilot-input" name="start" type="number" min={0} max={23} defaultValue={preferences?.quiet_start ?? 21} /></label><label className="block">สิ้นสุด (ชั่วโมง)<input className="pilot-input" name="end" type="number" min={0} max={23} defaultValue={preferences?.quiet_end ?? 7} /></label><button className="pilot-button" disabled={busy || !preferences}>บันทึกการตั้งค่า</button></form><p className="mt-6 text-sm text-secondary">เก็บบัญชี LINE ผลฝึก งาน และประวัติที่จำเป็นตามนโยบายโรงเรียน ติดต่อครูเพื่อถอนตัวจากนำร่อง</p><button className="pilot-secondary mt-3" disabled={busy} onClick={() => { if (window.confirm("ลบประวัติสนทนาของคุณจากระบบปัจจุบันหรือไม่?")) void run(async () => { await api("/me/data", { method: "DELETE", body: json({ deletion_scope: "conversations" }) }); setNotice("ลบประวัติสนทนาแล้ว"); }); }}>ลบประวัติสนทนา</button></>}
    </section>
  </main>;
}

function StudentMaterials({ courseId }: { courseId: string }) {
  const [files, setFiles] = useState<{ id: string; title: string; filename: string; version: number }[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<typeof files>(`/documents?course_id=${courseId}`).then((v) => { if (active) setFiles(v); }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [courseId]);
  return <><h2 className="pilot-heading">เอกสารประกอบการเรียน</h2>{error && <p role="alert">{error}</p>}{!files.length && <p>ยังไม่มีไฟล์บทเรียนที่สกัดข้อความสำเร็จ</p>}<ul className="space-y-3">{files.map((file) => <li key={file.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3"><span>{file.title} · รุ่น {file.version}</span><button className="pilot-secondary" onClick={() => { void api<Blob>(`/documents/versions/${file.id}/file`).then((blob) => saveBlob(blob, file.filename)).catch((e: Error) => setError(e.message)); }}>ดาวน์โหลด</button></li>)}</ul></>;
}


function PracticeAnswer({ question }: { question: Practice["question"] }) {
  const config = question.answer_config;
  if (question.answer_type === "multiple_choice") return <label className="block">คำตอบ<select name="answer" required className="pilot-input" defaultValue=""><option value="" disabled>เลือกคำตอบ</option>{config.options?.map((o) => <option key={o.id} value={o.id}>{o.text}</option>)}</select></label>;
  if (question.answer_type === "boolean") return <label className="block">คำตอบ<select name="answer" required className="pilot-input" defaultValue=""><option value="" disabled>เลือกคำตอบ</option><option value="true">จริง / ใช่</option><option value="false">เท็จ / ไม่ใช่</option></select></label>;
  if (question.answer_type === "manual") return <><p>เกณฑ์: {config.criteria}</p><label className="block">คำตอบอธิบาย<textarea name="answer" required maxLength={2000} rows={6} className="pilot-input" /></label><p className="text-sm">ครูจะตรวจและให้ข้อเสนอแนะ ดูผลได้ในหน้าความก้าวหน้า</p></>;
  return <label className="block">คำตอบ{config.unit ? ` (หน่วย ${config.unit})` : ""}<input name="answer" required maxLength={2000} className="pilot-input" placeholder={question.answer_type === "integer_set" ? "{-2, 0, 3}" : question.answer_type === "numeric" ? "กรอกเฉพาะตัวเลขตามหน่วยที่กำหนด" : "คำตอบสั้น"} /></label>;
}

type PracticeResult = { id: string; prompt: string; answer: string; result: { score_status: string; score: number | null; explanation: string; feedback?: string } };
function PracticeResults({ courseId }: { courseId: string }) {
  const [results, setResults] = useState<PracticeResult[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<PracticeResult[]>(`/practice/results?course_id=${courseId}`).then((r) => { if (active) setResults(r); }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [courseId]);
  return <section className="mt-6 space-y-3"><h3 className="font-semibold">ผลฝึกและข้อเสนอแนะล่าสุด</h3>
    <button className="pilot-secondary" onClick={() => { void api<PracticeResult[]>(`/practice/results?course_id=${courseId}`).then((r) => { setResults(r); setError(""); }).catch((e: Error) => setError(e.message)); }}>โหลดผลตรวจล่าสุด</button>
    {error && <p role="alert">{error}</p>}
    {results.map((r) => <article key={r.id} className="rounded-xl border border-border p-3"><p className="font-semibold">{r.prompt}</p><p className="whitespace-pre-wrap">คำตอบ: {r.answer}</p><p>{r.result.score_status === "pending_review" ? "รอครูตรวจ" : `คะแนน ${Math.round((r.result.score ?? 0) * 100)}/100`}</p><p className="whitespace-pre-wrap">{r.result.explanation}</p>{r.result.feedback && <p className="whitespace-pre-wrap">ครู: {r.result.feedback}</p>}</article>)}
  </section>;
}
