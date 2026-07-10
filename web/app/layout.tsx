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

// Runs before hydration so a stored light/dark choice applies without a
// flash of the system-default theme. No-op when the user never overrode it,
// leaving `prefers-color-scheme` in globals.css in control.
const THEME_INIT = `(function(){try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={figtree.variable} suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
        {children}
      </body>
    </html>
  );
}
