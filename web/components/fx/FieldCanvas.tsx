"use client";

import { useEffect, useRef, useState } from "react";

interface Point {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

/**
 * Ambient signal field: drifting particles linked by faint lines. Ported from
 * the design's canvas script, with proper teardown. Not rendered under
 * prefers-reduced-motion.
 */
export default function FieldCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    const reduce =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setEnabled(false);
      return;
    }

    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    let W = 0;
    let H = 0;
    let DPR = 1;
    let pts: Point[] = [];
    let raf = 0;
    let resizeTimer: ReturnType<typeof setTimeout> | undefined;

    const size = () => {
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = cv.width = window.innerWidth * DPR;
      H = cv.height = window.innerHeight * DPR;
      cv.style.width = window.innerWidth + "px";
      cv.style.height = window.innerHeight + "px";
    };

    const init = () => {
      pts = [];
      const n = Math.min(52, Math.round(window.innerWidth / 26));
      for (let i = 0; i < n; i++) {
        pts.push({
          x: Math.random() * W,
          y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.1 * DPR,
          vy: (Math.random() - 0.5) * 0.1 * DPR,
        });
      }
    };

    const tick = () => {
      ctx.clearRect(0, 0, W, H);
      const lim = 118 * DPR;
      for (let i = 0; i < pts.length; i++) {
        const p = pts[i];
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x += W;
        if (p.x > W) p.x -= W;
        if (p.y < 0) p.y += H;
        if (p.y > H) p.y -= H;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.2 * DPR, 0, 6.283);
        ctx.fillStyle = "rgba(210,78,31,.4)";
        ctx.fill();
        for (let j = i + 1; j < pts.length; j++) {
          const q = pts[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < lim) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = "rgba(27,28,34," + 0.05 * (1 - d / lim) + ")";
            ctx.lineWidth = DPR * 0.6;
            ctx.stroke();
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };

    const onResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        cancelAnimationFrame(raf);
        size();
        init();
        tick();
      }, 200);
    };

    size();
    init();
    tick();
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(resizeTimer);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  if (!enabled) return null;
  return <canvas id="field" ref={ref} aria-hidden="true" />;
}
