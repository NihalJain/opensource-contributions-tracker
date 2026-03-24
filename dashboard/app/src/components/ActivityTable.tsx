import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table';
import type { ActivityEvent } from '../types';

interface Props {
  events: ActivityEvent[];
}

const columnHelper = createColumnHelper<ActivityEvent>();

function Badge({ children, className }: { children: React.ReactNode; className: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

function TypeBadge({ type }: { type: 'pr' | 'issue' }) {
  return type === 'pr'
    ? <Badge className="bg-blue-900/60 text-blue-300 border border-blue-700/50">PR</Badge>
    : <Badge className="bg-orange-900/60 text-orange-300 border border-orange-700/50">Issue</Badge>;
}

function StateBadge({ state }: { state: 'open' | 'closed' }) {
  return state === 'open'
    ? <Badge className="bg-green-900/60 text-green-300 border border-green-700/50">Open</Badge>
    : <Badge className="bg-red-900/60 text-red-300 border border-red-700/50">Closed</Badge>;
}

function MergedBadge({ merged }: { merged: boolean }) {
  return merged
    ? <Badge className="bg-violet-900/60 text-violet-300 border border-violet-700/50">Merged</Badge>
    : <span className="text-slate-600 text-xs">—</span>;
}

const columns = [
  columnHelper.accessor('type', {
    header: 'Type',
    cell: info => <TypeBadge type={info.getValue()} />,
    size: 70,
  }),
  columnHelper.accessor('state', {
    header: 'State',
    cell: info => <StateBadge state={info.getValue()} />,
    size: 80,
  }),
  columnHelper.accessor('merged', {
    header: 'Merged',
    cell: info => <MergedBadge merged={info.getValue()} />,
    size: 80,
  }),
  columnHelper.accessor('project_key', {
    header: 'Project',
    cell: info => <span className="text-slate-300 text-xs">{info.getValue()}</span>,
  }),
  columnHelper.accessor('repo', {
    header: 'Repo',
    cell: info => (
      <a href={info.row.original.repo_url} target="_blank" rel="noreferrer" className="text-primary-400 hover:text-primary-300 text-xs truncate max-w-[140px] block">
        {info.getValue()}
      </a>
    ),
  }),
  columnHelper.accessor('user', {
    header: 'User',
    cell: info => (
      <a href={info.row.original.user_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5">
        <img src={info.row.original.user_avatar} alt={info.getValue()} className="w-5 h-5 rounded-full" />
        <span className="text-slate-300 text-xs">{info.getValue()}</span>
      </a>
    ),
  }),
  columnHelper.accessor('title', {
    header: 'Title',
    cell: info => (
      <a href={info.row.original.url} target="_blank" rel="noreferrer" className="text-slate-200 hover:text-white text-xs line-clamp-2 max-w-xs">
        {info.getValue()}
      </a>
    ),
    enableSorting: false,
  }),
  columnHelper.accessor('number', {
    header: '#',
    cell: info => <span className="text-slate-500 text-xs">#{info.getValue()}</span>,
    size: 60,
  }),
  columnHelper.accessor('created_at', {
    header: 'Created',
    cell: info => <span className="text-slate-400 text-xs whitespace-nowrap">{info.getValue().slice(0, 10)}</span>,
  }),
  columnHelper.accessor('updated_at', {
    header: 'Updated',
    cell: info => <span className="text-slate-400 text-xs whitespace-nowrap">{info.getValue().slice(0, 10)}</span>,
  }),
  columnHelper.accessor('labels', {
    header: 'Labels',
    cell: info => (
      <div className="flex flex-wrap gap-1">
        {info.getValue().map(l => (
          <span key={l} className="bg-slate-700 text-slate-300 text-xs px-1.5 py-0.5 rounded">{l}</span>
        ))}
      </div>
    ),
    enableSorting: false,
  }),
];

export default function ActivityTable({ events }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const data = useMemo(() => events, [events]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  });

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-slate-300 font-semibold text-sm">Activity</span>
          <span className="bg-slate-700 text-slate-300 text-xs px-2 py-0.5 rounded-full">
            {table.getFilteredRowModel().rows.length} rows
          </span>
        </div>
        <input
          type="text"
          placeholder="Search all columns…"
          value={globalFilter}
          onChange={e => setGlobalFilter(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-primary-500 w-full sm:w-64"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id} className="border-b border-slate-800">
                {hg.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap bg-slate-900/50 cursor-pointer select-none hover:text-slate-200"
                    onClick={header.column.getToggleSortingHandler()}
                    style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                  >
                    <span className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === 'asc' && ' ↑'}
                      {header.column.getIsSorted() === 'desc' && ' ↓'}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr key={row.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-2 align-top">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-slate-500 text-sm">
                  No results found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="p-4 border-t border-slate-800 flex items-center justify-between">
        <span className="text-slate-400 text-xs">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount() || 1}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium disabled:opacity-40 hover:bg-slate-700 disabled:cursor-not-allowed transition-colors"
          >
            ← Prev
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium disabled:opacity-40 hover:bg-slate-700 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
