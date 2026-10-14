import { describe, expect, it } from 'vitest';
import { makeItem } from './fixtures';
import { activeSpan, busiestMonth, longestOpen, mergeRate, median, medianDaysToMerge } from './insights';
import { monthlyBuckets } from './aggregate';

const DAY = 86_400_000;
const at = (iso: string) => Date.parse(iso);

describe('median', () => {
  it('returns the middle value of an odd list', () => {
    expect(median([5, 1, 3])).toBe(3);
  });
  it('averages the two middle values of an even list', () => {
    expect(median([1, 2, 3, 10])).toBe(2.5);
  });
  it('returns null for an empty list', () => {
    expect(median([])).toBeNull();
  });
});

describe('medianDaysToMerge', () => {
  it('uses only merged pull requests', () => {
    const items = [
      makeItem({ number: 1, outcome: 'merged', daysToMerge: 2, merged: 1 }),
      makeItem({ number: 2, outcome: 'merged', daysToMerge: 10, merged: 1 }),
      makeItem({ number: 3, outcome: 'merged', daysToMerge: 4, merged: 1 }),
      makeItem({ number: 4, outcome: 'open' }),
    ];
    expect(medianDaysToMerge(items)).toBe(4);
  });
  it('is null when nothing merged', () => {
    expect(medianDaysToMerge([makeItem({ number: 1, outcome: 'open' })])).toBeNull();
  });
});

describe('mergeRate', () => {
  it('compares merged with closed-without-merge, ignoring work still open', () => {
    const items = [
      makeItem({ number: 1, outcome: 'merged' }),
      makeItem({ number: 2, outcome: 'merged' }),
      makeItem({ number: 3, outcome: 'merged' }),
      makeItem({ number: 4, outcome: 'closed' }),
      makeItem({ number: 5, outcome: 'open' }),
      makeItem({ number: 6, kind: 'issue', outcome: 'closed' }),
    ];
    expect(mergeRate(items)).toEqual({ merged: 3, finished: 4, rate: 0.75 });
  });
  it('is null with no finished pull requests', () => {
    expect(mergeRate([makeItem({ number: 1, outcome: 'open' })])).toBeNull();
  });
});

describe('longestOpen', () => {
  it('finds the oldest open pull request and its age at the reference time', () => {
    const now = at('2026-01-01T00:00:00Z');
    const items = [
      makeItem({ number: 1, outcome: 'open', created: at('2025-12-01T00:00:00Z') }),
      makeItem({ number: 2, outcome: 'open', created: at('2025-01-01T00:00:00Z') }),
      makeItem({ number: 3, outcome: 'merged', created: at('2020-01-01T00:00:00Z') }),
      makeItem({ number: 4, kind: 'issue', outcome: 'open', created: at('2019-01-01T00:00:00Z') }),
    ];
    const result = longestOpen(items, now);
    expect(result?.item.number).toBe(2);
    expect(result?.days).toBeCloseTo((now - at('2025-01-01T00:00:00Z')) / DAY);
  });
  it('is null when nothing is open', () => {
    expect(longestOpen([makeItem({ number: 1, outcome: 'merged' })], Date.now())).toBeNull();
  });
});

describe('busiestMonth', () => {
  it('returns the month with the most activity', () => {
    const buckets = monthlyBuckets([
      makeItem({ number: 1, created: at('2024-01-02T00:00:00Z') }),
      makeItem({ number: 2, created: at('2024-02-02T00:00:00Z') }),
      makeItem({ number: 3, created: at('2024-02-03T00:00:00Z') }),
    ]);
    expect(busiestMonth(buckets)?.key).toBe('2024-02');
  });
  it('is null with no activity', () => {
    expect(busiestMonth([])).toBeNull();
  });
});

describe('activeSpan', () => {
  it('spans the first to the last creation date', () => {
    const items = [
      makeItem({ number: 1, created: at('2024-05-01T00:00:00Z') }),
      makeItem({ number: 2, created: at('2021-08-27T00:00:00Z') }),
    ];
    expect(activeSpan(items)).toEqual({ from: at('2021-08-27T00:00:00Z'), to: at('2024-05-01T00:00:00Z') });
  });
  it('is null for no items', () => {
    expect(activeSpan([])).toBeNull();
  });
});
