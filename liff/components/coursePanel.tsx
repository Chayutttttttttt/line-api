"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Course = { id: string; school_id: string; title: string; subject: string; learning_scope: string; response_language: string; grade_level: string | null; revision: number };
type Topic = { id: string; title: string; keywords: string[] };
type Review = { id: string; student: string; prompt: string; answer: string; criteria: string; explanation: string; hints_used: number };
const value = (form: FormData, key: string) => String(form.get(key) ?? "");
const body = (data: unknown) => JSON.stringify(data);

export default function CoursePanel({ courseId, onChanged }: { courseId: string; onChanged: () => Promise<void> }) {
  const [course, setCourse] = useState<Course | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<"reviews" | "topics" | "course">("reviews");

  useEffect(() => {
    let active = true;
    Promise.all([api<Course>(`/courses/${courseId}`), api<Topic[]>(`/topics?course_id=${courseId}`), api<Review[]>(`/courses/${courseId}/reviews`)])
      .then(([c, t, r]) => { if (active) { setCourse(c); setTopics(t); setReviews(r); } })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [courseId]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function refresh() {
    const [c, t, r] = await Promise.all([api<Course>(`/courses/${courseId}`), api<Topic[]>(`/topics?course_id=${courseId}`), api<Review[]>(`/courses/${courseId}/reviews`)]);
    setCourse(c); setTopics(t); setReviews(r);
    await onChanged();
  }
  function settings(form: FormData) {
    return { title: value(form, "title"), subject: value(form, "subject"), learning_scope: value(form, "scope"),
      response_language: value(form, "language"), grade_level: value(form, "grade") || null };
  }

  return <div className="space-y-6" aria-busy={busy}>
    <h2 className="pilot-heading">จัดการชั้นเรียน</h2>
    <nav aria-label="งานของครู" className="grid gap-2 sm:grid-cols-3">
      {([["reviews","ตรวจคำตอบนักเรียน"],["topics","จัดหัวข้อบทเรียน"],["course","ตั้งค่ารายวิชา"]] as const).map(([id,label]) =>
        <button type="button" key={id} className={tab === id ? "pilot-button" : "pilot-secondary"}
          aria-current={tab === id ? "page" : undefined} onClick={() => {setTab(id);setError("");setNotice("");}}>{label}</button>)}
    </nav>
    {error && <p role="alert" className="text-red-800">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!course && !error && <p role="status">กำลังโหลดรายวิชา…</p>}
    {course && <>
      {tab === "course" && <><form key={course.revision} className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => {
        await api(`/courses/${courseId}`, { method: "PUT", body: body({ ...settings(form), expected_revision: course.revision }) });
        await refresh(); setNotice("บันทึกขอบเขตแล้ว กรุณาจัดชุดประเมินให้ตรงขอบเขตใหม่ก่อนตรวจรับ");
      }); }}>
        <CourseFields course={course} />
        <p className="text-sm text-secondary">การเปลี่ยนขอบเขตหรือหัวข้อจะเริ่มชุดประเมินใหม่ ผลประเมินเดิมยังเก็บเป็นประวัติ</p>
        <button disabled={busy} className="pilot-button">บันทึกขอบเขตรายวิชา</button>
      </form>
      <details className="rounded-xl border border-border p-4"><summary>เพิ่มรายวิชาในโรงเรียนนี้</summary>
        <form className="mt-3 space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); const target = e.currentTarget; void run(async () => {
          await api("/courses", { method: "POST", body: body({ ...settings(form), school_id: course.school_id }) });
          await onChanged(); target.reset(); setNotice("สร้างวิชาแล้ว เลือกวิชาใหม่จากเมนูรายวิชา ผู้ดูแลเพิ่มสมาชิกได้ตามเดิม");
        }); }}><CourseFields /><button disabled={busy} className="pilot-button">สร้างรายวิชา</button></form>
      </details></>}
      {tab === "topics" && <section className="space-y-3"><h3 className="font-semibold">หัวข้อบทเรียนและคำค้นเพิ่มเติม</h3><p className="text-sm">คำค้นช่วยจับคำศัพท์และคำเรียกอื่น เช่น แรง, force แยกด้วยจุลภาค</p>
        {[...topics, { id: "", title: "", keywords: [] }].map((topic) => <form key={`${topic.id}-${course.revision}`} className="space-y-2 rounded-xl border border-border p-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => {
          await api(`/courses/${courseId}/topics${topic.id ? `/${topic.id}` : ""}`, { method: topic.id ? "PUT" : "POST", body: body({ title: value(form, "title"), keywords: value(form, "keywords").split(",").map((v) => v.trim()).filter(Boolean), expected_revision: course.revision }) });
          await refresh(); setNotice("บันทึกหัวข้อแล้ว");
        }); }}>
          <label className="block">{topic.id ? "หัวข้อ" : "หัวข้อใหม่"}<input name="title" required maxLength={255} defaultValue={topic.title} className="pilot-input" /></label>
          <label className="block">คำค้นเพิ่มเติม<input name="keywords" defaultValue={topic.keywords.join(", ")} className="pilot-input" /></label>
          <button disabled={busy} className="pilot-secondary">{topic.id ? "แก้ไขหัวข้อ" : "เพิ่มหัวข้อ"}</button>
        </form>)}
      </section>}
      {tab === "reviews" && <section className="space-y-3"><h3 className="font-semibold">คำตอบรอครูตรวจ</h3>
        <button disabled={busy} className="pilot-secondary" onClick={() => void run(refresh)}>โหลดรายการล่าสุด</button>
        {!reviews.length && <p>ไม่มีคำตอบรอตรวจ</p>}
        {reviews.map((review) => <form key={review.id} className="space-y-3 rounded-xl border border-border p-4" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => {
          await api(`/courses/${courseId}/reviews/${review.id}`, { method: "POST", body: body({ score: Number(value(form, "score")) / 100, feedback: value(form, "feedback") }) });
          await refresh(); setNotice("บันทึกคะแนนแล้ว ผู้เรียนดูผลได้ในหน้าความก้าวหน้า");
        }); }}>
          <p className="font-semibold">{review.student} · {review.hints_used ? "ใช้คำใบ้" : "ทำเอง"}</p><p>{review.prompt}</p>
          <p className="whitespace-pre-wrap rounded-xl bg-surface-soft p-3">{review.answer}</p>
          <p>เกณฑ์: {review.criteria}</p><p>แนวเฉลย: {review.explanation}</p>
          <label className="block">คะแนนเต็ม 100<input name="score" required type="number" min={0} max={100} step={1} className="pilot-input" /></label>
          <label className="block">ข้อเสนอแนะ<textarea name="feedback" required maxLength={4000} className="pilot-input" /></label>
          <button disabled={busy} className="pilot-button">ยืนยันคะแนน</button>
        </form>)}
      </section>}
    </>}
  </div>;
}

function CourseFields({ course }: { course?: Course }) {
  return <>
    <label className="block">ชื่อรายวิชา<input name="title" required maxLength={255} defaultValue={course?.title ?? ""} className="pilot-input" /></label>
    <label className="block">วิชา / กลุ่มสาระ<input name="subject" required maxLength={255} defaultValue={course?.subject ?? ""} placeholder="เช่น วิทยาศาสตร์ ภาษาอังกฤษ สังคมศึกษา" className="pilot-input" /></label>
    <label className="block">ระดับชั้น<input name="grade" maxLength={32} defaultValue={course?.grade_level ?? ""} className="pilot-input" /></label>
    <label className="block">ขอบเขตที่ให้สอนและสิ่งที่อยู่นอกขอบเขต<textarea name="scope" required maxLength={4000} rows={4} defaultValue={course?.learning_scope ?? ""} className="pilot-input" /></label>
    <label className="block">ภาษาที่ใช้ตอบ<input name="language" required maxLength={64} defaultValue={course?.response_language ?? "ไทย"} className="pilot-input" /></label>
  </>;
}
