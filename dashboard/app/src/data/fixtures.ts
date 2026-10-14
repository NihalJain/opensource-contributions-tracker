import type { Contribution, Item } from './types';

/** Shared builders for the data-layer tests. */
export function makeItem(patch: Partial<Item> & { number: number }): Item {
  const created = patch.created ?? Date.parse('2024-03-01T00:00:00Z');
  return {
    id: `apache/hbase#${patch.number}`,
    kind: 'pr',
    outcome: 'merged',
    title: `Change ${patch.number}`,
    url: `https://github.com/apache/hbase/pull/${patch.number}`,
    user: 'Ada Lovelace',
    project: 'Apache HBase',
    repo: 'apache/hbase',
    labels: [],
    created,
    updated: created + 86_400_000,
    merged: null,
    daysToMerge: null,
    ...patch,
  };
}

export function makeContribution(patch: Partial<Contribution> = {}): Contribution {
  return {
    project: 'Apache HBase',
    repo: 'apache/hbase',
    repoUrl: 'https://github.com/apache/hbase',
    description: '',
    repoAvatar: '',
    user: 'Ada Lovelace',
    commits: 0,
    prsOpen: 0,
    prsClosed: 0,
    issuesOpen: 0,
    issuesClosed: 0,
    reviews: 0,
    linesAdded: 0,
    linesRemoved: 0,
    rank: null,
    score: 0,
    ...patch,
  };
}
