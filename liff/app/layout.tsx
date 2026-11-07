import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ผู้ช่วยเรียน | LINE",
  description: "เข้าสู่ระบบและตั้งค่ารายวิชา เพื่อทำข้อสอบ ขอคำใบ้ และถามบทเรียนในแชต LINE",
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
