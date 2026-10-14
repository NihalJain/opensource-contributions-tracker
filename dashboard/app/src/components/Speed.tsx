import { BarList } from '../charts/BarList';
import type { SpeedBand } from '../data/aggregate';
import { formatInt, plural } from '../data/format';
import { ChartFrame, DataTable } from './ChartFrame';

export function Speed({ bands }: { bands: SpeedBand[] }) {
  const total = bands.reduce((sum, band) => sum + band.count, 0);

  const table = (
    <DataTable
      caption="Merged pull requests by time to merge"
      head={['Time to merge', 'Pull requests', 'Share']}
      rows={bands.map((b) => [b.label, formatInt(b.count), total ? `${Math.round((b.count / total) * 100)}%` : '0%'])}
    />
  );

  return (
    <ChartFrame
      title="How quickly pull requests merge"
      description={
        total === 0
          ? 'No merged pull requests in this view.'
          : `Time from opening to merge, for ${plural(total, 'merged pull request')}.`
      }
      table={table}
    >
      <BarList
        ariaLabel="Merged pull requests by time to merge"
        color="var(--c-merged)"
        rows={bands.map((b) => ({
          key: b.label,
          label: b.label,
          value: b.count,
          display: formatInt(b.count),
        }))}
      />
    </ChartFrame>
  );
}
