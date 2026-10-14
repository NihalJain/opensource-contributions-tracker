import type { ProjectBreakdown, Totals } from '../data/aggregate';
import { formatInt, formatMonth, plural } from '../data/format';
import type { Person } from '../data/types';
import type { Theme } from '../hooks/useTheme';
import { Ribbon } from './Ribbon';
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

export function Hero(props: Props) {
  const { totals, metrics, breakdown } = props;
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
          <Ribbon
            breakdown={breakdown}
            selected={props.selectedProjects}
            onToggle={props.onToggleProject}
          />
        ) : null}
      </div>
    </header>
  );
}
