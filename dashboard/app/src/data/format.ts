const intFormat = new Intl.NumberFormat('en-US');
const compactFormat = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const monthFormat = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const dateFormat = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

export const formatInt = (n: number): string => intFormat.format(n);

/** 999 stays whole; 1,200 becomes 1.2K. */
export const formatCompact = (n: number): string => (Math.abs(n) < 1000 ? intFormat.format(n) : compactFormat.format(n));

export const formatMonth = (ms: number): string => monthFormat.format(ms);
export const formatDate = (ms: number): string => dateFormat.format(ms);

/** `Aug 2021 to Sep 2026`, or a single month when both ends fall in the same one. */
export function formatSpan(from: number, to: number): string {
  const start = formatMonth(from);
  const end = formatMonth(to);
  return start === end ? start : `${start} to ${end}`;
}

/** A duration in days at a human scale: `3 days`, `5 weeks`, `2 months`, `1.4 years`. */
export function formatDays(days: number): string {
  if (days < 1) return 'Under a day';
  if (days < 14) {
    const d = Math.round(days);
    return `${d} ${d === 1 ? 'day' : 'days'}`;
  }
  if (days < 60) return `${Math.round(days / 7)} weeks`;
  if (days < 365) return `${Math.round(days / 30.4)} months`;
  return `${(Math.round((days / 365) * 10) / 10).toString()} years`;
}

export function plural(n: number, singular: string, pluralForm = `${singular}s`): string {
  return `${formatInt(n)} ${n === 1 ? singular : pluralForm}`;
}
