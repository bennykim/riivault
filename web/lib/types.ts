// Types mirroring GET /api/v1/issue/current (docs/CONTRACT.md).
// snake_case fields preserved to match the API response verbatim.

/** A single time-series point. `label` is an optional display override for the
 *  axis (the API sends ISO `period`; the sample provides ready-made labels). */
export interface SeriesPoint {
  period: string;
  value: number;
  label?: string;
}

export type PainKind =
  | "pain_point"
  | "feature_request"
  | "switch_intent"
  | "bug"
  | "praise";

export type SignalType = "spike" | "new_topic" | "sentiment_flip" | "migration";

export interface Lead {
  eyebrow: string;
  headline: string;
  dek: string;
  momentum_pct: number;
  threads: number;
  comments: number;
  window_weeks: number;
  subreddits: string[];
  chart_title: string;
  delta_label: string;
  delta_value: number;
  series: SeriesPoint[];
}

export interface TrackedEntity {
  entity_id: number;
  name: string;
  context: string;
  change_pct: number;
  spark: number[];
}

export interface PainPoint {
  fr_id: number;
  rank: number;
  text: string;
  kind: PainKind;
  occurrences: number;
  momentum_pct: number;
}

export interface SentimentFocus {
  label: string;
  current: number;
  trend: string;
  series: SeriesPoint[];
}

export interface MigrationDestination {
  name: string;
  share: number;
}

export interface Migration {
  origin: string;
  n: number;
  title: string;
  destinations: MigrationDestination[];
}

export interface EmergingSignal {
  signal_id: number;
  signal_type: SignalType;
  entity: string;
  description: string;
  strength: number;
  detected_label: string;
}

export interface IssueData {
  issue_no: number;
  week_start: string;
  week_end: string;
  generated_at: string;
  niche: string;
  communities: number;
  lead: Lead;
  tracked: TrackedEntity[];
  pain_points: PainPoint[];
  sentiment_focus: SentimentFocus;
  migration: Migration;
  emerging: EmergingSignal[];
}
