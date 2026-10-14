export interface RibbonRow {
  project: string;
  value: number;
  /** Fraction of the total, 0 to 1. */
  share: number;
}

/**
 * Split segments into those wide enough to draw and a thin tail to fold into one.
 *
 * If every sliver were widened to the minimum width, a long tail would take space from the
 * projects that matter and the bar would misstate how concentrated the work is. Folding the tail
 * keeps every drawn segment at its true proportion. A single thin segment is not folded: one item
 * is just drawn at the minimum, which distorts the bar by at most that many pixels.
 */
export function foldThin<T extends RibbonRow>(
  rows: T[],
  usablePx: number,
  minPx: number,
): { drawn: T[]; folded: T[]; foldedValue: number } {
  const thin = rows.filter((r) => r.share * usablePx < minPx);
  const folded = thin.length > 1 ? thin : [];
  const drawn = rows.filter((r) => !folded.includes(r));
  return { drawn, folded, foldedValue: folded.reduce((sum, r) => sum + r.value, 0) };
}
