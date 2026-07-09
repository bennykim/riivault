import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Figtree } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const figtree = Figtree({ subsets: ["latin"], variable: "--font-figtree" });

export const metadata: Metadata = {
  title: "riivault — This Week on Reddit",
  description:
    "Reddit Signal Intelligence — derived, aggregate insight from founder communities. Never raw content.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // data-astryx-theme on <html> makes the @scope'd theme tokens available
  // from the first SSR paint (the client Theme provider re-syncs the same
  // attribute); tokens must exist at the root for body/chart styling.
  return (
    <html lang="en" data-astryx-theme="neutral" className={figtree.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
