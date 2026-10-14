const CACHE_KEY = 'https://data.internal/activity.json';

const CORS_HEADERS: Record<string, string> = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

interface Env {
  ASSETS: Fetcher;
  /** Raw URL of the activity JSON feed; set under [vars] in wrangler.toml. */
  DATA_URL: string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method === 'GET' && url.pathname === '/activity.json') {
      if (!env.DATA_URL) {
        return new Response('DATA_URL is not configured. Set it under [vars] in dashboard/wrangler.toml.', {
          status: 500,
          headers: CORS_HEADERS,
        });
      }

      const bypassCache = url.searchParams.get('refresh') === '1';
      const cache = caches.default;

      if (!bypassCache) {
        const cached = await cache.match(CACHE_KEY);
        if (cached) {
          const response = new Response(cached.clone().body, cached);
          response.headers.set('X-Cache', 'HIT');
          return response;
        }
      }

      const fetchInit: RequestInit = bypassCache ? { cache: 'no-store' } : {};
      const upstream = await fetch(env.DATA_URL, fetchInit);
      if (!upstream.ok) {
        return new Response(`Upstream error: ${upstream.status}`, {
          status: 502,
          headers: CORS_HEADERS,
        });
      }

      const body = await upstream.text();
      const responseHeaders = new Headers({
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=86400',
        ...CORS_HEADERS,
      });

      const response = new Response(body, { status: 200, headers: responseHeaders });

      if (!bypassCache) {
        ctx.waitUntil(cache.put(CACHE_KEY, response.clone()));
      }

      return response;
    }

    return env.ASSETS.fetch(request);
  },
};
