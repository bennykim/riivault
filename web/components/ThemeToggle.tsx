"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | null; // null = follow system

const STORAGE_KEY = "theme";

function apply(theme: Theme) {
  if (theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
    localStorage.removeItem(STORAGE_KEY);
  }
}

// Cycles auto (follows prefers-color-scheme) -> light -> dark -> auto.
// The :root[data-theme] overrides already exist in globals.css; this is the
// missing piece that actually sets the attribute and persists the choice.
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") setTheme(stored);
  }, []);

  function cycle() {
    const order: Theme[] = [null, "light", "dark"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
    apply(next);
  }

  const label = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "Auto";

  return (
    <button
      type="button"
      className="chip theme-toggle"
      onClick={cycle}
      aria-label={`Theme: ${label}. Click to change.`}
    >
      {label}
    </button>
  );
}
