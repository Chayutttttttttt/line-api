# การติดตั้งและเก็บหลักฐานก่อนนำร่อง

## การกำหนด environment

แยก development/staging/production และใช้ LINE channels, bucket, database และ API keys แยกกัน ตั้ง API/worker ให้ใช้ database กับ bucket ชุดเดียวกันภายใน environment ทดสอบก่อน deploy ทุก migration ไม่รันคำสั่งตรวจรับกับข้อมูลนักเรียนจริง

`railway.toml` ที่ root สำหรับ API เท่านั้น สำหรับ worker ให้ใช้ start command `python -m worker.run` และปิด HTTP healthcheck เพราะไม่มี HTTP server ไม่รัน migrations พร้อมกันหลาย replica ในการ deploy แรก ให้ API อัปเกรดเสร็จก่อนเริ่ม worker

`.dockerignore` กัน `.env`, `.aws`, `.codex`, `.agents`, `.git`, `.venv`, node_modules และไฟล์ build ออกจาก backend image Dockerfile ของ LIFF ใช้ standalone output เพื่อแยกเว็บออกจาก Python image ไม่มี channel secret หรือ AI key ใน build arguments ของ LIFF

## ลำดับ smoke test บน staging

1. `/health` ต้องเชื่อม SQL ได้ ตรวจ `alembic_version` เป็น `20261018_acceptance`
2. เปิด `/login` ด้วยบัญชี LINE ทดสอบจริง ยืนยัน `/me` ตรงกับบัญชีและไม่มี role ที่ไม่ได้รับอนุมัติ ทดสอบ token ผิด channel/หมดอายุให้ 401
3. ผู้ดูแล bootstrap โรงเรียน/วิชา และเพิ่มครูกับนักเรียนทดสอบผ่าน CLI
4. อัปโหลดข้อความ PDF/DOCX ทดสอบ เก็บ checksum จาก API แล้วดาวน์โหลดผ่าน API ให้ hash ตรงกัน ยืนยัน bucket ไม่เปิด public และไม่มี URL ตรงหลุดออก student API
5. worker เปลี่ยนเอกสารเป็น review แก้ข้อความและหน้าให้ตรงต้นฉบับ อนุมัติ prototype แล้วนักเรียนต้องยังเปิดไม่ได้ อนุมัติ pilot หลังตรวจครบ นักเรียนในวิชาจึงเปิดได้
6. ถามหัวข้อที่มีหลักฐาน ตรวจ citation กับไฟล์/หน้า/รุ่นจริง ลองถอนเอกสารแล้วค้นและเปิดลิงก์เดิมซ้ำ ห้ามได้เอกสารที่ถอนผ่านสิทธิ์นักเรียน
7. ครูสร้างโจทย์และรับรองเฉลย ส่งคำตอบสมมูล ซ้ำ และข้าม session ต้องได้ผลตามเกณฑ์โดยไม่มี attempt เพิ่มซ้ำ
8. เปิดเตือนโดยสมัครใจ สร้างงาน/แผน ทดสอบเวลาเงียบ เปลี่ยนวัน/ทำงานเสร็จ/ปิดเตือน/บล็อก OA ก่อนส่ง สังเกต revision และ outbox
9. ทดสอบ Push จริงด้วยบัญชีทดสอบหนึ่งรายก่อน เปิด redelivery ใน LINE webhook ตรวจรหัส accepted request หลัง timeout ใช้ retry key เดิมตลอด ห้ามเปลี่ยน key เพื่อพยายามส่งข้อความเดิม
10. บันทึกผลจริงในทะเบียนหลักฐาน โดยใช้ commit ของ code ที่ deploy จริง ห้ามใช้ผล automated tests แทนผล OAuth/LINE/S3 จริง

การส่งที่ถูก LINE รับไปแล้วหรือกำลัง in-flight อาจเรียกคืนไม่ได้ การตรวจ source/revision ก่อนส่งป้องกันคิวที่ยังไม่ส่ง แต่ไม่ใช่ธุรกรรมร่วมกับ LINE

## สถานะที่ผู้ดูแลต้องติดตาม

- `jobs`: queued/retry ที่เก่านาน, running ที่ lease หมด, failed และจำนวน attempts
- `message_outbox`: pending, sending, accepted, failed, cancelled, unknown
- `document_versions`: uploaded/review/published/withdrawn/failed และ extraction_error
- `job.payload`: รุ่นโมเดล, prompt version, token usage, citation chunk/version/checksum หลังสำเร็จ เก็บข้อความผู้เรียนใน messages ไม่เขียนลง log
- request_id ใน HTTP error และ X-Request-ID ใช้ค้นเหตุการณ์ อย่าแนบ secrets ใน screenshot หรือ log ที่ส่งให้ผู้ตรวจ

ตัวอย่าง SQL สำหรับตรวจคิวโดยไม่แสดงข้อความผู้เรียน:

```sql
SELECT kind, state, count(*), min(created_at) FROM jobs GROUP BY kind, state;
SELECT state, count(*), min(created_at) FROM message_outbox GROUP BY state;
SELECT status, count(*) FROM document_versions GROUP BY status;
```

`accepted` เป็นสถานะ LINE API รับ ไม่ใช่ delivered/read `unknown` ใช้เมื่อหมดช่วง retry ที่ปลอดภัยหรือเกินจำนวนครั้ง ต้องตรวจสถานะกับ LINE ก่อนดำเนินการ ห้ามสร้าง push ใหม่แทนโดยอัตโนมัติ

## สำรอง กู้คืน และรายการลบ

เป้าหมายใน roadmap คือ RPO 24 ชั่วโมง และ RTO 4 ชั่วโมง ต้องทดสอบและวัดจริง ระบบนี้ไม่ได้ provision ตารางสำรองของ Railway ให้เอง และยังไม่ควรบันทึก BACKUP_RESTORE เป็นผ่านจนทำครบขั้นตอน

เก็บ backup SQL และสำเนา object ที่อ้างใน document_versions พร้อม checksum ในพื้นที่ private ที่แยกความเสียหายจากชุดหลัก กำหนดรอบหมดอายุ backup กับโรงเรียน ใช้ credentials จำกัดสิทธิ์ แยก deletion ledger ให้ใหม่กว่า backup ล่าสุดได้

```bash
.venv/bin/python manage.py export-deletions --output /secure-backup/deletion-ledger.json
pg_dump --format=custom --file=/secure-backup/database.dump "$DATABASE_URL"
```

ขั้นตอน restore ใน environment แยกที่ปิด worker และไม่เปิดรับผู้ใช้:

1. คืน SQL ไปฐานทดสอบว่างด้วย pg_restore และคืน objects ไป private bucket ทดสอบ อย่าต่อ URL/credentials production
2. ตรวจ checksum ของ objects และจำนวน records ตรวจ role/membership ก่อนเปิด API
3. ใช้ deletion ledger ล่าสุดจากนอก database backup เพื่อบังคับรายการลบซ้ำ **ก่อนเปิด API หรือ worker**:

```bash
.venv/bin/python manage.py replay-deletions --file /secure-backup/deletion-ledger.json
```

4. ตรวจว่าประวัติ งาน แบบฝึก และ session ของบัญชีที่ร้องขอลบไม่กลับมาใช้งาน และงาน AI เก่าถูกยกเลิก ทดสอบด้วยบัญชีจำลอง
5. วัดข้อมูลที่สูญหายและเวลา restore จริง แนบผล/รุ่น/ผู้ทดสอบในทะเบียน BACKUP_RESTORE

คำสั่งลบ `conversations` ลบข้อความ feedback ที่ผู้ใช้แจ้ง และยกเลิกคิว AI/outbox คำสั่ง `personal_data` ลบงาน แผน ผลฝึก โปรไฟล์ session ตัวเชื่อม LINE และสมาชิก พร้อมทำบัญชีเป็น deleted เอกสารวิชาและหลักฐานโรงเรียนยังเป็นข้อมูลสถาบัน ไม่ถูกลบโดยคำขอของนักเรียน และต้องมีนโยบายเก็บรักษาแยก

## สิ่งที่ยังต้องให้คนรับรอง

- สิทธิ์ใช้เอกสารหลัก `RelFnc.pdf` และเนื้อหาที่อ้าง หน้า 22, 38–39 ไม่ได้แนบไฟล์ต้นฉบับนี้ในงานรอบนี้ จึงยังไม่รับรองนิยาม/เฉลยจากเล่มนั้น
- rubric Word 0–2 สำหรับตรวจเนื้อหา กับ rubric PDF 0–3 สำหรับ AI เป็นคนละแบบประเมิน ห้ามแปลงคะแนนหรือเติมผลผ่านเอง
- catalog 80 กรณีเป็นกรณีเริ่มต้น ต้องให้ครูปรับตามเนื้อหาที่รับรองและบันทึก expected เฉพาะกรณีในหลักฐานจริง เปลี่ยนรอบทดสอบเมื่อ model/prompt/code/เอกสารเปลี่ยน
- กรณีวิกฤตต้องแก้แล้วรันชุดใหม่ ผลเก่าคงอยู่เพื่อสืบย้อน รายงานไม่เปิดนำร่องอัตโนมัติแม้หลักฐานครบ
- การตรวจเนื้อหาไม่ใช่ผลว่านักเรียนเรียนดีขึ้น แบบทดสอบก่อน/หลัง/ติดตามผลยังต้องจัดทำแยกจากคลัง RAG และเก็บผลจริงตามกระบวนการโรงเรียน
