import { describe, expect, it } from 'vitest';
import { normalizeFeed } from './normalize';
import type { FeedItem, FeedRecord } from './types';

const DAY = 86_400_000;

function item(number: number, patch: Partial<FeedItem> = {}): FeedItem {
  return {
    number,
    title: `Change ${number}`,
    html_url: `https://github.com/apache/hbase/pull/${number}`,
    state: 'closed',
    created_at: '2024-03-01T00:00:00Z',
    updated_at: '2024-03-05T00:00:00Z',
    labels: [],
    ...patch,
  };
}

function record(patch: Partial<FeedRecord> = {}): FeedRecord {
  return {
    user: 'Ada Lovelace',
    user_url: 'https://github.com/ada',
    user_avatar: 'https://avatars/ada',
    project_key: 'Apache HBase',
    repo: 'apache/hbase',
    repo_url: 'https://github.com/apache/hbase',
    open_prs: [],
    closed_prs: [],
    open_issues: [],
    closed_issues: [],
    ...patch,
  };
}

describe('normalizeFeed', () => {
  it('classifies pull requests as merged, closed or open', () => {
    const { items } = normalizeFeed([
      record({
        open_prs: [item(1, { state: 'open' })],
        closed_prs: [
          item(2, { pull_request: { merged_at: '2024-03-04T00:00:00Z' } }),
          item(3, { pull_request: { merged_at: null } }),
        ],
      }),
    ]);
    const byNumber = Object.fromEntries(items.map((i) => [i.number, i]));
    expect(byNumber[1]).toMatchObject({ kind: 'pr', outcome: 'open' });
    expect(byNumber[2]).toMatchObject({ kind: 'pr', outcome: 'merged' });
    expect(byNumber[3]).toMatchObject({ kind: 'pr', outcome: 'closed' });
  });

  it('classifies issues as open or closed', () => {
    const { items } = normalizeFeed([
      record({ open_issues: [item(4, { state: 'open' })], closed_issues: [item(5)] }),
    ]);
    expect(items.map((i) => [i.kind, i.outcome])).toEqual([
      ['issue', 'open'],
      ['issue', 'closed'],
    ]);
  });

  it('computes days to merge from creation to merge', () => {
    const { items } = normalizeFeed([
      record({
        closed_prs: [
          item(6, {
            created_at: '2024-03-01T00:00:00Z',
            pull_request: { merged_at: '2024-03-04T12:00:00Z' },
          }),
        ],
      }),
    ]);
    expect(items[0].daysToMerge).toBeCloseTo(3.5);
    expect(items[0].merged).toBe(Date.parse('2024-03-04T12:00:00Z'));
  });

  it('leaves days to merge empty for unmerged work', () => {
    const { items } = normalizeFeed([record({ closed_prs: [item(7, { pull_request: { merged_at: null } })] })]);
    expect(items[0].daysToMerge).toBeNull();
    expect(items[0].merged).toBeNull();
  });

  it('never reports a negative time to merge', () => {
    const { items } = normalizeFeed([
      record({
        closed_prs: [
          item(8, { created_at: '2024-03-05T00:00:00Z', pull_request: { merged_at: '2024-03-01T00:00:00Z' } }),
        ],
      }),
    ]);
    expect(items[0].daysToMerge).toBe(0);
  });

  it('carries project, repo, user and label names', () => {
    const { items } = normalizeFeed([
      record({ closed_prs: [item(9, { labels: [{ name: 'bug' }, { name: 'backport' }] })] }),
    ]);
    expect(items[0]).toMatchObject({
      id: 'apache/hbase#9',
      project: 'Apache HBase',
      repo: 'apache/hbase',
      user: 'Ada Lovelace',
      labels: ['bug', 'backport'],
      url: 'https://github.com/apache/hbase/pull/9',
    });
    expect(items[0].created).toBe(Date.parse('2024-03-01T00:00:00Z'));
    expect(items[0].updated - items[0].created).toBe(4 * DAY);
  });

  it('keeps each repository item once even if it appears in several records', () => {
    const dup = item(10);
    const { items } = normalizeFeed([record({ closed_prs: [dup] }), record({ closed_prs: [dup] })]);
    expect(items).toHaveLength(1);
  });

  it('lists each person once, in first-seen order', () => {
    const { people } = normalizeFeed([
      record(),
      record({ repo: 'apache/hadoop' }),
      record({ user: 'Grace Hopper', user_url: 'u', user_avatar: 'a' }),
    ]);
    expect(people.map((p) => p.name)).toEqual(['Ada Lovelace', 'Grace Hopper']);
  });

  it('tolerates an empty feed', () => {
    expect(normalizeFeed([])).toEqual({ items: [], people: [] });
  });
});
