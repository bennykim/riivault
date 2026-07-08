import type { IssueData, PainKind } from "@/lib/types";
import { pctLabel, vars } from "@/lib/format";

function tagFor(kind: PainKind): { cls: string; label: string } {
  switch (kind) {
    case "feature_request":
      return { cls: "feat", label: "Feature request" };
    case "switch_intent":
      return { cls: "switch", label: "Switch intent" };
    case "praise":
      return { cls: "feat", label: "Praise" };
    case "bug":
    case "pain_point":
    default:
      return { cls: "pain", label: "Pain point" };
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
          const width = `${Math.round((p.momentum_pct / maxMomentum) * 100)}%`;
          return (
            <div className="fr rv" key={p.fr_id}>
              <div className="rk">{String(p.rank).padStart(2, "0")}</div>
              <div className="txt">
                {p.text}
                <em>normalized · {p.occurrences} distinct threads</em>
              </div>
              <span className={`tag ${tag.cls}`}>{tag.label}</span>
              <div className="occ">
                <b>{p.occurrences}</b> mentions
              </div>
              <div className="mom">
                <span className="track2">
                  <i style={vars({ "--w": width })}></i>
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
