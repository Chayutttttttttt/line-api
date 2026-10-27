import liff from "@line/liff";
import { isIdTokenExpired } from "./tokenExpiry";

let initialization: Promise<void> | undefined;

export async function initliff() {
  const liffId = process.env.NEXT_PUBLIC_LIFF_ID;
  if (!liffId) throw new Error("NEXT_PUBLIC_LIFF_ID not defined");

  if (!initialization) {
    initialization = liff.init({ liffId }).catch((error: unknown) => {
      initialization = undefined;
      throw error;
    });
  }
  await initialization;
}

export function loginWithLine() {
  // liff.login() is not supported inside the LIFF browser.
  if (!liff.isInClient() && !liff.isLoggedIn()) liff.login();
}

/** Only invoke from an explicit user click, never from mount/effect. */
export function restartLineLogin(): boolean {
  if (liff.isInClient()) return false;
  if (liff.isLoggedIn()) liff.logout();
  liff.login();
  return true;
}

export function logoutLine() {
  if (liff.isLoggedIn()) liff.logout();
}

export function getLineIdToken() {
  return liff.getIDToken();
}

export function isLineIdTokenExpired() {
  return isIdTokenExpired(liff.getDecodedIDToken()?.exp);
}

export function isLineLoggedIn() {
  return liff.isLoggedIn();
}

export function isLineInClient() {
  return liff.isInClient();
}
