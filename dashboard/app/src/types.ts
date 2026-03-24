export interface RawRecord {
  user: string;
  user_url: string;
  user_avatar: string;
  project_key: string;
  repo: string;
  repo_url: string;
  open_prs: RawItem[];
  closed_prs: RawItem[];
  open_issues: RawItem[];
  closed_issues: RawItem[];
}

export interface RawItem {
  number: number;
  title: string;
  html_url: string;
  state: string;
  created_at: string;
  updated_at: string;
  labels: { name: string }[];
  pull_request?: { merged_at: string | null };
}

export interface ActivityEvent {
  id: string;
  type: 'pr' | 'issue';
  state: 'open' | 'closed';
  merged: boolean;
  project_key: string;
  repo: string;
  repo_url: string;
  user: string;
  user_url: string;
  user_avatar: string;
  title: string;
  number: number;
  url: string;
  created_at: string;
  updated_at: string;
  merged_at: string | null;
  labels: string[];
}

export interface Filters {
  projects: string[];
  repos: string[];
  users: string[];
  types: ('pr' | 'issue')[];
  states: ('open' | 'closed')[];
  merged: 'all' | 'merged' | 'unmerged';
  labels: string[];
  dateFrom: string;
  dateTo: string;
}
