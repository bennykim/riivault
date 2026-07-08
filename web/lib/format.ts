import type { CSSProperties } from "react";
import type { SeriesPoint } from "./types";

const MINUS = "−"; // U+2212 MINUS SIGN, as used in the design

/** Build an inline style object that may include CSS custom properties
 *  (e.g. `--w`, `--len`) which React's CSSProperties type does not model. */
export function vars(map: Record<string, string | number>): CSSProperties {
  return map as unknown as CSSProperties;
}

/** Percentage with an explicit sign: `+61%` / `−14%` (typographic minus). */
export function pctLabel(pct: number): string {
  const r = Math.round(pct);
  return r >= 0 ? `+${r}%` : `${MINUS}${Math.abs(r)}%`;
}

/** Signed decimal for sentiment, e.g. `-0.31` -> `−0.31`, `0.22` -> `0.22`. */
export function signedDecimal(value: number, digits = 2): string {
  return value < 0
    ? `${MINUS}${Math.abs(value).toFixed(digits)}`
    : value.toFixed(digits);
}

/** ISO date (`2026-07-03`) -> dotted masthead form (`2026·07·03`). */
export function dottedDate(iso: string): string {
  return iso.slice(0, 10).replace(/-/g, "·");
}

/** Derive a short axis label: explicit `label` wins, else month abbrev. */
export function axisLabel(p: SeriesPoint): string {
  if (p.label) return p.label;
  const d = new Date(`${p.period.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return p.period;
  return d.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
}

/** First / middle / last axis labels from a series (matches the 3 design ticks). */
export function axisTicks(series: SeriesPoint[]): [string, string, string] {
  const n = series.length;
  if (n === 0) return ["", "", ""];
  const mid = Math.floor((n - 1) / 2);
  return [axisLabel(series[0]), axisLabel(series[mid]), axisLabel(series[n - 1])];
}
