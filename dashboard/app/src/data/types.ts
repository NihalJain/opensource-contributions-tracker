/** One PR or issue exactly as the report generator writes it to activity.json. */
export interface FeedItem {
  number: number;
  title: string;
  html_url: string;
  state: string;
  created_at: string;
  updated_at: string;
  labels: { name: string }[];
  pull_request?: { merged_at: string | null };
}

/** One user's activity in one repository (a row of activity.json). */
export interface FeedRecord {
  user: string;
  user_url: string;
  user_avatar: string;
  project_key: string;
  repo: string;
  repo_url: string;
  open_prs: FeedItem[];
  closed_prs: FeedItem[];
  open_issues: FeedItem[];
  closed_issues: FeedItem[];
}

export type Kind = 'pr' | 'issue';

/** Pull requests end `merged` or `closed` (without merging); issues are `open` or `closed`. */
export type Outcome = 'merged' | 'closed' | 'open';

/** A pull request or issue, normalised for the UI. Dates are UTC epoch milliseconds. */
export interface Item {
  id: string;
  kind: Kind;
  outcome: Outcome;
  number: number;
  title: string;
  url: string;
  user: string;
  project: string;
  repo: string;
  labels: string[];
  created: number;
  updated: number;
  merged: number | null;
  daysToMerge: number | null;
}

export interface Person {
  name: string;
  url: string;
  avatar: string;
}

/** Aggregate metrics for one user in one repository (a row of contributions.json). */
export interface Contribution {
  project: string;
  repo: string;
  repoUrl: string;
  description: string;
  repoAvatar: string;
  user: string;
  commits: number;
  prsOpen: number;
  prsClosed: number;
  issuesOpen: number;
  issuesClosed: number;
  reviews: number;
  linesAdded: number;
  linesRemoved: number;
  /** The user's standing among the repository's contributors; null when unranked. */
  rank: number | null;
  score: number;
}

export interface Meta {
  builtAt: string | null;
}

export interface Dataset {
  items: Item[];
  people: Person[];
  contributions: Contribution[];
  meta: Meta;
}

export interface Filters {
  users: string[];
  projects: string[];
  repos: string[];
  kinds: Kind[];
  outcomes: Outcome[];
  labels: string[];
  /** Inclusive UTC dates, `YYYY-MM-DD`. */
  from: string | null;
  to: string | null;
  query: string;
}
