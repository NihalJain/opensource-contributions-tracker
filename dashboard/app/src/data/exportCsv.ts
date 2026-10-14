import type { Item } from './types';

const HEADER = ['Type', 'Status', 'Contributor', 'Project', 'Repository', 'Number', 'Title', 'Labels', 'Opened', 'Merged', 'Days to merge', 'URL'];

const day = (ms: number | null) => (ms === null ? '' : new Date(ms).toISOString().slice(0, 10));

/** Quote a field, and defuse values that spreadsheets would otherwise run as formulas. */
function field(value: string | number): string {
  let text = String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

const STATUS = { merged: 'Merged', closed: 'Closed', open: 'Open' } as const;

/** The items as CSV text, CRLF-terminated, ready to save as a file. */
export function toCsv(items: Item[]): string {
  const rows = items.map((item) =>
    [
      item.kind === 'pr' ? 'Pull request' : 'Issue',
      STATUS[item.outcome],
      item.user,
      item.project,
      item.repo,
      item.number,
      item.title,
      item.labels.join('; '),
      day(item.created),
      day(item.merged),
      item.daysToMerge === null ? '' : item.daysToMerge.toFixed(1),
      item.url,
    ]
      .map(field)
      .join(','),
  );
  return [HEADER.join(','), ...rows].join('\r\n') + '\r\n';
}
