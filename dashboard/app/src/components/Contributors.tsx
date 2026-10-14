import { BarList } from '../charts/BarList';
import { formatCompact, formatInt, plural } from '../data/format';
import type { Contribution, Item, Person } from '../data/types';
import { ChartFrame, DataTable } from './ChartFrame';
import './Contributors.css';

interface Props {
  people: Person[];
  items: Item[];
  contributions: Contribution[];
  selected: string[];
  onToggle: (name: string) => void;
}

/** Shown only when the report covers more than one person. */
export function Contributors({ people, items, contributions, selected, onToggle }: Props) {
  const useScore = contributions.some((c) => c.score > 0);

  const rows = people
    .map((person) => {
      const mine = contributions.filter((c) => c.user === person.name);
      const merged = items.filter((i) => i.user === person.name && i.outcome === 'merged').length;
      const total = items.filter((i) => i.user === person.name).length;
      const score = mine.reduce((s, c) => s + c.score, 0);
      const reviews = mine.reduce((s, c) => s + c.reviews, 0);
      const commits = mine.reduce((s, c) => s + c.commits, 0);
      return { person, merged, total, score, reviews, commits, value: useScore ? score : total };
    })
    .sort((a, b) => b.value - a.value);

  const table = (
    <DataTable
      caption="Contributors"
      head={['Contributor', useScore ? 'Score' : 'Items', 'Merged PRs', 'Reviews', 'Commits']}
      rows={rows.map((r) => [
        r.person.name,
        formatInt(r.value),
        formatInt(r.merged),
        formatInt(r.reviews),
        formatInt(r.commits),
      ])}
    />
  );

  return (
    <ChartFrame
      title="Contributors"
      description={`${plural(people.length, 'person', 'people')}, ranked by ${useScore ? 'contribution score' : 'pull requests and issues'}. Select one to filter the page.`}
      table={table}
    >
      <BarList
        ariaLabel="Contributors ranked by contribution"
        selected={selected}
        onSelect={onToggle}
        rows={rows.map((r) => ({
          key: r.person.name,
          label: r.person.name,
          value: r.value,
          display: useScore ? formatCompact(r.value) : formatInt(r.value),
          leading: <img className="contributor__avatar" src={r.person.avatar} alt="" width="28" height="28" loading="lazy" />,
          detail: [
            r.merged > 0 ? `${formatInt(r.merged)} merged` : null,
            r.reviews > 0 ? plural(r.reviews, 'review') : null,
            r.commits > 0 ? plural(r.commits, 'commit') : null,
          ]
            .filter(Boolean)
            .join(', '),
        }))}
      />
    </ChartFrame>
  );
}
