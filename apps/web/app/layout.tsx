import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Uzbek Local Voice AI", description: "Mahalliy va oflayn o‘zbek ovozli yordamchi" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="uz"><body>{children}</body></html>; }
