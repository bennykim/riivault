import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "riivault — This Week on Reddit",
  description:
    "Reddit Signal Intelligence — derived, aggregate insight from founder communities. Never raw content.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
