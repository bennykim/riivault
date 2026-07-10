import type { Lead } from "@/lib/types";
import { linePath } from "@/lib/chart";
import { axisTicks, vars } from "@/lib/format";

export default function HeroChart({ lead }: { lead: Lead }) {
  const values = lead.series.map((p) => p.value);
  const { d, areaD, lastX, lastY } = linePath(values, {
    w: 820,
    h: 300,
    padX: 6,
    padTop: 14,
    padBottom: 24,
    baseline: 276,
  });
  const [t0, t1, t2] = axisTicks(lead.series);

  return (
    <section className="panel span8">
      <div className="ph">
        <span>{lead.chart_title}</span>
        <b className="up">
          ▲ {lead.delta_value} · {lead.delta_label}
        </b>
      </div>
      <svg
        className="chart"
        viewBox="0 0 820 300"
        role="img"
        aria-label="Weekly mention index over the tracking window"
      >
        {[0, 1, 2, 3, 4].map((g) => {
          const y = 14 + (g * (300 - 14 - 24)) / 4;
          return <line key={g} x1="6" y1={y} x2="814" y2={y} stroke="var(--line)" />;
        })}
        <path d={areaD} fill="var(--primary)" opacity="0.09" />
        <path
          d={d}
          fill="none"
          stroke="var(--primary)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={lastX}
          cy={lastY}
          r="4"
          fill="var(--primary)"
          stroke="var(--panel)"
          strokeWidth="2"
        />
        <text className="axis" x="6" y="295">
          {t0}
        </text>
        <text className="axis" x="410" y="295" textAnchor="middle">
          {t1}
        </text>
        <text className="axis" x="814" y="295" textAnchor="end">
          {t2}
        </text>
      </svg>
      <div className="legend">
        <span>
          <i style={{ background: "var(--primary)" }}></i>mention index
        </span>
        <span>
          {t0} .. {t2}
        </span>
      </div>
    </section>
  );
}
