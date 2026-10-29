# Preview อัปเดต main ล่าสุดและย้ายระบบ AI เป็น OpenAI GPT

อัปเดต 29 ตุลาคม 2569: ตรวจงานที่ค้างและทำต่อจนเสร็จ โดยใช้ GitHub main commit `e20e85056cfd0b08c8da0d06208704a57336a211` เป็นฐานในเครื่อง จากเดิม `81dc5aacf0ec47b40d35d7f1c52d5e62ddcd98e4`

- เก็บงาน local ก่อนอัปเดตไว้ใน Git stash `9286f153f5b596532d851d0111af4d9174bb7832` ชื่อ `backup local OpenAI migration before syncing main 2026-10-29` รวมไฟล์ agent/llm.py ที่ยังไม่ tracked แล้ว fast-forward main สำเนา /tmp ที่สร้างก่อนหน้าไม่อยู่แล้ว แต่ตรวจยืนยันว่า stash ยังเก็บงานครบ
- ย้าย tutor เป็น `agent/llm.py` ใช้ OpenAI Responses API + Structured Outputs, `store=False`, ปิด SDK retries, ตรวจ citations/page spans และคงการซ่อมคำตอบผิด schema/citation 1 ครั้งจาก main ล่าสุด พร้อมข้อความสำรองสำหรับ refusal/คำตอบไม่ครบ
- `components/pdf_ai.py` ส่ง PDF ทีละหน้าเป็น base64 ให้ OpenAI อ่าน semantic sections; ต่ออายุ lease ก่อนแต่ละหน้า คงการตรวจข้อผิดพลาดและไม่คืนเอกสารบางส่วนเมื่อหน้าถัดไปอ่านล้มเหลว ส่ง previous_topic เป็นข้อมูลแทนการแทรกในคำสั่งระบบ
- คง Semantic Chunking เดิม: รวม sections หัวข้อตรงกันที่อยู่ติดกัน จำกัด 2400 ตัวอักษร พร้อมหน้าเริ่ม/สิ้นสุด รอครูตรวจอนุมัติ และคงฟังก์ชันใหม่จาก main เช่น LINE-only AI, admin และการลบเอกสาร
- Embeddings ย้ายเป็น OpenAI `text-embedding-3-small` ขนาด 768 มิติเท่า schema เดิม ปิดเป็นค่าเริ่มต้น คง hybrid retrieval และการกรอง embedding_model เพื่อไม่ผสมเวกเตอร์ Gemini เก่า
- เปลี่ยนข้อความการส่ง PDF และข้อผิดพลาดใน LIFF เป็น OpenAI พร้อมปรับ README และ .env.example

## ไฟล์ที่แก้

- `agent/gemini.py` → `agent/llm.py`, `components/pdf_ai.py`, `components/embeddings.py`, `worker/run.py`
- `config.py`, `requirements.txt`, `.env.example`, `components/documents.py` (type/comment), `components/semantic_chunking.py` (comment)
- `liff/components/teacherPanel.tsx`, `liff/lib/documentStatus.ts`, `liff/README.md`, `README.md`
- `tests/test_material_pipeline.py`, `tests/test_pdf_ai_ingest.py`, `PREVIEW.md`
- ไม่แก้ generated files หรือ migration ที่มากับ main ล่าสุด

## ผลตรวจ

- Backend: `python -m unittest discover -s tests -v` ผ่าน 40 tests รวม PDF/semantic chunking, OpenAI request/schema/repair/refusal/incomplete, embeddings และชุดลบเอกสารเดิม ใช้ SDK จริงกับ HTTP จำลอง ไม่มีค่า API
- หลังแยก previous_topic ออกจาก instructions ทดสอบเฉพาะ PDF ซ้ำผ่าน 9 tests
- ชุด Node tests ของ LIFF ทั้ง 2 ไฟล์ผ่าน; การเปลี่ยน LIFF รอบนี้เป็นข้อความเท่านั้น ไม่ได้ทำ full Next.js build (ไม่มี node_modules ใน checkout)
- API/worker imports, Python compile, pip check, dependency versions และ git diff --check ผ่าน
- ยังไม่ได้เรียก OpenAI/LINE/ฐานข้อมูลจริง หรือทดสอบคุณภาพ PDF ด้วยบัญชีจริง

## การตั้งค่าก่อนใช้งานจริง

- ใช้ `LLM_API_KEY` เป็น OpenAI API key; ค่าเริ่มต้น `LLM_MODEL=gpt-5.4-mini` และ PDF_READER_MODEL ใช้ค่าเดียวกันเมื่อไม่ได้ตั้งแยก ตั้งทั้ง API และ worker ให้ตรงกัน
- ตั้ง `AI_ENABLED=true` เมื่อต้องการให้ตอบนักเรียน; ตัวอ่าน PDF เรียก API ได้แม้ AI_ENABLED=false เพื่อให้ครูเตรียมเอกสารก่อนเปิดแชต
- เปลี่ยน PDF_READER_MODEL/EMBEDDING_MODEL ที่เคยระบุ Gemini ใน Railway ด้วย ไม่มี fallback ไปใช้ GEMINI_API_KEY
- Output budget: แชต 4096 (`LLM_MAX_OUTPUT_TOKENS`), PDF 16384 (`PDF_MAX_OUTPUT_TOKENS`) รวม reasoning tokens; PDF เริ่มต้นสูงสุด 40 หน้า
- หากเปิด embeddings ให้สร้าง/อัปเดต vector ของเอกสารที่อนุมัติแล้วใหม่ผ่านปุ่มเดิม ไม่ต้องแก้คอลัมน์ vector และไม่ต้องอัปโหลด PDF ใหม่เพื่อ reindex
- ใช้ migrations จาก main ล่าสุดตามขั้นตอน deploy เดิม; ไม่มี migration เพิ่มสำหรับการย้าย OpenAI นี้
- งานเสร็จในเครื่องเท่านั้น ยังไม่ได้ commit/push/deploy หรือเปลี่ยน Railway Variables

## ประวัติ preview ก่อนหน้า

# Preview ตรวจ repo หลักและแก้ไขข้อสรุปเรื่อง Semantic Chunking

อัปเดต 29 ตุลาคม 2569: อ่าน GitHub `Chayutttttttttt/line-api` โดยตรงที่ main commit `e20e85056cfd0b08c8da0d06208704a57336a211`; local HEAD คือ `81dc5aacf0ec47b40d35d7f1c52d5e62ddcd98e4` จึงเป็นคนละ revision คำอธิบายก่อนหน้าที่อ้าง local ไม่ตรงกับ repo หลัก

- repo หลักใช้ LLM-assisted semantic/topic chunking สำหรับ PDF การสอนจริง: `worker/run.py` เรียก `read_pdf_with_gemini()` และ `ingest()` เรียก `build_semantic_chunks()`
- `components/pdf_ai.py` ส่ง PDF ทีละหน้าให้ Gemini ถอดข้อความและแบ่ง sections พร้อม topic/keywords โดยส่งชื่อหัวข้อสุดท้ายของหน้าก่อนเพื่อช่วยความต่อเนื่อง
- `components/semantic_chunking.py` รวมส่วนติดกันที่ topic หลัง normalize ตรงกัน ภายในหน้าเดียวหรือหน้าถัดไป จำกัด 2400 ตัวอักษร ใช้ `chunk_page(..., overlap=0)` แบ่งส่วนยาว และเก็บ page_no/page_end; ไม่ใช่การใช้ embedding similarity หาแนวแบ่ง
- `components/documents.py` มี vector + lexical retrieval แบบเลือกเปิดด้วย `EMBEDDINGS_ENABLED`; การมีโค้ดไม่ได้ยืนยันว่าเปิดใช้ใน Railway
- repo หลักยังเรียก Google GenAI ทั้งอ่าน PDF และตอบคำถาม; `PDF_READER_MODEL` ค่าเริ่มต้น gemini-2.5-flash แยกจาก `LLM_MODEL` การตั้ง gpt-5.4-mini อย่างเดียวไม่เปลี่ยน SDK เป็น OpenAI
- งานนี้แก้เฉพาะ `PREVIEW.md`; ไม่ pull/merge ทับงาน local ไม่เปลี่ยน GitHub/Variables และไม่ deploy ผลตรวจยืนยันโค้ด repo เท่านั้น ไม่ยืนยัน runtime หรือวิธีที่ใช้สร้าง chunks เก่า

## ประวัติ preview ก่อนหน้า (อ้างอิง local revision ไม่ใช่ main บน GitHub)

# Preview ประเมิน Semantic Chunking

อัปเดต 29 ตุลาคม 2569: อธิบายว่า semantic chunking อาจช่วยรักษาบริบท แต่ไม่ได้รับประกันว่าคำตอบจะแม่นขึ้น และแยกจาก semantic retrieval ซึ่งโปรเจกต์ยังไม่ได้ใช้

- ข้อเสนอสำหรับเอกสารการสอน: ทดลองแบ่งตามหัวข้อ/ย่อหน้าและรักษาโจทย์กับวิธีทำก่อน แล้วเปรียบเทียบ semantic chunking และการค้นหาแบบ keyword ร่วมกับ vector ด้วยคำถามจริง งบ context เท่ากัน และตรวจความถูกต้องของคำตอบ/อ้างอิง
- ข้อจำกัดเดิมยังสำคัญ: ข้อความ PDF ที่สกัดผิดหรือการค้นหา lexical ที่ไม่พบคำพ้องความหมายไม่ได้ถูกแก้โดยเปลี่ยน chunking เพียงอย่างเดียว
- หลักฐาน: งานวิจัย NAACL 2025 พบว่าผลดีของ semantic chunking ไม่สม่ำเสมอเมื่อเทียบกับต้นทุน: https://aclanthology.org/2025.findings-naacl.114/
- งานนี้แก้เฉพาะ `PREVIEW.md`; ยังไม่ได้เปลี่ยนอัลกอริทึมหรือทดสอบ benchmark กับเอกสารจริงของโปรเจกต์

## ประวัติ preview ก่อนหน้า

# Preview อธิบาย PDF, chunking และการส่งข้อมูลให้ GPT

อัปเดต 29 ตุลาคม 2569: ตรวจโค้ดปัจจุบันเพื่ออธิบายกระบวนการรับ PDF, แบ่งข้อความ, ค้นหาเอกสาร และสร้างคำตอบ

- ระบบไม่ได้ส่ง PDF ให้ GPT แบ่ง chunks: worker ใช้ `pypdf.PdfReader` สกัดข้อความทีละหน้า แล้วตัดด้วย Python ครั้งละไม่เกิน 2100 ตัวอักษร เลื่อนครั้งละ 1800 จึงซ้อนทับสูงสุด 300 ตัวอักษรภายในหน้าเดียวกัน
- เก็บ chunks ใน PostgreSQL พร้อมรุ่นเอกสาร ลำดับ และเลขหน้า รอครูตรวจและอนุมัติเป็น published ก่อนใช้ตอบนักเรียน
- ค้นหาแบบ lexical โดยให้คะแนนคำตรง หัวข้อ/keywords และ Thai character trigrams เลือกสูงสุด 5 chunks ที่คะแนนมากกว่า 0; ยังไม่มีการสร้าง embeddings หรือค้นหา vector ในเส้นทางนี้
- ส่งคำถาม บริบทวิชา ข้อความ chunks และประวัติคำถามให้ OpenAI Responses API ในรูป JSON แล้วตรวจ chunk IDs ที่อ้างอิง; ถ้าไม่มี chunks จะไม่เรียก GPT
- ข้อจำกัด: ไม่มี OCR หรือการส่งภาพ PDF ให้โมเดล, การตัดตามจำนวนตัวอักษรอาจตัดกลางประโยค/ตาราง/สมการ, การเปลี่ยน LLM_MODEL ไม่เปลี่ยนวิธี chunking
- โค้ดที่ตรวจ: `components/documents.py`, `components/storage.py`, `worker/run.py`, `agent/llm.py`, `db/models.py`; งานนี้แก้เฉพาะ `PREVIEW.md` และไม่ได้ทดสอบการเรียก API จริงหรือ deploy

## ประวัติ preview ก่อนหน้า

# Preview ตรวจชื่อโมเดลจาก Railway Variables

อัปเดต 29 ตุลาคม 2569: เปิดลิงก์ Railway project AGENT / production ที่ผู้ใช้ให้ และตรวจ Variables ผ่าน connector กับหน้าเว็บ

- Connector ปิดบังค่า variables (`valuesRedacted=true`): `worker` มี `LLM_MODEL`; `line-api` ยังไม่มีตัวแปรนี้ในค่าที่ใช้งานจริง
- หน้าเว็บ `line-api` แสดง `LLM_MODEL` และ `LLM_API_KEY` ในรายการแก้ไขที่รอ deploy แต่ค่าปิดบังเป็น `*******` และไม่พบตัวควบคุมแสดงค่าในเซสชันนี้ จึงยังยืนยันชื่อโมเดลไม่ได้
- ต้องอ่านค่า `LLM_MODEL` จากเซสชัน Railway ที่แสดงค่าได้ โดยไม่ต้องส่ง API key
- ไฟล์ที่แก้ในงานนี้: `PREVIEW.md` เท่านั้น; ไม่เปลี่ยน Variables หรือ deploy

## ประวัติ preview ก่อนหน้า

# Preview ตรวจสถานะการใช้ OpenAI API

อัปเดต 29 ตุลาคม 2569: ตรวจโค้ด การตั้งค่า local และ Railway production เพื่อยืนยันสถานะการเชื่อมต่อ OpenAI โดยไม่เปิดเผยค่าคีย์

- โค้ด `agent/llm.py` ใช้ OpenAI Responses API ผ่าน `LLM_API_KEY` แล้ว และ local ติดตั้ง OpenAI SDK 2.54.0
- Local ไม่มี `.env`; ค่าที่โหลดได้คือ `AI_ENABLED=false` และไม่มี `LLM_API_KEY` / `LLM_MODEL`
- Railway `line-api`: การเพิ่ม `LLM_API_KEY`, `LLM_MODEL` และลบ `GEMINI_API_KEY` ยังเป็น staged changes ไม่ได้ deploy; รายการตัวแปร live ยังมี `GEMINI_API_KEY` และไม่มี `AI_ENABLED`
- Railway `worker`: รายการตัวแปร live มี `AI_ENABLED`, `GEMINI_API_KEY`, `LLM_MODEL` แต่ไม่มี `LLM_API_KEY`; connector ปิดบังค่า จึงไม่ยืนยันค่า AI_ENABLED หรือชื่อโมเดล
- ก่อนใช้งานจริงต้อง deploy โค้ด OpenAI พร้อมตั้ง key/model และเปิด AI ให้บริการที่เกี่ยวข้อง โดยเฉพาะ worker ซึ่งเป็นผู้เรียกโมเดล; ยังไม่ได้ทดสอบคำขอ OpenAI จริง
- งานนี้แก้เฉพาะ `PREVIEW.md`; ไม่เปลี่ยนโค้ดหรือการตั้งค่าบน Railway

## ประวัติ preview ก่อนหน้า

# Preview เปลี่ยน LLM เป็น OpenAI GPT

อัปเดต 29 ตุลาคม 2569: ปรับ `agent/llm.py` จาก Gemini เป็น OpenAI Responses API พร้อม Structured Outputs โดยใช้ `LLM_API_KEY` และ `LLM_MODEL` ตามชื่อตัวแปรที่ผู้ใช้เตรียมไว้ใน Railway

- ไฟล์ที่แก้ในงานนี้: `agent/llm.py`, `config.py`, `requirements.txt`, `.env.example`, `README.md`, `PREVIEW.md` ต่อจากการเปลี่ยนชื่อไฟล์และ import ใน `worker/run.py` ที่มีอยู่ก่อนแล้ว
- เปลี่ยน dependency เป็น `openai==2.54.0` และติดตั้งใน `.venv`; คง prompt `course-tutor-v2` และกฎตรวจ citation เดิม บันทึก model/usage จาก OpenAI รองรับ refusal และปฏิเสธคำตอบที่ไม่สมบูรณ์
- ใช้ timeout 45 วินาที ปิด SDK retries ให้ worker จัดการ ตั้ง `store=False` และเพิ่ม `LLM_MAX_OUTPUT_TOKENS` ค่าเริ่มต้น 4096 รวม reasoning tokens ไม่กำหนดโมเดลเริ่มต้นแทนค่าของผู้ใช้
- ผลตรวจ: 8 tests ผ่านโดยใช้ OpenAI SDK จริงกับ HTTP จำลอง ครอบคลุม request/schema, citations, refusal, incomplete/empty output, validation, AI ปิด/ไม่มี key/ไม่มีแหล่งข้อมูล และ HTTP 429; API/worker imports, Python syntax, `pip check` และ `git diff --check` ผ่าน ชุดตรวจชั่วคราวอยู่ใน `/tmp/line_api_gpt_checks.py`
- Railway service `line-api` / production: ตรวจพบการลบ `GEMINI_API_KEY` และเพิ่ม `LLM_API_KEY`, `LLM_MODEL` เป็น staged changes ยังไม่ deploy; connector ปิดบังค่า จึงยังยืนยันชื่อโมเดลและ key จริงไม่ได้ ไม่พบ `AI_ENABLED` ในรายการตัวแปรของบริการนี้
- ก่อนใช้งาน: นำโค้ดขึ้น GitHub/deploy พร้อม variables และตั้ง `AI_ENABLED=true` เมื่อพร้อมใช้ AI โดย API และ worker ต้องได้รับค่าที่ตรงกัน ยังไม่ได้ push/deploy เปลี่ยน Railway Variables หรือทดสอบเรียก OpenAI/LINE จริง
- อ้างอิง: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

## ประวัติ preview ก่อนหน้า

# Preview อธิบาย PROMPT_VERSION

อัปเดต 29 ตุลาคม 2569: อธิบาย `PROMPT_VERSION = "course-tutor-v2"` ใน `agent/llm.py` ว่าเป็นป้ายระบุรุ่นชุดคำสั่ง AI ที่ผู้พัฒนากำหนดเอง โดย worker บันทึกลง payload ของงาน และระบบตรวจรับมีช่อง `prompt_version` สำหรับบันทึกรุ่นที่ใช้ประเมิน

- ไฟล์ที่แก้ไขในงานนี้: `PREVIEW.md` เท่านั้น
- หมายเหตุ: การเปลี่ยนค่านี้ไม่ได้เปลี่ยน prompt หรือโมเดลอัตโนมัติ ควรปรับรุ่นเมื่อเปลี่ยนคำสั่ง AI เพื่อให้ติดตามผลย้อนหลังได้
- ตรวจสอบจากโค้ดปัจจุบันใน `agent/llm.py`, `worker/run.py`, `components/acceptance.py` และ `db/models.py`

## ประวัติ preview ก่อนหน้า

# Preview อธิบายโครงสร้าง components ฝั่ง backend

อัปเดต 29 ตุลาคม 2569: อธิบายเฉพาะ `components/` ที่อยู่นอก `liff/` ตามขอบเขตที่ผู้ใช้ระบุ ครอบคลุมหน้าที่ของ login, line, learning, grading, documents, storage, acceptance และ `__init__.py` พร้อมการลงทะเบียน router ใน `main.py` และความสัมพันธ์กับฐานข้อมูลและ worker

- ไฟล์ที่แก้ไข: `PREVIEW.md` เท่านั้น
- วิธีอ่านโค้ด: เริ่มจาก `main.py` ที่ลงทะเบียน router แล้วอ่าน `components/login.py` สำหรับ session/สิทธิ์ ก่อนตามไปยังโมดูลของฟีเจอร์ที่สนใจ
- งาน AI และนำเข้าเอกสารถูกประมวลผลผ่าน `worker/run.py`; ฟังก์ชันเรียก Gemini อยู่ใน `agent/gemini.py`
- ตรวจสอบจากโค้ดและจุด import โดยไม่ได้รันแอปหรือทดสอบบริการภายนอก

## ประวัติ preview ก่อนหน้า

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
