import { useEffect, useMemo } from 'react';
import site from '../site.config.json';
import { Timeline } from './charts/Timeline';
import { Contributors } from './components/Contributors';
import { Explorer } from './components/Explorer';
import { FilterBar } from './components/FilterBar';
import { Hero } from './components/Hero';
import { Insights } from './components/Insights';
import { Projects } from './components/Projects';
import { LoadError, Loading, NoData } from './components/States';
import { Speed } from './components/Speed';
import { monthlyBuckets, projectRows, speedHistogram, totals } from './data/aggregate';
import { applyFilters, filterContributions, isFiltered } from './data/filters';
import { formatDate } from './data/format';
import { activeSpan } from './data/insights';
import type { Dataset } from './data/types';
import { useDataset } from './hooks/useDataset';
import { useTheme } from './hooks/useTheme';
import { useView } from './hooks/useView';

const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

function Dashboard({ data, theme, onToggleTheme }: { data: Dataset; theme: 'light' | 'dark'; onToggleTheme: () => void }) {
  const { view, setFilters, clearFilters, setSort, setPage } = useView();
  const { filters } = view;
  const now = data.meta.builtAt ? Date.parse(data.meta.builtAt) : Date.now();

  // Each part of the page ignores the filters that would hide its own choices: the timeline keeps
  // every month so a range can be changed, and the project list keeps every project so one can be
  // switched off again.
  const filtered = useMemo(() => applyFilters(data.items, filters), [data.items, filters]);
  const forTimeline = useMemo(
    () => applyFilters(data.items, { ...filters, from: null, to: null }),
    [data.items, filters],
  );
  const forProjects = useMemo(
    () => applyFilters(data.items, { ...filters, projects: [], repos: [] }),
    [data.items, filters],
  );

  const scopedRows = useMemo(() => filterContributions(data.contributions, filters), [data.contributions, filters]);
  const projectRowsInput = useMemo(
    () => filterContributions(data.contributions, { ...filters, projects: [], repos: [] }),
    [data.contributions, filters],
  );

  const sums = useMemo(() => totals(filtered), [filtered]);
  const buckets = useMemo(() => monthlyBuckets(forTimeline), [forTimeline]);
  const breakdown = useMemo(() => projectRows(forProjects, projectRowsInput), [forProjects, projectRowsInput]);
  const speed = useMemo(() => speedHistogram(filtered), [filtered]);
  const span = useMemo(() => activeSpan(filtered.length > 0 ? filtered : data.items), [filtered, data.items]);

  const metrics = useMemo(
    () =>
      data.contributions.length === 0
        ? null
        : {
            reviews: scopedRows.reduce((s, r) => s + r.reviews, 0),
            commits: scopedRows.reduce((s, r) => s + r.commits, 0),
            score: scopedRows.reduce((s, r) => s + r.score, 0),
          },
    [data.contributions.length, scopedRows],
  );

  const projects = new Set([...filtered.map((i) => i.project), ...scopedRows.map((r) => r.project)]);
  const repos = new Set([...filtered.map((i) => i.repo), ...scopedRows.map((r) => r.repo)]);
  const multiUser = data.people.length > 1;
  const visiblePeople = filters.users.length > 0 ? data.people.filter((p) => filters.users.includes(p.name)) : data.people;
  const reviewsPerMerge = metrics && sums.merged > 0 && metrics.reviews > 0 ? metrics.reviews / sums.merged : null;

  return (
    <>
      <Hero
        title={site.title}
        people={visiblePeople}
        totals={sums}
        metrics={metrics}
        metricsAllTime={Boolean(filters.from || filters.to)}
        span={span}
        projectCount={projects.size}
        repoCount={repos.size}
        breakdown={breakdown}
        selectedProjects={filters.projects}
        onToggleProject={(project) => setFilters((f) => ({ ...f, projects: toggle(f.projects, project) }))}
        theme={theme}
        onToggleTheme={onToggleTheme}
      />

      <FilterBar
        items={data.items}
        filters={filters}
        shown={filtered.length}
        multiUser={multiUser}
        now={now}
        onChange={(update) => setFilters(update)}
        onClear={clearFilters}
      />

      <main id="main" className="page layout">
        <Insights items={filtered} buckets={buckets} now={now} reviewsPerMerge={reviewsPerMerge} />

        <div className="layout__block">
          <Timeline buckets={buckets} range={{ from: filters.from, to: filters.to }} onRange={(r) => setFilters(r)} />
        </div>

        <div className="layout__split">
          <Projects
            breakdown={breakdown}
            selectedProjects={filters.projects}
            selectedRepos={filters.repos}
            onToggleProject={(project) => setFilters((f) => ({ ...f, projects: toggle(f.projects, project) }))}
            onToggleRepo={(repo) => setFilters((f) => ({ ...f, repos: toggle(f.repos, repo) }))}
          />
          <div className="layout__stack">
            <Speed bands={speed} />
            {multiUser ? (
              <Contributors
                people={data.people}
                items={forProjects}
                contributions={projectRowsInput}
                selected={filters.users}
                onToggle={(name) => setFilters((f) => ({ ...f, users: toggle(f.users, name) }))}
              />
            ) : null}
          </div>
        </div>

        <div className="layout__block">
          <Explorer
            items={filtered}
            people={data.people}
            showContributor={multiUser}
            sort={view.sort}
            dir={view.dir}
            page={view.page}
            now={now}
            onSort={(sort) => setSort(sort)}
            onPage={setPage}
            onClear={clearFilters}
            filtered={isFiltered(filters)}
          />
        </div>
      </main>

      <footer className="footer">
        <div className="page footer__inner">
          <p>
            {data.meta.builtAt ? `Data as of ${formatDate(Date.parse(data.meta.builtAt))}. ` : ''}
            Generated by{' '}
            <a href="https://github.com/NihalJain/opensource-contributions-tracker" target="_blank" rel="noreferrer">
              opensource-contributions-tracker
            </a>
            , which anyone can fork to host their own.
          </p>
        </div>
      </footer>
    </>
  );
}

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme();
  const { state, reload } = useDataset();

  useEffect(() => {
    document.title = site.title;
  }, []);

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to the activity
      </a>
      {state.status === 'loading' ? <Loading title={site.title} /> : null}
      {state.status === 'error' ? <LoadError title={site.title} message={state.message} onRetry={reload} /> : null}
      {state.status === 'ready' && state.data.items.length === 0 ? <NoData title={site.title} /> : null}
      {state.status === 'ready' && state.data.items.length > 0 ? (
        <Dashboard data={state.data} theme={theme} onToggleTheme={toggleTheme} />
      ) : null}
    </>
  );
}
