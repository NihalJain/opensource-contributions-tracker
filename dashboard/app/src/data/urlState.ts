import { emptyFilters } from './filters';
import type { Filters, Kind, Outcome } from './types';

export type SortKey = 'created' | 'title' | 'repo' | 'speed';
export type SortDir = 'asc' | 'desc';

/** Everything that defines what the page is showing, so a link reproduces the view. */
export interface ViewState {
  filters: Filters;
  sort: SortKey;
  dir: SortDir;
  page: number;
}

export const defaultView: ViewState = { filters: emptyFilters, sort: 'created', dir: 'desc', page: 1 };

const KINDS: Kind[] = ['pr', 'issue'];
const OUTCOMES: Outcome[] = ['merged', 'closed', 'open'];
const SORTS: SortKey[] = ['created', 'title', 'repo', 'speed'];
const DATE = /^\d{4}-\d{2}-\d{2}$/;

const pick = <T extends string>(values: string[], allowed: readonly T[]): T[] =>
  values.filter((value): value is T => (allowed as readonly string[]).includes(value));

/** Serialise a view as a query string without the leading `?`; the default view is empty. */
export function encodeView(view: ViewState): string {
  const p = new URLSearchParams();
  const { filters: f } = view;
  f.users.forEach((v) => p.append('user', v));
  f.projects.forEach((v) => p.append('project', v));
  f.repos.forEach((v) => p.append('repo', v));
  f.kinds.forEach((v) => p.append('type', v));
  f.outcomes.forEach((v) => p.append('status', v));
  f.labels.forEach((v) => p.append('label', v));
  if (f.from) p.set('from', f.from);
  if (f.to) p.set('to', f.to);
  if (f.query.trim()) p.set('q', f.query.trim());
  if (view.sort !== defaultView.sort) p.set('sort', view.sort);
  if (view.dir !== defaultView.dir) p.set('dir', view.dir);
  if (view.page > 1) p.set('page', String(view.page));
  return p.toString();
}

/** Read a view from `location.hash` or `location.search`, ignoring anything it does not recognise. */
export function decodeView(input: string): ViewState {
  const p = new URLSearchParams(input.replace(/^#?\??/, ''));
  const date = (key: string) => {
    const value = p.get(key);
    return value && DATE.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) ? value : null;
  };
  const page = Number.parseInt(p.get('page') ?? '1', 10);
  const sort = p.get('sort');
  const dir = p.get('dir');

  return {
    filters: {
      users: p.getAll('user'),
      projects: p.getAll('project'),
      repos: p.getAll('repo'),
      kinds: pick(p.getAll('type'), KINDS),
      outcomes: pick(p.getAll('status'), OUTCOMES),
      labels: p.getAll('label'),
      from: date('from'),
      to: date('to'),
      query: p.get('q') ?? '',
    },
    sort: SORTS.includes(sort as SortKey) ? (sort as SortKey) : defaultView.sort,
    dir: dir === 'asc' || dir === 'desc' ? dir : defaultView.dir,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}
