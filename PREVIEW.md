# Preview: แยกโค้ดจาก main.py ตามหน้าที่

ใช้โฟลเดอร์ `agent/`, `components/` และ `db/` ที่มีอยู่ โดยไม่ต้องสร้างโฟลเดอร์เพิ่มเติม ให้ `main.py` เหลือเฉพาะการประกอบและรัน FastAPI

## โครงสร้างหลังแยก

```text
line-webhook-api/
├── main.py
├── config.py
├── agent/
│   ├── __init__.py
│   └── gemini.py
├── components/
│   ├── __init__.py
│   └── line.py
├── db/
│   ├── __init__.py
│   ├── database.py
│   └── models.py
├── requirements.txt
└── PREVIEW.md
```

## ส่วนไหนไปไว้ที่ไหน

| ไฟล์ | หน้าที่และโค้ดที่อยู่ในไฟล์ |
| --- | --- |
| `main.py` | เก็บ `lifespan()`, สร้าง `FastAPI`, ผูก LINE router และรัน Uvicorn |
| `components/line.py` | ย้าย LINE configuration, `WebhookHandler`, route `POST /webhook` (`get_json`) และ `handle_message()` มารวมกัน ดูแล signature, ข้อความส่วนตัว, mention ในกลุ่ม, mark as read และ reply |
| `agent/gemini.py` | ย้าย `get_genai_response()` ทั้งฟังก์ชัน รวม prompt, การตั้งค่า Gemini/Google Search, ดาวน์โหลดไฟล์ที่อ้างอิงจาก LINE, อัปโหลดไฟล์เข้า Gemini และข้อความเมื่อเกิดข้อผิดพลาด |
| `config.py` | เพิ่มไฟล์กลางสำหรับโหลด `.env` และอ่าน `CHANNEL_ACCESS_TOKEN`, `CHANNEL_SECRET`, `DATABASE_URL`, `PORT` ส่วน `GEMINI_API_KEY` ยังอ่านเมื่อเรียก Gemini ตามเดิม |
| `db/database.py` | คงส่วน engine และ `create_db_and_tables()` ไว้ในโฟลเดอร์เดิม เปลี่ยนให้อ่านค่าจาก `config.py` และ import models เพื่อให้ SQLModel รู้จักตาราง |
| `db/models.py` | คง `User`, `UserProfile`, `Conversation`, `Message` ไว้ตามเดิม แก้ค่าเริ่มต้น `User.created_at` |
| `agent/__init__.py`, `components/__init__.py`, `db/__init__.py` | เพิ่มเพื่อประกาศ Python package อย่างชัดเจน |
| `requirements.txt` | เพิ่ม `sqlmodel` ซึ่งโค้ดฐานข้อมูลเดิมใช้อยู่แต่ยังไม่ได้ระบุ dependency |

เก็บ route และ event handler ของ LINE ไว้ไฟล์เดียว เพราะทำงานร่วมกันโดยตรง และลบ import/โค้ดคอมเมนต์ที่ไม่ได้ใช้ออกจาก `main.py`

## ลำดับการทำงาน

```text
main.py → lifespan → db/database.py → สร้างตารางจาก db/models.py
POST /webhook → components/line.py → ตรวจ signature และชนิดข้อความ
             → agent/gemini.py → สร้างคำตอบ
             → components/line.py → mark as read และตอบกลับ LINE
```

## จุดที่แก้เพื่อให้เริ่มแอปได้

- เติม `yield` ใน `lifespan()` ให้เป็น async context manager ที่ FastAPI ใช้งานได้
- โหลด `.env` ก่อนสร้าง database engine ผ่าน `config.py`
- ลงทะเบียน models ก่อน `SQLModel.metadata.create_all()` เพื่อให้สร้างตารางทั้ง 4 ตารางได้จริง
- เปลี่ยน `User.created_at.default_factory` เป็น `lambda` เพื่อสร้างเวลาขณะสร้างแต่ละ record แทนการส่งค่า datetime เข้า factory

## การใช้งาน

ตั้งค่า `CHANNEL_ACCESS_TOKEN`, `CHANNEL_SECRET`, `GEMINI_API_KEY` และ `DATABASE_URL` ใน environment หรือ `.env` โดย `PORT` มีค่าเริ่มต้นเป็น `8080`

โมเดลเดิมใช้ `JSONB` ของ PostgreSQL จึงต้องใช้ฐานข้อมูลที่รองรับและติดตั้ง driver ให้ตรงกับ `DATABASE_URL` ก่อนรัน แอปจะเรียก `create_all()` เมื่อเริ่มทำงาน

```bash
pip install -r requirements.txt
python main.py
```

หรือใช้ `uvicorn main:app --host 0.0.0.0 --port 8080` ได้ตามเดิม ไม่ต้องเปลี่ยน Dockerfile หรือ URL webhook

## ผลตรวจสอบ

- ผ่านการตรวจ 12 กรณีด้วยสคริปต์ชั่วคราว `/tmp/verify_line_refactor.py`: lifecycle, model registration/การสร้าง SQL สำหรับ PostgreSQL, signature ที่ขาด/ผิด/ถูกต้อง, ข้อความส่วนตัว, mention ในกลุ่ม, กลุ่มที่ไม่ได้ mention, ไฟล์แนบ, การดาวน์โหลดล้มเหลว และ Gemini fallback
- เทียบ AST ของ body ใน `get_json()`, `handle_message()` และ `get_genai_response()` กับต้นฉบับแล้วตรงกัน จึงคง logic เดิมของทั้ง 3 ฟังก์ชัน รวมถึง prompt และโมเดล `gemini-2.5-flash`
- จำลอง LINE, Gemini และ database engine ในการทดสอบ ไม่ได้เรียก API หรือเชื่อมต่อฐานข้อมูลจริง
- ตัวทดสอบ FastAPI ค้างระหว่าง thread ใน sandbox จึงรันทดสอบนอก sandbox หลังได้รับอนุญาต และผ่านทั้งหมด
