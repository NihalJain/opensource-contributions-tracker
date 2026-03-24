import type { RawRecord, ActivityEvent, Filters } from '../types';

export function normalizeData(records: RawRecord[]): ActivityEvent[] {
  const events: ActivityEvent[] = [];
  for (const rec of records) {
    const base = {
      project_key: rec.project_key,
      repo: rec.repo,
      repo_url: rec.repo_url,
      user: rec.user,
      user_url: rec.user_url,
      user_avatar: rec.user_avatar,
    };
    const addItems = (items: RawRecord['open_prs'], type: 'pr' | 'issue', state: 'open' | 'closed') => {
      for (const item of items) {
        events.push({
          id: `${rec.repo}#${item.number}-${type}`,
          type,
          state,
          merged: type === 'pr' ? !!item.pull_request?.merged_at : false,
          ...base,
          title: item.title,
          number: item.number,
          url: item.html_url,
          created_at: item.created_at,
          updated_at: item.updated_at,
          merged_at: item.pull_request?.merged_at ?? null,
          labels: item.labels.map(l => l.name),
        });
      }
    };
    addItems(rec.open_prs, 'pr', 'open');
    addItems(rec.closed_prs, 'pr', 'closed');
    addItems(rec.open_issues, 'issue', 'open');
    addItems(rec.closed_issues, 'issue', 'closed');
  }
  return events;
}

export function applyFilters(events: ActivityEvent[], filters: Filters): ActivityEvent[] {
  return events.filter(e => {
    if (filters.projects.length && !filters.projects.includes(e.project_key)) return false;
    if (filters.repos.length && !filters.repos.includes(e.repo)) return false;
    if (filters.users.length && !filters.users.includes(e.user)) return false;
    if (filters.types.length && !filters.types.includes(e.type)) return false;
    if (filters.states.length && !filters.states.includes(e.state)) return false;
    if (filters.merged !== 'all') {
      if (filters.merged === 'merged' && !e.merged) return false;
      if (filters.merged === 'unmerged' && e.merged) return false;
    }
    if (filters.labels.length && !filters.labels.some(l => e.labels.includes(l))) return false;
    if (filters.dateFrom && new Date(e.created_at) < new Date(filters.dateFrom)) return false;
    if (filters.dateTo) {
      const toEnd = new Date(filters.dateTo);
      toEnd.setUTCHours(23, 59, 59, 999);
      if (new Date(e.created_at) > toEnd) return false;
    }
    return true;
  });
}
