"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Member = { user_id: string; role: string; status: string };
type User = { id: string; display_name: string | null; status: string };
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
  const userLabel = (id: string) => {
    const user = data?.users.find((entry) => entry.id === id);
    return user ? `${user.display_name || "ผู้ใช้"} (${shortId(id)})` : shortId(id);
  };

  return <div className="space-y-8" aria-busy={busy}>
    <div>
      <h2 className="pilot-heading">ผู้ดูแลระบบ (Global Admin)</h2>
      <p className="text-sm text-secondary">สิทธิ์จัดการทุกโรงเรียนและรายวิชา ตรวจสอบด้วยบัญชี LINE และ API ทุกครั้ง ไม่สามารถตั้งตนเองเป็น Admin ผ่านแบบฟอร์มได้</p>
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

      <section className="space-y-4">
        <h3 className="text-lg font-semibold">1. โรงเรียน</h3>
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
      </section>

      <section className="space-y-4">
        <h3 className="text-lg font-semibold">2. รายวิชา</h3>
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
          <h4 className="font-semibold">เพิ่มหรือแก้สิทธิ์ครู / นักเรียน</h4>
          <form className="grid gap-3" onSubmit={(e) => {
            e.preventDefault(); const fields = new FormData(e.currentTarget);
            void run(() => api("/admin/memberships", {method:"PUT",body:json({
              user_id:value(fields,"user_id"), course_id:selectedCourse.id, role:value(fields,"role")
            })}), "บันทึกสิทธิ์สมาชิกแล้ว");
          }}>
            <label>บัญชีผู้ใช้ (ต้องเคย Login LINE)
              <select name="user_id" className="pilot-input mt-1" required defaultValue="">
                <option value="" disabled>เลือกบัญชีผู้ใช้</option>
                {data.users.filter((user) => user.status === "active").map((user) =>
                  <option key={user.id} value={user.id}>{user.display_name || "ผู้ใช้"} · {shortId(user.id)}</option>)}
              </select>
            </label>
            <label>บทบาท
              <select name="role" className="pilot-input mt-1" defaultValue="student">
                <option value="student">นักเรียน</option>
                <option value="teacher">ครู</option>
              </select>
            </label>
            <button disabled={busy} className="pilot-button">บันทึกสิทธิ์</button>
          </form>
          <h4 className="font-semibold">สมาชิกปัจจุบัน ({selectedCourse.members.length})</h4>
          {!selectedCourse.members.length && <p className="text-sm text-secondary">ยังไม่มีสมาชิก</p>}
          {selectedCourse.members.map((member) => <div key={member.user_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-soft p-3">
            <div className="text-sm"><strong>{userLabel(member.user_id)}</strong><p>{member.role} · {member.status}</p></div>
            <button disabled={busy} className="pilot-secondary" onClick={() => {
              if (!window.confirm(`ลบ ${userLabel(member.user_id)} ออกจากวิชานี้หรือไม่?`)) return;
              void run(() => api(`/admin/memberships/${selectedCourse.id}/${member.user_id}`, {method:"DELETE"}), "ลบสมาชิกออกจากรายวิชาแล้ว");
            }}>เอาออก</button>
          </div>)}
          <p className="text-sm text-secondary">หากต้องการแก้เนื้อหา เอกสารหรือคำตอบ ให้เลือกวิชาจากเมนูด้านบนแล้วเปิด “จัดการวิชา / ตรวจคำตอบ”</p>
          <button disabled={busy} className="pilot-secondary" onClick={() => {
            if (!window.confirm(`ลบวิชา “${selectedCourse.title}” หรือไม่? ลบได้เฉพาะวิชาที่ไม่มีสมาชิกและข้อมูลอ้างอิง`)) return;
            void run(() => api(`/admin/courses/${selectedCourse.id}`, {method:"DELETE"}), "ลบรายวิชาที่ว่างแล้ว");
          }}>ลบรายวิชาที่ว่าง</button>
        </div>}
      </section>

      <section className="space-y-3">
        <h3 className="text-lg font-semibold">3. บัญชีผู้ใช้</h3>
        <p className="text-sm text-secondary">ผู้ใช้ต้อง Login ผ่าน LINE ก่อนจึงจะปรากฏในรายการนี้ การระงับบัญชีจะยกเลิก Session ที่มีอยู่</p>
        {data.users.map((user) => <div key={user.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3">
          <div className="min-w-0">
            <strong>{user.display_name || "ไม่มีชื่อแสดง"}</strong>
            <p className="text-xs text-secondary break-all">{user.id}</p>
            <p className="text-sm">{user.status}</p>
          </div>
          <div className="flex gap-2">
            <button className="pilot-secondary" onClick={() => { void navigator.clipboard?.writeText(user.id); }}>คัดลอก UUID</button>
            {user.status === "active" ? <button disabled={busy} className="pilot-secondary" onClick={() => {
              if (!window.confirm(`ระงับบัญชี ${user.display_name || shortId(user.id)} หรือไม่? ไม่สามารถระงับ Admin ตัวเองได้`)) return;
              void run(() => api(`/admin/users/${user.id}/status`, {method:"PATCH",body:json({status:"inactive"})}), "ระงับบัญชีแล้ว");
            }}>ระงับ</button> : <button disabled={busy} className="pilot-secondary" onClick={() => {
              void run(() => api(`/admin/users/${user.id}/status`, {method:"PATCH",body:json({status:"active"})}), "เปิดบัญชีแล้ว");
            }}>เปิดบัญชี</button>}
          </div>
        </div>)}
      </section>
    </>}
  </div>;
}
