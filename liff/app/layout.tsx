import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "เข้าสู่ระบบ | LINE",
  description: "เข้าสู่ระบบด้วยบัญชี LINE เพื่อเชื่อมต่อและเริ่มใช้งาน",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="th"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
