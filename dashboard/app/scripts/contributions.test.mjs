import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { toContributions } from './contributions.mjs';
import { prepareData } from './prepare-data.mjs';

const HEADER =
  'Project Key,Repository,Repository URL,Repository Description,Repository Avatar,User,User Avatar,User URL,' +
  'Commits,Pull Requests (Open),Pull Requests (Closed),Issues (Open),Issues (Closed),Code Reviews,' +
  'Lines Added (Merged),Lines Removed (Merged),Lines Added (Open PRs),Lines Removed (Open PRs),Lines Added,Lines Removed,' +
  'Rank,Overall Contribution';

const ROW =
  'Apache HBase,apache/hbase,https://github.com/apache/hbase,"Apache HBase, the Hadoop database",https://a/1,' +
  'Nihal Jain,https://a/2,https://github.com/NihalJain,84,6,150,0,1,253,10,2,5,1,15,3,28,343';

describe('toContributions', () => {
  it('maps report columns to typed fields', () => {
    const [row] = toContributions([
      {
        'Project Key': 'Apache HBase',
        Repository: 'apache/hbase',
        'Repository URL': 'https://github.com/apache/hbase',
        'Repository Description': 'Apache HBase, the Hadoop database',
        'Repository Avatar': 'https://a/1',
        User: 'Nihal Jain',
        Commits: '84',
        'Pull Requests (Open)': '6',
        'Pull Requests (Closed)': '150',
        'Issues (Open)': '0',
        'Issues (Closed)': '1',
        'Code Reviews': '253',
        'Lines Added': '15',
        'Lines Removed': '3',
        Rank: '28',
        'Overall Contribution': '343',
      },
    ]);
    expect(row).toMatchObject({
      project: 'Apache HBase',
      repo: 'apache/hbase',
      repoUrl: 'https://github.com/apache/hbase',
      description: 'Apache HBase, the Hadoop database',
      user: 'Nihal Jain',
      commits: 84,
      prsOpen: 6,
      prsClosed: 150,
      issuesOpen: 0,
      issuesClosed: 1,
      reviews: 253,
      linesAdded: 15,
      linesRemoved: 3,
      rank: 28,
      score: 343,
    });
  });

  it('treats a rank of -1 or a missing rank as unranked', () => {
    const rows = toContributions([{ Rank: '-1' }, { Rank: '' }, {}]);
    expect(rows.map((r) => r.rank)).toEqual([null, null, null]);
  });

  it('defaults missing or non-numeric counts to zero', () => {
    const [row] = toContributions([{ Commits: 'n/a' }]);
    expect(row.commits).toBe(0);
    expect(row.reviews).toBe(0);
    expect(row.score).toBe(0);
  });
});

describe('prepareData', () => {
  let dir;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'dashboard-data-'));
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  const paths = () => ({
    activityFile: join(dir, 'activity.json'),
    contributionsFile: join(dir, 'contrib.csv'),
    outDir: join(dir, 'public'),
  });

  it('copies the feed, converts the CSV and stamps the build time', () => {
    const p = paths();
    writeFileSync(p.activityFile, '[{"user":"a"}]');
    writeFileSync(p.contributionsFile, `${HEADER}\n${ROW}\n`);

    const result = prepareData({ ...p, now: new Date('2026-01-02T03:04:05Z') });

    expect(readFileSync(join(p.outDir, 'activity.json'), 'utf8')).toBe('[{"user":"a"}]');
    const contributions = JSON.parse(readFileSync(join(p.outDir, 'contributions.json'), 'utf8'));
    expect(contributions).toHaveLength(1);
    expect(contributions[0].description).toBe('Apache HBase, the Hadoop database');
    expect(contributions[0].score).toBe(343);
    expect(JSON.parse(readFileSync(join(p.outDir, 'meta.json'), 'utf8'))).toEqual({
      builtAt: '2026-01-02T03:04:05.000Z',
    });
    expect(result.contributions).toBe(1);
  });

  it('writes llms.txt using the configured site title', () => {
    const p = paths();
    writeFileSync(p.activityFile, '[]');

    prepareData({ ...p, title: 'Ada’s open source work' });

    const text = readFileSync(join(p.outDir, 'llms.txt'), 'utf8');
    expect(text.split('\n')[0]).toBe('# Ada’s open source work');
  });

  it('fails when the activity feed is missing', () => {
    expect(() => prepareData(paths())).toThrow(/Activity data not found/);
  });

  it('still builds without the CSV, publishing no aggregate metrics', () => {
    const p = paths();
    writeFileSync(p.activityFile, '[]');

    const result = prepareData(p);

    expect(JSON.parse(readFileSync(join(p.outDir, 'contributions.json'), 'utf8'))).toEqual([]);
    expect(existsSync(join(p.outDir, 'activity.json'))).toBe(true);
    expect(result.contributions).toBe(0);
  });
});
