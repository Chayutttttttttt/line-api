/** Preflight only: LINE still verifies the signed ID token on the backend. */
export function isIdTokenExpired(exp: unknown, nowSeconds = Date.now() / 1000): boolean {
  // A missing/malformed expiry must never be sent as an apparently valid token.
  return typeof exp !== "number" || !Number.isFinite(exp) || exp <= nowSeconds + 60;
}
