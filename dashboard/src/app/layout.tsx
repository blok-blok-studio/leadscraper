import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Sidebar } from "@/components/layout/sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LeadScraper Dashboard",
  description: "US Local Business Lead Scraper — Bloblok Studio",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} antialiased`}>
        <Sidebar />
        <main className="ml-60 min-h-screen bg-background p-8">
          {children}
        </main>
      </body>
    </html>
  );
}
