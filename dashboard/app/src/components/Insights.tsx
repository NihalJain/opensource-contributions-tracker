import type { MonthBucket } from '../data/aggregate';
import { formatDays, formatInt, formatMonth, plural } from '../data/format';
import { busiestMonth, longestOpen, mergeRate, medianDaysToMerge } from '../data/insights';
import type { Item } from '../data/types';
import './Insights.css';

interface Props {
  items: Item[];
  buckets: MonthBucket[];
  /** Reference time for ages, so the page reads the same as when the data was built. */
  now: number;
  /** Code reviews per merged pull request, when the report provides reviews. */
  reviewsPerMerge: number | null;
}

interface Fact {
  label: string;
  value: string;
  context: React.ReactNode;
}

export function Insights({ items, buckets, now, reviewsPerMerge }: Props) {
  const facts: Fact[] = [];

  const median = medianDaysToMerge(items);
  if (median !== null) {
    const merged = items.filter((i) => i.outcome === 'merged').length;
    facts.push({
      label: 'Typical time to merge',
      value: formatDays(median),
      context: `Median across ${plural(merged, 'merged pull request')}`,
    });
  }

  const rate = mergeRate(items);
  if (rate) {
    facts.push({
      label: 'Merge rate',
      value: `${Math.round(rate.rate * 100)}%`,
      context: `${formatInt(rate.merged)} of ${formatInt(rate.finished)} finished pull requests were merged`,
    });
  }

  if (reviewsPerMerge !== null) {
    facts.push({
      label: 'Reviews per merge',
      value: reviewsPerMerge.toFixed(1),
      context: 'Code reviews given for every pull request merged',
    });
  }

  const oldest = longestOpen(items, now);
  if (oldest) {
    facts.push({
      label: 'Longest open',
      value: formatDays(oldest.days),
      context: (
        <a href={oldest.item.url} target="_blank" rel="noreferrer">
          {oldest.item.repo} #{oldest.item.number}
        </a>
      ),
    });
  }

  const busiest = busiestMonth(buckets);
  if (busiest && buckets.length > 1) {
    facts.push({
      label: 'Busiest month',
      value: formatMonth(busiest.start),
      context: `${plural(busiest.total, 'pull request or issue', 'pull requests and issues')} opened`,
    });
  }

  if (facts.length === 0) return null;

  return (
    <section className="insights" aria-label="Highlights">
      <dl className="insights__list">
        {facts.map((fact) => (
          <div key={fact.label} className="insights__fact">
            <dt>{fact.label}</dt>
            <dd className="insights__value">{fact.value}</dd>
            <dd className="insights__context">{fact.context}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
