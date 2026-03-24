import { useState } from 'react';
import { useActivity } from './hooks/useActivity';
import KpiCards from './components/KpiCards';
import FilterDrawer from './components/FilterDrawer';
import Charts from './components/Charts';
import ActivityTable from './components/ActivityTable';

function Spinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-10 h-10 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  const {
    filteredEvents,
    loading,
    error,
    lastFetched,
    refresh,
    allProjects,
    allRepos,
    allUsers,
    allLabels,
    filters,
    setFilters,
  } = useActivity();

  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Navbar */}
      <header className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-3">
          {/* Mobile filter toggle */}
          <button
            onClick={() => setDrawerOpen(true)}
            className="lg:hidden p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
            aria-label="Open filters"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h18M6 8h12M10 12h4" />
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <span className="text-2xl">🚀</span>
            <h1 className="text-slate-100 font-bold text-base sm:text-lg leading-tight">
              OSS Contributions Dashboard
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastFetched && (
            <span className="hidden sm:block text-slate-500 text-xs">
              Updated {lastFetched.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={refresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar filter (desktop) + mobile drawer */}
        <FilterDrawer
          filters={filters}
          setFilters={setFilters}
          allProjects={allProjects}
          allRepos={allRepos}
          allUsers={allUsers}
          allLabels={allLabels}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
        />

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          {loading && <Spinner />}

          {error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-4 mb-6 text-red-300 text-sm">
              <strong>Error:</strong> {error}
            </div>
          )}

          {!loading && !error && (
            <>
              <KpiCards events={filteredEvents} />
              <Charts events={filteredEvents} />
              <ActivityTable events={filteredEvents} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}
