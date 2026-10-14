import { describe, expect, it } from 'vitest';
import { formatCompact, formatDate, formatDays, formatInt, formatMonth, formatSpan, plural } from './format';

describe('formatInt / formatCompact', () => {
  it('groups thousands', () => {
    expect(formatInt(1234567)).toBe('1,234,567');
  });
  it('keeps small numbers whole and compacts large ones', () => {
    expect(formatCompact(0)).toBe('0');
    expect(formatCompact(999)).toBe('999');
    expect(formatCompact(1200)).toBe('1.2K');
    expect(formatCompact(25_000)).toBe('25K');
  });
});

describe('formatDays', () => {
  it('describes durations at a human scale', () => {
    expect(formatDays(0.2)).toBe('Under a day');
    expect(formatDays(1)).toBe('1 day');
    expect(formatDays(3.4)).toBe('3 days');
    expect(formatDays(20)).toBe('3 weeks');
    expect(formatDays(75)).toBe('2 months');
    expect(formatDays(400)).toBe('1.1 years');
    expect(formatDays(900)).toBe('2.5 years');
  });
});

describe('dates', () => {
  it('formats in UTC so the day never shifts with the viewer time zone', () => {
    const ms = Date.parse('2024-08-14T23:30:00Z');
    expect(formatDate(ms)).toBe('Aug 14, 2024');
    expect(formatMonth(ms)).toBe('Aug 2024');
  });
  it('describes a span between two dates', () => {
    expect(formatSpan(Date.parse('2021-08-27T00:00:00Z'), Date.parse('2026-09-23T00:00:00Z'))).toBe('Aug 2021 to Sep 2026');
    expect(formatSpan(Date.parse('2024-03-01T00:00:00Z'), Date.parse('2024-03-20T00:00:00Z'))).toBe('Mar 2024');
  });
});

describe('plural', () => {
  it('chooses the singular only for exactly one', () => {
    expect(plural(1, 'review')).toBe('1 review');
    expect(plural(0, 'review')).toBe('0 reviews');
    expect(plural(1234, 'review')).toBe('1,234 reviews');
  });
  it('accepts an irregular plural', () => {
    expect(plural(2, 'repository', 'repositories')).toBe('2 repositories');
  });
});
