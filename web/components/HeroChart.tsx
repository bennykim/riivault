import type { Lead } from "@/lib/types";
import { linePath } from "@/lib/chart";
import { axisTicks, vars } from "@/lib/format";
import CountUp from "@/components/fx/CountUp";

export default function HeroChart({ lead }: { lead: Lead }) {
  const values = lead.series.map((p) => p.value);
  const { d, areaD, lastX, lastY, len } = linePath(values, {
    w: 520,
    h: 232,
    padX: 20,
    padTop: 30,
    padBottom: 57,
    baseline: 210,
  });
  const [t0, t1, t2] = axisTicks(lead.series);

  return (
    <figure className="herofig rv s4" id="heroChart">
      <div className="figtop">
        <span className="t">{lead.chart_title}</span>
        <span className="v tnum">
          ▲ <CountUp end={lead.delta_value} /> this wk ({lead.delta_label})
        </span>
      </div>
      <svg
        className="chart"
        viewBox="0 0 520 232"
        role="img"
        aria-label="Weekly mention index rising sharply over 12 weeks"
      >
        <defs>
          <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#D24E1F" stopOpacity="0.20" />
            <stop offset="1" stopColor="#D24E1F" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="20" y1="50" x2="500" y2="50" stroke="var(--grid)" />
        <line x1="20" y1="90" x2="500" y2="90" stroke="var(--grid)" />
        <line x1="20" y1="130" x2="500" y2="130" stroke="var(--grid)" />
        <line x1="20" y1="170" x2="500" y2="170" stroke="var(--grid)" />
        <path className="area-in" d={areaD} fill="url(#fill)" />
        <path
          className="draw"
          id="heroLine"
          d={d}
          fill="none"
          stroke="#D24E1F"
          strokeWidth="2.2"
          strokeLinejoin="round"
          strokeLinecap="round"
          style={vars({ "--len": len })}
        />
        <circle
          className="dot-in"
          cx={lastX}
          cy={lastY}
          r="4.5"
          fill="#D24E1F"
          stroke="#FBFBF8"
          strokeWidth="2"
        />
        <text className="axis" x="20" y="226">
          {t0}
        </text>
        <text className="axis" x="240" y="226" textAnchor="middle">
          {t1}
        </text>
        <text className="axis" x="500" y="226" textAnchor="end">
          {t2}
        </text>
      </svg>
    </figure>
  );
}
