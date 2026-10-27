"use client";

import { getLineIdToken, initliff, isLineIdTokenExpired, isLineLoggedIn } from "./liff";

const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
let token: string | undefined;
let expiresAt = 0;
let pendingLogin: Promise<void> | undefined;

export class LineReauthenticationRequired extends Error {
  constructor(message = "เซสชัน LINE หมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง") {
    super(message);
    this.name = "LineReauthenticationRequired";
  }
}

export async function verifyLineLogin() {
  if (token && Date.now() < expiresAt) return;
  pendingLogin ??= (async () => {
    if (!base) throw new Error("ยังไม่ได้ตั้งค่า API URL");
    await initliff();
    if (!isLineLoggedIn()) throw new Error("กรุณาเข้าสู่ระบบด้วย LINE");
    const idToken = getLineIdToken();
    if (!idToken) throw new Error("ไม่พบ LINE ID token โปรดเปิด scope openid");
    // A decoded claim is only a preflight check. The API must verify the JWT.
    if (isLineIdTokenExpired()) throw new LineReauthenticationRequired();
    const response = await fetch(`${base}/auth/line`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: idToken }), signal: AbortSignal.timeout(15000),
    });
    const result = await response.json().catch(() => ({}));
    if (response.status === 401 && result.code === "INVALID_LINE_TOKEN") {
      throw new LineReauthenticationRequired("LINE ไม่ยอมรับ ID token กรุณาเข้าสู่ระบบใหม่");
    }
    if (!response.ok || !result.access_token) throw new Error(result.message ?? "ยืนยัน LINE ไม่สำเร็จ");
    token = result.access_token;
    expiresAt = Date.now() + Math.max(0, result.expires_in - 60) * 1000;
  })().finally(() => { pendingLogin = undefined; });
  return pendingLogin;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  await verifyLineLogin();
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${base}${path}`, { ...options, headers, cache: "no-store", signal: options.signal ?? AbortSignal.timeout(45000) });
  if (response.status === 401) { token = undefined; expiresAt = 0; }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(`${error.message ?? "ทำรายการไม่สำเร็จ"}${error.request_id ? ` (${error.request_id})` : ""}`);
  }
  if (path.endsWith("/file")) return await response.blob() as T;
  return response.json();
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
