import { describe, expect, it } from 'vitest';
import { foldThin } from './ribbon';

const row = (project: string, share: number) => ({ project, value: share * 1000, share });

describe('foldThin', () => {
  it('keeps every segment that is wide enough', () => {
    const { drawn, folded } = foldThin([row('a', 0.6), row('b', 0.3), row('c', 0.1)], 1000, 6);
    expect(drawn.map((r) => r.project)).toEqual(['a', 'b', 'c']);
    expect(folded).toEqual([]);
  });

  it('folds two or more thin segments together, in order', () => {
    const { drawn, folded } = foldThin([row('a', 0.9), row('b', 0.004), row('c', 0.003), row('d', 0.003)], 1000, 6);
    expect(drawn.map((r) => r.project)).toEqual(['a']);
    expect(folded.map((r) => r.project)).toEqual(['b', 'c', 'd']);
  });

  it('draws a single thin segment as it is rather than folding one item', () => {
    const { drawn, folded } = foldThin([row('a', 0.99), row('b', 0.005)], 1000, 6);
    expect(drawn.map((r) => r.project)).toEqual(['a', 'b']);
    expect(folded).toEqual([]);
  });

  it('judges width in pixels, so a narrow bar folds more', () => {
    const rows = [row('a', 0.8), row('b', 0.1), row('c', 0.05), row('d', 0.05)];
    expect(foldThin(rows, 1000, 6).folded).toEqual([]);
    expect(foldThin(rows, 80, 6).folded.map((r) => r.project)).toEqual(['c', 'd']);
  });

  it('reports the combined value of what was folded', () => {
    const { foldedValue } = foldThin([row('a', 0.9), row('b', 0.004), row('c', 0.005)], 1000, 6);
    expect(foldedValue).toBeCloseTo(9);
  });

  it('treats a segment of exactly the minimum width as wide enough', () => {
    const { folded } = foldThin([row('a', 0.9), row('b', 0.004), row('c', 0.006)], 1000, 6);
    expect(folded).toEqual([]);
  });

  it('copes with no rows and a zero-width bar', () => {
    expect(foldThin([], 1000, 6)).toEqual({ drawn: [], folded: [], foldedValue: 0 });
    const { drawn } = foldThin([row('a', 1)], 0, 6);
    expect(drawn.map((r) => r.project)).toEqual(['a']);
  });
});
