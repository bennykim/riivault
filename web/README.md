# riivault — web

Next.js 15 (App Router) + React 19 + TypeScript (strict) frontend for riivault,
rendered entirely from the `GET /api/v1/issue/current` response (see
`docs/CONTRACT.md`). UI is built on the [Astryx](https://astryx.atmeta.com/)
design system (`@astryxdesign/core` + `theme-neutral`, versions pinned — beta):
light/dark follows the OS via the theme's `light-dark()` tokens, and legacy CSS
variables in `app/globals.css` are aliased to Astryx tokens so the hand-rolled
SVG charts (`lib/chart.ts`, no chart library) track the active mode.

## Commands

Uses pnpm (see `packageManager` in package.json).

```bash
pnpm install       # install dependencies
pnpm dev           # dev server on http://localhost:3000
pnpm build         # production build (TypeScript type-checking enabled)
pnpm start         # serve the production build
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
