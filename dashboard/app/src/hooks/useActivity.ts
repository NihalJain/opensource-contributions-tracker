import { useState, useEffect, useMemo } from 'react';
import type { RawRecord, ActivityEvent, Filters } from '../types';
import { normalizeData, applyFilters } from '../utils/normalize';

const API_URL = import.meta.env.VITE_ACTIVITY_API_URL ?? 'https://opensource-contribs-data.workers.dev/activity.json';
const CACHE_KEY = 'oss_activity_cache';
const CACHE_TTL = 86400_000; // 24h in ms

interface CacheEntry {
  fetchedAt: number;
  data: RawRecord[];
}

export interface UseActivityResult {
  events: ActivityEvent[];
  filteredEvents: ActivityEvent[];
  loading: boolean;
  error: string | null;
  lastFetched: Date | null;
  refresh: () => void;
  allProjects: string[];
  allRepos: string[];
  allUsers: string[];
  allLabels: string[];
  filters: Filters;
  setFilters: React.Dispatch<React.SetStateAction<Filters>>;
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

export function useActivity(): UseActivityResult {
  const [rawData, setRawData] = useState<RawRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);
  const [filters, setFilters] = useState<Filters>(defaultFilters);

  const fetchData = async (bypassCache = false) => {
    setLoading(true);
    setError(null);
    try {
      if (!bypassCache) {
        try {
          const cached = localStorage.getItem(CACHE_KEY);
          if (cached) {
            const entry: CacheEntry = JSON.parse(cached);
            if (Date.now() - entry.fetchedAt < CACHE_TTL) {
              setRawData(entry.data);
              setLastFetched(new Date(entry.fetchedAt));
              setLoading(false);
              return;
            }
          }
        } catch {
          // ignore cache errors
        }
      }
      const url = bypassCache ? `${API_URL}?refresh=1` : API_URL;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: RawRecord[] = await res.json();
      const entry: CacheEntry = { fetchedAt: Date.now(), data };
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(entry)); } catch { /* quota */ }
      setRawData(data);
      setLastFetched(new Date(entry.fetchedAt));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchData(); }, []);

  const events = useMemo(() => normalizeData(rawData), [rawData]);
  const filteredEvents = useMemo(() => applyFilters(events, filters), [events, filters]);

  const allProjects = useMemo(() => [...new Set(events.map(e => e.project_key))].sort(), [events]);
  const allRepos = useMemo(() => [...new Set(events.map(e => e.repo))].sort(), [events]);
  const allUsers = useMemo(() => [...new Set(events.map(e => e.user))].sort(), [events]);
  const allLabels = useMemo(() => [...new Set(events.flatMap(e => e.labels))].sort(), [events]);

  return {
    events,
    filteredEvents,
    loading,
    error,
    lastFetched,
    refresh: () => { void fetchData(true); },
    allProjects,
    allRepos,
    allUsers,
    allLabels,
    filters,
    setFilters,
  };
}
