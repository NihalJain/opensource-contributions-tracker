const DATA_URL =
  'https://raw.githubusercontent.com/NihalJain/opensource-contributions-tracker/main/output/github_activity_data.json';
const CACHE_KEY = 'https://data.internal/activity.json';

const CORS_HEADERS: Record<string, string> = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method === 'GET' && url.pathname === '/activity.json') {
      const bypassCache = url.searchParams.get('refresh') === '1';
      const cache = caches.default;

      if (!bypassCache) {
        const cached = await cache.match(CACHE_KEY);
        if (cached) {
          const response = new Response(cached.body, cached);
          response.headers.set('X-Cache', 'HIT');
          return response;
        }
      }

      const fetchInit: RequestInit = bypassCache ? { cache: 'no-store' } : {};
      const upstream = await fetch(DATA_URL, fetchInit);
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
        await cache.put(CACHE_KEY, response.clone());
      }

      return response;
    }

    return new Response('Not Found', { status: 404, headers: CORS_HEADERS });
  },
};
