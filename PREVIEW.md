# Preview: ตรวจสอบวิธีทดสอบ print(id_token, response)

- `components/login.py`: มี `POST /auth/line` รับ JSON `id_token` และ print แล้ว แต่ยังไม่มี return จึงได้ JSON null
- `main.py`: ลงทะเบียน auth router แล้ว ไม่มี CORS middleware และ startup ไม่เรียกฐานข้อมูล
- `liff/components/lineloginButton.tsx`: ปุ่มตรวจสถานะ LINE แต่ยังไม่ส่ง token ไป backend
- `liff/lib/liff.ts`: มี `getLineIdToken()` ให้ใช้แล้ว
- เปลี่ยนเฉพาะ `PREVIEW.md`; ยังไม่ได้แก้โค้ดแอป

## วิธีทดสอบ

รัน backend และส่ง `{"id_token":"test-token"}` ไป `POST /auth/line` ผ่าน `/docs` หรือ curl แล้วดู terminal ของ backend

สำหรับ token จริง: ตั้ง `NEXT_PUBLIC_LIFF_ID`, เปิด scope `openid` ใน LIFF และตั้ง Endpoint URL ให้ตรงกับหน้าเว็บ จากนั้นเรียก `getLineIdToken()` หลัง init และ login สำเร็จ แล้ว POST ไป backend ต้องส่งหลังกลับจาก login redirect ด้วย หากเรียก API ข้าม origin ให้ตั้ง CORS ตาม origin ที่ใช้จริง และใช้ HTTPS API เมื่อหน้าเว็บเป็น HTTPS

`response` ใน Python เป็น FastAPI Response object สำหรับตั้งค่า HTTP response ไม่ใช่ข้อมูลผู้ใช้จาก LINE การทดสอบนี้ยังไม่ได้ verify token หรือสร้าง session

## การตรวจสอบ

- เรียก handler โดยตรงด้วย token จำลอง: print ทำงาน และคืนค่า None
- การตรวจ HTTP ผ่าน TestClient ยังไม่สำเร็จ เนื่องจากการเรียกค้าง
- ยังไม่ได้ทดสอบ login กับ LINE จริง
