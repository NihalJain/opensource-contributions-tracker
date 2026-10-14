import type { MonthBucket } from './aggregate';
import type { Item } from './types';

const DAY_MS = 86_400_000;

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function medianDaysToMerge(items: Item[]): number | null {
  return median(
    items.flatMap((item) => (item.outcome === 'merged' && item.daysToMerge !== null ? [item.daysToMerge] : [])),
  );
}

/** Of the pull requests that are finished, the share that were merged. */
export function mergeRate(items: Item[]): { merged: number; finished: number; rate: number } | null {
  let merged = 0;
  let closed = 0;
  for (const item of items) {
    if (item.kind !== 'pr') continue;
    if (item.outcome === 'merged') merged += 1;
    else if (item.outcome === 'closed') closed += 1;
  }
  const finished = merged + closed;
  return finished === 0 ? null : { merged, finished, rate: merged / finished };
}

/** The open pull request that has waited longest, with its age at `now`. */
export function longestOpen(items: Item[], now: number): { item: Item; days: number } | null {
  let oldest: Item | null = null;
  for (const item of items) {
    if (item.kind === 'pr' && item.outcome === 'open' && (oldest === null || item.created < oldest.created)) {
      oldest = item;
    }
  }
  return oldest === null ? null : { item: oldest, days: Math.max(0, (now - oldest.created) / DAY_MS) };
}

export function busiestMonth(buckets: MonthBucket[]): MonthBucket | null {
  let best: MonthBucket | null = null;
  for (const bucket of buckets) {
    if (bucket.total > 0 && (best === null || bucket.total > best.total)) best = bucket;
  }
  return best;
}

export function activeSpan(items: Item[]): { from: number; to: number } | null {
  if (items.length === 0) return null;
  let from = Infinity;
  let to = -Infinity;
  for (const item of items) {
    from = Math.min(from, item.created);
    to = Math.max(to, item.created);
  }
  return { from, to };
}
