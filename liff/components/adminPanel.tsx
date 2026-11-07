"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import CourseRoster from "./courseRoster";

type Member = { user_id: string; role: string; status: string };
type User = {
  id: string; display_name: string | null; status: string;
  school_id: string | null; role: "student" | "teacher";
  membership_revision: number; is_admin: boolean;
};
type School = { id: string; name: string; members: Member[] };
type Course = { id: string; school_id: string; title: string; subject: string; grade_level: string | null; members: Member[] };
type Overview = {
  counts: { users: number; schools: number; courses: number };
  users: User[];
  schools: School[];
  courses: Course[];
};
const value = (form: FormData, key: string) => String(form.get(key) ?? "").trim();
const json = (body: unknown) => JSON.stringify(body);
const shortId = (id: string) => id.slice(0, 8);

export default function AdminPanel({ onChanged }: { onChanged: () => Promise<void> }) {
  const [data, setData] = useState<Overview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [schoolId, setSchoolId] = useState("");
  const [courseId, setCourseId] = useState("");
  const [schoolFilter, setSchoolFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [adminTab, setAdminTab] = useState<"schools" | "courses" | "users">("schools");

  useEffect(() => {
    let active = true;
    api<Overview>("/admin/overview")
      .then((overview) => { if (active) setData(overview); })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  async function refresh() {
    const overview = await api<Overview>("/admin/overview");
    setData(overview);
    if (!overview.schools.some((school) => school.id === schoolId)) setSchoolId("");
    if (!overview.courses.some((course) => course.id === courseId)) setCourseId("");
    await onChanged();
  }

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
      setNotice(success);
    } catch (e) {
      setError(e instanceof Error ? e.message : "ทำรายการไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  const selectedSchool = data?.schools.find((school) => school.id === schoolId);
  const selectedCourse = data?.courses.find((course) => course.id === courseId);
  const filteredUsers = data?.users.filter((user) =>
    (schoolFilter === "all" || (schoolFilter === "none" ? !user.school_id : user.school_id === schoolFilter)) &&
    (roleFilter === "all" || user.role === roleFilter)
  ) ?? [];

  return <div className="space-y-8" aria-busy={busy}>
    <div>
      <h2 className="pilot-heading">จัดการโรงเรียนและสมาชิก</h2>
      <p className="text-sm text-secondary">สำหรับผู้ดูแลที่ได้รับสิทธิ์เท่านั้น เลือกหัวข้อที่ต้องการจัดการด้านล่าง</p>
    </div>
    {error && <p role="alert" className="rounded-xl border border-danger bg-red-50 p-3 text-red-800">{error}</p>}
    {notice && <p role="status" className="rounded-xl bg-brand-mint p-3">{notice}</p>}
    {!data ? <p role="status">กำลังโหลดข้อมูลผู้ดูแล…</p> : <>
      <div className="grid grid-cols-3 gap-3">
        {([
          ["บัญชีผู้ใช้", data.counts.users],
          ["โรงเรียน", data.counts.schools],
          ["รายวิชา", data.counts.courses],
        ] as const).map(([label, count]) =>
          <div key={label} className="rounded-xl border border-border bg-surface-soft p-3 text-center">
            <p className="text-xs text-secondary">{label}</p>
            <strong className="text-2xl text-brand-navy">{count}</strong>
          </div>)}
      </div>

      <nav aria-label="เมนูผู้ดูแลระบบ" className="grid gap-2 sm:grid-cols-3">
        {([["schools","โรงเรียน"],["courses","รายวิชาและสมาชิก"],["users","บัญชีผู้ใช้"]] as const).map(([id,label]) =>
          <button key={id} type="button" className={adminTab === id ? "pilot-button" : "pilot-secondary"}
            aria-current={adminTab === id ? "page" : undefined}
            onClick={() => {setAdminTab(id);setError("");setNotice("");}}>{label}</button>)}
      </nav>
      {adminTab === "schools" && <section className="space-y-4">
        <h3 className="text-lg font-semibold">โรงเรียน</h3>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault(); const form = e.currentTarget; const fields = new FormData(form);
          void run(async () => { await api("/admin/schools", {method:"POST",body:json({name:value(fields,"name")})}); form.reset(); }, "เพิ่มโรงเรียนแล้ว");
        }}>
          <input className="pilot-input min-w-0 flex-1" name="name" required maxLength={255} placeholder="ชื่อโรงเรียนใหม่" aria-label="ชื่อโรงเรียนใหม่" />
          <button className="pilot-button" disabled={busy}>เพิ่มโรงเรียน</button>
        </form>
        <label className="block">จัดการโรงเรียน
          <select className="pilot-input mt-1" value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
            <option value="">เลือกโรงเรียน</option>
            {data.schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
          </select>
        </label>
        {selectedSchool && <div className="rounded-xl border border-border p-4 space-y-3">
          <p className="text-xs text-secondary break-all">School ID: {selectedSchool.id}</p>
          <form className="flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault(); const fields = new FormData(e.currentTarget);
            void run(() => api(`/admin/schools/${selectedSchool.id}`, {method:"PATCH",body:json({name:value(fields,"name")})}), "เปลี่ยนชื่อโรงเรียนแล้ว");
          }}>
            <input className="pilot-input min-w-0 flex-1" name="name" required maxLength={255} defaultValue={selectedSchool.name} aria-label="เปลี่ยนชื่อโรงเรียน"/>
            <button className="pilot-secondary" disabled={busy}>บันทึกชื่อ</button>
          </form>
          <p className="text-sm">สมาชิกระดับโรงเรียน: {selectedSchool.members.length} คน</p>
          <button className="pilot-secondary" disabled={busy} onClick={() => {
            if (!window.confirm(`ลบโรงเรียน “${selectedSchool.name}” หรือไม่? ระบบอนุญาตเฉพาะโรงเรียนที่ไม่มีรายวิชาและสมาชิก`)) return;
            void run(() => api(`/admin/schools/${selectedSchool.id}`, {method:"DELETE"}), "ลบโรงเรียนว่างแล้ว");
          }}>ลบโรงเรียนที่ว่าง</button>
        </div>}
      </section>}
      {adminTab === "courses" && <section className="space-y-4">
        <h3 className="text-lg font-semibold">รายวิชาและสมาชิก</h3>
        <form className="grid gap-3 rounded-xl border border-border p-4" onSubmit={(e) => {
          e.preventDefault(); const form = e.currentTarget; const fields = new FormData(form);
          void run(async () => { await api("/admin/courses", {method:"POST",body:json({
            school_id: value(fields,"school_id"), title:value(fields,"title"),
            subject:value(fields,"subject"), learning_scope:value(fields,"scope"),
            response_language:"ไทย", grade_level:value(fields,"grade") || null
          })}); form.reset(); }, "สร้างรายวิชาแล้ว");
        }}>
          <label>โรงเรียน
            <select name="school_id" required defaultValue="" className="pilot-input mt-1">
              <option value="" disabled>เลือกโรงเรียน</option>
              {data.schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
            </select>
          </label>
          <label>ชื่อรายวิชา<input name="title" className="pilot-input mt-1" required maxLength={255} placeholder="เช่น คณิตศาสตร์ ม.4" /></label>
          <label>กลุ่มสาระ<input name="subject" className="pilot-input mt-1" required maxLength={255} placeholder="เช่น คณิตศาสตร์" /></label>
          <label>ระดับชั้น (ไม่บังคับ)<input name="grade" className="pilot-input mt-1" maxLength={32} placeholder="เช่น ม.4" /></label>
          <label>ขอบเขตความรู้<textarea name="scope" required maxLength={4000} rows={3} className="pilot-input mt-1" placeholder="ขอบเขตที่ครูอนุญาตให้ AI ใช้ตอบ" /></label>
          <button className="pilot-button" disabled={busy || !data.schools.length}>สร้างรายวิชา</button>
        </form>
        <label className="block">จัดการสมาชิกในรายวิชา
          <select value={courseId} onChange={(e) => setCourseId(e.target.value)} className="pilot-input mt-1">
            <option value="">เลือกรายวิชา</option>
            {data.courses.map((course) => <option key={course.id} value={course.id}>
              {data.schools.find((school) => school.id === course.school_id)?.name} · {course.title}
            </option>)}
          </select>
        </label>
        {selectedCourse && <div className="space-y-4 rounded-xl border border-border p-4">
          <p className="text-xs text-secondary break-all">Course ID: {selectedCourse.id}</p>
          <CourseRoster key={selectedCourse.id} courseId={selectedCourse.id} onChanged={refresh} />
          <p className="text-sm text-secondary">หากต้องการแก้เนื้อหา เอกสารหรือคำตอบ ให้เลือกวิชาจากเมนูด้านบนแล้วเปิด “จัดการวิชา / ตรวจคำตอบ”</p>
          <button disabled={busy} className="pilot-secondary" onClick={() => {
            if (!window.confirm(`ลบวิชา “${selectedCourse.title}” หรือไม่? ลบได้เฉพาะวิชาที่ไม่มีสมาชิกและข้อมูลอ้างอิง`)) return;
            void run(() => api(`/admin/courses/${selectedCourse.id}`, {method:"DELETE"}), "ลบรายวิชาที่ว่างแล้ว");
          }}>ลบรายวิชาที่ว่าง</button>
        </div>}
      </section>}
      {adminTab === "users" && <section className="space-y-3">
        <h3 className="text-lg font-semibold">บัญชีผู้ใช้</h3>
        <p className="text-sm text-secondary">ผู้ใช้ต้อง Login ผ่าน LINE ก่อนจึงจะปรากฏในรายการนี้ การระงับบัญชีจะยกเลิก Session ที่มีอยู่</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label>กรองตามโรงเรียน
            <select className="pilot-input mt-1" value={schoolFilter} onChange={(e) => setSchoolFilter(e.target.value)}>
              <option value="all">ทุกโรงเรียน</option><option value="none">ไม่มีสังกัด</option>
              {data.schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
            </select>
          </label>
          <label>กรองตามบทบาท
            <select className="pilot-input mt-1" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
              <option value="all">ทุกบทบาท</option><option value="student">นักเรียน</option><option value="teacher">ครู</option>
            </select>
          </label>
        </div>
        <p className="text-sm text-secondary">พบ {filteredUsers.length} บัญชี · การเปลี่ยนโรงเรียนหรือบทบาทจะยกเลิกสิทธิ์รายวิชาเดิมที่ไม่ตรงกับข้อมูลใหม่ โดยเก็บประวัติการเรียนไว้</p>
        {!filteredUsers.length && <p>ไม่พบบัญชีตามตัวกรอง</p>}
        {filteredUsers.map((user) => <UserAccountRow key={`${user.id}-${user.membership_revision}-${user.status}`}
          user={user} schools={data.schools} busy={busy} run={run} />)}
      </section>}
    </>}
  </div>;
}


function UserAccountRow({ user, schools, busy, run }: {
  user: User;
  schools: School[];
  busy: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [schoolId, setSchoolId] = useState(user.school_id ?? "");
  const [role, setRole] = useState(user.role);
  const changed = schoolId !== (user.school_id ?? "") || role !== user.role;
  const schoolName = schools.find((school) => school.id === user.school_id)?.name ?? "ไม่มีสังกัด";
  return <article className="space-y-3 rounded-xl border border-border p-4" aria-label={user.display_name || user.id}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <strong>{user.display_name || "ไม่มีชื่อแสดง"}</strong>
        {user.is_admin && <span className="ml-2 rounded bg-brand-mint px-2 py-1 text-xs">ผู้ดูแลระบบ</span>}
        <p className="text-xs text-secondary break-all">{user.id}</p>
        <p className="mt-1 text-sm">{schoolName} · {user.role === "teacher" ? "ครู" : "นักเรียน"} · {user.status === "active" ? "ใช้งานอยู่" : user.status === "deleted" ? "ลบบัญชีแล้ว" : "ระงับบัญชี"}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="pilot-secondary" onClick={() => { void navigator.clipboard?.writeText(user.id); }}>คัดลอก UUID</button>
        {user.status !== "deleted" && <button disabled={busy} className="pilot-secondary" onClick={() => {
          const status = user.status === "active" ? "inactive" : "active";
          if (status === "inactive" && !window.confirm(`ระงับบัญชี ${user.display_name || shortId(user.id)} หรือไม่?`)) return;
          void run(() => api(`/admin/users/${user.id}/status`, { method: "PATCH", body: json({ status }) }), status === "active" ? "เปิดบัญชีแล้ว" : "ระงับบัญชีแล้ว");
        }}>{user.status === "active" ? "ระงับ" : "เปิดบัญชี"}</button>}
      </div>
    </div>
    {user.status !== "deleted" && <form className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]" onSubmit={(e) => {
      e.preventDefault();
      if (!changed || busy) return;
      void run(() => api(`/admin/users/${user.id}/affiliation`, {
        method: "PATCH", body: json({ school_id: schoolId || null, role, expected_revision: user.membership_revision }),
      }), "บันทึกโรงเรียนและบทบาทแล้ว");
    }}>
      <label>โรงเรียนปัจจุบัน
        <select className="pilot-input mt-1" value={schoolId} disabled={busy} onChange={(e) => setSchoolId(e.target.value)}>
          <option value="">ไม่มีสังกัด</option>
          {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
        </select>
      </label>
      <label>บทบาท
        <select className="pilot-input mt-1" value={role} disabled={busy} onChange={(e) => setRole(e.target.value as User["role"])}>
          <option value="student">นักเรียน</option><option value="teacher">ครู</option>
        </select>
      </label>
      <button className="pilot-button" disabled={busy || !changed}>บันทึก</button>
    </form>}
  </article>;
}
