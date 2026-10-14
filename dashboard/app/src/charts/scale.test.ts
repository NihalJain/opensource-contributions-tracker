import { describe, expect, it } from 'vitest';
import { monthBounds, niceScale, topRoundedRect } from './scale';

describe('niceScale', () => {
  it('rounds the top up to a clean step', () => {
    expect(niceScale(33)).toMatchObject({ top: 40, step: 10, ticks: [0, 10, 20, 30, 40] });
  });
  it('uses steps of 1, 2 or 5 times a power of ten', () => {
    expect(niceScale(7).step).toBe(2);
    expect(niceScale(100).step).toBe(50);
    expect(niceScale(1200).step).toBe(500);
  });
  it('never returns a zero-height axis', () => {
    const { top, ticks } = niceScale(0);
    expect(top).toBeGreaterThan(0);
    expect(ticks[0]).toBe(0);
    expect(ticks.length).toBeGreaterThan(1);
  });
  it('keeps small integer data on whole-number ticks', () => {
    expect(niceScale(3).ticks.every(Number.isInteger)).toBe(true);
  });
});

describe('monthBounds', () => {
  it('returns the first and last day, including leap years', () => {
    expect(monthBounds('2024-02')).toEqual({ from: '2024-02-01', to: '2024-02-29' });
    expect(monthBounds('2023-02')).toEqual({ from: '2023-02-01', to: '2023-02-28' });
    expect(monthBounds('2024-12')).toEqual({ from: '2024-12-01', to: '2024-12-31' });
  });
});

describe('topRoundedRect', () => {
  it('limits the radius to half the width and the height', () => {
    expect(topRoundedRect(0, 0, 4, 100, 10)).toContain('Q0,0 2,0');
    expect(topRoundedRect(0, 0, 40, 1, 4)).toContain('V1');
  });
});
