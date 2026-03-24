import type { ActivityEvent } from '../types';

interface Props {
  events: ActivityEvent[];
}

interface KpiCard {
  label: string;
  count: number;
  icon: string;
  colorClass: string;
  bgClass: string;
}

export default function KpiCards({ events }: Props) {
  const openPRs = events.filter(e => e.type === 'pr' && e.state === 'open').length;
  const mergedPRs = events.filter(e => e.type === 'pr' && e.merged).length;
  const closedUnmergedPRs = events.filter(e => e.type === 'pr' && e.state === 'closed' && !e.merged).length;
  const openIssues = events.filter(e => e.type === 'issue' && e.state === 'open').length;
  const closedIssues = events.filter(e => e.type === 'issue' && e.state === 'closed').length;

  const cards: KpiCard[] = [
    { label: 'Open PRs', count: openPRs, icon: '⬆️', colorClass: 'text-sky-400', bgClass: 'from-sky-900/40 to-sky-800/20 border-sky-700/40' },
    { label: 'Merged PRs', count: mergedPRs, icon: '✅', colorClass: 'text-violet-400', bgClass: 'from-violet-900/40 to-violet-800/20 border-violet-700/40' },
    { label: 'Closed PRs', count: closedUnmergedPRs, icon: '🚫', colorClass: 'text-red-400', bgClass: 'from-red-900/40 to-red-800/20 border-red-700/40' },
    { label: 'Open Issues', count: openIssues, icon: '🔴', colorClass: 'text-orange-400', bgClass: 'from-orange-900/40 to-orange-800/20 border-orange-700/40' },
    { label: 'Closed Issues', count: closedIssues, icon: '✔️', colorClass: 'text-green-400', bgClass: 'from-green-900/40 to-green-800/20 border-green-700/40' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
      {cards.map(card => (
        <div
          key={card.label}
          className={`bg-gradient-to-br ${card.bgClass} border rounded-xl p-4 flex flex-col gap-2`}
        >
          <div className="flex items-center justify-between">
            <span className="text-2xl">{card.icon}</span>
            <span className={`text-3xl font-bold ${card.colorClass}`}>{card.count}</span>
          </div>
          <p className="text-slate-400 text-sm font-medium">{card.label}</p>
        </div>
      ))}
    </div>
  );
}
