# LINE Learning — ผู้ช่วยเรียนหลายวิชา

ระบบ FastAPI + PostgreSQL/pgvector + LIFF รองรับการตั้งรายวิชาได้อิสระ เช่น คณิตศาสตร์ วิทยาศาสตร์ ภาษา สังคมศึกษา และศิลปะ โดยครูกำหนดขอบเขต หัวข้อ ภาษา และเอกสารประจำวิชา เก็บเอกสารต้นฉบับใน private S3 bucket และเก็บรุ่น checksum ผู้อนุมัติ ผลตรวจ และหลักฐานใน SQL

ในโปรเจกต์ Railway ที่ให้มา `adaptable-folder` คือ **ชื่อแสดงผลของ Railway Bucket** ไม่ใช่บริการ Adaptable แยกต่างหาก ตั้งค่า S3 ด้วยชื่อ bucket จริงจากหน้า Credentials ซึ่งอาจมี suffix เพิ่มจากชื่อแสดงผล ตาม [เอกสาร Railway](https://docs.railway.com/storage-buckets)

## สิ่งที่ใช้งานได้ในโค้ด

- ตรวจ LINE ID token กับ LINE ก่อนสร้าง opaque bearer session เก็บเฉพาะ hash ของ session token ในฐานข้อมูล ไม่ print token บทบาทมาจากสมาชิกโรงเรียนและรายวิชาที่ผู้ดูแลเพิ่ม
- รับ signed raw webhook ที่ `/webhook` และ `/webhooks/line` บันทึก event + job ในธุรกรรมเดียว และกัน event ซ้ำด้วย UNIQUE
- SQL worker มี lease, retry, stale-worker fencing และจัดลำดับงานรายผู้ใช้ บันทึกคำตอบกับ outbox ในธุรกรรมเดียว Push ใช้ retry key เดิม สถานะ `accepted` หมายถึง LINE API รับ ไม่ใช่ส่งถึงหรืออ่านแล้ว
- อัปโหลด PDF, DOCX, TXT สูงสุด 10 MB สกัดข้อความใน worker แบ่ง chunk แบบคงขอบเขตย่อหน้า/หน้า เก็บ checksum และคำเตือนหน้าสกัดไม่ได้ เอกสารสอนจะพร้อมค้นอัตโนมัติเมื่อสกัดสำเร็จ (ไม่ต้องอนุมัติ PDF) ครูยังแก้ข้อความ/เลขหน้าและถอนรุ่นได้
- แยกเอกสาร `teaching` กับ `evidence` และจัดชนิดสื่อ `lesson`, `textbook`, `worksheet`, `solution`, `slides`, `reference` พร้อม topic_id เฉพาะในรายวิชา ค้นด้วย Thai lexical + character grams เสริม Vector Gemini 768 มิติแบบ opt-in (`EMBEDDINGS_ENABLED=true`) และ fallback เป็น lexical เมื่อ Vector API มีปัญหา
- Gemini adapter มี schema ตรวจ citation กับ chunk ที่ส่งจริง จำกัดเวลาและ output เก็บ model/prompt version กับ usage ไม่เปิดเครื่องมือเขียนข้อมูลให้โมเดล
- แบบฝึก 6 รูปแบบ: ปรนัย จริง/เท็จ ตัวเลขพร้อม tolerance/หน่วย คำตอบสั้นตามรายการ เซตจำนวนเต็ม และคำตอบอธิบายที่ครูตรวจ ไม่ใช้ `eval` ผูกกับรุ่นโจทย์ ไม่เปิดเฉลยก่อนส่ง และกัน submission ซ้ำ
- คำตอบอธิบายเป็น `pending_review` ไม่นับเป็นถูก/ผิดหรือจำนวนฝึกอิสระที่ตรวจแล้ว ครูในวิชาให้คะแนน 0–100 พร้อมข้อเสนอแนะ ห้ามตรวจของตัวเอง ผู้เรียนดูผลล่าสุดในหน้าความก้าวหน้า
- งานใช้ Idempotency-Key และ revision แผนสอบต้องเปิดใช้ก่อนสร้างเตือน การเตือนต้อง opt-in ตรวจ revision เวลาเงียบ และสิทธิ์ก่อนส่ง
- LIFF เป็นเว็บจัดการการเรียน ไม่เปิดช่องถาม AI บนเว็บอีกต่อไป: หน้าแรก → การเรียน (ฝึกโจทย์/ผลเรียน/เอกสาร) → งานและแผน → ตั้งค่า; ครูมีเมนูสำหรับครูที่แยกอัปโหลดไฟล์/ตรวจไฟล์/สร้างโจทย์ และตรวจคำตอบ/หัวข้อ/ตั้งวิชา พร้อมเมนูตรวจรับที่แยกขั้นตอน; AI ตอบใน LINE Chat เท่านั้น
- ทะเบียนหลักฐาน T01–T12, backup/restore, โรงเรียน คู่มือ และ load test พร้อมชุดประเมิน AI 80 กรณีต่อรายวิชา ไม่เติมคะแนนผ่านจำลอง รายงานตรวจว่าครูอย่างน้อยสองคนตรวจแต่ละกรณี

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
.venv/bin/python manage.py bootstrap --teacher-user-id USER_UUID --school 'ชื่อโรงเรียน' --course 'วิทยาศาสตร์ ม.4' --subject 'วิทยาศาสตร์' --scope 'แรงและการเคลื่อนที่' --topic 'แรง' --topic 'การเคลื่อนที่'
.venv/bin/python manage.py add-member --user-id STUDENT_UUID --course-id COURSE_UUID --role student
```

หน้าเว็บแสดง UUID บัญชีในส่วนตั้งค่า หลังเพิ่มสมาชิกให้ reload หน้าเว็บ

## ตั้งรายวิชาและใช้ผ่าน LINE

1. ครูที่มีสิทธิ์เดิมเปิด LIFF → **จัดการวิชา / ตรวจคำตอบ** ตั้งชื่อ วิชา ระดับชั้น ขอบเขต และภาษาที่ตอบ เพิ่มวิชาอื่นในโรงเรียนเดิมได้จากหน้านี้ บทบาทครูยังมาจากผู้ดูแล
2. เพิ่มหัวข้อและคำค้น/คำเรียกอื่น เช่น `แรง, force` ไม่มีการสร้างหัวข้อคณิตศาสตร์ตายตัวในวิชาใหม่ CLI ใช้ `--topic` ซ้ำได้ และ `--language` เพื่อเลือกภาษา
3. อัปโหลดเอกสารสอนแล้วใช้ค้นได้เมื่อสกัดสำเร็จ; การรับรองโจทย์/เฉลยยังเป็นกระบวนการแยกต่างหาก ทุกวิชาใช้ LINE channels, API/worker, SQL และ private bucket เดิม แยกการเข้าถึงด้วย course membership
4. นักเรียนเลือกรายวิชาใน LIFF สำหรับถาม/ฝึก แล้วกด **ใช้วิชานี้ในแชต LINE** ข้อความ LINE ถัดไปจะผูกวิชานี้ตั้งแต่รับ webhook การเปลี่ยนวิชาภายหลังไม่ย้ายคำถามที่เข้าคิวแล้ว ผู้ที่มีหลายวิชาแต่ยังไม่เลือกจะได้รับข้อความให้เลือกผ่าน LIFF
5. AI รับขอบเขตและหัวข้อของรายวิชา พร้อมหลักฐานที่อนุมัติของวิชานั้นเท่านั้น ถ้าไม่มีหลักฐานให้ถามเพิ่ม ระบบไม่ได้มีเนื้อหาครบทุกวิชามาให้และไม่ได้รับรองความถูกต้องทุกวิชาโดยอัตโนมัติ
6. คำตอบตัวเลขกรอกเฉพาะตัวเลขในหน่วยที่โจทย์กำหนด รองรับทศนิยม/เลขยกกำลังฐานสิบ ไม่แปลงหน่วยหรือแก้สมการทั่วไป คำตอบสั้นเทียบรายการหลังปรับ Unicode/ช่องว่าง เลือกแยกตัวพิมพ์ได้ งานวิเคราะห์หรือประเมินทักษะใช้ครูตรวจ

## อัปเกรดฐานข้อมูลเดิม

Migration ใหม่ `20261021_multisubject` เพิ่มข้อมูลในตารางเดิม ไม่เปลี่ยน bucket หรือย้ายไฟล์ ไม่แก้ migration generated เดิม สำรองก่อนอัปเกรด แล้วหยุด worker เดิม รัน `python -m db.migrate` ให้สำเร็จก่อนเริ่ม API/worker/LIFF รุ่นใหม่ร่วมกัน

รายวิชาที่มีอยู่ก่อนอัปเกรดยังคงขอบเขตคณิตศาสตร์และชุดประเมินเดิม (`relations-pilot`) เอกสาร โจทย์ และสมาชิกยังอยู่ครบ วิชาใหม่ใช้ `general` ครูเปลี่ยนรายวิชาเดิมได้จากเมนูจัดการวิชา เมื่อเปลี่ยนขอบเขตหรือหัวข้อจะเริ่มชุดประเมินใหม่และเพิ่ม revision ผลเก่ายังเก็บแต่ใช้ยืนยันรุ่นใหม่ไม่ได้ การ downgrade จะลบ metadata ใหม่ จึงใช้ backup เมื่อต้องกู้กลับ

## Railway

1. เปิดให้บริการ Railway กลับมาออนไลน์ก่อน จากหน้าที่อ่านได้เมื่อ 18 ตุลาคม 2569 โปรเจกต์แสดง Trial expired และ API/Postgres ออฟไลน์ โค้ดรอบนี้ไม่ได้เปลี่ยนแพ็กเกจหรือ deploy ขึ้น production
2. PostgreSQL ต้องรองรับ `CREATE EXTENSION vector` หาก image เดิมไม่มี pgvector ต้องเลือก image/template ที่มี extension ก่อน ทดสอบสำรองและ restore ก่อนย้ายฐานเดิม
3. API ใช้ root ของ repository และ Dockerfile ที่ root Startup เรียก `python -m db.migrate` ก่อน uvicorn `/health` ตรวจการเชื่อมต่อ SQL
4. ตั้ง `DATABASE_URL` เป็น variable reference ของ Postgres และค่า LINE ตาม `.env.example` ตั้ง CORS เป็น origin ของ LIFF จริง ไม่ใส่ path
5. Bucket `adaptable-folder`: ตั้ง `STORAGE_BACKEND=s3` และ map `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` จาก Credentials/Variable References ของ bucket ใช้ `S3_ADDRESSING_STYLE=virtual` เว้นแต่ Credentials ของ bucket เดิมระบุ path-style ห้ามเปิด bucket เป็น public
6. เพิ่ม worker จาก repository/image เดียวกัน ใช้ start command `python -m worker.run` และ Variables ชุดเดียวกับ API **ปิด HTTP healthcheck ของ worker** หากสืบทอด `railway.toml` ใช้ Settings override ให้ worker ไม่มี healthcheck `/health` Worker รวม scheduler และ outbox sender แล้ว ไม่ต้องเพิ่ม cron ที่ส่งซ้ำ
7. LIFF แยก service ใช้ Root Directory `liff` กับ Dockerfile ในโฟลเดอร์นั้น ใส่ `NEXT_PUBLIC_LIFF_ID` และ `NEXT_PUBLIC_API_URL` เป็น build variables ก่อน build ค่าเหล่านี้ไม่ใช่ secrets
8. เริ่ม `AI_ENABLED=false` จนมีเอกสารสอนที่ตรวจความถูกต้องและสิทธิ์แล้ว เมื่อเปิด AI ให้ตั้ง `LLM_API_KEY`, ตรวจรุ่นโมเดล/ราคา และงบจริง `MAX_DAILY_AI_REQUESTS` จำกัดจำนวนคำขอต่อผู้ใช้ ไม่ใช่การรับประกันเพดานค่าเงิน

`db.migrate` เปิด extension ก่อน migration แรกเพื่อรองรับ vector column ไม่แก้ migration ที่สร้างอัตโนมัติเดิม หากมีข้อมูลสมาชิกข้ามโรงเรียนอยู่แล้ว migration ใหม่จะปฏิเสธ ต้องแก้ข้อมูลตามหลักฐานก่อน deploy

## ขั้นตอนตรวจรับเอกสาร

1. ครูอัปโหลด roadmap และแบบฟอร์มเป็น `evidence` ส่วนเอกสารบทเรียนที่มีสิทธิ์ใช้ให้อัปโหลดเป็น `teaching` ไม่ถือไฟล์โครงการเป็นแหล่งเฉลย
2. รอ worker ให้สถานะ `published` (สำหรับ `teaching`) แล้วตรวจต้นฉบับกับข้อความ สมการ ตาราง และเลขหน้า DOCX/TXT ไม่มีเลขหน้าจริงที่เชื่อถือได้ PDF ที่มีบางหน้าเป็นภาพสแกนจะแสดงคำเตือน; หากไม่มีข้อความสกัดได้เลยจะเป็น `failed` และต้องใช้ OCR ภายนอกหรือไฟล์ข้อความ
3. เอกสาร `teaching` ที่สกัดสำเร็จค้นได้ทันที โดยไม่ต้องกรอก checklist หรือ rubric อนุมัติ PDF; โปรดตรวจสิทธิ์การใช้ไฟล์และความถูกต้องก่อนอัปโหลด การตรวจรับระบบสำหรับนำร่องยังคงเป็นขั้นตอนแยกกัน
4. สร้างโจทย์ร่าง ใส่เฉลย คำใบ้ และเหตุผล แล้วครูรับรองแต่ละข้อ โจทย์ที่เผยแพร่เป็น immutable ให้สร้างข้อ/รุ่นใหม่เพื่อแก้เนื้อหา
5. บันทึก T01–T12 พร้อม commit, expected/actual และไฟล์หลักฐาน แต่ละผลเป็น record ใหม่ ไม่เขียนทับประวัติเดิม
6. ในวิชาใหม่ ให้ครูจัดโจทย์ ผลคาดหวัง และเงื่อนไขผิดพลาดให้ตรงวิชาครบ 80 กรณีผ่านหน้าหลักฐานตรวจรับก่อน แล้วประเมิน AI โดยใช้ run UUID เดียวกันสำหรับครูสองคน rubric 0–3 ตาม PDF แยกจาก rubric 0–2 ของแบบตรวจเนื้อหา Word บันทึกข้อผิดพลาดวิกฤตทุกครั้ง การแก้กรณีทดสอบเพิ่ม course revision และต้องใช้รอบประเมินใหม่ ห้ามรวมผลต่าง revision ในรอบเดียว
7. ส่งออก JSON จากหน้าตรวจรับ โดยระบุ build reference และ run UUID รายงานยังเป็น `not_ready` เมื่อหลักฐานไม่ครบหรือไม่ผ่าน แม้ครบก็รอการตัดสินโรงเรียน

นำเข้าไฟล์จากเครื่องผู้ดูแลได้ด้วย CLI (อัปโหลดไป bucket ที่ตั้งค่าไว้ ไม่อนุมัติเอง):

```bash
.venv/bin/python manage.py import-document --user-id TEACHER_UUID --course-id COURSE_UUID --file '/path/to/roadmap.pdf' --title 'ข้อกำหนดโครงการ' --purpose evidence
```

ไฟล์ต้นฉบับที่ให้มายังไม่ถูกอัปโหลดไป Railway เนื่องจากบริการออฟไลน์ และไม่มีการอนุมัติเนื้อหาแทนครู `RelFnc.pdf` ที่แบบฟอร์มอ้างถึงไม่ได้แนบมาด้วย

## ตรวจคุณภาพและ build ฝั่ง LIFF

```bash
npm --prefix liff run lint
node liff/node_modules/typescript/bin/tsc --project liff/tsconfig.json --noEmit --incremental false
npm --prefix liff run build -- --webpack
```

## ข้อจำกัดที่ต้องตรวจจริงก่อนนำร่อง

- ยังไม่ทดสอบ OAuth, S3 Bucket, Gemini และ LINE Push กับบัญชีจริงหรือโหลด 30 ผู้ใช้บน Railway ไม่ใช้ผล mock แทนหลักฐานเหล่านี้
- Thai lexical retrieval เป็นฐานเริ่มต้น และรองรับ Vector ranking แบบเลือกเปิด ยังไม่มี OCR ใน Worker, การรับภาพโจทย์ หรือผู้ให้บริการ LLM ตัวที่สอง
- ไม่เปิด AI tool calling ที่เขียนงาน/แผน การสร้างรายการใช้แบบฟอร์มและ API ที่ตรวจสิทธิ์ อาจเพิ่ม orchestration ภายหลังโดยใช้บริการเดียวกัน
- ช่องทาง LINE ใช้ asynchronous Push จาก outbox ไม่มี Reply รับเรื่องทันที จึงต้องวัดเวลาและโควตา Push จริง
- ยังไม่มีระบบคำเชิญด้วยตนเอง Rich Menu provisioning หรือการศึกษาคะแนนก่อน/หลังและติดตามผล ใช้ operator CLI เพิ่มสมาชิกที่ยืนยันตัวตนแล้ว
- Ingress rate limit อยู่ต่อ process ต้องเสริม limit ส่วนกลางเมื่อเพิ่มหลาย API replicas การกัน event/task/submission ซ้ำอยู่ที่ PostgreSQL
- ลบข้อมูลส่วนตัวจาก live database และเก็บ tombstone สำหรับ restore เอกสารรายวิชาและหลักฐานโรงเรียนเป็นระเบียนสถาบัน ต้องกำหนดอายุเก็บและผู้รับผิดชอบร่วมกับโรงเรียน ยังไม่มีงานลบตามอายุอัตโนมัติหรือระบบ backup ของผู้ให้บริการที่ provision ให้
- ดูขั้นตอนกู้คืนและบังคับรายการลบซ้ำใน `OPERATIONS.md` เป้าหมาย RPO/RTO และผลการเรียนรู้ต้องวัดจริง

## API ที่เพิ่มสำหรับหลายวิชา

- `POST /courses`, `GET/PUT /courses/{id}`: ครูสร้างในโรงเรียนที่มีสิทธิ์และกำหนดขอบเขต การแก้ต้องส่ง `expected_revision`
- `POST /courses/{id}/topics`, `PUT /courses/{id}/topics/{topic_id}`: ชื่อหัวข้อ คำค้น และ expected revision ของรายวิชา
- `PUT /me/active-course`: `{ "course_id": "UUID" }` เลือกวิชาสำหรับ LINE; `/me` คืน `active_course_id`
- `GET /practice/results?course_id=...`: ผลฝึกและข้อเสนอแนะของตนเอง 100 รายการล่าสุด
- `GET /courses/{id}/reviews`, `POST /courses/{id}/reviews/{attempt_id}`: คิวครูตรวจ 100 รายการแรก; ส่ง `score` ช่วง 0–1 และ `feedback` บันทึกได้ครั้งเดียว หน้าครูแสดงคะแนนเต็ม 100
- `GET /evaluation/cases?course_id=...`: ครูอ่านชุดประเมินและ `course_revision`; `PUT /courses/{id}/evaluation-cases/{case_id}` ส่ง `input`, `expected`, `failure`, `expected_revision`
- การบันทึก `/courses/{id}/evaluations` ต้องเพิ่ม `expected_course_revision`; รายงานส่งออกแนบชุดทดสอบ ขอบเขตและ revision ด้วย ผลเก่าไม่ถูกลบ


## Course knowledge pipeline (2026-10-28)

- อัปโหลด `purpose=teaching` พร้อม `material_type` (lesson/textbook/worksheet/solution/slides/reference), `topic_id` (ถ้ามี) และไฟล์ PDF/DOCX/TXT. รายการ `evidence` ไม่ถูกค้นโดย AI
- Worker สกัดข้อความตามหน้า ตัด chunk โดยให้ความสำคัญกับการขึ้นย่อหน้า/บรรทัดและเก็บ `page_no`, `chunk_id`, `version_id`. หน้าที่ไม่มีข้อความจะแจ้ง `extraction_warning` และยังไม่มี OCR อัตโนมัติ
- งาน Gemini ตรวจคำตอบ JSON กับ schema และ citation UUID ที่ส่งให้จริง ลองซ่อมคำตอบ 1 ครั้ง และแสดงข้อความข้อจำกัดหากตรวจไม่ผ่าน (ไม่แต่งอ้างอิง)
- เปิด embedding เพิ่มได้ด้วย `EMBEDDINGS_ENABLED=true` และ `EMBEDDING_MODEL=gemini-embedding-001` (ต้องมี `LLM_API_KEY` และมีค่าใช้จ่าย API เพิ่ม). Worker สร้าง Vector 768 มิติโดยแบ่งงานย่อย 8 chunks/Job; การค้นจะผสม vector similarity กับ lexical search. ค่าเริ่มต้น **ปิด** เพื่อไม่เพิ่มค่าใช้จ่ายหรือทำให้ระบบเดิมสะดุด
- สำหรับเอกสารเก่า ครูเปิดเอกสารแล้วกด **สร้าง/อัปเดต Vector ของไฟล์นี้** เพื่อเรียก `POST /documents/versions/{version_id}/index`. ต้องเปิด `EMBEDDINGS_ENABLED=true` ให้ทั้ง API และ Worker ก่อน; กดซ้ำระหว่างมีงานค้างจะถูกปฏิเสธ
- เนื้อหาทุกประเภทต้องตรวจสิทธิ์ตามโรงเรียนและรายวิชา. ไฟล์ต้นฉบับอยู่ใน Private Object Storage ไม่ได้ส่ง URL สาธารณะให้ Gemini
- หลัง deploy migration `20261028_course_materials` ให้ตรวจ API/Worker/LIFF และทดลองถามจริงด้วย PDF ที่มีข้อความ; การอัปโหลดเอกสารที่มีลิขสิทธิ์ต้องมีสิทธิ์ใช้งาน

## การใช้งาน LIFF หลังปรับเมนู (28 ตุลาคม 2569)

1. นักเรียนเข้าสู่ระบบ เลือกรายวิชา กด **ใช้วิชานี้ในแชต LINE** แล้วกลับไปถามบทเรียนใน LINE; ไม่มีกล่องถาม AI ใน LIFF อีกต่อไป และ deep link `?view=ask` เก่าจะเปิดหน้าแรก
2. หมวด **การเรียน** มีฝึกโจทย์ ผลการเรียน และเอกสาร (สำหรับนักเรียน); หมวด **งานและแผน** แยกงานกับแผนอ่านสอบ; ข้อมูลบัญชีทางเทคนิคและการลบประวัติอยู่ในหัวข้อความเป็นส่วนตัวที่กางออกได้
3. หมวด **สำหรับครู** แยกไฟล์และแบบฝึก (อัปโหลด/ดูและแก้ไฟล์/สร้างโจทย์), รายวิชาและตรวจคำตอบ (ตรวจคำตอบ/จัดหัวข้อ/ตั้งค่ารายวิชา), และตรวจรับระบบ (หลักฐาน/กรณีทดสอบ/คะแนน AI/รายงาน)
4. หมวด **ผู้ดูแลระบบ** แยกโรงเรียน, รายวิชา/สมาชิก และบัญชีผู้ใช้ ไม่ปะปนในหน้าเดียว

ระบบรับคำถามจาก LINE Webhook และ Worker ยังคงทำงานตามเดิม UI ครั้งนี้ไม่ใช่การแก้ปัญหา Gemini Citation และไม่ใช่ผลทดสอบ End-to-End ของ LINE
