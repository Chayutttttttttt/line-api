import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ผู้ช่วยเรียน | LINE",
  description: "เรียนและฝึกทุกวิชาจากเอกสารที่ครูอนุมัติ พร้อมหลักฐานตรวจรับก่อนนำร่อง",
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
