# Preview สรุปฟังก์ชันปัจจุบันของโปรเจกต์

งานล่าสุดวันที่ 18 ตุลาคม 2569: ตรวจ routes และหน้า LIFF เพื่อสรุปฟังก์ชันที่มีอยู่ในโค้ด โดยแยกจากสถานะทดสอบบริการจริง

- ผู้เรียน: LINE Login, ถามบทเรียนจากเอกสารที่อนุมัติ, ฝึกโจทย์/คำใบ้/ตรวจคำตอบ, งานส่วนตัว, แผนสอบ, การเตือน, ความก้าวหน้า, ดาวน์โหลดเอกสาร และตั้งค่าหรือลบประวัติ
- ครู: อัปโหลด PDF/DOCX/TXT ตรวจข้อความและหน้า อนุมัติ/ถอนรุ่น รับรองโจทย์ บันทึกหลักฐานตรวจรับและคะแนนชุด AI 80 กรณี ส่งออก JSON ภาพรวมวิชาและติดตาม feedback มี API ฝั่งครู
- หลังบ้าน: PostgreSQL, private S3 adapter, คิว worker/outbox/retry/กันซ้ำ, ตรวจสิทธิ์โรงเรียนและรายวิชา, CLI จัดสมาชิกและ replay deletion ledger
- ฟังก์ชันส่วนใหญ่มีหน้า LIFF; แชต LINE รุ่นนี้รับข้อความถามบทเรียนและส่ง Push/เตือน ไม่รองรับ AI สั่งเขียนงาน/แผน ภาพโจทย์/OCR หรือสร้าง Rich Menu อัตโนมัติ
- ยังไม่ถือว่าทดสอบ LINE/Gemini/Bucket จริงผ่าน รอบนี้แก้เฉพาะ PREVIEW.md ไม่เปลี่ยนโค้ดและไม่รันทดสอบซ้ำ

## รายละเอียดงานพัฒนาก่อนหน้า

# Preview พัฒนาระบบเตรียมตรวจรับตาม roadmap

งานล่าสุดวันที่ 18 ตุลาคม 2569: ต่อระบบเดิมเป็นเส้นทางเตรียมตรวจรับก่อนนำร่อง โดยใช้ Railway รัน API/worker และ PostgreSQL พร้อม private S3 storage สำหรับ Bucket ที่แสดงชื่อ `adaptable-folder` ในโปรเจกต์ที่ผู้ใช้ระบุ

## การเปลี่ยนแปลงหลัก

- LINE Login ตรวจ ID token จริงก่อนออก bearer session แบบเก็บ hash ไม่ print token ตรวจสมาชิกโรงเรียน/รายวิชาฝั่ง server
- Webhook ตรวจ HMAC จาก raw body บันทึก event/job ในธุรกรรมเดียว กัน event ซ้ำ และแยกงาน AI ไป SQL worker มี lease, retry, fencing, ลำดับรายผู้ใช้ และ outbox ที่ใช้ LINE retry key เดิม
- คลังไฟล์ PDF/DOCX/TXT มี checksum รุ่นเอกสาร ข้อความ/เลขหน้าที่ครูตรวจ และประวัติผลตรวจ แยก `teaching` จาก `evidence` อนุมัติต้นแบบยังไม่เปิดให้นักเรียน การอนุมัติเนื้อหาใช้ rubric Word 0–2 แยกจากการประเมิน AI 0–3
- เพิ่ม exact lexical retrieval เฉพาะแหล่งเผยแพร่ Gemini adapter ตรวจ schema/citation แบบฝึกเซตจำนวนเต็มและการเป็นฟังก์ชัน งาน idempotency/revision แผนสอบแบบ draft/activate การเตือน opt-in/เวลาเงียบ และความก้าวหน้าแยกทำเองกับใช้คำใบ้
- LIFF มีหน้าเรียน ฝึก งาน แผน เอกสาร ตั้งค่า และหน้าครูจัดไฟล์/ตรวจรับ เพิ่มทะเบียนหลักฐาน T01–T12 และ catalog AI 80 กรณี ส่งออก JSON พร้อมรุ่น checksum ผู้ตรวจ คะแนน และรายการที่ยังไม่ผ่าน ไม่สร้างผลผ่านแทนครู
- เพิ่ม CLI จัดโรงเรียน/สมาชิก นำเข้าไฟล์ ส่งออก deletion ledger และบังคับรายการลบซ้ำหลัง restore พร้อม Docker/API/LIFF และคู่มือติดตั้ง Railway

## ไฟล์ที่ได้รับผล

- Backend: `main.py`, `config.py`, `components/login.py`, `components/line.py`, `components/documents.py`, `components/learning.py`, `components/acceptance.py`, `components/grading.py`, `components/storage.py`, `agent/gemini.py`, `worker/`, `manage.py`
- SQL: `db/models.py`, `db/database.py`, `db/migrate.py`, migration ใหม่ `alembic/versions/20261018_acceptance_workflow.py` ไม่แก้ migration generated เดิม
- LIFF: `liff/app/page.tsx`, `layout.tsx`, `globals.css`, `components/dashboard.tsx`, `teacherPanel.tsx`, `lineloginButton.tsx`, `lib/api.ts`, `next.config.ts`
- ตั้งค่าและคู่มือ: Dockerfiles, `.dockerignore`, `.env.example`, `railway.toml`, requirements, `README.md`, `OPERATIONS.md`, `liff/README.md`, `liff/.gitignore`, `tests/` และไฟล์นี้ ไม่แก้ dependency lock เดิมหรือเอกสารต้นฉบับที่แนบ

## ผลตรวจสอบ

- pytest กับ PostgreSQL/pgvector ชั่วคราวแยกจาก Railway: **39 ผ่าน** รวม webhook ซ้ำพร้อมกัน 10 ครั้ง, session/สิทธิ์ข้ามผู้ใช้, ถอนเอกสาร, checksum, submission/task idempotency, lease กู้คืน, LINE timeout/retry key, S3 stub, deletion ledger replay และ downgrade/upgrade migration
- ESLint ทั้ง LIFF และ TypeScript ผ่าน
- Next.js production build ด้วย `--webpack` ผ่าน Turbopack ใน environment นี้ติดข้อจำกัดเปิดพอร์ตภายใน จึงใช้ Webpack
- Python compile และ `git diff --check` ผ่าน
- ทดลอง extractor กับไฟล์แนบทั้งสองในเครื่อง: DOCX อ่านข้อความได้ และ PDF อ่านได้ 32 หน้า ไม่มีการอัปโหลดหรือแก้ไฟล์ต้นฉบับ
- LINE, Gemini และ S3 ภายนอกใช้ mock/stub ใน automated tests ไม่ใช่ผลทดสอบบริการจริงหรือคะแนน AI 80 กรณีจากครู

## การใช้งานและสถานะจริง

ดูขั้นตอนใน `README.md` และ `OPERATIONS.md` ตั้งค่า S3 จาก Credentials/Variable References ของ bucket โดยใช้ชื่อ S3 bucket จริง ไม่เดาจากชื่อแสดงผล เริ่ม API และ worker แยก service แล้วให้ผู้ดูแลเพิ่มสมาชิกหลัง Login จริง

หน้า Railway ที่ตรวจอ่านแสดง Trial expired และ API/Postgres ออฟไลน์ จึงยังไม่ได้ deploy อัปโหลดไฟล์แนบ หรือทดสอบ OAuth/LINE Push/Gemini/Bucket จริง เริ่ม `AI_ENABLED=false` จนเอกสารผ่านครู `RelFnc.pdf` ที่แบบฟอร์มอ้างถึงยังไม่ได้รับมา

ก่อนนำร่องยังต้องมีผลบริการจริง ผลครูประเมิน 80 กรณีอย่างอิสระอย่างน้อยสองคน ผล backup/restore/load test และการอนุมัติโรงเรียน รายงานคง `not_ready` เมื่อหลักฐานไม่ครบ ฟังก์ชัน OCR/vector ranking/AI tools ที่เขียนรายการ/การศึกษาผลก่อนหลังยังอยู่นอกโค้ดชุดนี้ตามรายละเอียดใน README
