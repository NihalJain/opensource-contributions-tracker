import { useMemo } from 'react';
import { facetCounts, activeFilterCount } from '../data/filters';
import { formatDate, formatInt } from '../data/format';
import type { Filters, Item, Kind, Outcome } from '../data/types';
import { FilterMenu, Popover, type Option } from './FilterMenu';
import './FilterBar.css';

interface Props {
  items: Item[];
  filters: Filters;
  shown: number;
  multiUser: boolean;
  /** Reference time for date presets. */
  now: number;
  onChange: (update: Partial<Filters>) => void;
  onClear: () => void;
}

const KIND_LABEL: Record<Kind, string> = { pr: 'Pull requests', issue: 'Issues' };
const OUTCOME_LABEL: Record<Outcome, string> = { merged: 'Merged', open: 'Open', closed: 'Closed' };

const isoDay = (ms: number) => new Date(ms).toISOString().slice(0, 10);

function options(counts: Map<string, number>, selected: string[], label: (v: string) => string = (v) => v): Option[] {
  const values = new Set([...counts.keys(), ...selected]);
  return [...values]
    .map((value) => ({ value, label: label(value), count: counts.get(value) ?? 0 }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function DateMenu({ filters, now, onChange }: { filters: Filters; now: number; onChange: Props['onChange'] }) {
  const year = new Date(now).getUTCFullYear();
  const presets = [
    { label: 'Last 12 months', from: isoDay(now - 365 * 86_400_000), to: null },
    { label: `${year}`, from: `${year}-01-01`, to: `${year}-12-31` },
    { label: `${year - 1}`, from: `${year - 1}-01-01`, to: `${year - 1}-12-31` },
    { label: 'All time', from: null, to: null },
  ];
  const active = Boolean(filters.from || filters.to);
  const badge = active ? 'On' : undefined;

  return (
    <Popover label="Dates" badge={badge} active={active}>
      {() => (
        <div className="dates">
          <ul className="dates__presets">
            {presets.map((p) => {
              const selected = p.from === filters.from && p.to === filters.to;
              return (
                <li key={p.label}>
                  <button
                    type="button"
                    className="dates__preset"
                    aria-pressed={selected}
                    onClick={() => onChange({ from: p.from, to: p.to })}
                  >
                    <span className="dates__check" aria-hidden="true">
                      {selected ? '✓' : ''}
                    </span>
                    {p.label}
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="dates__custom">
            <label>
              <span>From</span>
              <input type="date" value={filters.from ?? ''} onChange={(e) => onChange({ from: e.target.value || null })} />
            </label>
            <label>
              <span>To</span>
              <input type="date" value={filters.to ?? ''} onChange={(e) => onChange({ to: e.target.value || null })} />
            </label>
          </div>
        </div>
      )}
    </Popover>
  );
}

export function FilterBar({ items, filters, shown, multiUser, now, onChange, onClear }: Props) {
  const facets = useMemo(
    () => ({
      users: facetCounts(items, filters, 'users'),
      projects: facetCounts(items, filters, 'projects'),
      repos: facetCounts(items, filters, 'repos'),
      kinds: facetCounts(items, filters, 'kinds'),
      outcomes: facetCounts(items, filters, 'outcomes'),
      labels: facetCounts(items, filters, 'labels'),
    }),
    [items, filters],
  );

  const chips: { key: string; text: string; remove: () => void }[] = [];
  const addChips = (group: string, values: string[], text: (v: string) => string, set: (next: string[]) => void) =>
    values.forEach((value) =>
      chips.push({ key: `${group}:${value}`, text: `${group}: ${text(value)}`, remove: () => set(values.filter((v) => v !== value)) }),
    );
  addChips('Contributor', filters.users, (v) => v, (users) => onChange({ users }));
  addChips('Project', filters.projects, (v) => v, (projects) => onChange({ projects }));
  addChips('Repository', filters.repos, (v) => v, (repos) => onChange({ repos }));
  addChips('Type', filters.kinds, (v) => KIND_LABEL[v as Kind], (kinds) => onChange({ kinds: kinds as Kind[] }));
  addChips('Status', filters.outcomes, (v) => OUTCOME_LABEL[v as Outcome], (outcomes) => onChange({ outcomes: outcomes as Outcome[] }));
  addChips('Label', filters.labels, (v) => v, (labels) => onChange({ labels }));
  if (filters.from || filters.to) {
    const f = filters.from ? formatDate(Date.parse(`${filters.from}T00:00:00Z`)) : 'start';
    const t = filters.to ? formatDate(Date.parse(`${filters.to}T00:00:00Z`)) : 'today';
    chips.push({ key: 'dates', text: `Opened: ${f} to ${t}`, remove: () => onChange({ from: null, to: null }) });
  }

  const count = activeFilterCount(filters);

  return (
    <div className="filters no-print" role="search" aria-label="Filter activity">
      <div className="page">
        <div className="filters__row">
          <label className="filters__search">
            <span className="visually-hidden">Search titles, repositories, labels or #number</span>
            <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
              <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
              <path d="m13 13 4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              placeholder="Search titles, repositories, #number"
              value={filters.query}
              onChange={(e) => onChange({ query: e.target.value })}
            />
          </label>

          <div className="filters__menus">
            {multiUser ? (
              <FilterMenu
                label="Contributor"
                options={options(facets.users, filters.users)}
                selected={filters.users}
                onChange={(users) => onChange({ users })}
              />
            ) : null}
            <FilterMenu
              label="Project"
              options={options(facets.projects, filters.projects)}
              selected={filters.projects}
              onChange={(projects) => onChange({ projects })}
            />
            <FilterMenu
              label="Repository"
              options={options(facets.repos, filters.repos)}
              selected={filters.repos}
              onChange={(repos) => onChange({ repos })}
              searchable
            />
            <FilterMenu
              label="Type"
              options={options(facets.kinds, filters.kinds, (v) => KIND_LABEL[v as Kind])}
              selected={filters.kinds}
              onChange={(kinds) => onChange({ kinds: kinds as Kind[] })}
            />
            <FilterMenu
              label="Status"
              options={options(facets.outcomes, filters.outcomes, (v) => OUTCOME_LABEL[v as Outcome])}
              selected={filters.outcomes}
              onChange={(outcomes) => onChange({ outcomes: outcomes as Outcome[] })}
            />
            <FilterMenu
              label="Label"
              options={options(facets.labels, filters.labels)}
              selected={filters.labels}
              onChange={(labels) => onChange({ labels })}
              searchable
            />
            <DateMenu filters={filters} now={now} onChange={onChange} />
          </div>
        </div>

        <div className="filters__status">
          <p className="filters__count" aria-live="polite">
            {count === 0
              ? `${formatInt(shown)} pull requests and issues`
              : `${formatInt(shown)} of ${formatInt(items.length)} pull requests and issues match`}
          </p>
          {chips.length > 0 ? (
            <ul className="filters__chips">
              {chips.map((chip) => (
                <li key={chip.key}>
                  <button type="button" className="chip" onClick={chip.remove} aria-label={`Remove filter ${chip.text}`}>
                    {chip.text}
                    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
                      <path d="m3 3 6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    </svg>
                  </button>
                </li>
              ))}
              <li>
                <button type="button" className="filters__clear" onClick={onClear}>
                  Clear all
                </button>
              </li>
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}
