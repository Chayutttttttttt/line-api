# LINE Math รุ่นเตรียมตรวจรับก่อนนำร่อง

ระบบ FastAPI + PostgreSQL/pgvector + LIFF สำหรับหน่วยโดเมน เรนจ์ และการเป็นฟังก์ชันจากเซตคู่อันดับ เก็บเอกสารต้นฉบับใน private S3 bucket และเก็บรุ่น checksum ผู้อนุมัติ ผลตรวจ และหลักฐานใน SQL

ในโปรเจกต์ Railway ที่ให้มา `adaptable-folder` คือ **ชื่อแสดงผลของ Railway Bucket** ไม่ใช่บริการ Adaptable แยกต่างหาก ตั้งค่า S3 ด้วยชื่อ bucket จริงจากหน้า Credentials ซึ่งอาจมี suffix เพิ่มจากชื่อแสดงผล ตาม [เอกสาร Railway](https://docs.railway.com/storage-buckets)

## สิ่งที่ใช้งานได้ในโค้ด

- ตรวจ LINE ID token กับ LINE ก่อนสร้าง opaque bearer session เก็บเฉพาะ hash ของ session token ในฐานข้อมูล ไม่ print token บทบาทมาจากสมาชิกโรงเรียนและรายวิชาที่ผู้ดูแลเพิ่ม
- รับ signed raw webhook ที่ `/webhook` และ `/webhooks/line` บันทึก event + job ในธุรกรรมเดียว และกัน event ซ้ำด้วย UNIQUE
- SQL worker มี lease, retry, stale-worker fencing และจัดลำดับงานรายผู้ใช้ บันทึกคำตอบกับ outbox ในธุรกรรมเดียว Push ใช้ retry key เดิม สถานะ `accepted` หมายถึง LINE API รับ ไม่ใช่ส่งถึงหรืออ่านแล้ว
- อัปโหลด PDF, DOCX, TXT สูงสุด 10 MB สกัดข้อความใน worker ตรวจ checksum แก้ข้อความ/เลขหน้า และบันทึกผลตรวจครูแบบ append-only แยกอนุมัติต้นแบบกับเนื้อหานำร่อง ถอนแล้วหยุดค้นและดาวน์โหลดสำหรับนักเรียน
- แยกเอกสาร `teaching` กับ `evidence` เอกสารโครงการและหลักฐานไม่ถูกค้นเป็นเนื้อหาสอน ใช้ exact lexical search ขนาดเล็ก ไม่มี vector embedding ที่ยังไม่ตรวจรับหรือ cache ข้ามผู้ใช้
- Gemini adapter มี schema ตรวจ citation กับ chunk ที่ส่งจริง จำกัดเวลาและ output เก็บ model/prompt version กับ usage ไม่เปิดเครื่องมือเขียนข้อมูลให้โมเดล
- แบบฝึกตรวจเซตจำนวนเต็มและการเป็นฟังก์ชันตามเฉลยครู ไม่ใช้ `eval` ผูกกับโจทย์และรุ่นที่เสิร์ฟ บันทึกคำใบ้ฝั่ง server และกัน submission ซ้ำ
- งานใช้ Idempotency-Key และ revision แผนสอบต้องเปิดใช้ก่อนสร้างเตือน การเตือนต้อง opt-in ตรวจ revision เวลาเงียบ และสิทธิ์ก่อนส่ง
- LIFF มีหน้าถาม งาน ฝึก แผน ความก้าวหน้า เอกสาร ตั้งค่า และหน้าครูจัดเอกสาร/ตรวจรับ ส่งออก JSON ที่ระบุรายการยังไม่ผ่านได้
- ทะเบียนหลักฐาน T01–T12, backup/restore, โรงเรียน คู่มือ และ load test พร้อม catalog AI 80 กรณี ไม่เติมคะแนนผ่านจำลอง รายงานตรวจว่าครูอย่างน้อยสองคนตรวจแต่ละกรณี

## เริ่มพัฒนา

ใช้ Python 3.12, Node.js 22 และ PostgreSQL ที่ติดตั้ง extension `vector` ได้ เก็บ `.env` จาก `.env.example` โดยใส่ secrets เฉพาะเครื่องหรือ Railway Variables

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m db.migrate
.venv/bin/python main.py
```

อีก terminal:

```bash
.venv/bin/python -m worker.run
```

สำหรับการทดสอบไฟล์ในเครื่องใช้ `STORAGE_BACKEND=local` และไดเรกทอรีที่เขียนได้ อย่าใช้ `/tmp` เป็นที่เก็บ production

LIFF ใช้ `liff/.env.example` เป็นรายการค่าที่ต้องกำหนด:

```bash
npm --prefix liff ci
npm --prefix liff run dev
```

ตั้ง `NEXT_PUBLIC_API_URL` เป็น HTTPS API ที่มือถือเข้าถึงได้ ตั้ง LIFF Endpoint URL และ `openid` scope ใน LINE Login channel ให้ Login channel และ Messaging API channel อยู่ใต้ Provider เดียวกัน ดู [LINE token verification](https://developers.line.biz/en/reference/line-login/#verify-id-token)

เปิด `/login` เพื่อยืนยันบัญชี จากนั้นเข้าหน้าหลัก `/` Session ฝั่ง browser อยู่ในหน่วยความจำ เมื่อ reload จะตรวจ LINE token ใหม่ ไม่มี bearer token ใน localStorage

## เพิ่มโรงเรียนและสมาชิกโดยผู้ดูแล

ผู้ใช้ต้อง Login จริงก่อน นำ UUID จาก `/me` ไปให้ผู้ดูแลที่มีสิทธิ์เข้าฐานข้อมูล ใช้ CLI นี้ในสภาพแวดล้อมที่ถูกต้อง ไม่มี public API ให้เลือกเป็นครูเอง

```bash
.venv/bin/python manage.py bootstrap --teacher-user-id USER_UUID --school 'ชื่อโรงเรียน' --course 'ความสัมพันธ์และฟังก์ชัน'
.venv/bin/python manage.py add-member --user-id STUDENT_UUID --course-id COURSE_UUID --role student
```

หน้าเว็บแสดง UUID บัญชีในส่วนตั้งค่า หลังเพิ่มสมาชิกให้ reload หน้าเว็บ

## Railway

1. เปิดให้บริการ Railway กลับมาออนไลน์ก่อน จากหน้าที่อ่านได้เมื่อ 18 ตุลาคม 2569 โปรเจกต์แสดง Trial expired และ API/Postgres ออฟไลน์ โค้ดรอบนี้ไม่ได้เปลี่ยนแพ็กเกจหรือ deploy ขึ้น production
2. PostgreSQL ต้องรองรับ `CREATE EXTENSION vector` หาก image เดิมไม่มี pgvector ต้องเลือก image/template ที่มี extension ก่อน ทดสอบสำรองและ restore ก่อนย้ายฐานเดิม
3. API ใช้ root ของ repository และ Dockerfile ที่ root Startup เรียก `python -m db.migrate` ก่อน uvicorn `/health` ตรวจการเชื่อมต่อ SQL
4. ตั้ง `DATABASE_URL` เป็น variable reference ของ Postgres และค่า LINE ตาม `.env.example` ตั้ง CORS เป็น origin ของ LIFF จริง ไม่ใส่ path
5. Bucket `adaptable-folder`: ตั้ง `STORAGE_BACKEND=s3` และ map `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` จาก Credentials/Variable References ของ bucket ใช้ `S3_ADDRESSING_STYLE=virtual` เว้นแต่ Credentials ของ bucket เดิมระบุ path-style ห้ามเปิด bucket เป็น public
6. เพิ่ม worker จาก repository/image เดียวกัน ใช้ start command `python -m worker.run` และ Variables ชุดเดียวกับ API **ปิด HTTP healthcheck ของ worker** หากสืบทอด `railway.toml` ใช้ Settings override ให้ worker ไม่มี healthcheck `/health` Worker รวม scheduler และ outbox sender แล้ว ไม่ต้องเพิ่ม cron ที่ส่งซ้ำ
7. LIFF แยก service ใช้ Root Directory `liff` กับ Dockerfile ในโฟลเดอร์นั้น ใส่ `NEXT_PUBLIC_LIFF_ID` และ `NEXT_PUBLIC_API_URL` เป็น build variables ก่อน build ค่าเหล่านี้ไม่ใช่ secrets
8. เริ่ม `AI_ENABLED=false` จนมีเอกสารสอนที่ครูอนุมัติ เมื่อเปิด AI ให้ตั้ง `LLM_API_KEY`, ตรวจรุ่นโมเดล/ราคา และงบจริง `MAX_DAILY_AI_REQUESTS` จำกัดจำนวนคำขอต่อผู้ใช้ ไม่ใช่การรับประกันเพดานค่าเงิน

`db.migrate` เปิด extension ก่อน migration แรกเพื่อรองรับ vector column ไม่แก้ migration ที่สร้างอัตโนมัติเดิม หากมีข้อมูลสมาชิกข้ามโรงเรียนอยู่แล้ว migration ใหม่จะปฏิเสธ ต้องแก้ข้อมูลตามหลักฐานก่อน deploy

## ขั้นตอนตรวจรับเอกสาร

1. ครูอัปโหลด roadmap และแบบฟอร์มเป็น `evidence` ส่วนเอกสารบทเรียนที่มีสิทธิ์ใช้ให้อัปโหลดเป็น `teaching` ไม่ถือไฟล์โครงการเป็นแหล่งเฉลย
2. รอ worker ให้สถานะ `review` กดรีเฟรช ตรวจต้นฉบับกับข้อความ สมการ ตาราง และเลขหน้า DOCX ไม่มีเลขหน้าจริงที่เชื่อถือได้ ต้องให้ครูระบุหน้าเอง PDF สแกนที่ไม่มี text จะเข้าสู่ failed และต้องใช้ไฟล์ข้อความหรือ OCR ที่ตรวจแล้ว
3. บันทึก checklist ทั้งหมด พร้อม scope `prototype` หรือ `pilot` เฉพาะอนุมัติ `pilot` จึงค้นเป็นเนื้อหาสำหรับนักเรียนได้ การอนุมัติเนื้อหาไม่ถือเป็นการอนุญาตเริ่มทดลอง
4. สร้างโจทย์ร่าง ใส่เฉลย คำใบ้ และเหตุผล แล้วครูรับรองแต่ละข้อ โจทย์ที่เผยแพร่เป็น immutable ให้สร้างข้อ/รุ่นใหม่เพื่อแก้เนื้อหา
5. บันทึก T01–T12 พร้อม commit, expected/actual และไฟล์หลักฐาน แต่ละผลเป็น record ใหม่ ไม่เขียนทับประวัติเดิม
6. ประเมิน AI 80 กรณี ใช้ run UUID เดียวกันสำหรับครูสองคน rubric 0–3 ตาม PDF แยกจาก rubric 0–2 ของแบบตรวจเนื้อหา Word บันทึกข้อผิดพลาดวิกฤตทุกครั้ง
7. ส่งออก JSON จากหน้าตรวจรับ โดยระบุ build reference และ run UUID รายงานยังเป็น `not_ready` เมื่อหลักฐานไม่ครบหรือไม่ผ่าน แม้ครบก็รอการตัดสินโรงเรียน

นำเข้าไฟล์จากเครื่องผู้ดูแลได้ด้วย CLI (อัปโหลดไป bucket ที่ตั้งค่าไว้ ไม่อนุมัติเอง):

```bash
.venv/bin/python manage.py import-document --user-id TEACHER_UUID --course-id COURSE_UUID --file '/path/to/roadmap.pdf' --title 'ข้อกำหนดโครงการ' --purpose evidence
```

ไฟล์ต้นฉบับที่ให้มายังไม่ถูกอัปโหลดไป Railway เนื่องจากบริการออฟไลน์ และไม่มีการอนุมัติเนื้อหาแทนครู `RelFnc.pdf` ที่แบบฟอร์มอ้างถึงไม่ได้แนบมาด้วย

## ทดสอบ

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
npm --prefix liff run lint
node liff/node_modules/typescript/bin/tsc --project liff/tsconfig.json --noEmit --incremental false
npm --prefix liff run build -- --webpack
```

pytest สร้าง PostgreSQL/pgvector ชั่วคราวด้วย pgserver และ **แทน DATABASE_URL ก่อน import แอป** ไม่แตะฐาน Railway การทดสอบ LINE/AI/S3 ใช้ stub ไม่ส่งข้อความจริง จำนวนกรณี automated tests ไม่ใช่ผลประเมิน AI 80 กรณีโดยครู

## ข้อจำกัดที่ต้องตรวจจริงก่อนนำร่อง

- ยังไม่ทดสอบ OAuth, S3 Bucket, Gemini และ LINE Push กับบัญชีจริงหรือโหลด 30 ผู้ใช้บน Railway ไม่ใช้ผล mock แทนหลักฐานเหล่านี้
- Exact lexical retrieval เป็นฐานเริ่มต้น ยังไม่มี embedding/vector ranking, OCR, การรับภาพโจทย์ หรือผู้ให้บริการ LLM ตัวที่สอง
- ไม่เปิด AI tool calling ที่เขียนงาน/แผน การสร้างรายการใช้แบบฟอร์มและ API ที่ตรวจสิทธิ์ อาจเพิ่ม orchestration ภายหลังโดยใช้บริการเดียวกัน
- ช่องทาง LINE ใช้ asynchronous Push จาก outbox ไม่มี Reply รับเรื่องทันที จึงต้องวัดเวลาและโควตา Push จริง
- ยังไม่มีระบบคำเชิญด้วยตนเอง Rich Menu provisioning หรือการศึกษาคะแนนก่อน/หลังและติดตามผล ใช้ operator CLI เพิ่มสมาชิกที่ยืนยันตัวตนแล้ว
- Ingress rate limit อยู่ต่อ process ต้องเสริม limit ส่วนกลางเมื่อเพิ่มหลาย API replicas การกัน event/task/submission ซ้ำอยู่ที่ PostgreSQL
- ลบข้อมูลส่วนตัวจาก live database และเก็บ tombstone สำหรับ restore เอกสารรายวิชาและหลักฐานโรงเรียนเป็นระเบียนสถาบัน ต้องกำหนดอายุเก็บและผู้รับผิดชอบร่วมกับโรงเรียน ยังไม่มีงานลบตามอายุอัตโนมัติหรือระบบ backup ของผู้ให้บริการที่ provision ให้
- ดูขั้นตอนกู้คืนและบังคับรายการลบซ้ำใน `OPERATIONS.md` เป้าหมาย RPO/RTO และผลการเรียนรู้ต้องวัดจริง
