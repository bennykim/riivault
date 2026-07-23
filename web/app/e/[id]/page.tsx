import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAdoptionSeries,
  getEntityDetail,
  getEntityVoc,
  getMentionSeries,
  getSentimentSeries,
  type AdoptionSeries,
} from "@/lib/db";
import { linePath } from "@/lib/chart";
import { compact, pctLabel, signedDecimal } from "@/lib/format";
import type { PainKind } from "@/lib/types";
import ThemeToggle from "@/components/ThemeToggle";

export const dynamic = "force-dynamic";

const DAY_CHOICES = [30, 90, 180] as const;

const ADOPTION_LABELS: Record<string, string> = {
  "github:stars_total": "GitHub stars (total)",
  "github:releases": "GitHub releases / day",
  "npm:downloads": "npm downloads / day",
  "pypi:downloads": "PyPI downloads / day",
  "stackexchange:questions": "Stack Overflow questions / day",
};

function kindTag(kind: PainKind): { cls: string; label: string } {
  switch (kind) {
    case "feature_request":
      return { cls: "ok", label: "Feature request" };
    case "switch_intent":
      return { cls: "warn", label: "Switch intent" };
    case "praise":
      return { cls: "ok", label: "Praise" };
    case "bug":
      return { cls: "warn", label: "Bug" };
    default:
      return { cls: "", label: "Pain point" };
  }
}

function SeriesPanel({
  title,
  meta,
  series,
  span,
  color = "var(--primary)",
  fixedRange,
  valueLabel,
}: {
  title: string;
  meta: string;
  series: { period: string; value: number }[];
  span: string;
  color?: string;
  fixedRange?: [number, number];
  valueLabel: (v: number) => string;
}) {
  if (series.length === 0) {
    return (
      <section className={`panel ${span}`}>
        <div className="ph">
          <span>{title}</span>
          <b>{meta}</b>
        </div>
        <p className="sans" style={{ color: "var(--faint)", fontSize: ".8rem" }}>
          No data in this window yet — the index grows every two hours.
        </p>
      </section>
    );
  }
  const values = series.map((p) => p.value);
  const last = values[values.length - 1];
  const { d, areaD, lastX, lastY } = linePath(values, {
    w: 560,
    h: 240,
    padX: 6,
    padTop: 14,
    padBottom: 24,
    baseline: 216,
    yMin: fixedRange?.[0],
    yMax: fixedRange?.[1],
  });
  const t0 = series[0].period.slice(5);
  const t2 = series[series.length - 1].period.slice(5);

  return (
    <section className={`panel ${span}`}>
      <div className="ph">
        <span>{title}</span>
        <b>{meta}</b>
      </div>
      <svg className="chart" viewBox="0 0 560 240" role="img" aria-label={title}>
        {[0, 1, 2, 3, 4].map((g) => {
          const y = 14 + (g * (240 - 14 - 24)) / 4;
          return <line key={g} x1="6" y1={y} x2="554" y2={y} stroke="var(--line)" />;
        })}
        {!fixedRange && <path d={areaD} fill={color} opacity="0.09" />}
        <path
          d={d}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle cx={lastX} cy={lastY} r="4" fill={color} stroke="var(--panel)" strokeWidth="2" />
        <text className="axis" x="6" y="235">{t0}</text>
        <text className="axis" x="554" y="235" textAnchor="end">{t2}</text>
      </svg>
      <div className="legend">
        <span>
          <i style={{ background: color }}></i>latest {valueLabel(last)}
        </span>
        <span>
          {t0} .. {t2}
        </span>
      </div>
    </section>
  );
}

export default async function EntityPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ days?: string }>;
}) {
  const { id } = await params;
  const entityId = Number(id);
  if (!Number.isInteger(entityId) || entityId <= 0) notFound();

  const requested = Number((await searchParams).days);
  const days = (DAY_CHOICES as readonly number[]).includes(requested)
    ? requested
    : 90;

  const entity = await getEntityDetail(entityId).catch(() => null);
  if (!entity) notFound();

  const [mentions, sentiment, adoption, voc] = await Promise.all([
    getMentionSeries(entityId, days).catch(() => []),
    getSentimentSeries(entityId, days).catch(() => []),
    getAdoptionSeries(entityId, days).catch(() => [] as AdoptionSeries[]),
    getEntityVoc(entityId).catch(() => []),
  ]);

  const totalMentions = mentions.reduce((acc, p) => acc + p.value, 0);
  const currentSentiment = sentiment.length
    ? sentiment[sentiment.length - 1].value
    : null;

  return (
    <div className="page">
      <header className="bar">
        <span className="wm">
          <Link href="/">riivault</Link>
          <span>_</span>
        </span>
        <span className="sep">/</span>
        <span className="sys">ENTITY {String(entity.entity_id).padStart(3, "0")}</span>
        <div className="right">
          <span className="chip">{entity.type}</span>
          {entity.context && <span className="chip">{entity.context}</span>}
          {Object.entries(entity.mappings).map(([key, value]) => (
            <span className="chip" key={key} title={key}>
              {key}:{value}
            </span>
          ))}
          <ThemeToggle />
        </div>
      </header>

      <div className="grid">
        <section className="panel lead-panel span12">
          <div className="eyebrow">
            Entity drill-down · last {days} days ·{" "}
            {DAY_CHOICES.map((choice, i) => (
              <span key={choice}>
                {i > 0 && " / "}
                {choice === days ? (
                  <b>{choice}d</b>
                ) : (
                  <Link href={`/e/${entity.entity_id}?days=${choice}`}>{choice}d</Link>
                )}
              </span>
            ))}
          </div>
          <h1 className="head sans">{entity.name}</h1>
          <p className="srcline">
            SRC: <b>{totalMentions.toLocaleString("en-US")}</b> mentions in window
            {currentSentiment != null && (
              <>
                {" "}· net sentiment <b>{signedDecimal(currentSentiment)}</b>
              </>
            )}{" "}
            · {adoption.length} adoption series · derived aggregates only
          </p>
        </section>

        <SeriesPanel
          title="Mentions / day"
          meta="all sources combined"
          series={mentions}
          span="span6"
          valueLabel={(v) => `${v} mentions`}
        />
        <SeriesPanel
          title="Sentiment curve"
          meta={
            currentSentiment != null
              ? `${signedDecimal(currentSentiment)} current`
              : "no samples yet"
          }
          series={sentiment}
          span="span6"
          color="var(--sentiment)"
          fixedRange={[-1, 1]}
          valueLabel={(v) => signedDecimal(v)}
        />

        {adoption.map((a) => (
          <SeriesPanel
            key={`${a.source}:${a.metric}`}
            title={ADOPTION_LABELS[`${a.source}:${a.metric}`] ?? `${a.source} ${a.metric}`}
            meta="adoption"
            series={a.series}
            span="span6"
            color="var(--pos)"
            valueLabel={compact}
          />
        ))}

        <section className="panel span12">
          <div className="ph">
            <span>VoC ledger</span>
            <b>{voc.length ? `latest ${voc.length} entries` : "empty"}</b>
          </div>
          {voc.length === 0 ? (
            <p className="sans" style={{ color: "var(--faint)", fontSize: ".8rem" }}>
              No classified feedback for this entity yet.
            </p>
          ) : (
            <table className="ptab">
              <thead>
                <tr>
                  <th>Entry</th>
                  <th className="hide-sm">Kind</th>
                  <th className="r hide-sm">Seen</th>
                  <th className="r hide-sm">First / Last</th>
                  <th className="r">Momentum</th>
                </tr>
              </thead>
              <tbody>
                {voc.map((item) => {
                  const tag = kindTag(item.kind);
                  return (
                    <tr key={item.fr_id}>
                      <td className="txt sans">{item.text}</td>
                      <td className="hide-sm">
                        <span className={`kindtag ${tag.cls}`}>{tag.label}</span>
                      </td>
                      <td className="r hide-sm">{item.occurrences}</td>
                      <td className="r hide-sm" style={{ whiteSpace: "nowrap" }}>
                        {item.first_seen.slice(5)} → {item.last_seen.slice(5)}
                      </td>
                      <td className="r">
                        <span className="mom">
                          <span className="pv">{pctLabel(item.momentum_pct)}</span>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        <footer className="span12">
          <div className="foot-meta">
            <span>
              <Link href="/">← BACK TO THE WEEKLY ISSUE</Link>
            </span>
            <span>LIVE INDEX · DERIVED AGGREGATES ONLY · NEVER RAW CONTENT</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
