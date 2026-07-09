import { Card } from "@astryxdesign/core/Card";
import type { IssueData, Migration, SentimentFocus } from "@/lib/types";
import { linePath } from "@/lib/chart";
import { axisTicks, signedDecimal, vars } from "@/lib/format";

function SentimentPanel({ sentiment }: { sentiment: SentimentFocus }) {
  const values = sentiment.series.map((p) => p.value);
  const { d, lastX, lastY, len } = linePath(values, {
    w: 500,
    h: 200,
    padX: 20,
    padTop: 20,
    padBottom: 20,
    yMin: -1,
    yMax: 1,
  });
  const [t0, t1, t2] = axisTicks(sentiment.series);

  return (
    <Card className="panel rv" id="sentCard">
      <div className="ph">
        <span className="t">Sentiment curve</span>
        <span className="s">{sentiment.label}</span>
      </div>
      <svg
        className="chart"
        viewBox="0 0 500 200"
        role="img"
        aria-label="Net sentiment over time"
      >
        <line
          x1="18"
          y1="100"
          x2="482"
          y2="100"
          stroke="var(--grid)"
          strokeDasharray="4 4"
        />
        <text className="axis" x="482" y="96" textAnchor="end">
          neutral
        </text>
        <path
          className="draw"
          id="sentLine"
          d={d}
          fill="none"
          stroke="var(--neg)"
          strokeWidth="2.2"
          strokeLinejoin="round"
          style={vars({ "--len": len })}
        />
        <circle
          className="dot-in"
          cx={lastX}
          cy={lastY}
          r="4.5"
          fill="var(--neg)"
          stroke="var(--card)"
          strokeWidth="2"
        />
        <text className="axis" x="20" y="196">
          {t0}
        </text>
        <text className="axis" x="250" y="196" textAnchor="middle">
          {t1}
        </text>
        <text className="axis" x="480" y="196" textAnchor="end">
          {t2}
        </text>
      </svg>
      <div className="legend">
        <span>
          <i style={{ background: "var(--neg)" }}></i>net sentiment
        </span>
        <span>
          {sentiment.current != null ? signedDecimal(sentiment.current) : "—"}{" "}
          &amp; {sentiment.trend}
        </span>
      </div>
    </Card>
  );
}

function MigrationPanel({ migration }: { migration: Migration }) {
  const maxShare = Math.max(...migration.destinations.map((x) => x.share), 0.0001);

  return (
    <Card className="panel rv">
      <div className="ph">
        <span className="t">Community migration</span>
        <span className="s">{migration.title}</span>
      </div>
      <div className="mig">
        {migration.destinations.map((dst) => {
          const width = `${Math.round((dst.share / maxShare) * 100)}%`;
          const faint = dst.name.toLowerCase() === "stayed";
          return (
            <div className="mrow" key={dst.name}>
              <span>{dst.name}</span>
              <span className="tk">
                <i
                  style={
                    faint
                      ? vars({ "--w": width, background: "var(--faint)" })
                      : vars({ "--w": width })
                  }
                ></i>
              </span>
              <span>{Math.round(dst.share * 100)}%</span>
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
    </Card>
  );
}

export default function SignalCharts({ issue }: { issue: IssueData }) {
  const sentiment = issue.sentiment_focus;
  const migration = issue.migration;
  // Real issues carry no migration analysis yet (Phase 3); render whichever
  // panels have data and hide the section when neither does.
  if (!sentiment && !migration) return null;

  return (
    <section className="blk">
      <div className="sechead rv">
        <h2>Signal charts</h2>
        <span className="sub">Derived time-series · never raw content</span>
      </div>
      <div className="duo">
        {sentiment && <SentimentPanel sentiment={sentiment} />}
        {migration && <MigrationPanel migration={migration} />}
      </div>
    </section>
  );
}
