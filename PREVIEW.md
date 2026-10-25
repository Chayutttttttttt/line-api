# Preview บันทึกคำอธิบายโค้ดใน Obsidian

อัปเดต 25 ตุลาคม 2569: เขียนโน้ตภาษาไทยอธิบายสถาปัตยกรรม โครงสร้างไฟล์ ลำดับงานหลัก ฐานข้อมูล LIFF วิธีเริ่มรัน และข้อจำกัดของโปรเจกต์ลงในหมวด `01 Project/line-api` ของ Obsidian vault

- ไฟล์ที่ได้รับผล: `Documents/Obsidian Vault/01 Project/line-api/อธิบายโค้ด LINE Learning.md` (นอก repository) และ `PREVIEW.md`
- วิธีใช้: เปิดโน้ตใน Obsidian ที่หมวด `01 Project → line-api`; ตารางและ Mermaid ช่วยไล่โครงสร้างระบบ
- ไม่มีการแก้โค้ดแอปหรือไฟล์ generated

## ประวัติ preview ก่อนหน้า

# Preview ลบชุดทดสอบอัตโนมัติ

อัปเดต 25 ตุลาคม 2569: ลบชุด pytest ของ backend และรายการ dependencies สำหรับทดสอบ พร้อมเอาคำสั่งรัน pytest ออกจากคู่มือ

- ไฟล์ที่ได้รับผล: ลบ `tests/conftest.py`, `tests/test_pilot.py`, `tests/test_subjects.py`, `requirements-dev.txt`; ปรับ `README.md`, `.dockerignore` และ `PREVIEW.md`
- ยังใช้คำสั่ง lint, TypeScript check และ build ฝั่ง LIFF ตาม `README.md` ได้
- ชุดประเมิน AI 80 กรณีและบันทึกหลักฐานตรวจรับยังเป็นฟีเจอร์ใช้งานจริงของแอป

## ประวัติ preview ก่อนหน้า

# Preview ติดตั้ง Python dependencies

อัปเดต 25 ตุลาคม 2569: ติดตั้งแพ็กเกจจาก `requirements.txt` ลงใน `.venv` ของโปรเจกต์ (Python 3.14.8) สำเร็จ โดยไม่ได้แก้รายการ dependencies หรือโค้ดแอป

- ไฟล์ที่ได้รับผล: `.venv/` (สภาพแวดล้อมในเครื่องและถูกละเว้นโดย Git), `PREVIEW.md`
- ตรวจสอบ: `pip check` ไม่พบข้อขัดแย้ง และ import ไลบรารีหลักทั้ง 14 รายการได้
- วิธีใช้: เรียก Python ผ่าน `.venv/bin/python` หรือเปิดใช้งานด้วย `source .venv/bin/activate`

## ประวัติ preview ก่อนหน้า

# Preview รองรับรายวิชาได้อิสระบนระบบเดิม

อัปเดต 21 ตุลาคม 2569: ปรับ LINE Learning ให้ครูกำหนดรายวิชาได้เอง โดยใช้ LINE channels, Railway API/worker, PostgreSQL และ private bucket เดิม

## สิ่งที่เปลี่ยน

- เพิ่มการสร้าง/ตั้งวิชาในโรงเรียนที่ครูมีสิทธิ์: ชื่อ กลุ่มสาระ ระดับชั้น ขอบเขต ภาษา หัวข้อ และคำค้น พร้อม revision ป้องกันการเขียนทับจากการแก้พร้อมกัน
- AI ใช้บริบทรายวิชาและแหล่งที่ครูอนุมัติของวิชานั้น เลิกจำกัด prompt เฉพาะโดเมน/เรนจ์ เพิ่มคำค้นหัวข้อและ Thai character grams ใน lexical retrieval
- LIFF มีปุ่มเลือกวิชาสำหรับ LINE โดยตรึง course_id ตอนรับ webhook แยกประวัติและแหล่งอ้างอิง ไม่ย้ายข้อความที่เข้าคิวแล้วตามการเลือกภายหลัง ตรวจ revision อีกครั้งก่อนบันทึกคำตอบและส่ง outbox
- แบบฝึก 6 ชนิด: ปรนัย จริง/เท็จ ตัวเลขพร้อม tolerance/หน่วย คำตอบสั้นตามรายการ เซตจำนวนเต็ม และคำตอบอธิบายให้ครูตรวจ ไม่เปิดเฉลยก่อนส่ง ไม่ใช้ eval
- คำตอบอธิบายเป็น pending_review ยังไม่คิดถูก/ผิด ครูในรายวิชาให้คะแนนและข้อเสนอแนะได้ครั้งเดียวพร้อม audit ห้ามตรวจตัวเอง ผู้เรียนดูผลในความก้าวหน้า
- ชุดตรวจรับ AI 80 กรณีแยกวิชา ครูแก้โจทย์/ผลคาดหวัง/เงื่อนไขผิดพลาดได้ ชุดทั่วไปเริ่มเป็นแม่แบบ ต้องกำหนดครบก่อนรับรอง การเปลี่ยนขอบเขตหรือชุดทดสอบทำให้ผล revision เก่าไม่นับผ่าน ผลเก่ายังคงเป็นประวัติ
- Migration เขียนใหม่เพิ่มคอลัมน์ในตารางเดิม รายวิชาเดิมคงขอบเขตและชุดประเมินคณิตศาสตร์ โจทย์ เอกสาร และสมาชิกเดิมไม่ถูกลบ ไม่แก้ migration generated หรือ dependency lock

## ไฟล์หลัก

- `db/models.py`, `alembic/versions/20261021_multisubject.py`
- `agent/gemini.py`, `components/learning.py`, `components/grading.py`, `components/documents.py`, `components/acceptance.py`
- `components/line.py`, `components/login.py`, `worker/run.py`, `manage.py`, `main.py`
- `liff/components/coursePanel.tsx` (ใหม่), `dashboard.tsx`, `teacherPanel.tsx`, `lineloginButton.tsx`, `liff/app/layout.tsx`
- `tests/test_subjects.py` (ใหม่), `tests/test_pilot.py`, `tests/conftest.py`
- `README.md`, `OPERATIONS.md`, `liff/README.md`, `PREVIEW.md`

## ผลตรวจ

- pytest: **70 ผ่าน** บน PostgreSQL/pgvector ชั่วคราว แยกจาก Railway รวมแบบฝึกหลายวิชา การตรวจครู สิทธิ์ การเลือกวิชา LINE การเปลี่ยน revision ระหว่างทำงาน การแก้พร้อมกัน และ upgrade/downgrade ที่รักษาเอกสาร/สมาชิก
- ESLint, TypeScript และ Next.js production build (`--webpack`) ผ่าน
- `git diff --check` ผ่าน มี deprecation warnings เดิมสองรายการจาก Starlette/httpx และ AnyIO ในชุดทดสอบ
- LINE/Gemini ใช้ stub ใน automated tests ไม่มีการส่งข้อความจริงหรือเปลี่ยนข้อมูล Railway

## วิธีเริ่มใช้หลัง deploy

1. สำรองฐานข้อมูล หยุด worker เดิม รัน `python -m db.migrate` ถึง `20261021_multisubject` แล้วเริ่ม API/worker/LIFF รุ่นใหม่ร่วมกัน ใช้ variables และ bucket เดิม
2. ครูเปิด **จัดการวิชา / ตรวจคำตอบ** เพิ่มวิชา/หัวข้อ อัปโหลดและรับรองเอกสาร สร้างและรับรองโจทย์ ผู้ดูแลเพิ่มสมาชิกด้วย CLI เดิม
3. นักเรียนเลือกรายวิชาใน LIFF กด **ใช้วิชานี้ในแชต LINE** ก่อนถามใน LINE เมื่อมีหลายวิชา
4. ครูจัดชุดทดสอบประจำวิชาและประเมินจริงก่อนนำร่อง ดูรายละเอียดใน README และ OPERATIONS

รองรับการตั้งวิชาได้อิสระ แต่ต้องมีเอกสารและโจทย์ที่ครูรับรอง ไม่ได้มีเนื้อหาครบทุกวิชาหรือผลตรวจรับสำเร็จรูป ตัวเลขใช้หน่วยตามโจทย์ ไม่แปลงหน่วย/แก้สมการทั่วไป คำตอบสั้นเทียบรายการ ไม่ให้ AI ตัดสินคำตอบอธิบายแทนครู ยังไม่เพิ่ม OCR ภาพ เสียง วิดีโอ หรือการตรวจทักษะปฏิบัติอัตโนมัติ ยังไม่ได้ deploy หรือทดสอบ LINE/Gemini/Bucket จริง

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
