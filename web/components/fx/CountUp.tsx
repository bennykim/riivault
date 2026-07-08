"use client";

import { useEffect, useRef, useState } from "react";

function format(value: number, comma: boolean, dec: number): string {
  if (dec) return value.toFixed(dec);
  return comma
    ? Math.round(value).toLocaleString("en-US")
    : String(Math.round(value));
}

/**
 * Animated number. Renders the final formatted value on the server (correct for
 * no-JS / SEO) and counts up from 0 over 1300ms with a cubic ease-out once it
 * scrolls into view. Reduced-motion shows the final value immediately.
 */
export default function CountUp({
  end,
  comma = false,
  dec = 0,
}: {
  end: number;
  comma?: boolean;
  dec?: number;
}) {
  const [display, setDisplay] = useState(() => format(end, comma, dec));
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setDisplay(format(end, comma, dec));
      return;
    }

    const run = () => {
      if (started.current) return;
      started.current = true;
      const dur = 1300;
      let t0: number | null = null;
      const step = (ts: number) => {
        if (t0 === null) t0 = ts;
        const k = Math.min((ts - t0) / dur, 1);
        const eased = 1 - Math.pow(1 - k, 3);
        setDisplay(format(end * eased, comma, dec));
        if (k < 1) requestAnimationFrame(step);
        else setDisplay(format(end, comma, dec));
      };
      requestAnimationFrame(step);
    };

    if (!("IntersectionObserver" in window)) {
      run();
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            run();
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [end, comma, dec]);

  return <span ref={ref}>{display}</span>;
}
