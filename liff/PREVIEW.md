# Preview: ใช้ react-icons และเรียก LIFF helpers โดยตรง

## สิ่งที่เปลี่ยน

- `liff/components/lineloginButton.tsx`: ใช้ `IoLogIn`, `IoReloadOutline` และ `IoCheckmarkCircleOutline` จาก `react-icons/io5` แทน SVG ที่เขียนเองและ spinner เดิม ขนาด 24px พร้อม `aria-hidden` และรองรับ reduced motion
- Import `initliff`, `isLineLoggedIn`, `loginWithLine` จาก `@/lib/liff` โดยตรง แทน dynamic import และ wrapper ใน component
- `liff/lib/liff.ts`: ย้ายการเก็บ initialization promise มาไว้ใน `initliff()` ป้องกันการ init ซ้ำ และล้าง promise เมื่อเกิดข้อผิดพลาดเพื่อให้ลองใหม่ได้
- `PREVIEW.md` และ `liff/PREVIEW.md`: อัปเดตสรุปงานล่าสุด

## หมายเหตุ

ฟังก์ชันใน `liff.ts` เป็น named exports (`export function`) จึง import ด้วยชื่อใน `{ ... }` ได้หลายตัว ส่วน `export default` มีได้หนึ่งรายการต่อไฟล์ ไม่จำเป็นต้องเปลี่ยนเป็น default export

เปิดหน้า `/login` เพื่อดูผล การตั้งค่า `NEXT_PUBLIC_LIFF_ID` และพฤติกรรม login/loading/error/success ยังใช้แบบเดิม

## การตรวจสอบ

- TypeScript ผ่าน (`tsc --noEmit --incremental false`)
- ESLint ผ่านเฉพาะสองไฟล์โค้ดที่แก้ไข
- Production build ด้วย Webpack ผ่าน รวมการ prerender หน้า `/login` เมื่อ import LIFF โดยตรง
- ยังไม่ได้ทดสอบ OAuth กับบัญชี LINE จริงหรือภาพในเบราว์เซอร์
