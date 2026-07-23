import Link from "next/link";
import type { IssueData } from "@/lib/types";

function Items({ issue }: { issue: IssueData }) {
  return (
    <>
      {issue.tracked.map((t) => {
        const up = t.change_pct != null && t.change_pct >= 0;
        return (
          <span className="tk" key={t.entity_id}>
            <b>
              <Link href={`/e/${t.entity_id}`}>{t.name}</Link>
            </b>
            {t.context && <span className="s">{t.context}</span>}
            <span className={up ? "up" : "down"}>
              {t.change_pct == null
                ? "—"
                : `${up ? "▲" : "▼"}${Math.abs(Math.round(t.change_pct))}%`}
            </span>
          </span>
        );
      })}
      <span className="tk">
        <b>MENTION INDEX</b>
        <span className="up">▲{issue.lead.delta_value}</span>
      </span>
      {issue.sentiment_focus?.current != null && (
        <span className="tk">
          <b>SENTIMENT {issue.sentiment_focus.label.toUpperCase()}</b>
          <span className={issue.sentiment_focus.current >= 0 ? "up" : "down"}>
            {issue.sentiment_focus.current >= 0 ? "▲" : "▼"}
            {Math.abs(issue.sentiment_focus.current).toFixed(2)}
          </span>
        </span>
      )}
    </>
  );
}

// Marquee duplicates its content once so the -50% keyframe loops seamlessly.
export default function Ticker({ issue }: { issue: IssueData }) {
  return (
    <div className="ticker" aria-label="Tracked entities ticker">
      <div className="ticker-track">
        <Items issue={issue} />
        <Items issue={issue} />
      </div>
    </div>
  );
}
