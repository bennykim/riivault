"use client";

import { useEffect } from "react";

/**
 * Reveal controller. Ports the design's scroll-reveal script to React without
 * wrapping elements (so `.feed .fr:nth-child` / `.cards .ecard:nth-child` delay
 * selectors keep working): on mount it measures every `.draw` path for the
 * stroke-draw effect, then adds `.in` to each `.rv` element as it enters view.
 * Renders nothing. Respects prefers-reduced-motion by revealing immediately.
 */
export default function Reveal() {
  useEffect(() => {
    const reduce =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Set --len so the CSS stroke-draw transition has an accurate dash length.
    document.querySelectorAll<SVGPathElement>("path.draw").forEach((p) => {
      try {
        p.style.setProperty("--len", String(p.getTotalLength()));
      } catch {
        /* getTotalLength unsupported — SSR inline --len already covers it */
      }
    });

    const targets = Array.from(document.querySelectorAll<HTMLElement>(".rv"));

    if (reduce || !("IntersectionObserver" in window)) {
      targets.forEach((el) => el.classList.add("in"));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );

    targets.forEach((el) => {
      if (!el.classList.contains("in")) io.observe(el);
    });

    return () => io.disconnect();
  }, []);

  return null;
}
