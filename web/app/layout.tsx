import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Figtree } from "next/font/google";
import "./globals.css";

const figtree = Figtree({ subsets: ["latin"], variable: "--font-figtree" });

export const metadata: Metadata = {
  title: "riivault · This Week on Reddit",
  description:
    "Reddit Signal Intelligence. Derived, aggregate insight from founder communities. Never raw content.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={figtree.variable}>
      <body>{children}</body>
    </html>
  );
}
