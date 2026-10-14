import { useMemo } from 'react';
import { formatDate, formatDays, formatInt } from '../data/format';
import { toCsv } from '../data/exportCsv';
import type { Item } from '../data/types';
import type { SortDir, SortKey } from '../data/urlState';
import './Explorer.css';

const PAGE_SIZE = 25;

interface Props {
  items: Item[];
  sort: SortKey;
  dir: SortDir;
  page: number;
  now: number;
  onSort: (sort: SortKey) => void;
  onPage: (page: number) => void;
  onClear: () => void;
  filtered: boolean;
}

const STATUS = { merged: 'Merged', closed: 'Closed', open: 'Open' } as const;

function compare(sort: SortKey, a: Item, b: Item): number {
  switch (sort) {
    case 'title':
      return a.title.localeCompare(b.title);
    case 'repo':
      return a.repo.localeCompare(b.repo) || a.number - b.number;
    case 'speed':
      // Work that has not merged has no speed; keep it after everything that has.
      if (a.daysToMerge === null && b.daysToMerge === null) return 0;
      if (a.daysToMerge === null) return 1;
      if (b.daysToMerge === null) return -1;
      return a.daysToMerge - b.daysToMerge;
    default:
      return a.created - b.created;
  }
}

function SortHeader({
  label,
  field,
  sort,
  dir,
  onSort,
  align,
}: {
  label: string;
  field: SortKey;
  sort: SortKey;
  dir: SortDir;
  onSort: (sort: SortKey) => void;
  align?: 'end';
}) {
  const active = sort === field;
  return (
    <th scope="col" aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'} className={align ? 'is-end' : undefined}>
      <button type="button" className="sort" onClick={() => onSort(field)}>
        {label}
        <span className="sort__arrow" aria-hidden="true">
          {active ? (dir === 'asc' ? '↑' : '↓') : ''}
        </span>
      </button>
    </th>
  );
}

function download(items: Item[]) {
  const blob = new Blob([toCsv(items)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'open-source-contributions.csv';
  link.click();
  URL.revokeObjectURL(url);
}

export function Explorer({ items, sort, dir, page, now, onSort, onPage, onClear, filtered }: Props) {
  const sorted = useMemo(() => {
    const direction = dir === 'asc' ? 1 : -1;
    return [...items].sort((a, b) => compare(sort, a, b) * direction || a.id.localeCompare(b.id));
  }, [items, sort, dir]);

  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const start = (current - 1) * PAGE_SIZE;
  const visible = sorted.slice(start, start + PAGE_SIZE);

  return (
    <section className="explorer" aria-labelledby="explorer-title">
      <header className="explorer__head">
        <div>
          <h2 id="explorer-title" className="explorer__title">
            Every pull request and issue
          </h2>
          <p className="explorer__desc" aria-live="polite">
            {sorted.length === 0
              ? 'Nothing to show.'
              : `Showing ${formatInt(start + 1)} to ${formatInt(start + visible.length)} of ${formatInt(sorted.length)}.`}
          </p>
        </div>
        <button type="button" className="explorer__export no-print" onClick={() => download(sorted)} disabled={sorted.length === 0}>
          Download CSV
        </button>
      </header>

      {sorted.length === 0 ? (
        <div className="explorer__empty">
          <p>No pull requests or issues match these filters.</p>
          {filtered ? (
            <button type="button" className="explorer__export" onClick={onClear}>
              Clear filters
            </button>
          ) : null}
        </div>
      ) : (
        <>
          <div className="explorer__scroll">
            <table className="grid">
              <thead>
                <tr>
                  <SortHeader label="Title" field="title" sort={sort} dir={dir} onSort={onSort} />
                  <th scope="col">Type</th>
                  <th scope="col">Status</th>
                  <SortHeader label="Opened" field="created" sort={sort} dir={dir} onSort={onSort} />
                  <SortHeader label="Time to merge" field="speed" sort={sort} dir={dir} onSort={onSort} align="end" />
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => (
                  <tr key={item.id}>
                    <td className="grid__title" data-label="Title">
                      <a href={item.url} target="_blank" rel="noreferrer">
                        {item.title}
                      </a>
                      <span className="grid__meta">
                        {item.repo} #{item.number}
                        {item.labels.slice(0, 3).map((label) => (
                          <span key={label} className="grid__label">
                            {label}
                          </span>
                        ))}
                        {item.labels.length > 3 ? <span className="grid__more">+{item.labels.length - 3}</span> : null}
                      </span>
                    </td>
                    <td data-label="Type">{item.kind === 'pr' ? 'Pull request' : 'Issue'}</td>
                    <td data-label="Status">
                      <span className="status" data-outcome={item.outcome}>
                        <span className="status__dot" aria-hidden="true" />
                        {STATUS[item.outcome]}
                      </span>
                    </td>
                    <td data-label="Opened" className="grid__num">
                      {formatDate(item.created)}
                    </td>
                    <td data-label="Time to merge" className="grid__num is-end">
                      {item.daysToMerge !== null
                        ? formatDays(item.daysToMerge)
                        : item.kind === 'pr' && item.outcome === 'open'
                          ? `Open ${formatDays((now - item.created) / 86_400_000)}`
                          : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 ? (
            <nav className="pager no-print" aria-label="Pagination">
              <button type="button" onClick={() => onPage(current - 1)} disabled={current <= 1}>
                Previous
              </button>
              <span className="pager__status">
                Page {formatInt(current)} of {formatInt(pages)}
              </span>
              <button type="button" onClick={() => onPage(current + 1)} disabled={current >= pages}>
                Next
              </button>
            </nav>
          ) : null}
        </>
      )}
    </section>
  );
}
