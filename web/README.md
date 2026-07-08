# riivault — web

Next.js 15 (App Router) + React 19 + TypeScript (strict) frontend for riivault.
A pixel-faithful port of `design/index.html`, rendered entirely from the
`GET /api/v1/issue/current` response (see `docs/CONTRACT.md`). No Tailwind — the
design CSS is ported verbatim into `app/globals.css`. No external CDN / font /
chart library; charts are generated from data by `lib/chart.ts`.

## Commands

```bash
npm install       # install dependencies
npm run dev       # dev server on http://localhost:3000
npm run build     # production build (TypeScript type-checking enabled)
npm run start     # serve the production build
```

## Environment variables

| Variable              | Default                 | Used by                                   |
| --------------------- | ----------------------- | ----------------------------------------- |
| `API_URL`             | `http://localhost:8000` | Server-side issue fetch (`lib/api.ts`)    |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Subscribe POST (client) + server fallback |

The server fetch prefers `API_URL`, falling back to `NEXT_PUBLIC_API_URL`, then
`http://localhost:8000`.

## Data flow

- `app/page.tsx` (server component) calls `getIssue()`.
  - On success it renders the live `IssueData`.
  - On `404` / network error it falls back to `lib/sample.ts` (numbers identical
    to the design) and flags `isSample`, which flips the compliance footer text
    to "Sample data — design preview …".
- Every section is a presentational component driven by `IssueData` props — no
  content is hard-coded outside `lib/sample.ts`.

## Structure

```
app/         layout.tsx · page.tsx · globals.css (ported design CSS)
lib/         types.ts · api.ts · sample.ts · chart.ts · format.ts
components/   Masthead · Lead · HeroChart · TrackedRail · SubscribeCta
              PainPointsFeed · SignalCharts · EmergingSignals · Footer
components/fx/ Reveal · CountUp · FieldCanvas · TiltCard  (client, "use client")
```

### Charts (`lib/chart.ts`)

- `linePath(values, opts)` → `{ d, areaD, lastX, lastY, len }`. y is min–max
  normalized, or fixed-scaled when `yMin`/`yMax` are given (sentiment uses
  `-1..+1`). `len` seeds the CSS stroke-draw reveal (`--len`).
- `sparkPoints(values)` / `sparkColor(values)` → tracked-entity sparklines.

### Interactions (`components/fx/*`)

`Reveal` adds `.in` to `.rv` elements on scroll (IntersectionObserver) and sets
`--len` for the stroke-draw. `CountUp` animates numbers. `FieldCanvas` renders
the ambient particle field. `TiltCard` adds pointer tilt to emerging cards. All
respect `prefers-reduced-motion`.
