import { describe, expect, it } from 'vitest';
import { emptyFilters } from './filters';
import { decodeView, defaultView, encodeView } from './urlState';

describe('encodeView', () => {
  it('is empty for the default view so the address stays clean', () => {
    expect(encodeView(defaultView)).toBe('');
  });

  it('writes only what differs from the default', () => {
    const search = encodeView({
      ...defaultView,
      filters: { ...emptyFilters, projects: ['Apache HBase'], outcomes: ['merged'] },
      sort: 'speed',
    });
    const params = new URLSearchParams(search);
    expect(params.getAll('project')).toEqual(['Apache HBase']);
    expect(params.getAll('status')).toEqual(['merged']);
    expect(params.get('sort')).toBe('speed');
    expect(params.has('dir')).toBe(false);
    expect(params.has('page')).toBe(false);
  });
});

describe('decodeView', () => {
  it('round-trips every field', () => {
    const view = {
      filters: {
        users: ['Ada Lovelace'],
        projects: ['Apache HBase', 'Apache Phoenix'],
        repos: ['apache/hbase'],
        kinds: ['pr' as const],
        outcomes: ['merged' as const, 'open' as const],
        labels: ['bug', 'help wanted'],
        from: '2023-01-01',
        to: '2024-06-30',
        query: 'scanner leak',
      },
      sort: 'title' as const,
      dir: 'asc' as const,
      page: 3,
    };
    expect(decodeView(encodeView(view))).toEqual(view);
  });

  it('accepts a leading ? or #? as written in the address bar', () => {
    expect(decodeView('?project=Apache%20HBase').filters.projects).toEqual(['Apache HBase']);
    expect(decodeView('#?project=Apache%20HBase').filters.projects).toEqual(['Apache HBase']);
  });

  it('returns the default view for empty input', () => {
    expect(decodeView('')).toEqual(defaultView);
  });

  it('drops values it does not recognise rather than failing', () => {
    const view = decodeView('type=pr&type=bogus&status=nope&sort=weird&dir=sideways&page=-4&from=yesterday&to=2024-02-30x');
    expect(view.filters.kinds).toEqual(['pr']);
    expect(view.filters.outcomes).toEqual([]);
    expect(view.sort).toBe(defaultView.sort);
    expect(view.dir).toBe(defaultView.dir);
    expect(view.page).toBe(1);
    expect(view.filters.from).toBeNull();
    expect(view.filters.to).toBeNull();
  });
});
