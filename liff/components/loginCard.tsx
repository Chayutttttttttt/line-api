import LineLoginButton from "@/components/lineloginButton";

import { FaLine } from "react-icons/fa6";
import { TbLockPassword } from "react-icons/tb";

export default function LoginCard() {
  return (
    <section
      aria-labelledby="login-title"
      className="w-full max-w-[440px] overflow-hidden rounded-[18px] border border-[#E9EDF4] bg-white shadow-[0_1px_2px_rgba(25,35,60,0.04),0_6px_20px_rgba(41,54,129,0.06)]"
    >
      <div className="flex items-center justify-between border-b border-border bg-surface-soft px-6 py-4 sm:px-8">
        <span className="text-sm font-semibold text-brand-navy">LINE Login</span>
        <span className="rounded-full bg-brand-mint px-3 py-1 text-xs font-medium text-brand-navy">
          ยินดีต้อนรับ
        </span>
      </div>

      <div className="px-6 py-8 sm:p-8">
        <div
          aria-hidden="true"
          className="mb-6 flex size-16 items-center justify-center rounded-[18px] border border-brand-sky/40 bg-[#E7F3F7] text-brand-navy"
        >
          <FaLine className="w-full h-full" />
        </div>

        <h1 id="login-title" className="text-[28px] leading-[1.5] font-bold text-brand-navy">
          เริ่มต้นใช้งานด้วย LINE
        </h1>
        <p className="mt-3 text-base leading-relaxed text-secondary">
          เข้าสู่ระบบด้วยบัญชี LINE ของคุณ
          <br />
          เพื่อเชื่อมต่อและเริ่มใช้งาน
        </p>

        <div className="mt-8">
          <LineLoginButton />
        </div>

        <div className="mt-6 flex items-start gap-3 border-t border-border pt-6 text-sm leading-relaxed text-secondary">
          <TbLockPassword className="text-2xl"/>
          <p>ยืนยันตัวตนผ่าน LINE<br />ไม่ต้องกรอกรหัสผ่านในหน้านี้</p>
        </div>
      </div>
    </section>
  );
}
