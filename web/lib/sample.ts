import type { IssueData } from "./types";

// Bundled fallback used when the API has no published issue (404) or is
// unreachable. Numbers reproduce design/index.html exactly. This is the ONLY
// place hard-coded content lives; every section renders from an IssueData prop.
export const sampleIssue: IssueData = {
  issue_no: 27,
  week_start: "2026-06-29",
  week_end: "2026-07-03",
  generated_at: "2026-07-03T09:00:00Z",
  niche: "SaaS",
  communities: 34,
  lead: {
    eyebrow: "Lead signal · momentum +38%",
    headline:
      "The AI-wrapper honeymoon is ending — churn complaints tripled in six weeks",
    dek: 'Across founder communities, the story flipped from "look what I shipped" to "why is everyone leaving." Threads about thin GPT wrappers now skew toward retention, pricing fatigue, and "this is just a prompt" — the first sustained negative turn riivault has logged for the category since tracking began.',
    momentum_pct: 38.0,
    threads: 1240,
    comments: 8900,
    window_weeks: 12,
    subreddits: ["r/SaaS", "r/indiehackers", "r/microsaas"],
    chart_title: 'Mention Index — "AI wrapper" churn',
    delta_label: "+40% w/w",
    delta_value: 168,
    series: [
      { period: "2026-04-13", value: 34, label: "wk15" },
      { period: "2026-04-20", value: 37 },
      { period: "2026-04-27", value: 36 },
      { period: "2026-05-04", value: 43 },
      { period: "2026-05-11", value: 57 },
      { period: "2026-05-18", value: 52, label: "wk21" },
      { period: "2026-05-25", value: 66 },
      { period: "2026-06-01", value: 77 },
      { period: "2026-06-08", value: 89 },
      { period: "2026-06-15", value: 107 },
      { period: "2026-06-22", value: 133 },
      { period: "2026-06-29", value: 168, label: "wk27" },
    ],
  },
  tracked: [
    { entity_id: 1, name: "Cursor", context: "r/programming", change_pct: 52.0, spark: [3, 4, 4, 6, 7, 9, 11] },
    { entity_id: 2, name: "Notion AI", context: "r/productivity", change_pct: -14.0, spark: [12, 11, 12, 9, 8, 6, 5] },
    { entity_id: 3, name: "Zapier", context: "r/nocode", change_pct: -6.0, spark: [9, 10, 9, 9, 8, 8, 7] },
    { entity_id: 4, name: "Supabase", context: "r/webdev", change_pct: 29.0, spark: [4, 5, 6, 7, 7, 10, 12] },
    { entity_id: 5, name: "Framer", context: "r/web_design", change_pct: 11.0, spark: [7, 7, 8, 8, 9, 9, 10] },
  ],
  pain_points: [
    { fr_id: 1, rank: 1, text: "Per-seat pricing punishes small teams", kind: "pain_point", occurrences: 214, momentum_pct: 61.0 },
    { fr_id: 2, rank: 2, text: '"AI features feel bolted-on, not useful"', kind: "pain_point", occurrences: 188, momentum_pct: 47.0 },
    { fr_id: 3, rank: 3, text: "Leaving Notion for something faster on mobile", kind: "switch_intent", occurrences: 141, momentum_pct: 38.0 },
    { fr_id: 4, rank: 4, text: "Wants offline-first / local export before trusting a tool", kind: "feature_request", occurrences: 97, momentum_pct: 22.0 },
    { fr_id: 5, rank: 5, text: "Onboarding assumes you already know the jargon", kind: "pain_point", occurrences: 84, momentum_pct: 15.0 },
    { fr_id: 6, rank: 6, text: "Asking for usage-based pricing instead of tiers", kind: "feature_request", occurrences: 76, momentum_pct: 9.0 },
  ],
  sentiment_focus: {
    label: '"AI note-takers"',
    current: -0.31,
    trend: "falling",
    series: [
      { period: "2026-04-06", value: 0.35, label: "Apr" },
      { period: "2026-04-13", value: 0.4 },
      { period: "2026-04-20", value: 0.25 },
      { period: "2026-04-27", value: 0.18 },
      { period: "2026-05-04", value: 0.28 },
      { period: "2026-05-11", value: 0.05, label: "May" },
      { period: "2026-05-18", value: -0.05 },
      { period: "2026-05-25", value: -0.22 },
      { period: "2026-06-01", value: -0.3 },
      { period: "2026-06-08", value: -0.4 },
      { period: "2026-06-15", value: -0.5, label: "Jun" },
    ],
  },
  migration: {
    origin: "r/Notion",
    n: 141,
    title: "where r/Notion posters go",
    destinations: [
      { name: "r/Obsidian", share: 0.41 },
      { name: "r/logseq", share: 0.23 },
      { name: "r/AppFlowy", share: 0.17 },
      { name: "r/Anytype", share: 0.12 },
      { name: "stayed", share: 0.07 },
    ],
  },
  emerging: [
    {
      signal_id: 1,
      signal_type: "spike",
      entity: '"Local-first" SaaS',
      description:
        "Mentions up 4.2× in three weeks across dev communities. Driven by data-ownership and offline anxiety, not a single launch.",
      strength: 0.86,
      detected_label: "Detected wk25",
    },
    {
      signal_id: 2,
      signal_type: "new_topic",
      entity: 'Agent "handoff" UX',
      description:
        "A vocabulary forming around multi-agent handoffs and trust boundaries — no incumbent owns the term yet. Green-field naming window.",
      strength: 0.71,
      detected_label: "Detected wk26",
    },
    {
      signal_id: 3,
      signal_type: "sentiment_flip",
      entity: "No-code AI builders",
      description:
        'Flipped from net-positive to net-negative as "vibe-coded" apps hit maintenance reality. Complaints center on debugging opacity.',
      strength: 0.64,
      detected_label: "Detected wk27",
    },
  ],
};
