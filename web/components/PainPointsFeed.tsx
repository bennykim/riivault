import { Badge } from "@astryxdesign/core/Badge";
import type { BadgeVariant } from "@astryxdesign/core/Badge";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import type { IssueData, PainKind } from "@/lib/types";
import { pctLabel } from "@/lib/format";

function tagFor(kind: PainKind): { variant: BadgeVariant; label: string } {
  switch (kind) {
    case "feature_request":
      return { variant: "success", label: "Feature request" };
    case "switch_intent":
      return { variant: "warning", label: "Switch intent" };
    case "praise":
      return { variant: "success", label: "Praise" };
    case "bug":
    case "pain_point":
    default:
      return { variant: "info", label: "Pain point" };
  }
}

export default function PainPointsFeed({ issue }: { issue: IssueData }) {
  const points = issue.pain_points;
  const maxMomentum = Math.max(...points.map((p) => p.momentum_pct), 1);

  return (
    <section className="blk">
      <div className="sechead rv">
        <h2>Rising pain points</h2>
        <span className="sub">
          Ranked by momentum · last 7 days · {issue.niche} niche
        </span>
      </div>
      <div className="feed">
        {points.map((p) => {
          const tag = tagFor(p.kind);
          return (
            <div className="fr rv" key={p.fr_id}>
              <div className="rk">{String(p.rank).padStart(2, "0")}</div>
              <div className="txt">
                {p.text}
                <em>normalized · {p.occurrences} distinct threads</em>
              </div>
              <span className="tagcell">
                <Badge variant={tag.variant} label={tag.label} />
              </span>
              <div className="occ">
                <b>{p.occurrences}</b> mentions
              </div>
              <div className="mom">
                <span className="mombar">
                  <ProgressBar
                    value={p.momentum_pct}
                    max={maxMomentum}
                    label="Momentum"
                    isLabelHidden
                    variant="accent"
                  />
                </span>
                <span className="pct tnum">{pctLabel(p.momentum_pct)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
