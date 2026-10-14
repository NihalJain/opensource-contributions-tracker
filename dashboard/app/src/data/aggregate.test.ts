import { describe, expect, it } from 'vitest';
import { isCountsOnly, monthlyBuckets, projectRows, speedHistogram, totals } from './aggregate';
import { makeContribution, makeItem } from './fixtures';

const at = (iso: string) => Date.parse(iso);

describe('totals', () => {
  it('splits pull requests by outcome and counts issues apart', () => {
    const t = totals([
      makeItem({ number: 1, outcome: 'merged' }),
      makeItem({ number: 2, outcome: 'merged' }),
      makeItem({ number: 3, outcome: 'closed' }),
      makeItem({ number: 4, outcome: 'open' }),
      makeItem({ number: 5, kind: 'issue', outcome: 'open' }),
      makeItem({ number: 6, kind: 'issue', outcome: 'closed' }),
    ]);
    expect(t).toEqual({ merged: 2, closedPrs: 1, openPrs: 1, issues: 2, openIssues: 1, items: 6 });
  });
});

describe('monthlyBuckets', () => {
  it('buckets by month of creation and splits by outcome', () => {
    const buckets = monthlyBuckets([
      makeItem({ number: 1, outcome: 'merged', created: at('2024-01-05T00:00:00Z') }),
      makeItem({ number: 2, outcome: 'closed', created: at('2024-01-20T00:00:00Z') }),
      makeItem({ number: 3, outcome: 'open', created: at('2024-01-31T23:59:59Z') }),
      makeItem({ number: 4, kind: 'issue', outcome: 'open', created: at('2024-01-02T00:00:00Z') }),
    ]);
    expect(buckets).toHaveLength(1);
    expect(buckets[0]).toMatchObject({ key: '2024-01', merged: 1, closed: 1, open: 1, issues: 1, total: 4 });
  });

  it('fills months with no activity so gaps show as zero', () => {
    const buckets = monthlyBuckets([
      makeItem({ number: 1, created: at('2024-01-15T00:00:00Z') }),
      makeItem({ number: 2, created: at('2024-04-15T00:00:00Z') }),
    ]);
    expect(buckets.map((b) => [b.key, b.total])).toEqual([
      ['2024-01', 1],
      ['2024-02', 0],
      ['2024-03', 0],
      ['2024-04', 1],
    ]);
  });

  it('crosses year boundaries in order', () => {
    const buckets = monthlyBuckets([
      makeItem({ number: 1, created: at('2023-12-31T23:00:00Z') }),
      makeItem({ number: 2, created: at('2024-02-01T00:00:00Z') }),
    ]);
    expect(buckets.map((b) => b.key)).toEqual(['2023-12', '2024-01', '2024-02']);
  });

  it('returns no buckets for no items', () => {
    expect(monthlyBuckets([])).toEqual([]);
  });
});

describe('speedHistogram', () => {
  const merged = (number: number, days: number) =>
    makeItem({ number, outcome: 'merged', daysToMerge: days, merged: 1 });

  it('counts merged pull requests into time-to-merge bands', () => {
    const bands = speedHistogram([merged(1, 0.2), merged(2, 2), merged(3, 5), merged(4, 20), merged(5, 60), merged(6, 400)]);
    expect(bands.map((b) => b.count)).toEqual([1, 1, 1, 1, 1, 1]);
    expect(bands.map((b) => b.label)).toEqual(['Under a day', '1 to 3 days', '3 to 7 days', '1 to 4 weeks', '1 to 3 months', 'Over 3 months']);
  });

  it('puts a boundary value in the slower band', () => {
    const bands = speedHistogram([merged(1, 1), merged(2, 7)]);
    expect(bands[1].count).toBe(1);
    expect(bands[3].count).toBe(1);
  });

  it('ignores work that was never merged', () => {
    const bands = speedHistogram([makeItem({ number: 1, outcome: 'open' }), makeItem({ number: 2, outcome: 'closed' })]);
    expect(bands.every((b) => b.count === 0)).toBe(true);
  });
});

describe('projectRows', () => {
  const items = [
    makeItem({ number: 1, project: 'Apache HBase', repo: 'apache/hbase', outcome: 'merged' }),
    makeItem({ number: 2, project: 'Apache HBase', repo: 'apache/hbase', outcome: 'merged' }),
    makeItem({ number: 3, project: 'Apache HBase', repo: 'apache/hbase-connectors', outcome: 'open' }),
    makeItem({ number: 4, project: 'Apache Phoenix', repo: 'apache/phoenix', outcome: 'merged' }),
  ];

  it('ranks projects by contribution score when the report provides one', () => {
    const rows = projectRows(items, [
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase', score: 5, reviews: 9, commits: 3, rank: 28 }),
      makeContribution({ project: 'Apache Phoenix', repo: 'apache/phoenix', score: 50, reviews: 1, commits: 2, rank: 4 }),
    ]);
    expect(rows.measure).toBe('score');
    expect(rows.projects.map((p) => p.project)).toEqual(['Apache Phoenix', 'Apache HBase']);
    expect(rows.projects[0].value).toBe(50);
  });

  it('falls back to counting activity when there are no aggregate rows', () => {
    const rows = projectRows(items, []);
    expect(rows.measure).toBe('activity');
    expect(rows.projects.map((p) => [p.project, p.value])).toEqual([
      ['Apache HBase', 3],
      ['Apache Phoenix', 1],
    ]);
  });

  it('nests repositories under their project, largest first', () => {
    const rows = projectRows(items, []);
    const hbase = rows.projects[0];
    expect(hbase.repos.map((r) => [r.repo, r.value])).toEqual([
      ['apache/hbase', 2],
      ['apache/hbase-connectors', 1],
    ]);
  });

  it('sums commits, reviews and merged pull requests per project', () => {
    const rows = projectRows(items, [
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase', score: 5, reviews: 9, commits: 3 }),
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase-connectors', score: 1, reviews: 1, commits: 1 }),
    ]);
    const hbase = rows.projects.find((p) => p.project === 'Apache HBase')!;
    expect(hbase).toMatchObject({ reviews: 10, commits: 4, merged: 2, score: 6 });
  });

  it('reports the best rank when several people contribute to a repository', () => {
    const rows = projectRows(items, [
      makeContribution({ repo: 'apache/hbase', user: 'a', rank: 28, score: 1 }),
      makeContribution({ repo: 'apache/hbase', user: 'b', rank: 7, score: 1 }),
    ]);
    const repo = rows.projects[0].repos.find((r) => r.repo === 'apache/hbase')!;
    expect(repo.rank).toBe(7);
  });

  it('gives each project the avatar of its highest-ranked repository', () => {
    const rows = projectRows(items, [
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase-connectors', score: 1, repoAvatar: 'https://a/small' }),
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase', score: 9, repoAvatar: 'https://a/main' }),
    ]);
    expect(rows.projects.find((p) => p.project === 'Apache HBase')?.avatar).toBe('https://a/main');
  });

  it('skips repositories without an avatar, and leaves the project blank if none has one', () => {
    const withGap = projectRows(items, [
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase', score: 9, repoAvatar: '' }),
      makeContribution({ project: 'Apache HBase', repo: 'apache/hbase-connectors', score: 1, repoAvatar: 'https://a/other' }),
    ]);
    expect(withGap.projects.find((p) => p.project === 'Apache HBase')?.avatar).toBe('https://a/other');
    expect(projectRows(items, []).projects.every((p) => p.avatar === '')).toBe(true);
  });
});

describe('counts-only work (redacted private repositories)', () => {
  // What the generator writes for "private_repos": "redact": one row per user with no repository link.
  const redacted = makeContribution({
    project: 'Private work',
    repo: 'Private repositories',
    repoUrl: '',
    score: 40,
    commits: 30,
    reviews: 2,
  });
  const items = [makeItem({ number: 1, project: 'Apache HBase', repo: 'apache/hbase', outcome: 'merged' })];
  const open = makeContribution({ project: 'Apache HBase', repo: 'apache/hbase', score: 5 });

  it('is recognised by having no repository link and no owner/repo name', () => {
    expect(isCountsOnly(redacted)).toBe(true);
    expect(isCountsOnly(open)).toBe(false);
    expect(isCountsOnly(makeContribution({ repo: 'apache/hbase', repoUrl: '' }))).toBe(false);
  });

  it('does not invent a GitHub link for it', () => {
    const rows = projectRows(items, [open, redacted]);
    const row = rows.projects.find((p) => p.project === 'Private work')!.repos[0];
    expect(row.repoUrl).toBe('');
    expect(rows.projects.find((p) => p.project === 'Apache HBase')!.repos[0].repoUrl).toBe('https://github.com/apache/hbase');
  });

  it('marks its project counts-only, and only that project', () => {
    const rows = projectRows(items, [open, redacted]);
    expect(rows.projects.find((p) => p.project === 'Private work')?.countsOnly).toBe(true);
    expect(rows.projects.find((p) => p.project === 'Apache HBase')?.countsOnly).toBe(false);
  });

  it('still counts towards the ranking, the score and the commits', () => {
    const rows = projectRows(items, [open, redacted]);
    expect(rows.projects.map((p) => [p.project, p.value])).toEqual([
      ['Private work', 40],
      ['Apache HBase', 5],
    ]);
    expect(rows.projects[0]).toMatchObject({ commits: 30, reviews: 2, items: 0, merged: 0 });
  });

  it('has no link to follow even if activity records happen to name it', () => {
    const withItems = [makeItem({ number: 9, project: 'Private work', repo: 'Private repositories' })];
    const rows = projectRows(withItems, [redacted]);
    expect(rows.projects[0].items).toBe(1);
    expect(rows.projects[0].countsOnly).toBe(true);   // still no link to follow, whatever else is known
  });
});
