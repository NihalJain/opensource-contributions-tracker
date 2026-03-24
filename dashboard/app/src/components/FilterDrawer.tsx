import type { Filters } from '../types';

interface Props {
  filters: Filters;
  setFilters: React.Dispatch<React.SetStateAction<Filters>>;
  allProjects: string[];
  allRepos: string[];
  allUsers: string[];
  allLabels: string[];
  open: boolean;
  onClose: () => void;
}

const defaultFilters: Filters = {
  projects: [],
  repos: [],
  users: [],
  types: [],
  states: [],
  merged: 'all',
  labels: [],
  dateFrom: '',
  dateTo: '',
};

function MultiCheckbox({
  title,
  options,
  selected,
  onChange,
}: {
  title: string;
  options: string[];
  selected: string[];
  onChange: (val: string[]) => void;
}) {
  const toggle = (opt: string) => {
    onChange(selected.includes(opt) ? selected.filter(s => s !== opt) : [...selected, opt]);
  };
  return (
    <div className="mb-4">
      <p className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">{title}</p>
      <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-1">
        {options.map(opt => (
          <label key={opt} className="flex items-center gap-2 cursor-pointer group">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onChange={() => toggle(opt)}
              className="accent-primary-500 w-4 h-4"
            />
            <span className="text-slate-300 text-sm group-hover:text-white truncate">{opt}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

export default function FilterDrawer({
  filters,
  setFilters,
  allProjects,
  allRepos,
  allUsers,
  allLabels,
  open,
  onClose,
}: Props) {
  const update = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const content = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-slate-100 font-semibold text-base">Filters</h2>
        <button
          onClick={() => setFilters(defaultFilters)}
          className="text-xs text-primary-400 hover:text-primary-300 font-medium"
        >
          Clear All
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1">
        <MultiCheckbox
          title="Projects"
          options={allProjects}
          selected={filters.projects}
          onChange={v => update('projects', v)}
        />
        <MultiCheckbox
          title="Repos"
          options={allRepos}
          selected={filters.repos}
          onChange={v => update('repos', v)}
        />
        <MultiCheckbox
          title="Users"
          options={allUsers}
          selected={filters.users}
          onChange={v => update('users', v)}
        />

        <div className="mb-4">
          <p className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">Type</p>
          <div className="flex flex-col gap-1">
            {(['pr', 'issue'] as const).map(t => (
              <label key={t} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.types.includes(t)}
                  onChange={() => {
                    const next = filters.types.includes(t)
                      ? filters.types.filter(x => x !== t)
                      : [...filters.types, t];
                    update('types', next);
                  }}
                  className="accent-primary-500 w-4 h-4"
                />
                <span className="text-slate-300 text-sm capitalize">{t === 'pr' ? 'Pull Request' : 'Issue'}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="mb-4">
          <p className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">State</p>
          <div className="flex flex-col gap-1">
            {(['open', 'closed'] as const).map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.states.includes(s)}
                  onChange={() => {
                    const next = filters.states.includes(s)
                      ? filters.states.filter(x => x !== s)
                      : [...filters.states, s];
                    update('states', next);
                  }}
                  className="accent-primary-500 w-4 h-4"
                />
                <span className="text-slate-300 text-sm capitalize">{s}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="mb-4">
          <p className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">Merged</p>
          <div className="flex flex-col gap-1">
            {(['all', 'merged', 'unmerged'] as const).map(m => (
              <label key={m} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="merged"
                  value={m}
                  checked={filters.merged === m}
                  onChange={() => update('merged', m)}
                  className="accent-primary-500 w-4 h-4"
                />
                <span className="text-slate-300 text-sm capitalize">{m === 'all' ? 'All' : m === 'merged' ? 'Merged Only' : 'Unmerged Only'}</span>
              </label>
            ))}
          </div>
        </div>

        {allLabels.length > 0 && (
          <MultiCheckbox
            title="Labels"
            options={allLabels}
            selected={filters.labels}
            onChange={v => update('labels', v)}
          />
        )}

        <div className="mb-4">
          <p className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">Created Date</p>
          <div className="flex flex-col gap-2">
            <div>
              <label className="text-slate-400 text-xs mb-1 block">From</label>
              <input
                type="date"
                value={filters.dateFrom}
                onChange={e => update('dateFrom', e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="text-slate-400 text-xs mb-1 block">To</label>
              <input
                type="date"
                value={filters.dateTo}
                onChange={e => update('dateTo', e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-72 shrink-0 bg-slate-900 border-r border-slate-800 p-4 h-screen sticky top-0 overflow-y-auto">
        {content}
      </aside>

      {/* Mobile drawer overlay */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-black/60" onClick={onClose} />
          <div className="relative z-50 w-72 bg-slate-900 border-r border-slate-800 p-4 flex flex-col h-full overflow-y-auto">
            <button
              onClick={onClose}
              className="absolute top-3 right-3 text-slate-400 hover:text-white text-xl"
            >
              ✕
            </button>
            {content}
          </div>
        </div>
      )}
    </>
  );
}
