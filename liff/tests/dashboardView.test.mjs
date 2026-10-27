import assert from "node:assert/strict";
import test from "node:test";
import { getRequestedDashboardView, getDashboardHref } from "../lib/dashboardView.ts";

test("opens every supported Rich Menu target", () => {
  for (const view of ["ask", "tasks", "practice", "plans", "progress", "documents", "settings", "course", "acceptance"]) {
    assert.equal(getRequestedDashboardView(`?view=${view}`), view);
    assert.equal(getDashboardHref(`?view=${view}`), `/?view=${view}`);
  }
});
test("falls back safely for no view or unsupported destinations", () => {
  assert.equal(getRequestedDashboardView(""), null);
  assert.equal(getDashboardHref(""), "/");
  for (const search of ["?view=home", "?view=../../admin", "?view=javascript:alert(1)", "?view=foo", "?view="]) {
    assert.equal(getRequestedDashboardView(search), null);
    assert.equal(getDashboardHref(search), "/");
  }
});
test("ignores other LIFF SDK and unrelated query parameters", () => {
  assert.equal(getRequestedDashboardView("?liff.referrer=x&view=practice&campaign=1"), "practice");
  assert.equal(getDashboardHref("?liff.referrer=x&view=practice"), "/?view=practice");
});
