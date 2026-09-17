# Preview: ต่อ LIFF Login เข้ากับ Backend เพื่อทดสอบรับ token

## สิ่งที่เปลี่ยน

- `liff/components/lineloginButton.tsx`: ใช้ `getLineIdToken()` เดิม ส่ง POST JSON ไป `${NEXT_PUBLIC_API_URL}/auth/line` หลัง init และ login สำเร็จ รวมตอนกลับจาก LINE redirect
- แสดงสำเร็จเมื่อ API ตอบ `received: true` เท่านั้น รองรับ error/retry และ timeout 15 วินาที ป้องกัน POST ซ้ำจาก Strict Mode effect replay
- `components/login.py`: รับ token ที่ไม่เป็นสตริงว่าง, `print(id_token, response, flush=True)` และตอบ `{"received": true}` โดยไม่ส่ง token กลับ
- `config.py` และ `main.py`: เพิ่ม CORS สำหรับ POST JSON ตั้ง origins ได้ด้วย `CORS_ORIGINS` ใน `.env` ฝั่ง Backend
- `PREVIEW.md` และ `liff/PREVIEW.md`: อัปเดตสรุปและวิธีทดสอบ

## วิธีใช้งาน

1. รัน Backend จาก root: `.venv/bin/python main.py`
2. Frontend ใช้ `NEXT_PUBLIC_LIFF_ID` และ `NEXT_PUBLIC_API_URL` ที่ตั้งไว้แล้วในไฟล์ env ของ `liff/` (ปัจจุบัน API เป็น `http://localhost:8000`)
3. รัน Frontend: `npm --prefix liff run dev` แล้วเปิด `/login` บน URL ที่ตั้งไว้ใน LINE Developers หากตั้งเป็น HTTPS localhost ให้ใช้ `npm --prefix liff run dev -- --experimental-https`
4. กดเข้าสู่ระบบด้วย LINE เมื่อกลับมายังเว็บจะส่ง token อัตโนมัติ ถ้าล็อกอินอยู่แล้วจะส่งทันทีหลัง init
5. ดู token และ Response object ใน terminal ของ Python ส่วนหน้าเว็บแสดง “ส่งข้อมูล LINE สำเร็จ”

CORS ค่าเริ่มต้นรองรับ `http://localhost:3000`, `https://localhost:3000` และ `127.0.0.1` ทั้งสอง protocol หากใช้โดเมนหรือพอร์ตอื่น ให้กำหนด origin จริง เช่น `CORS_ORIGINS=https://your-frontend.example` (หลาย origin คั่นด้วย comma, ไม่มี path) แล้ว restart Backend

หากทดสอบบนมือถือ `localhost` จะหมายถึงมือถือ ให้ใช้ API URL ที่มือถือเข้าถึงได้ และใช้ HTTPS API สำหรับเว็บ HTTPS จากนั้น restart/rebuild Frontend เมื่อเปลี่ยน `NEXT_PUBLIC_API_URL`

นี่เป็นขั้นตอนทดสอบการส่ง token เท่านั้น ยังไม่มีการ verify token หรือสร้าง session; `response` ที่ print เป็น FastAPI Response object การ print token เต็มเป็นโค้ด debug ชั่วคราว

## การตรวจสอบ

- TypeScript: `tsc --noEmit --incremental false` ผ่าน
- ESLint เฉพาะ component ที่แก้ผ่าน
- HTTP ผ่าน ASGI transport กับแอปจริง: POST token จำลองแล้ว print และตอบ JSON ถูกต้อง, token หาย/ว่าง/null ได้ 422, CORS preflight ของ origin ที่อนุญาตผ่านและ origin อื่นถูกปฏิเสธ
- จำลอง Frontend ด้วย LIFF/fetch/hooks: ส่ง POST ครั้งเดียวระหว่าง effect replay, เรียก login เมื่อยังไม่ล็อกอิน, API error แล้ว retry สำเร็จ, token/API URL หายแสดง error
- ยังไม่ได้ทดสอบ OAuth ด้วยบัญชี LINE จริงหรือในเบราว์เซอร์
