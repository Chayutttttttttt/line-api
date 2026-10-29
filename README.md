# LINE Learning — ผู้ช่วยเรียนหลายวิชา

ระบบ FastAPI + PostgreSQL/pgvector + LIFF รองรับการตั้งรายวิชาได้อิสระ เช่น คณิตศาสตร์ วิทยาศาสตร์ ภาษา สังคมศึกษา และศิลปะ โดยครูกำหนดขอบเขต หัวข้อ ภาษา และเอกสารประจำวิชา เก็บเอกสารต้นฉบับใน private S3 bucket และเก็บรุ่น checksum ผู้อนุมัติ ผลตรวจ และหลักฐานใน SQL

ในโปรเจกต์ Railway ที่ให้มา `adaptable-folder` คือ **ชื่อแสดงผลของ Railway Bucket** ไม่ใช่บริการ Adaptable แยกต่างหาก ตั้งค่า S3 ด้วยชื่อ bucket จริงจากหน้า Credentials ซึ่งอาจมี suffix เพิ่มจากชื่อแสดงผล ตาม [เอกสาร Railway](https://docs.railway.com/storage-buckets)

## สิ่งที่ใช้งานได้ในโค้ด

- ตรวจ LINE ID token กับ LINE ก่อนสร้าง opaque bearer session เก็บเฉพาะ hash ของ session token ในฐานข้อมูล ไม่ print token บทบาทมาจากสมาชิกโรงเรียนและรายวิชาที่ผู้ดูแลเพิ่ม
- รับ signed raw webhook ที่ `/webhook` และ `/webhooks/line` บันทึก event + job ในธุรกรรมเดียว และกัน event ซ้ำด้วย UNIQUE
- SQL worker มี lease, retry, stale-worker fencing และจัดลำดับงานรายผู้ใช้ บันทึกคำตอบกับ outbox ในธุรกรรมเดียว Push ใช้ retry key เดิม สถานะ `accepted` หมายถึง LINE API รับ ไม่ใช่ส่งถึงหรืออ่านแล้ว
- อัปโหลด PDF, DOCX, TXT สูงสุด 10 MB: PDF แบบสื่อการสอนให้ OpenAI อ่านเป็นรายหน้า (ไม่ใช้ pypdf.extract_text), สร้างข้อความและ Keywords ที่ผูกกับ Chunks/เลขหน้า; DOCX/TXT ยังใช้ Python อ่านข้อความทั่วไป ครูต้องตรวจและอนุมัติ Checklist ก่อนเอกสารสอนเข้าสู่ระบบค้นหา Evidence ไม่ส่ง OpenAI
- แยกเอกสาร `teaching` กับ `evidence` และจัดชนิดสื่อ `lesson`, `textbook`, `worksheet`, `solution`, `slides`, `reference` พร้อม topic_id เฉพาะในรายวิชา ค้นด้วย Thai lexical + character grams เสริม Vector OpenAI 768 มิติแบบ opt-in (`EMBEDDINGS_ENABLED=true`) และ fallback เป็น lexical เมื่อ Vector API มีปัญหา
- OpenAI adapter มี schema ตรวจ citation กับ chunk ที่ส่งจริง จำกัดเวลาและ output เก็บ model/prompt version กับ usage ไม่เปิดเครื่องมือเขียนข้อมูลให้โมเดล
- แบบฝึก 6 รูปแบบ: ปรนัย จริง/เท็จ ตัวเลขพร้อม tolerance/หน่วย คำตอบสั้นตามรายการ เซตจำนวนเต็ม และคำตอบอธิบายที่ครูตรวจ ไม่ใช้ `eval` ผูกกับรุ่นโจทย์ ไม่เปิดเฉลยก่อนส่ง และกัน submission ซ้ำ
- คำตอบอธิบายเป็น `pending_review` ไม่นับเป็นถูก/ผิดหรือจำนวนฝึกอิสระที่ตรวจแล้ว ครูในวิชาให้คะแนน 0–100 พร้อมข้อเสนอแนะ ห้ามตรวจของตัวเอง ผู้เรียนดูผลล่าสุดในหน้าความก้าวหน้า
- งานใช้ Idempotency-Key และ revision แผนสอบต้องเปิดใช้ก่อนสร้างเตือน การเตือนต้อง opt-in ตรวจ revision เวลาเงียบ และสิทธิ์ก่อนส่ง
- LIFF จัดหน้าสำหรับผู้ใช้ทั่วไปเป็นหมวด หน้าแรก / การเรียน (ฝึกโจทย์ ผลเรียน เอกสาร) / งานและแผน / ตั้งค่า; ครูมีเมนูย่อยจัดไฟล์และแบบฝึก รายวิชาและตรวจคำตอบ และการตรวจรับระบบ; ถามบทเรียน AI ผ่านแชต LINE เท่านั้น (ไม่มีฟอร์มบนเว็บ)
- ทะเบียนหลักฐาน T01–T12, backup/restore, โรงเรียน คู่มือ และ load test พร้อมชุดประเมิน AI 80 กรณีต่อรายวิชา ไม่เติมคะแนนผ่านจำลอง รายงานตรวจว่าครูอย่างน้อยสองคนตรวจแต่ละกรณี

## เริ่มพัฒนา

ใช้ Python 3.12, Node.js 22 และ PostgreSQL ที่ติดตั้ง extension `vector` ได้ สร้าง `.env` ในเครื่องเองหรือกำหนด Railway Variables โดยใส่ secrets เฉพาะในสองที่นี้ ดูตัวแปรที่ระบบอ่านใน `config.py` และหัวข้อ OpenAI GPT configuration ด้านล่าง

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

LIFF ต้องกำหนด `NEXT_PUBLIC_LIFF_ID` และ `NEXT_PUBLIC_API_URL` ใน `liff/.env.local` หรือ Railway build variables:

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
ยังไม่ได้ push/deploy หรือเรียก OpenAI ด้วยคีย์จริง และยังไม่ได้ทำ full LIFF buil
## ตั้งรายวิชาและใช้ผ่าน LINE

1. ครูที่มีสิทธิ์เดิมเปิด LIFF → **จัดการวิชา / ตรวจคำตอบ** ตั้งชื่อ วิชา ระดับชั้น ขอบเขต และภาษาที่ตอบ เพิ่มวิชาอื่นในโรงเรียนเดิมได้จากหน้านี้ บทบาทครูยังมาจากผู้ดูแล
2. เพิ่มหัวข้อและคำค้น/คำเรียกอื่น เช่น `แรง, force` ไม่มีการสร้างหัวข้อคณิตศาสตร์ตายตัวในวิชาใหม่ CLI ใช้ `--topic` ซ้ำได้ และ `--language` เพื่อเลือกภาษา
3. อัปโหลด PDF แล้วรอ AI อ่าน จากนั้นครูตรวจข้อความ คำสำคัญ สูตร และเลขหน้ากับต้นฉบับ กด Checklist และอนุมัติเป็น pilot จึงค้นเป็นบทเรียนได้; การรับรองโจทย์ยังแยกต่างหาก ทุกวิชาใช้ LINE channels, API/worker, SQL และ private bucket เดิม แยกการเข้าถึงด้วย course membership
4. นักเรียนเลือกรายวิชาใน LIFF สำหรับฝึกและกำหนดวิชาที่ต้องการใช้ใน LINE แล้วกด **ใช้วิชานี้ในแชต LINE** ข้อความ LINE ถัดไปจะผูกวิชานี้ตั้งแต่รับ webhook การเปลี่ยนวิชาภายหลังไม่ย้ายคำถามที่เข้าคิวแล้ว ผู้ที่มีหลายวิชาแต่ยังไม่เลือกจะได้รับข้อความให้เลือกผ่าน LIFF
5. AI รับขอบเขตและหัวข้อของรายวิชา พร้อมหลักฐานที่อนุมัติของวิชานั้นเท่านั้น ถ้าไม่มีหลักฐานให้ถามเพิ่ม ระบบไม่ได้มีเนื้อหาครบทุกวิชามาให้และไม่ได้รับรองความถูกต้องทุกวิชาโดยอัตโนมัติ
6. คำตอบตัวเลขกรอกเฉพาะตัวเลขในหน่วยที่โจทย์กำหนด รองรับทศนิยม/เลขยกกำลังฐานสิบ ไม่แปลงหน่วยหรือแก้สมการทั่วไป คำตอบสั้นเทียบรายการหลังปรับ Unicode/ช่องว่าง เลือกแยกตัวพิมพ์ได้ งานวิเคราะห์หรือประเมินทักษะใช้ครูตรวจ

## อัปเกรดฐานข้อมูลเดิม

Migration ใหม่ `20261021_multisubject` เพิ่มข้อมูลในตารางเดิม ไม่เปลี่ยน bucket หรือย้ายไฟล์ ไม่แก้ migration generated เดิม สำรองก่อนอัปเกรด แล้วหยุด worker เดิม รัน `python -m db.migrate` ให้สำเร็จก่อนเริ่ม API/worker/LIFF รุ่นใหม่ร่วมกัน

รายวิชาที่มีอยู่ก่อนอัปเกรดยังคงขอบเขตคณิตศาสตร์และชุดประเมินเดิม (`relations-pilot`) เอกสาร โจทย์ และสมาชิกยังอยู่ครบ วิชาใหม่ใช้ `general` ครูเปลี่ยนรายวิชาเดิมได้จากเมนูจัดการวิชา เมื่อเปลี่ยนขอบเขตหรือหัวข้อจะเริ่มชุดประเมินใหม่และเพิ่ม revision ผลเก่ายังเก็บแต่ใช้ยืนยันรุ่นใหม่ไม่ได้ การ downgrade จะลบ metadata ใหม่ จึงใช้ backup เมื่อต้องกู้กลับ

## Railway

1. เปิดให้บริการ Railway กลับมาออนไลน์ก่อน จากหน้าที่อ่านได้เมื่อ 18 ตุลาคม 2569 โปรเจกต์แสดง Trial expired และ API/Postgres ออฟไลน์ โค้ดรอบนี้ไม่ได้เปลี่ยนแพ็กเกจหรือ deploy ขึ้น production
2. PostgreSQL ต้องรองรับ `CREATE EXTENSION vector` หาก image เดิมไม่มี pgvector ต้องเลือก image/template ที่มี extension ก่อน ทดสอบสำรองและ restore ก่อนย้ายฐานเดิม
3. API ใช้ root ของ repository และ Dockerfile ที่ root Startup เรียก `python -m db.migrate` ก่อน uvicorn `/health` ตรวจการเชื่อมต่อ SQL
4. ตั้ง `DATABASE_URL` เป็น variable reference ของ Postgres และค่า LINE ได้แก่ `CHANNEL_ACCESS_TOKEN`, `CHANNEL_SECRET`, `LINE_CHANNEL_ID`, `LINE_LOGIN_CHANNEL_ID`, `LINE_PROVIDER_ID` ตั้ง CORS เป็น origin ของ LIFF จริง ไม่ใส่ path
5. Bucket `adaptable-folder`: ตั้ง `STORAGE_BACKEND=s3` และ map `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` จาก Credentials/Variable References ของ bucket ใช้ `S3_ADDRESSING_STYLE=virtual` เว้นแต่ Credentials ของ bucket เดิมระบุ path-style ห้ามเปิด bucket เป็น public
6. เพิ่ม worker จาก repository/image เดียวกัน ใช้ start command `python -m worker.run` และ Variables ชุดเดียวกับ API **ปิด HTTP healthcheck ของ worker** หากสืบทอด `railway.toml` ใช้ Settings override ให้ worker ไม่มี healthcheck `/health` Worker รวม scheduler และ outbox sender แล้ว ไม่ต้องเพิ่ม cron ที่ส่งซ้ำ
7. LIFF แยก service ใช้ Root Directory `liff` กับ Dockerfile ในโฟลเดอร์นั้น ใส่ `NEXT_PUBLIC_LIFF_ID` และ `NEXT_PUBLIC_API_URL` เป็น build variables ก่อน build ค่าเหล่านี้ไม่ใช่ secrets
8. เริ่ม `AI_ENABLED=false` จนมีเอกสารสอนที่ตรวจความถูกต้องและสิทธิ์แล้ว เมื่อเปิด AI ให้ตั้ง `LLM_API_KEY`, ตรวจรุ่นโมเดล/ราคา และงบจริง `MAX_DAILY_AI_REQUESTS` จำกัดจำนวนคำขอต่อผู้ใช้ ไม่ใช่การรับประกันเพดานค่าเงิน

`db.migrate` เปิด extension ก่อน migration แรกเพื่อรองรับ vector column ไม่แก้ migration ที่สร้างอัตโนมัติเดิม หากมีข้อมูลสมาชิกข้ามโรงเรียนอยู่แล้ว migration ใหม่จะปฏิเสธ ต้องแก้ข้อมูลตามหลักฐานก่อน deploy

## OpenAI GPT configuration (29 ตุลาคม 2569)

ใช้ OpenAI Python SDK สำหรับทั้งการตอบคำถามและอ่าน PDF ผ่าน Responses API + Structured Outputs:

```dotenv
LLM_API_KEY=<OpenAI API key>
LLM_MODEL=gpt-5.4-mini
PDF_READER_MODEL=gpt-5.4-mini
LLM_MAX_OUTPUT_TOKENS=4096
PDF_MAX_OUTPUT_TOKENS=16384
PDF_AI_MAX_PAGES=40
AI_ENABLED=true
EMBEDDINGS_ENABLED=false
EMBEDDING_MODEL=text-embedding-3-small
```

- ตั้งค่าบน API และ worker ให้ตรงกัน; ไม่ใช้ `GEMINI_API_KEY` แล้ว และต้องเปลี่ยนค่าที่เคยตั้ง `PDF_READER_MODEL`/`EMBEDDING_MODEL` เป็นโมเดล Gemini ด้วย ค่า PDF_READER_MODEL ที่ว่างหรือไม่ได้ตั้งจะใช้ LLM_MODEL
- `AI_ENABLED` เปิด/ปิดการตอบนักเรียนเท่านั้น การอัปโหลด PDF สอนจะเรียก OpenAI แม้ AI_ENABLED=false เพื่อให้ครูตรวจเอกสารก่อนเปิดแชต; evidence ไม่ส่งให้โมเดล
- PDF ส่งเป็น base64 ของไฟล์ชุดละ 2 หน้าโดยไม่สร้างไฟล์ค้างใน OpenAI Files API ใช้ `store=False`; ยังคง semantic sections, topic continuity, 2400-character chunks และ page spans จาก main ล่าสุด
- ไม่ส่ง temperature; output limits รวม reasoning tokens ด้วย การตอบแชตใช้ timeout 30 วินาทีต่อครั้งและซ่อม schema/citation ได้ 1 ครั้ง การอ่าน PDF ใช้ 60 วินาทีต่อชุดและต่ออายุ job lease ก่อนอ่านแต่ละชุด; ปิด SDK retries ให้ worker จัดการข้อผิดพลาดชั่วคราว
- การตอบไม่ครบหรือ refusal จะไม่ถูกแสดงเป็นคำตอบมีหลักฐาน และ PDF ที่อ่านไม่ครบ/ผิด schema จะไม่ถูกบันทึกเป็นเอกสารพร้อมอนุมัติ
- หากเปิด embeddings ใช้ `text-embedding-3-small` พร้อม `dimensions=768` ให้ตรงคอลัมน์เดิม ไม่ต้องเปลี่ยน schema ฐานข้อมูลสำหรับการย้าย provider นี้ การค้นกรอง embedding_model ให้ตรงกับโมเดลปัจจุบันจึงไม่ผสม vector เก่าจาก Gemini; กด **สร้าง/อัปเดต Vector ของไฟล์นี้** เพื่อทำดัชนีเอกสารที่อนุมัติแล้วใหม่
- การอัปเดตจาก checkout เก่าต้องรัน migrations ที่มากับ main ล่าสุดตามขั้นตอนปกติ และใช้ API/worker รุ่นเดียวกัน เอกสารเดิมไม่ถูกอ่านหรือแบ่ง chunks ใหม่อัตโนมัติ

อ้างอิง: [PDF inputs](https://developers.openai.com/api/docs/guides/file-inputs), [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Embedding dimensions](https://developers.openai.com/api/docs/guides/embeddings)

## ขั้นตอนตรวจรับเอกสาร

1. ครูอัปโหลด roadmap และแบบฟอร์มเป็น `evidence` ส่วนเอกสารบทเรียนที่มีสิทธิ์ใช้ให้อัปโหลดเป็น `teaching` ไม่ถือไฟล์โครงการเป็นแหล่งเฉลย
2. รอ Worker อ่านไฟล์ PDF ด้วย OpenAI ให้สถานะ `review` แล้วครูเปิดต้นฉบับเทียบข้อความ สูตร ตาราง คำสำคัญ และเลขหน้า; DOCX/TXT ยังเป็น text parser และไม่มีเลขหน้าจริง PDF ที่อ่านไม่ชัดจะมีคำเตือนให้ตรวจเอง; หาก AI อ่านไม่สำเร็จจะเป็น `failed`
3. เอกสาร `teaching` จะไม่ถูกใช้ตอบ AI ใน LINE จนกว่าครูจะยืนยัน Checklist ทุกข้อและ rubric ทุกด้านผ่าน พร้อมกดอนุมัติจริง (`pilot`) ในหน้า “ดูและแก้ไฟล์”; สิทธิ์เอกสารและความถูกต้องยังต้องให้ครูยืนยัน ไม่ถือว่า OpenAI อ่านถูกทั้งหมด
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

- ยังไม่ทดสอบ OAuth, S3 Bucket, OpenAI และ LINE Push กับบัญชีจริงหรือโหลด 30 ผู้ใช้บน Railway ไม่ใช้ผล mock แทนหลักฐานเหล่านี้
- Thai lexical retrieval ผสม Keywords ที่ OpenAI สร้างแล้วเชื่อมกับ Chunks และรองรับ Vector ranking แบบเลือกเปิด PDF สแกนใช้ความสามารถมองเห็นเอกสารของ OpenAI แต่ยังต้องตรวจผลจริง; ยังไม่มี OCR Python, การรับภาพโจทย์ หรือผู้ให้บริการ LLM ตัวที่สอง
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
- งาน OpenAI ตรวจคำตอบ JSON กับ schema และ citation UUID ที่ส่งให้จริง ลองซ่อมคำตอบ 1 ครั้ง และแสดงข้อความข้อจำกัดหากตรวจไม่ผ่าน (ไม่แต่งอ้างอิง)
- เปิด embedding เพิ่มได้ด้วย `EMBEDDINGS_ENABLED=true` และ `EMBEDDING_MODEL=text-embedding-3-small` (ต้องมี `LLM_API_KEY` และมีค่าใช้จ่าย API เพิ่ม). Worker สร้าง Vector 768 มิติโดยแบ่งงานย่อย 8 chunks/Job; การค้นจะผสม vector similarity กับ lexical search. ค่าเริ่มต้น **ปิด** เพื่อไม่เพิ่มค่าใช้จ่ายหรือทำให้ระบบเดิมสะดุด
- สำหรับเอกสารเก่า ครูเปิดเอกสารแล้วกด **สร้าง/อัปเดต Vector ของไฟล์นี้** เพื่อเรียก `POST /documents/versions/{version_id}/index`. ต้องเปิด `EMBEDDINGS_ENABLED=true` ให้ทั้ง API และ Worker ก่อน; กดซ้ำระหว่างมีงานค้างจะถูกปฏิเสธ
- เนื้อหาทุกประเภทต้องตรวจสิทธิ์ตามโรงเรียนและรายวิชา. ไฟล์ต้นฉบับอยู่ใน Private Object Storage ไม่ได้ส่ง URL สาธารณะให้ OpenAI
- หลัง deploy migration `20261028_course_materials` ให้ตรวจ API/Worker/LIFF และทดลองถามจริงด้วย PDF ที่มีข้อความ; การอัปโหลดเอกสารที่มีลิขสิทธิ์ต้องมีสิทธิ์ใช้งาน


## การใช้งาน LIFF หลังปรับเมนู (28 ตุลาคม 2569)

1. นักเรียนเข้าสู่ระบบ เลือกรายวิชา กด **ใช้วิชานี้ในแชต LINE** แล้วกลับไปถามบทเรียนใน LINE; ไม่มีกล่องถาม AI ใน LIFF อีกต่อไป และ deep link `?view=ask` เก่าจะเปิดหน้าแรก
2. หมวด **การเรียน** มีฝึกโจทย์ ผลการเรียน และเอกสาร (สำหรับนักเรียน); หมวด **งานและแผน** แยกงานกับแผนอ่านสอบ; ข้อมูลบัญชีทางเทคนิคและการลบประวัติอยู่ในหัวข้อความเป็นส่วนตัวที่กางออกได้
3. หมวด **สำหรับครู** แยกไฟล์และแบบฝึก (อัปโหลด/ดูและแก้ไฟล์/สร้างโจทย์), รายวิชาและตรวจคำตอบ (ตรวจคำตอบ/จัดหัวข้อ/ตั้งค่ารายวิชา), และตรวจรับระบบ (หลักฐาน/กรณีทดสอบ/คะแนน AI/รายงาน)
4. หมวด **ผู้ดูแลระบบ** แยกโรงเรียน, รายวิชา/สมาชิก และบัญชีผู้ใช้ ไม่ปะปนในหน้าเดียว

ระบบรับคำถามจาก LINE Webhook และ Worker ยังคงทำงานตามเดิม การปรับ LIFF ไม่ใช่การแก้ปัญหา OpenAI Citation และไม่ใช่ผลทดสอบ End-to-End ของ LINE


## OpenAI PDF reading + teacher review (28 ตุลาคม 2569)

- ครูอัปโหลด PDF สื่อการสอน (ขนาดไม่เกิน 10 MB, เริ่มต้นไม่เกิน **40 หน้า** โดยปรับ `PDF_AI_MAX_PAGES` ได้แต่ไม่เกินขีดจำกัดตรวจ 200 หน้า) จาก private bucket Worker แยกหน้าโดยใช้ pypdf เฉพาะโครงสร้างไฟล์ แล้วให้ OpenAI `PDF_READER_MODEL` อ่านชุดละ 2 หน้าด้วย PDF vision โดยคืนข้อมูลแยกตามเลขหน้าจริง และตอบ JSON เป็นข้อความ/Keywords/คำเตือน การอ่านนี้มีค่า OpenAI API ตามเนื้อหาที่ส่ง ไม่ได้จำกัดโดยจำนวนคำถามของนักเรียน
- ไฟล์ `evidence` ไม่ส่งไป OpenAI และไม่เข้า RAG; DOCX/TXT ยังสกัดข้อความแบบเดิม
- ระบบเก็บ Chunks พร้อม `version_id`, `page_no`, `chunk_id`, `text`, `keywords`. การค้นแบบข้อความไทย/character grams ใช้ Keywords ประกอบ; ไม่ได้เปลี่ยน Keywords ให้เป็นแหล่งอ้างอิงแทนข้อความต้นฉบับ และ Vector Embedding ยังเป็นโหมดเลือกเปิด
- ไฟล์การสอนที่ AI อ่านเสร็จมีสถานะ `review` (ไม่ถูกใช้ตอบคำถามหรือดาวน์โหลดโดยนักเรียน) ครูต้องเปรียบเทียบ PDF ต้นฉบับกับข้อความ/เลขหน้า/Keywords แล้วแก้ไขในหน้า “ดูและแก้ไฟล์” ทำเครื่องหมาย Checklist 13 ข้อและยืนยัน rubric สี่ด้าน ก่อนอนุมัติระดับ `pilot` ให้เปลี่ยนเป็น `published`
- หน้า/สูตรที่อ่านไม่ชัดจะมีคำเตือน; ครูต้องกรอกหมายเหตุเพื่อยืนยันผลตรวจหากพบคำเตือน และห้ามถือว่าการอ่านจาก OpenAI แม่นยำ 100%
- หากไม่มี `LLM_API_KEY`, โมเดลตอบ JSON ผิด หรือจำนวนหน้าเกินขีดจำกัด งานจะเป็น `failed` ไม่ fallback ไปใช้ข้อความ PDF ที่ Python อ่านผิด และไม่เผยแพร่เอกสารอัตโนมัติ
- อย่าอัปโหลดเอกสารที่ไม่มีสิทธิ์ส่งให้ผู้ให้บริการประมวลผล AI; การอ่านไฟล์ด้วย OpenAI อาจมีค่าใช้จ่ายเพิ่มตามจำนวนหน้า
- Migration `20261028_chunk_keywords` เพิ่มคอลัมน์ JSONB แบบไม่ลบข้อมูล Chunk เดิม; เอกสารที่เผยแพร่แล้วก่อนอัปเกรดยังคงเผยแพร่ ส่วนเอกสารสถานะ `review` จะไม่ถูกค้นจนกว่าครูอนุมัติ


## Semantic Chunking ตามหัวข้อ (28 ตุลาคม 2569)

- เมื่อครูอัปโหลด **PDF ใหม่** OpenAI อ่านชุดละ 2 หน้าในรอบเดิมและส่งรายการ `sections` (หัวข้อ `topic`, ข้อความต้นฉบับ `text`, `keywords`) แทนการแบ่งตามหน้าเป็นหลัก ไม่เรียก OpenAI เพิ่มเพื่อแบ่ง Chunks
- Python รวม Sections ที่ต่อเนื่องกันและมี **ชื่อหัวข้อตรงกัน** แม้ต่อข้ามหน้ากระดาษ โดยมีเพดานข้อความ 2,400 ตัวอักษรต่อ Chunk สำหรับควบคุม Context; หัวข้อต่างกันจะไม่ถูกผสาน และช่วงที่เกินเพดานจะตัดตามขอบเขตย่อหน้า
- เก็บ `chunks.topic`, `chunks.page_no` (หน้าเริ่มต้นเดิม), `chunks.page_end`, Keywords และ `chunk_id` เพื่อค้นและอ้างอิง LINE ว่า "หน้า 4–6" ได้ ข้อมูลเดิมย้ายแบบ additive ด้วย Migration `20261028_semantic_chunks`
- LIFF หน้าครูสามารถตรวจ/แก้หัวข้อ ข้อความ Keywords หน้าเริ่มต้น และหน้าสิ้นสุดก่อนผ่าน Checklist แล้วอนุมัติเอกสาร หาก OpenAI ตีหัวข้อหรืออ่านข้อความผิด ต้องให้ครูตรวจแก้กับ PDF จริง
- แหล่งข้อมูลเก่าไม่มี Semantic Sections ไม่ถูกแปลงโดยอัตโนมัติ; จะได้ Semantic Chunks เมื่ออัปโหลดไฟล์ PDF เป็นรุ่นใหม่ ส่วน DOCX/TXT ยังใช้การแยกข้อความตามย่อหน้าเป็น fallback เพราะไม่มี OpenAI PDF Vision สำหรับไฟล์สองชนิดนี้
- การจับชื่อหัวข้อเป็นเกณฑ์ที่ตั้งใจให้ระมัดระวัง: ถ้าระบุชื่อหัวข้อต่างกันระบบจะไม่รวมข้ามหน้าเพื่อป้องกันการรวมความหมายผิด; รูปแบบนี้ต้อง Benchmark กับชุดคำถามจริงก่อนอ้างว่าประหยัด Token หรือแม่นยำขึ้น


## ลบไฟล์ที่ไม่ใช้แล้วและดูผลการอ่าน PDF ใน LIFF (29 ตุลาคม 2569)

- ในเมนูครู → สื่อการสอนและแบบฝึกหัด → **ดูและแก้ไฟล์** แสดงผลแต่ละรุ่นว่า `uploaded` (รับไฟล์), `processing` (กำลังอ่าน), `review` (อ่านสำเร็จและรอตรวจ), `published` (อนุมัติแล้ว), `failed` (อ่านล้มเหลว), `withdrawn` (ถอนแล้ว) หรือ `deleting` (ลบค้างและลองซ้ำได้) พร้อมรหัสและคำอธิบายข้อผิดพลาด
- ครูผู้มีสิทธิ์ในรายวิชาสามารถกด **ลบไฟล์รุ่นนี้ถาวร** พร้อมกล่องยืนยัน เพื่อเรียก `DELETE /documents/versions/{version_id}` พร้อม `expected_revision` API ลบเฉพาะ Object ตาม `storage_key`, Chunks/Vector/Keywords, ประวัติการตรวจ, Jobs ที่เชื่อมและ Metadata รุ่นไฟล์ ถ้าไม่มีรุ่นอื่นเหลือจะลบแถว `documents` ด้วย แต่คง Audit Event `document.delete`
- ไฟล์ `published` ต้องถอนการใช้ก่อนลบ ส่วนไฟล์ที่กำลังมี Job `queued/retry/running` และรุ่นที่มีคำถาม/หลักฐานประเมินอ้างอิงจะถูกปฏิเสธด้วย HTTP 409 พร้อมเหตุผล; ข้อมูลอื่นในรายวิชาไม่ถูกลบตาม
- เพื่อไม่ให้ฐานข้อมูลหลงสถานะหาก S3 ลบไม่สำเร็จ ระบบเปลี่ยนสถานะเป็น `deleting` ก่อน หาก Storage มีปัญหาจะแสดงว่าลบไม่สำเร็จและครูสามารถลองลบซ้ำได้หลังแก้ปัญหา; ไม่ลบ Bucket ทั้งก้อน
- ข้อมูลที่เผยแพร่แล้วหรือมีแหล่งอ้างอิงในบทสนทนาเก่าอาจไม่สามารถเปิดต้นฉบับย้อนกลับได้หลังลบถาวร ควรสำรองไฟล์ก่อน และตรวจว่าหมดการใช้งานจริง


## PDF checkpoint ทุก 2 หน้า

Worker ส่งหน้า 1–2, 3–4, … ให้ OpenAI ครั้งละชุด (ชุดสุดท้ายอาจมีหน้าเดียว) ตรวจว่า JSON มีเลขหน้าครบและเรียงตรงกับชุดที่ส่ง แล้ว commit ผลใน `jobs.payload.pdf_checkpoint` หลังแต่ละชุดสำเร็จ ไม่ต้องเพิ่มตารางหรือ migration

Checkpoint ผูกกับ checksum ของไฟล์, รุ่น prompt, โมเดล, จำนวนหน้า, batch size และ output limit เมื่อ retry งานเดิมหรือ worker กลับมารับงานหลัง lease หมด จะอ่านต่อจากชุดที่ยังไม่สำเร็จ โดยส่งหัวข้อสุดท้ายของชุดก่อนเป็นบริบทด้วย หากการตั้งค่าหรือไฟล์เปลี่ยนจะหยุดด้วย PDF_CHECKPOINT_MISMATCH เพื่อไม่รวมผลต่างรุ่น

เมื่ออ่านครบจึงสร้าง semantic chunks จากทุกหน้า แล้ว commit chunks, สถานะ review, งาน done และล้าง checkpoint ใน transaction เดียว ครูยังต้องอนุมัติก่อนใช้ RAG หากมีข้อผิดพลาดชั่วคราวจะ retry ตาม MAX_JOB_ATTEMPTS เดิม; ข้อผิดพลาดถาวร/ครบจำนวนครั้งยังเป็น failed และเก็บ checkpoint ไว้ ไม่เริ่มงาน failed ใหม่เอง

ถ้า process หยุดหลัง API ตอบแต่ก่อน checkpoint commit อาจต้องเรียกชุดนั้นซ้ำ; ชุดที่ commit แล้วจะไม่ถูกอ่านซ้ำ การใช้ checkpoint ลดงานซ้ำได้แต่ไม่รับประกันการเรียก API แบบ exactly-once `PDF_MAX_OUTPUT_TOKENS` เป็นงบต่อชุด (ค่าเริ่มต้น 16384) หากคำตอบไม่ครบจะไม่บันทึกชุดนั้นและไม่สร้าง chunks บางส่วน
