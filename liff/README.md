# LINE Math LIFF

หน้า `/login` ยืนยัน LINE ID token กับ backend; `/` แสดงถามบทเรียน งาน แบบฝึก แผน ความก้าวหน้า เอกสาร และตั้งค่า ครูที่มีสมาชิกวิชาตามสิทธิ์จะเห็นการจัดเอกสารและหลักฐานตรวจรับ

ตั้ง `NEXT_PUBLIC_LIFF_ID` กับ `NEXT_PUBLIC_API_URL` ตาม `.env.example` และเปิด scope `openid` ใน LIFF ตั้ง backend CORS ให้ตรง origin ของเว็บ

```bash
npm ci
npm run dev
npm run lint
npm run build -- --webpack
npm start
```

การเข้าสู่ระบบต้องใช้ LINE จริง ไม่มีโหมดปลอมตัวเป็นครูใน browser Token อยู่ในหน่วยความจำและยืนยันใหม่หลัง reload หน้า settings แสดง UUID สำหรับให้ผู้ดูแลเพิ่มรายวิชา รายละเอียด provisioning, Railway Bucket และ worker อยู่ใน README ที่ root

Railway ใช้ Root Directory `liff` กับ Dockerfile นี้ กำหนด public variables ก่อน build และใช้ PORT ที่ Railway จัดให้ Next standalone server อ่าน PORT ได้อัตโนมัติ
