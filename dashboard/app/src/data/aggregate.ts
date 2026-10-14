import type { Contribution, Item } from './types';

export interface Totals {
  merged: number;
  closedPrs: number;
  openPrs: number;
  issues: number;
  openIssues: number;
  items: number;
}

export function totals(items: Item[]): Totals {
  const t: Totals = { merged: 0, closedPrs: 0, openPrs: 0, issues: 0, openIssues: 0, items: items.length };
  for (const item of items) {
    if (item.kind === 'issue') {
      t.issues += 1;
      if (item.outcome === 'open') t.openIssues += 1;
    } else if (item.outcome === 'merged') {
      t.merged += 1;
    } else if (item.outcome === 'closed') {
      t.closedPrs += 1;
    } else {
      t.openPrs += 1;
    }
  }
  return t;
}

export interface MonthBucket {
  /** `YYYY-MM`, UTC. */
  key: string;
  /** First instant of the month, UTC epoch milliseconds. */
  start: number;
  merged: number;
  closed: number;
  open: number;
  issues: number;
  total: number;
}

const monthKey = (ms: number) => new Date(ms).toISOString().slice(0, 7);
const monthStart = (ms: number) => {
  const d = new Date(ms);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1);
};

/** Items per month of creation from the first to the last month, including empty months. */
export function monthlyBuckets(items: Item[]): MonthBucket[] {
  if (items.length === 0) return [];

  let first = Infinity;
  let last = -Infinity;
  for (const item of items) {
    first = Math.min(first, item.created);
    last = Math.max(last, item.created);
  }

  const buckets = new Map<string, MonthBucket>();
  const cursor = new Date(monthStart(first));
  const end = monthStart(last);
  while (cursor.getTime() <= end) {
    const start = cursor.getTime();
    buckets.set(monthKey(start), { key: monthKey(start), start, merged: 0, closed: 0, open: 0, issues: 0, total: 0 });
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }

  for (const item of items) {
    const bucket = buckets.get(monthKey(item.created));
    if (!bucket) continue;
    bucket.total += 1;
    if (item.kind === 'issue') bucket.issues += 1;
    else if (item.outcome === 'merged') bucket.merged += 1;
    else if (item.outcome === 'closed') bucket.closed += 1;
    else bucket.open += 1;
  }

  return [...buckets.values()];
}

export interface SpeedBand {
  label: string;
  /** Inclusive lower bound, in days. */
  min: number;
  /** Exclusive upper bound, in days. */
  max: number;
  count: number;
}

const BANDS: Omit<SpeedBand, 'count'>[] = [
  { label: 'Under a day', min: 0, max: 1 },
  { label: '1 to 3 days', min: 1, max: 3 },
  { label: '3 to 7 days', min: 3, max: 7 },
  { label: '1 to 4 weeks', min: 7, max: 28 },
  { label: '1 to 3 months', min: 28, max: 91 },
  { label: 'Over 3 months', min: 91, max: Infinity },
];

/** How long merged pull requests took to land, in ordered bands. */
export function speedHistogram(items: Item[]): SpeedBand[] {
  const bands = BANDS.map((band) => ({ ...band, count: 0 }));
  for (const item of items) {
    if (item.outcome !== 'merged' || item.daysToMerge === null) continue;
    const band = bands.find((b) => item.daysToMerge! >= b.min && item.daysToMerge! < b.max);
    if (band) band.count += 1;
  }
  return bands;
}

export interface RepoRow {
  repo: string;
  repoUrl: string;
  description: string;
  repoAvatar: string;
  /** The ranking measure: contribution score, or number of items when the report has no score. */
  value: number;
  score: number;
  reviews: number;
  commits: number;
  merged: number;
  items: number;
  rank: number | null;
}

export interface ProjectRow {
  project: string;
  value: number;
  score: number;
  reviews: number;
  commits: number;
  merged: number;
  items: number;
  repos: RepoRow[];
}

export interface ProjectBreakdown {
  /** `score` uses the report's weighted contribution score; `activity` counts pull requests and issues. */
  measure: 'score' | 'activity';
  projects: ProjectRow[];
}

/** Group items and aggregate rows by project and repository, ranked by contribution. */
export function projectRows(items: Item[], contributions: Contribution[]): ProjectBreakdown {
  const useScore = contributions.some((row) => row.score > 0);
  const repos = new Map<string, RepoRow & { project: string }>();

  const repoRow = (project: string, repo: string) => {
    let row = repos.get(repo);
    if (!row) {
      row = {
        project,
        repo,
        repoUrl: `https://github.com/${repo}`,
        description: '',
        repoAvatar: '',
        value: 0,
        score: 0,
        reviews: 0,
        commits: 0,
        merged: 0,
        items: 0,
        rank: null,
      };
      repos.set(repo, row);
    }
    return row;
  };

  for (const c of contributions) {
    const row = repoRow(c.project, c.repo);
    row.repoUrl = c.repoUrl || row.repoUrl;
    row.description = c.description || row.description;
    row.repoAvatar = c.repoAvatar || row.repoAvatar;
    row.score += c.score;
    row.reviews += c.reviews;
    row.commits += c.commits;
    if (c.rank !== null) row.rank = row.rank === null ? c.rank : Math.min(row.rank, c.rank);
  }

  for (const item of items) {
    const row = repoRow(item.project, item.repo);
    row.items += 1;
    if (item.outcome === 'merged') row.merged += 1;
  }

  const projects = new Map<string, ProjectRow>();
  for (const row of repos.values()) {
    row.value = useScore ? row.score : row.items;
    let project = projects.get(row.project);
    if (!project) {
      project = { project: row.project, value: 0, score: 0, reviews: 0, commits: 0, merged: 0, items: 0, repos: [] };
      projects.set(row.project, project);
    }
    project.value += row.value;
    project.score += row.score;
    project.reviews += row.reviews;
    project.commits += row.commits;
    project.merged += row.merged;
    project.items += row.items;
    const { project: _project, ...repoOnly } = row;
    project.repos.push(repoOnly);
  }

  const byValue = <T extends { value: number }>(list: T[]) => list.sort((a, b) => b.value - a.value);
  const ranked = byValue([...projects.values()]).filter((p) => p.value > 0 || p.items > 0 || p.reviews > 0);
  for (const project of ranked) byValue(project.repos);

  return { measure: useScore ? 'score' : 'activity', projects: ranked };
}
