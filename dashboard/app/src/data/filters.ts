import type { Contribution, Filters, Item } from './types';

export const emptyFilters: Filters = {
  users: [],
  projects: [],
  repos: [],
  kinds: [],
  outcomes: [],
  labels: [],
  from: null,
  to: null,
  query: '',
};

export type FacetKey = 'users' | 'projects' | 'repos' | 'kinds' | 'outcomes' | 'labels';
export type FilterKey = keyof Filters;

const startOfDay = (date: string) => Date.parse(`${date}T00:00:00Z`);
const endOfDay = (date: string) => Date.parse(`${date}T23:59:59.999Z`);

function matchesQuery(item: Item, tokens: string[]): boolean {
  if (tokens.length === 0) return true;
  const haystack = [item.title, item.repo, item.project, item.user, `#${item.number}`, ...item.labels]
    .join(' ')
    .toLowerCase();
  return tokens.every((token) => haystack.includes(token));
}

/**
 * Apply filters to items. Pass `skip` to ignore one dimension, which is how a facet shows the
 * counts it would have if its own selection were cleared.
 */
export function applyFilters(items: Item[], f: Filters, skip?: FilterKey): Item[] {
  const use = (key: FilterKey) => key !== skip;
  const tokens = f.query.toLowerCase().split(/\s+/).filter(Boolean);
  const from = use('from') && f.from ? startOfDay(f.from) : null;
  const to = use('to') && f.to ? endOfDay(f.to) : null;

  return items.filter(
    (item) =>
      (!use('users') || f.users.length === 0 || f.users.includes(item.user)) &&
      (!use('projects') || f.projects.length === 0 || f.projects.includes(item.project)) &&
      (!use('repos') || f.repos.length === 0 || f.repos.includes(item.repo)) &&
      (!use('kinds') || f.kinds.length === 0 || f.kinds.includes(item.kind)) &&
      (!use('outcomes') || f.outcomes.length === 0 || f.outcomes.includes(item.outcome)) &&
      (!use('labels') || f.labels.length === 0 || item.labels.some((label) => f.labels.includes(label))) &&
      (from === null || item.created >= from) &&
      (to === null || item.created <= to) &&
      (!use('query') || matchesQuery(item, tokens)),
  );
}

/** How many items each value of a facet would match, ignoring that facet's own selection. */
export function facetCounts(items: Item[], f: Filters, key: FacetKey): Map<string, number> {
  const counts = new Map<string, number>();
  for (const item of applyFilters(items, f, key)) {
    const values: string[] =
      key === 'users'
        ? [item.user]
        : key === 'projects'
          ? [item.project]
          : key === 'repos'
            ? [item.repo]
            : key === 'kinds'
              ? [item.kind]
              : key === 'outcomes'
                ? [item.outcome]
                : item.labels;
    for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return counts;
}

/** Aggregate rows have no dates or states, so only who and where can scope them. */
export function filterContributions(rows: Contribution[], f: Filters): Contribution[] {
  return rows.filter(
    (row) =>
      (f.users.length === 0 || f.users.includes(row.user)) &&
      (f.projects.length === 0 || f.projects.includes(row.project)) &&
      (f.repos.length === 0 || f.repos.includes(row.repo)),
  );
}

export function activeFilterCount(f: Filters): number {
  return (
    [f.users, f.projects, f.repos, f.kinds, f.outcomes, f.labels].filter((list) => list.length > 0).length +
    (f.from || f.to ? 1 : 0) +
    (f.query.trim() ? 1 : 0)
  );
}

export function isFiltered(f: Filters): boolean {
  return activeFilterCount(f) > 0;
}
