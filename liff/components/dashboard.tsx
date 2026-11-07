"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, saveBlob } from "@/lib/api";
import { getLineChatUrl, initliff, isLineInClient, openLineChat } from "@/lib/liff";
import { getRequestedDashboardView, type DashboardView } from "@/lib/dashboardView";
import TeacherPanel from "./teacherPanel";
import CoursePanel, { CreateCourseForm } from "./coursePanel";
import AdminPanel from "./adminPanel";

type Course = { id: string; title: string; role: string };
type Me = { id: string; display_name: string; courses: Course[]; active_course_id: string | null; is_admin: boolean; role: "student" | "teacher"; school: { id: string; name: string } | null };
type Task = { id: string; title: string; state: string; revision: number; due_at: string | null };
type Plan = { plan: { id: string; state: string; revision: number; end_date: string }; items: { id: string; scheduled_at: string; minutes: number }[] };
type Progress = { attempts: number; independent_attempts: number; independent_correct: number; with_hints: number; pending_review: number; recommendation: string };
type Preferences = { reminders_enabled: boolean; quiet_start: number; quiet_end: number };
type View = DashboardView;
type Group = "home" | "teacher" | "settings" | "admin";
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
  const [plans, setPlans] = useState<Plan[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [inLine, setInLine] = useState(false);

  useEffect(() => {
    let active = true;
    const loadAccount = async () => {
      try {
        // LINE carries Rich Menu parameters in liff.state until init resolves.
        await initliff();
        if (!active) return;
        setInLine(isLineInClient());
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
    const loadView = async () => {
      if (view === "tasks") {
        const value = await api<Task[]>("/tasks");
        if (active) setTasks(value);
      } else if (view === "plans") {
        const value = await api<Plan[]>("/plans");
        if (active) setPlans(value);
      } else if (view === "settings") {
        const value = await api<Preferences>("/me/preferences");
        if (active) setPreferences(value);
      } else if (view === "progress" && courseId) {
        const value = await api<Progress>(`/progress?course_id=${courseId}`);
        if (active) setProgress(value);
      }
    };
    void loadView().catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [me, courseId, view]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const course = me?.courses.find((c) => c.id === courseId);
  const teacher = course?.role === "teacher" || course?.role === "admin";
  const group: Group = view === "home" || view === "ask" || view === "practice" ? "home"
    : view === "course" || view === "acceptance" || (view === "documents" && teacher) ? "teacher"
    : view === "admin" ? "admin" : "settings";
  const subviews: [View, string][] = group === "settings"
    ? [["settings", "บัญชีและการแจ้งเตือน"], ["tasks", "จัดการงาน"], ["plans", "ตั้งแผนอ่านสอบ"], ["progress", "ประวัติการเรียน"], ...(!teacher ? [["documents", "เอกสารบทเรียน"] as [View, string]] : [])]
    : group === "teacher" ? [["documents", "ไฟล์และแบบฝึก"], ["course", "รายวิชาและตรวจคำตอบ"], ["acceptance", "ตรวจรับระบบ"]]
    : [];
  const menu: { id: Group; label: string; subtitle: string; target: View }[] = [
    {id:"home",label:"เรียนผ่าน LINE",subtitle:"ทำข้อสอบและขอคำใบ้",target:"home"},
    {id:"settings",label:"ตั้งค่าการใช้งาน",subtitle:"บัญชีและการแจ้งเตือน",target:"settings"},
    ...(teacher ? [{id:"teacher" as Group,label:"สำหรับครู",subtitle:"จัดการชั้นเรียน",target:"documents" as View}] : []),
    ...(me?.is_admin ? [{id:"admin" as Group,label:"ผู้ดูแลระบบ",subtitle:"จัดการสมาชิก",target:"admin" as View}] : []),
  ];

  if (!me) return <main className="mx-auto w-full max-w-xl p-8"><h1 className="text-2xl font-bold text-brand-navy">ผู้ช่วยเรียน</h1><p className="my-4" role="status">{error || "กำลังตรวจสอบบัญชี LINE…"}</p><Link className="text-brand-blue underline" href={requestedView ? `/login?view=${requestedView}` : "/login"}>เข้าสู่ระบบด้วย LINE</Link></main>;

  return <main className="mx-auto w-full max-w-5xl p-4 pb-16 sm:p-8">
    <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-sm font-medium text-secondary">LINE Learning</p>
        <h1 className="text-2xl font-bold text-brand-navy">สวัสดี {me.display_name || "ผู้เรียน"}</h1>
        <p className="mt-1 text-sm text-secondary">ตั้งค่าบัญชีและรายวิชาที่นี่ · เรียนและทำข้อสอบในแชต LINE</p>
      </div>
      <Link href="/login" className="pilot-secondary text-sm">บัญชี LINE</Link>
    </header>
    <div className="mb-5 rounded-2xl border border-border bg-white p-4 sm:p-5">
      <label className="block font-semibold">รายวิชาที่กำลังใช้
        <select className="pilot-input mt-2" value={courseId} disabled={busy} onChange={(e) => {
          setCourseId(e.target.value); setView("home");
          setProgress(null); setError(""); setNotice("");
        }}>
          <option value="">เลือกรายวิชา</option>
          {me.courses.map((c) => <option key={c.id} value={c.id}>{c.title}{["teacher", "admin"].includes(c.role) ? " · ครู" : ""}</option>)}
        </select>
      </label>
      {courseId && <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-secondary">แชตและข้อสอบใน LINE ใช้วิชา: <strong>{me.courses.find((c) => c.id === me.active_course_id)?.title ?? "ยังไม่ได้เลือก"}</strong></p>
        <button className="pilot-secondary text-sm" disabled={busy || me.active_course_id === courseId} onClick={() => void run(async () => {
          await api("/me/active-course", { method:"PUT", body:json({course_id:courseId}) });
          setMe(await api<Me>("/me")); setNotice("ตั้งวิชาสำหรับเรียนและทำข้อสอบใน LINE เรียบร้อยแล้ว");
        })}>{me.active_course_id === courseId ? "กำลังใช้วิชานี้ใน LINE" : "ใช้วิชานี้ในแชต LINE"}</button>
      </div>}
      <p className="mt-3 text-sm text-secondary">โรงเรียนปัจจุบัน: {me.school?.name ?? "ไม่มีสังกัด"} · {me.role === "teacher" ? "ครู" : "นักเรียน"}</p>
      {!me.courses.length && (me.role === "teacher" && me.school ? <section className="mt-4 border-t border-border pt-4">
        <h2 className="font-semibold">สร้างรายวิชาแรกใน {me.school.name}</h2>
        <CreateCourseForm schoolId={me.school.id} onCreated={async (id) => {
          setMe(await api<Me>("/me")); setCourseId(id); setView("course");
        }} />
      </section> : <p className="mt-3 text-sm text-secondary">ยังไม่มีรายวิชา {me.role === "teacher" ? "ให้ผู้ดูแลกำหนดโรงเรียนในหน้าบัญชีผู้ใช้ก่อนสร้างรายวิชา" : "กรุณาติดต่อครูหรือผู้ดูแลเพื่อกำหนดโรงเรียนและเพิ่มเข้ารายวิชา"}</p>)}
    </div>
    <nav aria-label="หมวดหมู่หลัก" className="mb-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
      {menu.map((item) => <button key={item.id} type="button"
        aria-current={group === item.id ? "page" : undefined}
        onClick={() => {setView(item.target);setError("");setNotice("");}}
        className={`min-h-22 rounded-2xl border p-3 text-left transition focus-visible:outline-2 focus-visible:outline-brand-blue ${group === item.id ? "border-brand-blue bg-brand-mint/50 text-brand-navy shadow-sm" : "border-border bg-white hover:border-brand-blue"}`}>
        <span className="block font-semibold">{item.label}</span>
        <span className="mt-1 block text-xs text-secondary">{item.subtitle}</span>
      </button>)}
    </nav>
    {subviews.length > 0 && <nav aria-label="เมนูย่อย" className="mb-5 flex flex-wrap gap-2 rounded-2xl bg-surface-soft p-2">
      {subviews.map(([id, label]) => <button type="button" key={id}
        aria-current={view === id ? "page" : undefined}
        onClick={() => {setView(id);setError("");setNotice("");}}
        className={view === id ? "pilot-button" : "pilot-secondary"}>{label}</button>)}
    </nav>}
    {error && <p role="alert" className="mb-4 rounded-xl border border-danger p-3 text-red-800">{error}</p>}
    {notice && <p role="status" className="mb-4 rounded-xl bg-brand-mint p-3">{notice}</p>}
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm" aria-busy={busy}>
      {(view === "home" || view === "ask" || view === "practice") && <div className="space-y-5">
        <LineLearningGuide
          ready={!!courseId && me.active_course_id === courseId}
          busy={busy}
          inLine={inLine}
          onOpen={(message) => { void run(async () => openLineChat(message)); }}
        />
        <h2 className="text-lg font-bold">บัญชีและการตั้งค่า</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {([
            ["settings", "บัญชีและการแจ้งเตือน", "ตั้งเวลาเตือนและจัดการข้อมูลส่วนตัว"],
            ...(teacher ? [["documents", "ไฟล์สอนและโจทย์", "อัปโหลดและอนุมัติเอกสาร"], ["course", "งานของครู", "ตรวจคำตอบและจัดรายวิชา"]] : []),
          ] as [View, string, string][]).map(([id, title, desc]) => <button key={id} type="button"
            onClick={() => {setView(id); setError(""); setNotice("");}}
            className="rounded-2xl border border-border bg-white p-4 text-left hover:border-brand-blue focus-visible:outline-2 focus-visible:outline-brand-blue">
            <span className="block font-semibold text-brand-navy">{title}</span>
            <span className="mt-1 block text-sm text-secondary">{desc}</span>
          </button>)}
        </div>
      </div>}
      {view === "tasks" && <><h2 className="pilot-heading">งานของฉัน</h2><form className="mb-5 grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); const target = e.currentTarget; void run(async () => { const due = field(form, "due"); await api("/tasks", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: json({ title: field(form, "title"), due_at: due ? new Date(due).toISOString() : null, course_id: courseId || null }) }); setTasks(await api<Task[]>("/tasks")); target.reset(); }); }}><label>ชื่องาน<input className="pilot-input" name="title" required maxLength={255} /></label><label>กำหนดส่ง (เวลาบนอุปกรณ์)<input className="pilot-input" name="due" type="datetime-local" /></label><button disabled={busy} className="pilot-button sm:col-span-2">บันทึกงาน</button></form><ul className="space-y-3">{tasks.map((task) => <li key={task.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3"><div><strong>{task.title}</strong><p className="text-sm text-secondary">{task.due_at ? dateTime(task.due_at) : "ไม่มีกำหนดส่ง"} · {task.state}</p></div>{task.state === "pending" && <button disabled={busy} className="pilot-secondary" onClick={() => void run(async () => { await api(`/tasks/${task.id}`, { method: "PATCH", body: json({ expected_revision: task.revision, state: "done" }) }); setTasks(await api<Task[]>("/tasks")); })}>ทำเสร็จแล้ว</button>}</li>)}</ul>{!tasks.length && <p>ยังไม่มีงาน</p>}</>}
      {view === "plans" && <><h2 className="pilot-heading">ร่างแผนอ่านสอบ</h2><form className="mb-5 space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { await api("/plans/draft", { method: "POST", body: json({ course_id: courseId, exam_date: field(form, "exam"), minutes_per_day: Number(field(form, "minutes")) }) }); setPlans(await api<Plan[]>("/plans")); }); }}><label className="block">วันสอบที่ยืนยันแล้ว<input type="date" name="exam" required className="pilot-input" /></label><label className="block">นาทีต่อวัน<input type="number" name="minutes" min={5} max={120} defaultValue={20} required className="pilot-input" /></label><p className="text-sm text-secondary">เสนอเวลาอ่าน 18:00 น. ตามเขตเวลาบัญชี ตรวจวันจริงก่อนเปิดแผน</p><button className="pilot-button" disabled={busy || !courseId}>สร้างแผนร่าง</button></form>{plans.map(({plan, items}) => <article key={plan.id} className="mb-4 rounded-xl border border-border p-4"><h3 className="font-semibold">สอบ {plan.end_date} · {plan.state}</h3><ul className="my-3 max-h-52 overflow-auto text-sm">{items.map((item) => <li className="py-1" key={item.id}>{dateTime(item.scheduled_at)} · {item.minutes} นาที</li>)}</ul>{plan.state === "draft" && <button disabled={busy} className="pilot-button" onClick={() => void run(async () => { await api(`/plans/${plan.id}/activate`, { method: "POST", body: json({ expected_revision: plan.revision }) }); setPlans(await api<Plan[]>("/plans")); })}>ยืนยันวันและเปิดแผน</button>}{plan.state !== "cancelled" && <button disabled={busy} className="pilot-secondary ml-2" onClick={() => void run(async () => { await api(`/plans/${plan.id}/cancel`, { method: "POST", body: json({ expected_revision: plan.revision }) }); setPlans(await api<Plan[]>("/plans")); })}>ยกเลิกแผน</button>}</article>)}</>}
      {view === "progress" && <><h2 className="pilot-heading">ความก้าวหน้าของฉัน</h2>{progress ? <><dl className="grid grid-cols-2 gap-3">{[["ฝึกทั้งหมด", progress.attempts], ["ทำเอง", progress.independent_attempts], ["ทำเองถูก", progress.independent_correct], ["ใช้คำใบ้", progress.with_hints], ["รอครูตรวจ", progress.pending_review]].map(([label, value]) => <div key={label} className="rounded-xl bg-surface-soft p-4"><dt>{label}</dt><dd className="text-3xl font-bold text-brand-navy">{value}</dd></div>)}</dl><p className="mt-4">{progress.recommendation}</p></> : <p>เลือกรายวิชาเพื่อดูผล</p>}{courseId && <PracticeResults key={courseId} courseId={courseId} />}</>}
      {view === "admin" && me.is_admin && <AdminPanel onChanged={async () => { setMe(await api<Me>("/me")); }} />}
      {view === "course" && teacher && courseId && <CoursePanel key={courseId} courseId={courseId} onChanged={async () => { setMe(await api<Me>("/me")); }} />}
      {(view === "documents" || view === "acceptance") && teacher && courseId && <TeacherPanel key={`${courseId}-${view}`} courseId={courseId} mode={view} />}
      {view === "documents" && !teacher && courseId && <StudentMaterials key={courseId} courseId={courseId} />}
      {view === "settings" && <><h2 className="pilot-heading">ตั้งค่าการแจ้งเตือน</h2><p className="mb-4 text-sm text-secondary">เลือกว่าจะรับการแจ้งเตือนงานและแผนอ่านสอบผ่าน LINE หรือไม่</p><form key={JSON.stringify(preferences)} className="space-y-4" onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => { setPreferences(await api<Preferences>("/me/preferences", { method: "PUT", body: json({ reminders_enabled: form.has("enabled"), quiet_start: Number(field(form, "start")), quiet_end: Number(field(form, "end")) }) })); setNotice("บันทึกการตั้งค่าแล้ว ใช้กับงานและแผนที่สร้างหรือเปิดใช้หลังจากนี้"); }); }}><label className="flex gap-3"><input type="checkbox" name="enabled" defaultChecked={preferences?.reminders_enabled ?? false} /> เปิดการเตือนผ่าน LINE โดยสมัครใจ</label><label className="block">เวลาเงียบเริ่ม (ชั่วโมง)<input className="pilot-input" name="start" type="number" min={0} max={23} defaultValue={preferences?.quiet_start ?? 21} /></label><label className="block">สิ้นสุด (ชั่วโมง)<input className="pilot-input" name="end" type="number" min={0} max={23} defaultValue={preferences?.quiet_end ?? 7} /></label><button className="pilot-button" disabled={busy || !preferences}>บันทึกการตั้งค่า</button></form><details className="mt-6 rounded-xl border border-border p-4"><summary className="cursor-pointer font-semibold">ข้อมูลบัญชีและความเป็นส่วนตัว</summary><p className="mt-3 break-all text-xs text-secondary">รหัสบัญชีสำหรับแจ้งผู้ดูแล: {me.id}</p><p className="mt-3 text-sm text-secondary">เก็บบัญชี LINE ผลฝึก งาน และประวัติที่จำเป็นตามนโยบายโรงเรียน ติดต่อครูเพื่อถอนตัวจากนำร่อง</p><button className="pilot-secondary mt-3" disabled={busy} onClick={() => { if (window.confirm("ลบประวัติสนทนาของคุณจากระบบปัจจุบันหรือไม่?")) void run(async () => { await api("/me/data", { method: "DELETE", body: json({ deletion_scope: "conversations" }) }); setNotice("ลบประวัติสนทนาแล้ว"); }); }}>ลบประวัติสนทนาใน LINE AI</button></details></>}
    </section>
  </main>;
}

function LineLearningGuide({ ready, busy, inLine, onOpen }: {
  ready: boolean;
  busy: boolean;
  inLine: boolean;
  onOpen: (message?: string) => void;
}) {
  const chatConfigured = !!getLineChatUrl();
  return <section className="rounded-2xl bg-brand-mint/40 p-5">
    <h2 className="text-xl font-bold text-brand-navy">ทำข้อสอบ ตอบคำถาม และขอคำใบ้ใน LINE</h2>
    <p className="mt-2">เปิดแชตส่วนตัวกับ LINE Learning แล้วพิมพ์ <strong>ทำข้อสอบ</strong> เพื่อเริ่มหรือทำชุดเดิมต่อ</p>
    {!ready && <p role="status" className="mt-4 font-medium">เลือกรายวิชาและกด “ใช้วิชานี้ในแชต LINE” ด้านบนก่อนเริ่มสอบ</p>}
    {chatConfigured ? <>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" className="pilot-button" disabled={busy || !ready} onClick={() => onOpen("ทำข้อสอบ")}>ทำข้อสอบใน LINE</button>
        <button type="button" className="pilot-secondary" disabled={busy} onClick={() => onOpen()}>เปิดแชต LINE Learning</button>
      </div>
      <p className="mt-2 text-sm text-secondary">ปุ่มทำข้อสอบจะเปิดแชตพร้อมข้อความ “ทำข้อสอบ” ให้คุณกดส่งใน LINE</p>
    </> : <>
      {inLine && <button type="button" className="pilot-button mt-4" disabled={busy} onClick={() => onOpen()}>กลับไปที่ LINE</button>}
      <p className="mt-2 text-sm text-secondary">{inLine ? "กลับไปเปิด" : "เปิดแอป LINE แล้วเลือก"}แชต LINE Learning แล้วส่งข้อความ “ทำข้อสอบ”</p>
    </>}
    <details className="mt-4 border-t border-border pt-4">
      <summary className="cursor-pointer font-semibold">วิธีตอบคำถามและขอคำใบ้ในแชต</summary>
      <ol className="mt-3 list-decimal space-y-2 pl-5">
        <li>ระบบส่งโจทย์ทีละข้อ แตะตัวเลือกหรือพิมพ์คำตอบในแชต</li>
        <li>ถ้าต้องการความช่วยเหลือ แตะปุ่ม <strong>คำใบ้</strong> หรือพิมพ์ <strong>ขอคำใบ้</strong> แล้วตอบข้อเดิมต่อได้</li>
        <li>เมื่อจบชุด ระบบส่งคะแนนและหัวข้อที่ควรทบทวนในแชต พิมพ์ <strong>ผลสอบ</strong> เพื่อดูอีกครั้ง</li>
      </ol>
      <p className="mt-3 text-sm text-secondary">พิมพ์ “ยกเลิกสอบ” เพื่อออกจากชุดที่กำลังทำ แล้วถามบทเรียนกับ AI ต่อในแชตได้</p>
    </details>
  </section>;
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
