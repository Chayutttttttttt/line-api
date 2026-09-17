# Preview: อธิบายส่วนที่จำสถานะ Login

- อธิบาย `liff/lib/liff.ts`: `liff.init()` เตรียม SDK, `liff.isLoggedIn()` อ่านสถานะ Login ที่ SDK จัดการ และ `initialization` เก็บ promise เพื่อไม่ init ซ้ำในหน่วยความจำ
- อธิบาย `liff/components/lineloginButton.tsx`: effect ตรวจสถานะหลัง init แล้วส่ง token; `status` เก็บสถานะหน้าจอ, `initialCheck` ป้องกันงานเริ่มต้นซ้ำ และ `requestPending` ป้องกันคลิกซ้ำ
- เมื่อ reload หน้า React state/ref เริ่มใหม่ แล้วตรวจสถานะจาก LIFF อีกครั้ง หากยังล็อกอินจะส่ง token ไป Backend ใหม่
- Backend ใน `components/login.py` ยังรับและ print ข้อมูลแล้วตอบ `received: true` เท่านั้น ไม่มีการ verify token, บันทึกผู้ใช้ หรือสร้าง session/cookie
- งานรอบนี้แก้เฉพาะ `PREVIEW.md` ไม่แก้โค้ดแอป และไม่รันการทดสอบซ้ำเพราะเป็นการอธิบายโค้ด
