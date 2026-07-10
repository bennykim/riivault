import type { IssueData, Migration, SentimentFocus } from "@/lib/types";
import { linePath } from "@/lib/chart";
import { axisTicks, signedDecimal } from "@/lib/format";

function SentimentPanel({ sentiment }: { sentiment: SentimentFocus }) {
  const values = sentiment.series.map((p) => p.value);
  const { d, lastX, lastY } = linePath(values, {
    w: 560,
    h: 260,
    padX: 6,
    padTop: 14,
    padBottom: 24,
    yMin: -1,
    yMax: 1,
  });
  const [t0, t1, t2] = axisTicks(sentiment.series);
  const zeroY = 14 + ((260 - 14 - 24) * 1) / 2;

  return (
    <section className="panel span6">
      <div className="ph">
        <span>Sentiment curve</span>
        <b>
          {sentiment.label} ·{" "}
          {sentiment.current != null ? signedDecimal(sentiment.current) : "—"}{" "}
          {sentiment.trend}
        </b>
      </div>
      <svg
        className="chart"
        viewBox="0 0 560 260"
        role="img"
        aria-label="Net sentiment over time"
      >
        {[0, 1, 2, 3, 4].map((g) => {
          const y = 14 + (g * (260 - 14 - 24)) / 4;
          return <line key={g} x1="6" y1={y} x2="554" y2={y} stroke="var(--line)" />;
        })}
        <line
          x1="6"
          y1={zeroY}
          x2="554"
          y2={zeroY}
          stroke="var(--faint)"
          strokeDasharray="3 4"
        />
        <text className="axis" x="554" y={zeroY - 6} textAnchor="end">
          neutral
        </text>
        <path
          d={d}
          fill="none"
          stroke="var(--sentiment)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={lastX}
          cy={lastY}
          r="4"
          fill="var(--sentiment)"
          stroke="var(--panel)"
          strokeWidth="2"
        />
        <text className="axis" x="6" y="255">
          {t0}
        </text>
        <text className="axis" x="280" y="255" textAnchor="middle">
          {t1}
        </text>
        <text className="axis" x="554" y="255" textAnchor="end">
          {t2}
        </text>
      </svg>
      <div className="legend">
        <span>
          <i style={{ background: "var(--sentiment)" }}></i>net sentiment
        </span>
      </div>
    </section>
  );
}

function MigrationPanel({ migration }: { migration: Migration }) {
  const maxShare = Math.max(...migration.destinations.map((x) => x.share), 0.0001);

  return (
    <section className="panel span6">
      <div className="ph">
        <span>Community migration</span>
        <b>{migration.title}</b>
      </div>
      <div>
        {migration.destinations.map((dst) => {
          const faint = dst.name.toLowerCase() === "stayed";
          return (
            <div className={`mrow${faint ? " faint" : ""}`} key={dst.name}>
              <span>{dst.name}</span>
              <span className="track">
                <i
                  style={{
                    width: `${Math.round((dst.share / maxShare) * 100)}%`,
                  }}
                ></i>
              </span>
              <span className="mv">{Math.round(dst.share * 100)}%</span>
            </div>
          );
        })}
      </div>
      <div className="legend">
        <span>
          <i style={{ background: "var(--pos)" }}></i>destination share
        </span>
        <span>n = {migration.n} switch-intent threads</span>
      </div>
    </section>
  );
}

export default function SignalCharts({ issue }: { issue: IssueData }) {
  const sentiment = issue.sentiment_focus;
  const migration = issue.migration;
  // Real issues carry no migration analysis yet (Phase 3); render whichever
  // panels have data and hide the section when neither does.
  if (!sentiment && !migration) return null;

  return (
    <>
      {sentiment && <SentimentPanel sentiment={sentiment} />}
      {migration && <MigrationPanel migration={migration} />}
    </>
  );
}
