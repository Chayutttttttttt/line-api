"use client";

import { useEffect, useId, useRef, useState } from "react";
import { IoCheckmarkCircleOutline, IoLogIn, IoReloadOutline } from "react-icons/io5";
import { initliff, isLineLoggedIn, loginWithLine } from "@/lib/liff";

const liffId = process.env.NEXT_PUBLIC_LIFF_ID;

export default function LineLoginButton() {
  const [status, setStatus] = useState<"idle" | "checking" | "loading" | "success" | "error">(
    liffId ? "checking" : "idle",
  );
  const requestPending = useRef(false);
  const messageId = useId();
  const isBusy = status === "checking" || status === "loading";

  useEffect(() => {
    if (!liffId) return;
    let cancelled = false;

    initliff().then(
      () => {
        if (!cancelled) setStatus(isLineLoggedIn() ? "success" : "idle");
      },
      () => {
        if (!cancelled) setStatus("error");
      },
    );

    return () => { cancelled = true; };
  }, []);

  async function handleLogin() {
    if (requestPending.current || isBusy || status === "success") return;
    if (!liffId) {
      setStatus("error");
      return;
    }

    requestPending.current = true;
    setStatus("loading");

    try {
      await initliff();
      if (isLineLoggedIn()) {
        setStatus("success");
        requestPending.current = false;
      } else {
        loginWithLine();
      }
    } catch {
      requestPending.current = false;
      setStatus("error");
    }
  }

  const label = status === "checking" ? "กำลังตรวจสอบบัญชี…"
    : status === "loading" ? "กำลังเข้าสู่ระบบ…"
    : status === "success" ? "เชื่อมต่อกับ LINE แล้ว"
    : status === "error" ? "ลองเข้าสู่ระบบอีกครั้ง"
    : "เข้าสู่ระบบด้วย LINE";

  return (
    <div>
      <button
        type="button"
        onClick={handleLogin}
        disabled={isBusy || status === "success"}
        aria-busy={isBusy}
        aria-describedby={status === "error" ? messageId : undefined}
        className={`flex min-h-12 w-full items-center justify-center gap-3 rounded-[14px] px-[18px] py-3 text-base leading-relaxed font-semibold transition-[background-color,transform,opacity] duration-150 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-blue enabled:active:scale-[0.98] disabled:cursor-default motion-reduce:transform-none motion-reduce:transition-none ${status === "success" ? "bg-brand-mint text-brand-navy" : "bg-brand-blue text-white enabled:hover:bg-[#3663BD] disabled:opacity-45"}`}
      >
        {isBusy ? (
          <IoReloadOutline aria-hidden="true" className="size-6 shrink-0 animate-spin motion-reduce:animate-none" />
        ) : status === "success" ? (
          <IoCheckmarkCircleOutline aria-hidden="true" className="size-6 shrink-0" />
        ) : (
          <IoLogIn aria-hidden="true" className="size-6 shrink-0" />
        )}
        <span>{label}</span>
      </button>
      <p className="sr-only" role="status">{label}</p>
      {status === "error" ? (
        <p id={messageId} role="alert" className="mt-3 rounded-xl border border-danger/25 bg-[#FFF5F5] p-3 text-sm leading-relaxed text-[#A52D2D]">
          {liffId
            ? "เชื่อมต่อ LINE ไม่สำเร็จ กรุณาตรวจสอบอินเทอร์เน็ตแล้วลองอีกครั้ง"
            : "ขณะนี้ยังไม่สามารถเข้าสู่ระบบได้ กรุณาลองใหม่ภายหลังหรือติดต่อผู้ดูแล"}
        </p>
      ) : null}
    </div>
  );
}
