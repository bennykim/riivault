// Pure data -> SVG helpers. No external charting library (per contract).
// The look of design/index.html is reproduced with plain <path>/<polyline>.

export interface LinePathOpts {
  /** viewBox width / height */
  w: number;
  h: number;
  /** horizontal inset on both sides (x runs padX..w-padX) */
  padX?: number;
  /** vertical insets: max value maps to y=padTop, min to y=h-padBottom */
  padTop?: number;
  padBottom?: number;
  /** area fill baseline (defaults to h - padBottom) */
  baseline?: number;
  /** fixed value range instead of data min/max (e.g. sentiment -1..+1) */
  yMin?: number;
  yMax?: number;
}

export interface LinePath {
  /** polyline `d` (straight L segments, matching the design) */
  d: string;
  /** closed area `d` dropping to the baseline */
  areaD: string;
  firstX: number;
  lastX: number;
  lastY: number;
  /** total polyline length, for the CSS stroke-draw reveal (--len) */
  len: number;
}

const r = (n: number): number => Math.round(n * 100) / 100;

function xAt(i: number, n: number, padX: number, w: number): number {
  const innerW = w - padX * 2;
  return padX + (n <= 1 ? 0 : (i * innerW) / (n - 1));
}

/**
 * Map a numeric series to an SVG polyline. y is normalized over the data
 * min..max unless an explicit `yMin`/`yMax` range is supplied (fixed scale).
 */
export function linePath(values: number[], opts: LinePathOpts): LinePath {
  const { w, h, padX = 20, padTop = 20, padBottom = 20 } = opts;
  const n = values.length;
  const plotH = h - padTop - padBottom;

  const lo = opts.yMin ?? Math.min(...values);
  const hi = opts.yMax ?? Math.max(...values);
  const span = hi - lo || 1;

  const pts = values.map((v, i) => {
    const x = xAt(i, n, padX, w);
    const y = padTop + (1 - (v - lo) / span) * plotH;
    return [x, y] as const;
  });

  const d = pts
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${r(x)},${r(y)}`)
    .join(" ");

  let len = 0;
  for (let i = 1; i < pts.length; i++) {
    len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  }

  const baseline = opts.baseline ?? h - padBottom;
  const first = pts[0] ?? [padX, h];
  const last = pts[n - 1] ?? [padX, h];
  const areaD = `${d} L${r(last[0])},${r(baseline)} L${r(first[0])},${r(baseline)} Z`;

  return {
    d,
    areaD,
    firstX: r(first[0]),
    lastX: r(last[0]),
    lastY: r(last[1]),
    len: r(len),
  };
}

/** `points` string for a sparkline <polyline> (min..max normalized). */
export function sparkPoints(values: number[], w = 72, h = 22): string {
  const n = values.length;
  const padX = 2;
  const padTop = 3;
  const padBottom = 4;
  const plotH = h - padTop - padBottom;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((v, i) => {
      const x = xAt(i, n, padX, w);
      const y = padTop + (1 - (v - min) / span) * plotH;
      return `${r(x)},${r(y)}`;
    })
    .join(" ");
}

/** Sparkline stroke color from overall direction (last vs first). */
export function sparkColor(values: number[]): string {
  const rising = values[values.length - 1] - values[0] >= 0;
  return rising ? "var(--pos)" : "var(--neg)";
}
