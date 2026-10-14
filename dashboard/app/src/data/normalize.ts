import type { FeedItem, FeedRecord, Item, Kind, Outcome, Person } from './types';

const DAY_MS = 86_400_000;

function toItem(record: FeedRecord, raw: FeedItem, kind: Kind, outcome: Outcome): Item {
  const created = Date.parse(raw.created_at);
  const merged = raw.pull_request?.merged_at ? Date.parse(raw.pull_request.merged_at) : null;
  return {
    id: `${record.repo}#${raw.number}`,
    kind,
    outcome,
    number: raw.number,
    title: raw.title,
    url: raw.html_url,
    user: record.user,
    project: record.project_key,
    repo: record.repo,
    labels: raw.labels.map((label) => label.name),
    created,
    updated: Date.parse(raw.updated_at),
    merged,
    daysToMerge: merged === null ? null : Math.max(0, (merged - created) / DAY_MS),
  };
}

/** Flatten the report's per-user, per-repository records into one list of items and people. */
export function normalizeFeed(records: FeedRecord[]): { items: Item[]; people: Person[] } {
  const items = new Map<string, Item>();
  const people = new Map<string, Person>();

  for (const record of records) {
    if (!people.has(record.user)) {
      people.set(record.user, { name: record.user, url: record.user_url, avatar: record.user_avatar });
    }

    const add = (list: FeedItem[], kind: Kind, outcomeOf: (raw: FeedItem) => Outcome) => {
      for (const raw of list) {
        const item = toItem(record, raw, kind, outcomeOf(raw));
        if (!items.has(item.id)) items.set(item.id, item);
      }
    };

    add(record.open_prs, 'pr', () => 'open');
    add(record.closed_prs, 'pr', (raw) => (raw.pull_request?.merged_at ? 'merged' : 'closed'));
    add(record.open_issues, 'issue', () => 'open');
    add(record.closed_issues, 'issue', () => 'closed');
  }

  return { items: [...items.values()], people: [...people.values()] };
}
