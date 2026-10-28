/** Plain-language outcomes of the document processing and teacher review workflow. */
export type DocumentState = {
  status: string;
  extraction_error: string | null;
  extraction_warning: string | null;
  purpose?: string;
};

const failureReasons: Record<string, string> = {
  ENCRYPTED_OR_TOO_MANY_PAGES: "PDF มีรหัสป้องกันหรือจำนวนหน้าเกินที่ตั้งไว้ (ค่าเริ่มต้น 40 หน้า) กรุณาตรวจจำนวนหน้าและการเข้ารหัส",
  INVALID_PDF: "ไฟล์ไม่ใช่ PDF ที่ระบบเปิดอ่านได้ กรุณาส่งออก PDF ใหม่",
  PDF_AI_KEY_NOT_CONFIGURED: "ระบบยังไม่ได้ตั้งค่า API Key สำหรับอ่าน PDF โปรดแจ้งผู้ดูแลระบบ",
  PDF_AI_RESPONSE_INVALID: "Gemini ส่งข้อมูลที่ไม่ตรงรูปแบบที่ระบบกำหนด กรุณาลองใช้ PDF ใหม่หรือติดต่อผู้ดูแล",
  PDF_AI_NO_SEARCHABLE_TEXT: "Gemini ไม่พบข้อความที่นำไปทำบทเรียนได้",
  PDF_AI_TEXT_TOO_LARGE: "ข้อความที่อ่านได้มีปริมาณเกินขีดจำกัดระบบ",
  PDF_PAGE_TOO_LONG: "มีหน้า PDF ที่ข้อความยาวเกินขีดจำกัด",
  NO_SEARCHABLE_TEXT: "ไม่พบข้อความที่นำไปสร้าง Chunks ได้",
  EMPTY_OR_TOO_LARGE_TEXT_USE_TEXT_PDF: "เอกสารว่าง หรือมีข้อความมากเกินขีดจำกัด",
  PDF_AI_REQUIRED: "ขั้นตอนอ่าน PDF ด้วย Gemini ไม่ได้รับข้อมูลที่จำเป็น",
  MODEL_SCHEMA_INVALID: "ผลลัพธ์จากโมเดลไม่ตรงรูปแบบที่ระบบต้องการ",
  UNSUPPORTED_FILE: "ไฟล์ชนิดนี้ไม่ได้รับการรองรับ",
};

export function documentOutcome(v: DocumentState) {
  const evidence = v.purpose === "evidence";
  switch (v.status) {
    case "uploaded": return { label: "รับไฟล์แล้ว", detail: "รอ Worker เริ่มอ่านไฟล์ ยังไม่สามารถอนุมัติได้", success: false };
    case "processing": return { label: "กำลังอ่านไฟล์", detail: "Worker กำลังประมวลผล กรุณารีเฟรชสถานะ ยังไม่สามารถอนุมัติได้", success: false };
    case "review": return { label: evidence ? "รับหลักฐานสำเร็จ" : "อ่านไฟล์สำเร็จ", detail: evidence
      ? "เก็บไว้เป็นหลักฐานโครงการ ไม่ใช้ตอบคำถามของ AI"
      : "สร้าง Chunks แล้ว รอครูตรวจหัวข้อ ข้อความ และเลขหน้าก่อนอนุมัติ", success: true };
    case "published": return { label: "อนุมัติแล้ว", detail: "ครูอนุมัติแล้ว AI ใน LINE สามารถค้นข้อมูลจากไฟล์นี้ได้", success: true };
    case "failed": return { label: "อ่านไฟล์ไม่สำเร็จ", detail: failureReasons[v.extraction_error ?? ""] ??
      (v.extraction_error ? `งานล้มเหลว (รหัส: ${v.extraction_error}) กรุณาตรวจ Logs หรือส่งไฟล์ใหม่`
        : "ประมวลผลไม่สำเร็จ กรุณาตรวจ Logs และลองส่งไฟล์ใหม่"), success: false };
    case "withdrawn": return { label: "ถอนการใช้แล้ว", detail: "เอกสารไม่ถูกใช้ตอบคำถามอีก สามารถลบถาวรได้หากไม่มีข้อมูลอื่นอ้างอิง", success: false };
    case "deleting": return { label: "กำลังลบ/รอลบซ้ำ", detail: "เริ่มลบถาวรแล้ว หากไฟล์ยังปรากฏให้ลองกดลบอีกครั้ง หรือแจ้งผู้ดูแลหาก Storage ลบไม่สำเร็จ", success: false };
    default: return { label: v.status, detail: "ไม่สามารถยืนยันผลการประมวลผลได้ กรุณาตรวจสถานะอีกครั้ง", success: false };
  }
}

export function documentDeleteError(error: Error): string {
  const value = error.message;
  if (value.includes("DOCUMENT_JOB_STILL_RUNNING"))
    return "ยังลบไม่ได้: Worker กำลังอ่านไฟล์หรือสร้าง Vector อยู่ โปรดรีเฟรชหลังงานสิ้นสุด";
  if (value.includes("DOCUMENT_USED_BY_QUESTIONS"))
    return "ยังลบไม่ได้: แบบฝึกหัดบางข้อยังอ้างอิงไฟล์นี้ ต้องย้าย/แก้แหล่งอ้างอิงของโจทย์ก่อน";
  if (value.includes("DOCUMENT_USED_BY_EVIDENCE"))
    return "ยังลบไม่ได้: หลักฐานประเมินโครงการยังอ้างอิงไฟล์นี้";
  if (value.includes("WITHDRAW_PUBLISHED_DOCUMENT_FIRST"))
    return "ไฟล์นี้อนุมัติแล้ว กรุณากดถอนการใช้เอกสารก่อนลบถาวร";
  if (value.includes("VERSION_CONFLICT"))
    return "ข้อมูลเปลี่ยนแล้ว กรุณารีเฟรชสถานะก่อนดำเนินการอีกครั้ง";
  if (value.includes("FILE_STORAGE_DELETE_FAILED") || value.includes("FILE_STORAGE_UNAVAILABLE"))
    return "ลบต้นฉบับจาก Storage ไม่สำเร็จ ระบบเก็บรายการไว้ให้ลองลบซ้ำได้";
  return value;
}
