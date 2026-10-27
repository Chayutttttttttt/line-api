"use client";

import { useEffect, useId, useRef, useState } from "react";
import { IoCheckmarkCircleOutline, IoLogIn, IoReloadOutline } from "react-icons/io5";
import {
  initliff, isLineIdTokenExpired, isLineInClient, isLineLoggedIn,
  loginWithLine, restartLineLogin,
} from "@/lib/liff";

const liffId = process.env.NEXT_PUBLIC_LIFF_ID;
type Status = "idle" | "checking" | "loading" | "success" | "expired" | "reopen" | "error";
import { LineReauthenticationRequired, verifyLineLogin } from "@/lib/api";
import Link from "next/link";

export default function LineLoginButton() {
  const [status, setStatus] = useState<Status>(liffId ? "checking" : "idle");
  const [errorMessage, setErrorMessage] = useState("");
  const requestPending = useRef(false);
  const initialCheck = useRef<Promise<"success" | "idle" | "expired"> | null>(null);
  const messageId = useId();
  const isBusy = status === "checking" || status === "loading";

  useEffect(() => {
    if (!liffId) return;
    let cancelled = false;

    // No automatic login redirects: an expired token is shown to the user.
    // Memoize for React Strict Mode effect replay.
    initialCheck.current ??= initliff().then(async () => {
      if (!isLineLoggedIn()) return "idle";
      try {
        await verifyLineLogin();
        return "success";
      } catch (error) {
        if (error instanceof LineReauthenticationRequired) return "expired";
        throw error;
      }
    });

    initialCheck.current.then(
      (nextStatus) => { if (!cancelled) setStatus(nextStatus); },
      (error: unknown) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "เชื่อมต่อ LINE ไม่สำเร็จ");
          setStatus("error");
        }
      },
    );
    return () => { cancelled = true; };
  }, []);

  async function handleLogin() {
    if (requestPending.current || isBusy || status === "success" || status === "reopen") return;
    if (!liffId) { setStatus("error"); return; }

    requestPending.current = true;
    setStatus("loading");
    setErrorMessage("");
    try {
      await initliff();
      if (!isLineLoggedIn()) {
        if (isLineInClient()) setStatus("reopen");
        else loginWithLine();
        return;
      }

      if (status === "expired" || isLineIdTokenExpired()) {
        // LINE's LIFF browser doesn't support liff.login(). Ask the user to
        // close/reopen the LIFF app instead of triggering a redirect loop.
        if (!restartLineLogin()) setStatus("reopen");
        return;
      }

      try {
        await verifyLineLogin();
        setStatus("success");
      } catch (error) {
        if (error instanceof LineReauthenticationRequired) {
          if (!restartLineLogin()) setStatus("reopen");
          return;
        }
        throw error;
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "เชื่อมต่อ LINE ไม่สำเร็จ");
      setStatus("error");
    } finally {
      requestPending.current = false;
    }
  }

  const label = status === "checking" ? "กำลังตรวจสอบบัญชี…"
    : status === "loading" ? "กำลังเข้าสู่ระบบ…"
    : status === "success" ? "ยืนยันบัญชี LINE สำเร็จ"
    : status === "expired" ? "เข้าสู่ระบบ LINE ใหม่"
    : status === "reopen" ? "กรุณาเปิด LIFF ใหม่"
    : status === "error" ? "ลองเข้าสู่ระบบอีกครั้ง"
    : "เข้าสู่ระบบด้วย LINE";

  return (
    <div>
      <button
        type="button"
        onClick={handleLogin}
        disabled={isBusy || status === "success" || status === "reopen"}
        aria-busy={isBusy}
        aria-describedby={["expired", "reopen", "error"].includes(status) ? messageId : undefined}
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
      {status === "success" && <Link href="/" className="mt-4 block text-center font-semibold text-brand-blue underline">เปิดผู้ช่วยเรียน</Link>}
      <p className="sr-only" role="status">{label}</p>
      {["expired", "reopen", "error"].includes(status) && (
        <p id={messageId} role="alert" className="mt-3 rounded-xl border border-danger/25 bg-[#FFF5F5] p-3 text-sm leading-relaxed text-[#A52D2D]">
          {status === "expired" ? "เซสชัน LINE หมดอายุหรือไม่ถูกยอมรับ กดปุ่มเพื่อเข้าสู่ระบบใหม่"
            : status === "reopen" ? "LINE ภายในแอปไม่รองรับการเรียก Login ซ้ำ กรุณาปิดหน้านี้และเปิด LIFF URL ผ่านแชต LINE อีกครั้ง"
            : errorMessage || "เชื่อมต่อ LINE หรือส่งข้อมูลไม่สำเร็จ กรุณาลองอีกครั้ง"}
        </p>
      )}
    </div>
  );
}
