import { describe, expect, it } from 'vitest';
import { activeFilterCount, applyFilters, emptyFilters, facetCounts, filterContributions, isFiltered } from './filters';
import { makeContribution, makeItem } from './fixtures';

const items = [
  makeItem({ number: 1, project: 'Apache HBase', repo: 'apache/hbase', created: Date.parse('2024-01-10T00:00:00Z') }),
  makeItem({
    number: 2,
    project: 'Apache Phoenix',
    repo: 'apache/phoenix',
    outcome: 'open',
    labels: ['bug'],
    created: Date.parse('2024-02-10T00:00:00Z'),
  }),
  makeItem({
    number: 3,
    kind: 'issue',
    outcome: 'closed',
    project: 'Apache Zookeeper',
    repo: 'apache/zookeeper',
    user: 'Grace Hopper',
    title: 'Memory leak in scanner',
    created: Date.parse('2024-03-10T12:00:00Z'),
  }),
];

describe('applyFilters', () => {
  it('returns everything when nothing is selected', () => {
    expect(applyFilters(items, emptyFilters)).toHaveLength(3);
  });

  it('matches any selected value within one dimension', () => {
    const result = applyFilters(items, { ...emptyFilters, projects: ['Apache HBase', 'Apache Phoenix'] });
    expect(result.map((i) => i.number)).toEqual([1, 2]);
  });

  it('requires every dimension to match', () => {
    const result = applyFilters(items, { ...emptyFilters, projects: ['Apache HBase'], outcomes: ['open'] });
    expect(result).toEqual([]);
  });

  it('filters by kind, outcome, user and label', () => {
    expect(applyFilters(items, { ...emptyFilters, kinds: ['issue'] }).map((i) => i.number)).toEqual([3]);
    expect(applyFilters(items, { ...emptyFilters, outcomes: ['open'] }).map((i) => i.number)).toEqual([2]);
    expect(applyFilters(items, { ...emptyFilters, users: ['Grace Hopper'] }).map((i) => i.number)).toEqual([3]);
    expect(applyFilters(items, { ...emptyFilters, labels: ['bug'] }).map((i) => i.number)).toEqual([2]);
  });

  it('treats the date range as inclusive on both ends', () => {
    const result = applyFilters(items, { ...emptyFilters, from: '2024-02-10', to: '2024-03-10' });
    expect(result.map((i) => i.number)).toEqual([2, 3]);
  });

  it('supports an open-ended range', () => {
    expect(applyFilters(items, { ...emptyFilters, from: '2024-03-01' }).map((i) => i.number)).toEqual([3]);
    expect(applyFilters(items, { ...emptyFilters, to: '2024-01-31' }).map((i) => i.number)).toEqual([1]);
  });

  it('searches titles, repos and labels case-insensitively with every word required', () => {
    expect(applyFilters(items, { ...emptyFilters, query: 'MEMORY scanner' }).map((i) => i.number)).toEqual([3]);
    expect(applyFilters(items, { ...emptyFilters, query: 'phoenix' }).map((i) => i.number)).toEqual([2]);
    expect(applyFilters(items, { ...emptyFilters, query: 'bug' }).map((i) => i.number)).toEqual([2]);
    expect(applyFilters(items, { ...emptyFilters, query: 'memory phoenix' })).toEqual([]);
  });

  it('finds an item by its number', () => {
    expect(applyFilters(items, { ...emptyFilters, query: '#2' }).map((i) => i.number)).toEqual([2]);
  });

  it('can ignore one dimension so its own options keep their counts', () => {
    const f = { ...emptyFilters, projects: ['Apache HBase'], outcomes: ['open' as const] };
    expect(applyFilters(items, f).map((i) => i.number)).toEqual([]);
    expect(applyFilters(items, f, 'projects').map((i) => i.number)).toEqual([2]);
  });
});

describe('facetCounts', () => {
  it('counts items per value, ignoring the facet being counted', () => {
    const f = { ...emptyFilters, projects: ['Apache HBase'] };
    const counts = facetCounts(items, f, 'projects');
    expect(counts.get('Apache HBase')).toBe(1);
    expect(counts.get('Apache Phoenix')).toBe(1);
    expect(counts.get('Apache Zookeeper')).toBe(1);
  });

  it('counts every label an item carries', () => {
    const counts = facetCounts(items, emptyFilters, 'labels');
    expect(counts.get('bug')).toBe(1);
  });
});

describe('filter state helpers', () => {
  it('reports whether anything is applied', () => {
    expect(isFiltered(emptyFilters)).toBe(false);
    expect(isFiltered({ ...emptyFilters, query: 'x' })).toBe(true);
    expect(isFiltered({ ...emptyFilters, from: '2024-01-01' })).toBe(true);
  });

  it('counts active dimensions, treating a date range as one', () => {
    const f = { ...emptyFilters, projects: ['a'], from: '2024-01-01', to: '2024-02-01', query: 'x' };
    expect(activeFilterCount(f)).toBe(3);
  });
});

describe('filterContributions', () => {
  const rows = [
    makeContribution({ project: 'Apache HBase', repo: 'apache/hbase', user: 'Ada Lovelace', score: 10 }),
    makeContribution({ project: 'Apache Phoenix', repo: 'apache/phoenix', user: 'Grace Hopper', score: 5 }),
  ];

  it('scopes aggregate rows by user, project and repo only', () => {
    expect(filterContributions(rows, { ...emptyFilters, users: ['Grace Hopper'] })).toHaveLength(1);
    expect(filterContributions(rows, { ...emptyFilters, projects: ['Apache HBase'] })[0].score).toBe(10);
    expect(filterContributions(rows, { ...emptyFilters, repos: ['apache/phoenix'] })).toHaveLength(1);
  });

  it('ignores item-level filters such as outcome and dates', () => {
    const f = { ...emptyFilters, outcomes: ['open' as const], from: '2030-01-01', query: 'zzz' };
    expect(filterContributions(rows, f)).toHaveLength(2);
  });
});
