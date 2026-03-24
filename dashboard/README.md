# OSS Contributions Dashboard

A full-stack dashboard for visualising open-source contribution activity, built with **Vite + React + TypeScript + Tailwind CSS + ECharts + TanStack Table** and backed by a **Cloudflare Worker** that proxies and caches the data feed.

---

## Folder structure

```
dashboard/
├── README.md
├── wrangler.toml          ← Cloudflare Worker config
├── app/                   ← Vite React frontend
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── types.ts
│       ├── hooks/useActivity.ts
│       ├── utils/normalize.ts
│       └── components/
│           ├── KpiCards.tsx
│           ├── FilterDrawer.tsx
│           ├── Charts.tsx
│           └── ActivityTable.tsx
└── worker/
    ├── package.json
    ├── tsconfig.json
    └── src/index.ts
```

---

## Local development

### Frontend app

```bash
cd dashboard/app
npm install
npm run dev        # http://localhost:5173
```

Set the data endpoint via an env variable (optional – defaults to the deployed worker):

```bash
VITE_ACTIVITY_API_URL=http://localhost:8787/activity.json npm run dev
```

### Cloudflare Worker

```bash
cd dashboard
npm install --prefix worker   # or cd worker && npm install
npx wrangler dev worker/src/index.ts --port 8787
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_ACTIVITY_API_URL` | `https://opensource-contribs-data.workers.dev/activity.json` | Worker endpoint used by the frontend |

---

## Production build

```bash
cd dashboard/app
npm ci
npm run build
# Output: dashboard/app/dist/
```

---

## Deploying to Cloudflare Pages (frontend)

1. Connect the repository to Cloudflare Pages.
2. Set the following build settings:
   - **Build command:** `npm ci && npm run build`
   - **Root directory:** `dashboard/app`
   - **Output directory:** `dist`
3. Add the `VITE_ACTIVITY_API_URL` environment variable pointing to your deployed worker.

---

## Deploying the Cloudflare Worker

```bash
cd dashboard
npx wrangler deploy
```

The worker is configured in `dashboard/wrangler.toml`.  
It fetches data from the upstream GitHub raw URL, caches responses for 24 hours in the Cloudflare edge cache, and exposes a CORS-enabled `/activity.json` endpoint.

Add `?refresh=1` to bypass the cache: `/activity.json?refresh=1`.
