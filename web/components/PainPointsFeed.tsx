import type { IssueData, PainKind } from "@/lib/types";
import { pctLabel } from "@/lib/format";

function tagFor(kind: PainKind): { cls: string; label: string } {
  switch (kind) {
    case "feature_request":
      return { cls: "ok", label: "Feature request" };
    case "switch_intent":
      return { cls: "warn", label: "Switch intent" };
    case "praise":
      return { cls: "ok", label: "Praise" };
    case "bug":
    case "pain_point":
    default:
      return { cls: "", label: "Pain point" };
  }
}

export default function PainPointsFeed({ issue }: { issue: IssueData }) {
  const points = issue.pain_points;
  const maxMomentum = Math.max(...points.map((p) => p.momentum_pct), 1);

  return (
    <section className="panel span12">
      <div className="ph">
        <span>Rising pain points</span>
        <b>
          ranked by momentum · last 7d · {issue.niche} niche
        </b>
      </div>
      <table className="ptab">
        <thead>
          <tr>
            <th>#</th>
            <th>Pain point</th>
            <th className="hide-sm">Kind</th>
            <th className="r hide-sm">Mentions</th>
            <th className="r">Momentum</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => {
            const tag = tagFor(p.kind);
            const w = Math.round((p.momentum_pct / maxMomentum) * 100);
            return (
              <tr key={p.fr_id}>
                <td className="rank">{String(p.rank).padStart(2, "0")}</td>
                <td className="txt sans">{p.text}</td>
                <td className="hide-sm">
                  <span className={`kindtag ${tag.cls}`}>{tag.label}</span>
                </td>
                <td className="r hide-sm">{p.occurrences}</td>
                <td className="r">
                  <span className="mom">
                    <span
                      className="bar"
                      style={{
                        background: `linear-gradient(to right, var(--primary) ${w}%, var(--panel2) ${w}%)`,
                      }}
                    ></span>
                    <span className="pv">{pctLabel(p.momentum_pct)}</span>
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
