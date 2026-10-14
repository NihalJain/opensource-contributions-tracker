import { useCallback, useEffect, useState } from 'react';
import type { Filters } from '../data/types';
import { decodeView, defaultView, encodeView, type SortDir, type SortKey, type ViewState } from '../data/urlState';

const readHash = (): ViewState => decodeView(window.location.hash);

/**
 * The page's filters, sort and page, mirrored into the address bar so any view can be shared.
 * It writes with replaceState, so filtering does not fill the back button with steps.
 */
export function useView() {
  const [view, setView] = useState<ViewState>(readHash);

  useEffect(() => {
    const encoded = encodeView(view);
    const next = encoded ? `#?${encoded}` : '';
    if (window.location.hash !== next) {
      const base = window.location.pathname + window.location.search;
      window.history.replaceState(null, '', next ? base + next : base);
    }
  }, [view]);

  // Follow edits to the address bar and links that change only the hash.
  useEffect(() => {
    const onHashChange = () => setView(readHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const setFilters = useCallback((update: Partial<Filters> | ((current: Filters) => Filters)) => {
    setView((current) => ({
      ...current,
      page: 1,
      filters: typeof update === 'function' ? update(current.filters) : { ...current.filters, ...update },
    }));
  }, []);

  const clearFilters = useCallback(() => setView((current) => ({ ...current, page: 1, filters: defaultView.filters })), []);

  const setSort = useCallback((sort: SortKey, dir?: SortDir) => {
    setView((current) => ({
      ...current,
      page: 1,
      sort,
      dir: dir ?? (current.sort === sort && current.dir === 'desc' ? 'asc' : 'desc'),
    }));
  }, []);

  const setPage = useCallback((page: number) => setView((current) => ({ ...current, page })), []);

  return { view, setFilters, clearFilters, setSort, setPage };
}
