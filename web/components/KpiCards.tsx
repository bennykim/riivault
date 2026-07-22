import type { ReactNode } from "react";
import type { IssueData } from "@/lib/types";
import { pctLabel } from "@/lib/format";
import CountUp from "@/components/fx/CountUp";

function Kpi({
  value,
  delta,
  deltaUp = true,
  label,
}: {
  value: ReactNode;
  delta?: string;
  deltaUp?: boolean;
  label: string;
}) {
  return (
    <div className="kpi">
      <span className="v">{value}</span>
      {delta && <span className={`d ${deltaUp ? "up" : "down"}`}>{delta}</span>}
      <div className="k">{label}</div>
    </div>
  );
}

export default function KpiCards({ issue }: { issue: IssueData }) {
  const { lead } = issue;
  return (
    <div className="span12 kpi-strip">
      <Kpi
        value={<CountUp end={lead.threads} comma />}
        delta={pctLabel(lead.momentum_pct)}
        deltaUp={lead.momentum_pct >= 0}
        label="Threads synthesized"
      />
      {lead.comments != null && (
        <Kpi value={<CountUp end={lead.comments} comma />} label="Comments analyzed" />
      )}
      <Kpi value={<CountUp end={issue.sources.length} />} label="Sources tracked" />
      <Kpi
        value={<CountUp end={lead.delta_value} />}
        delta={lead.delta_label}
        label="Mention index · this week"
      />
    </div>
  );
}
