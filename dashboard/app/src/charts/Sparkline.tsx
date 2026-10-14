import type { MonthBucket } from '../data/aggregate';

interface Props {
  buckets: MonthBucket[];
  /** Number of most recent months to draw. */
  months?: number;
  width?: number;
  height?: number;
  label: string;
}

/** A small trend line with no axes; the value is stated in text next to it. */
export function Sparkline({ buckets, months = 24, width = 96, height = 28, label }: Props) {
  const recent = buckets.slice(-months);
  const max = Math.max(...recent.map((b) => b.total), 1);
  if (recent.length < 2) return <span className="visually-hidden">{label}</span>;

  const step = (width - 4) / (recent.length - 1);
  const points = recent.map((b, i) => [2 + i * step, height - 2 - (b.total / max) * (height - 4)] as const);
  const line = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join('');
  const [lastX, lastY] = points[points.length - 1];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <path d={line} fill="none" stroke="var(--c-merged)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="3" fill="var(--c-merged)" stroke="var(--surface)" strokeWidth="2" />
    </svg>
  );
}
