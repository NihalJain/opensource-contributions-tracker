import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ProjectBreakdown, Totals } from '../data/aggregate';
import { formatCompact, formatInt, formatMonth, plural } from '../data/format';
import type { Person } from '../data/types';
import { useWidth } from '../hooks/useSize';
import type { Theme } from '../hooks/useTheme';
import './Hero.css';

export interface HeroMetrics {
  reviews: number;
  commits: number;
  score: number;
}

interface Props {
  title: string;
  people: Person[];
  totals: Totals;
  metrics: HeroMetrics | null;
  /** True when a date range hides that reviews, commits and score are not dated. */
  metricsAllTime: boolean;
  span: { from: number; to: number } | null;
  projectCount: number;
  repoCount: number;
  breakdown: ProjectBreakdown;
  selectedProjects: string[];
  onToggleProject: (project: string) => void;
  theme: Theme;
  onToggleTheme: () => void;
}

function Identity({ people }: { people: Person[] }) {
  if (people.length === 1) {
    const [person] = people;
    return (
      <a className="hero__who" href={person.url} target="_blank" rel="noreferrer">
        <img className="hero__avatar" src={person.avatar} alt="" width="36" height="36" />
        <span>{person.name}</span>
      </a>
    );
  }
  return (
    <p className="hero__who">
      <span className="hero__stack" aria-hidden="true">
        {people.slice(0, 5).map((person) => (
          <img key={person.name} className="hero__avatar" src={person.avatar} alt="" width="36" height="36" />
        ))}
      </span>
      <span>{plural(people.length, 'contributor')}</span>
    </p>
  );
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button type="button" className="hero__theme no-print" onClick={onToggle} aria-label={`Switch to ${next} theme`}>
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        {theme === 'dark' ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
          </>
        ) : (
          <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />
        )}
      </svg>
    </button>
  );
}

/** Horizontal padding inside a ribbon segment, both sides together. */
const SEGMENT_PADDING = 26;

/**
 * Measures text in the real font so a label is only drawn where it fits. The measurement is
 * repeated once web fonts finish loading, because the fallback font is wider or narrower.
 */
function useTextWidth(font: string) {
  const [loaded, setLoaded] = useState(0);
  const context = useMemo(() => document.createElement('canvas').getContext('2d'), []);

  useEffect(() => {
    let cancelled = false;
    document.fonts?.ready.then(() => {
      if (!cancelled) setLoaded((n) => n + 1);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return useCallback(
    (text: string) => {
      if (!context) return text.length * 8;
      context.font = font;
      return context.measureText(text).width;
    },
    // `loaded` is a dependency on purpose: it changes when the fonts become available.
    [context, font, loaded],
  );
}

/** WCAG 2.2 minimum pointer target. */
const MIN_TARGET = 24;

export function Hero(props: Props) {
  const { totals, metrics, breakdown } = props;
  const { ref: ribbonRef, width: ribbonWidth } = useWidth<HTMLUListElement>(960);
  const nameWidth = useTextWidth('600 13px "Archivo Variable", sans-serif');
  const valueWidth = useTextWidth('700 13px "Archivo Variable", sans-serif');
  const total = breakdown.projects.reduce((sum, p) => sum + p.value, 0);
  const usable = Math.max(ribbonWidth - 2 * Math.max(breakdown.projects.length - 1, 0), 0);
  const measureLabel = breakdown.measure === 'score' ? 'by contribution score' : 'by pull requests and issues';
  const places = `${plural(props.projectCount, 'project')} and ${plural(props.repoCount, 'repository', 'repositories')}`;
  const start = props.span ? formatMonth(props.span.from) : null;
  const many = props.people.length > 1;
  const sentence =
    totals.items === 0
      ? 'No activity matches the current filters.'
      : `${many ? `From ${plural(props.people.length, 'contributor')} ` : ''}${
          start ? (many ? 'since ' : 'Since ') + start + ', across ' : many ? 'across ' : 'Across '
        }${places}.`;

  const facts: { label: string; value: string }[] = [];
  if (metrics) {
    facts.push({ label: 'Code reviews', value: formatInt(metrics.reviews) });
    facts.push({ label: 'Commits', value: formatInt(metrics.commits) });
    if (metrics.score > 0) facts.push({ label: 'Contribution score', value: formatInt(metrics.score) });
  }
  facts.push({ label: 'Issues opened', value: formatInt(totals.issues) });
  facts.push({ label: 'Pull requests open', value: formatInt(totals.openPrs) });

  return (
    <header className="hero">
      <div className="page">
        <div className="hero__bar">
          <h1 className="hero__title">{props.title}</h1>
          <ThemeToggle theme={props.theme} onToggle={props.onToggleTheme} />
        </div>

        <div className="hero__main">
          <div className="hero__lead">
            <Identity people={props.people} />
            <p className="hero__figure" aria-label={`${formatInt(totals.merged)} pull requests merged`}>
              {formatInt(totals.merged)}
            </p>
            <p className="hero__caption">{totals.merged === 1 ? 'pull request merged' : 'pull requests merged'}</p>
            <p className="hero__sentence">{sentence}</p>
          </div>

          <dl className="hero__facts">
            {facts.map((fact) => (
              <div key={fact.label} className="hero__fact">
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
        </div>
        {metrics && props.metricsAllTime ? (
          <p className="hero__note">Reviews, commits and score are not dated, so they always cover all time.</p>
        ) : null}

        {breakdown.projects.length > 0 ? (
          <section className="ribbon" aria-label="Where the work went">
            <div className="ribbon__head">
              <h2 className="ribbon__title">Where the work went</h2>
              <p className="ribbon__measure">{measureLabel}</p>
            </div>
            <ul className="ribbon__bar" ref={ribbonRef}>
              {breakdown.projects.map((project, i) => {
                const share = total > 0 ? project.value / total : 0;
                const selected = props.selectedProjects.includes(project.project);
                const dim = props.selectedProjects.length > 0 && !selected;
                const value = breakdown.measure === 'score' ? formatCompact(project.value) : formatInt(project.value);
                const room = share * usable;
                const interactive = room >= MIN_TARGET;
                const showName = room >= nameWidth(project.project) + SEGMENT_PADDING;
                const showValue = room >= valueWidth(value) + SEGMENT_PADDING;
                return (
                  <li key={project.project} style={{ flexGrow: Math.max(project.value, 0.0001), ['--i' as string]: i }}>
                    {interactive ? (
                      <button
                        type="button"
                        className="ribbon__seg"
                        data-selected={selected || undefined}
                        data-dim={dim || undefined}
                        data-narrow={!showValue || undefined}
                        aria-pressed={selected}
                        title={`${project.project}: ${value}`}
                        onClick={() => props.onToggleProject(project.project)}
                      >
                        {showName ? <span className="ribbon__name">{project.project}</span> : null}
                        {showValue ? <span className="ribbon__value">{value}</span> : null}
                        {!showName && !showValue ? (
                          <span className="visually-hidden">{`${project.project}: ${value}`}</span>
                        ) : null}
                      </button>
                    ) : (
                      <span
                        className="ribbon__seg ribbon__seg--static"
                        data-selected={selected || undefined}
                        data-dim={dim || undefined}
                        data-narrow
                        title={`${project.project}: ${value}`}
                        role="img"
                        aria-label={`${project.project}: ${value}`}
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}
      </div>
    </header>
  );
}
