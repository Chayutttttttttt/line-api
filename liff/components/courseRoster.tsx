"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Student = { id: string; display_name: string | null; status: string };
type Roster = {
  school: { id: string; name: string };
  owner: { id: string; display_name: string | null } | null;
  students: Student[];
  available: Student[];
};
const label = (student: { id: string; display_name: string | null }) =>
  `${student.display_name || "ผู้ใช้"} (${student.id.slice(0, 8)})`;

export default function CourseRoster({ courseId, onChanged }: {
  courseId: string;
  onChanged: () => Promise<void>;
}) {
  const [roster, setRoster] = useState<Roster | null>(null);
  const [studentId, setStudentId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const path = `/courses/${courseId}/students`;

  useEffect(() => {
    let active = true;
    api<Roster>(path)
      .then((result) => { if (active) setRoster(result); })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [path]);

  async function change(action: () => Promise<unknown>, message: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      await action();
      setStudentId("");
      setRoster(await api<Roster>(path));
      await onChanged();
      setNotice(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "ทำรายการไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return <section className="space-y-4" aria-busy={busy} aria-label="นักเรียนในรายวิชา">
    {error && <p role="alert" className="text-red-800">{error}</p>}
    {notice && <p role="status" className="rounded-xl bg-brand-mint p-3">{notice}</p>}
    {!roster && !error && <p role="status">กำลังโหลดนักเรียน…</p>}
    {roster && <>
      <div className="rounded-xl bg-surface-soft p-3 text-sm">
        <p>โรงเรียน: <strong>{roster.school.name}</strong></p>
        <p>เจ้าของรายวิชา: <strong>{roster.owner ? label(roster.owner) : "ไม่พบข้อมูลผู้สร้างรายวิชาเดิม"}</strong></p>
      </div>
      <form className="grid gap-3" onSubmit={(e) => {
        e.preventDefault();
        if (!studentId || busy) return;
        void change(() => api(path, {
          method: "PUT", body: JSON.stringify({ user_id: studentId }),
        }), "เพิ่มนักเรียนเข้ารายวิชาแล้ว");
      }}>
        <label>เพิ่มนักเรียนในโรงเรียนนี้
          <select className="pilot-input mt-1" required value={studentId}
            disabled={busy || !roster.available.length} onChange={(e) => setStudentId(e.target.value)}>
            <option value="">เลือกนักเรียน</option>
            {roster.available.map((student) => <option key={student.id} value={student.id}>{label(student)}</option>)}
          </select>
        </label>
        {!roster.available.length && <p className="text-sm text-secondary">ไม่มีนักเรียนที่เพิ่มได้ในขณะนี้ ผู้ดูแลกำหนดโรงเรียนและบทบาทได้ที่ “บัญชีผู้ใช้”</p>}
        <button className="pilot-button" disabled={busy || !studentId}>เพิ่มนักเรียน</button>
      </form>
      <h3 className="font-semibold">นักเรียนปัจจุบัน ({roster.students.length})</h3>
      {!roster.students.length && <p className="text-sm text-secondary">ยังไม่มีนักเรียนในรายวิชา</p>}
      {roster.students.map((student) => <div key={student.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-soft p-3">
        <div className="min-w-0 text-sm"><strong className="break-words">{label(student)}</strong>
          {student.status !== "active" && <p>บัญชีถูกระงับ</p>}
        </div>
        <button className="pilot-secondary" disabled={busy} onClick={() => {
          if (!window.confirm(`นำ ${label(student)} ออกจากรายวิชานี้หรือไม่?`)) return;
          void change(() => api(`${path}/${student.id}`, { method: "DELETE" }), "นำออกจากรายวิชาแล้ว โรงเรียนและประวัติการเรียนยังอยู่");
        }}>เอาออก</button>
      </div>)}
    </>}
  </section>;
}
