"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Pointer-tracked 3D tilt for the emerging-signal cards. Renders the `.ecard`
 * element itself (so `.cards .ecard:nth-child` reveal delays still apply).
 * Tilt is disabled under prefers-reduced-motion.
 */
export default function TiltCard({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useRef(false);

  useEffect(() => {
    reduce.current =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  const onMove = (ev: React.PointerEvent<HTMLDivElement>) => {
    const c = ref.current;
    if (!c || reduce.current) return;
    const r = c.getBoundingClientRect();
    const x = (ev.clientX - r.left) / r.width - 0.5;
    const y = (ev.clientY - r.top) / r.height - 0.5;
    c.style.transform = `rotateY(${(x * 6).toFixed(2)}deg) rotateX(${(-y * 6).toFixed(2)}deg) translateY(-3px)`;
  };

  const onLeave = () => {
    const c = ref.current;
    if (c) c.style.transform = "";
  };

  return (
    <div ref={ref} className={className} onPointerMove={onMove} onPointerLeave={onLeave}>
      {children}
    </div>
  );
}
