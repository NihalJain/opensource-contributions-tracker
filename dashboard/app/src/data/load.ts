import { normalizeFeed } from './normalize';
import type { Contribution, Dataset, FeedRecord, Meta } from './types';

const url = (name: string) => `${import.meta.env.BASE_URL}${name}`;

async function getJson<T>(name: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url(name), { signal });
  if (!response.ok) throw new Error(`${name} returned HTTP ${response.status}`);
  return (await response.json()) as T;
}

/** Fetch the optional file; the dashboard works without it, minus the metrics it carries. */
async function getOptional<T>(name: string, fallback: T, signal?: AbortSignal): Promise<T> {
  try {
    return await getJson<T>(name, signal);
  } catch (error) {
    if (signal?.aborted) throw error;
    return fallback;
  }
}

export async function loadDataset(signal?: AbortSignal): Promise<Dataset> {
  const [feed, contributions, meta] = await Promise.all([
    getJson<FeedRecord[]>('activity.json', signal),
    getOptional<Contribution[]>('contributions.json', [], signal),
    getOptional<Meta>('meta.json', { builtAt: null }, signal),
  ]);

  if (!Array.isArray(feed)) throw new Error('activity.json is not a list of activity records');

  const { items, people } = normalizeFeed(feed);
  return { items, people, contributions: Array.isArray(contributions) ? contributions : [], meta };
}
