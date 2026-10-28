/** Validated LIFF Rich Menu targets. Never navigate to arbitrary URLs from a query string. */
export const DASHBOARD_VIEWS = [
  "tasks", "practice", "plans", "progress",
  "documents", "acceptance", "course", "settings", "admin",
] as const;

export type DashboardView = (typeof DASHBOARD_VIEWS)[number];

const allowedViews: ReadonlySet<string> = new Set(DASHBOARD_VIEWS);

export function getRequestedDashboardView(search: string): DashboardView | null {
  const view = new URLSearchParams(search).get("view");
  return view && allowedViews.has(view) ? (view as DashboardView) : null;
}

/** Keep the requested tab through the separate LINE login page. */
export function getDashboardHref(search: string): string {
  const view = getRequestedDashboardView(search);
  return view ? `/?view=${view}` : "/";
}
