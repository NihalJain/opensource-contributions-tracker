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

Create `dashboard/app/.env.local` to point at the local Worker during development:

```
VITE_ACTIVITY_API_URL=http://localhost:8787/activity.json
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

## Deploying (single Cloudflare Worker)

The Worker serves both the built frontend (static assets from `app/dist`) and the `/activity.json` API endpoint from one `*.workers.dev` URL. No Cloudflare Pages is required.

### Prerequisites

- A free [Cloudflare account](https://dash.cloudflare.com/sign-up).
- Node.js 18+ and npm installed locally.
- `wrangler` available – it is a dev-dependency of the worker package, so `npx wrangler` works without a global install.

### Step 1 – Install Worker dependencies

```bash
cd dashboard
npm install --prefix worker
```

### Step 2 – Authenticate wrangler with your Cloudflare account

```bash
cd dashboard
npx wrangler login
```

This opens a browser window. Log in and click **Allow** to grant wrangler access to your account. You only need to do this once per machine.

To confirm authentication succeeded:

```bash
npx wrangler whoami
```

### Step 3 – (Optional) Set the Worker name

The Worker is deployed as `opensource-contribs-data` by default (see `name` in `wrangler.toml`).  
If you want a different name, edit that field before deploying:

```toml
# dashboard/wrangler.toml
name = "my-custom-worker-name"
```

Your live URL will be `https://<name>.<your-subdomain>.workers.dev`.

### Step 4 – Deploy

```bash
cd dashboard
npx wrangler deploy
```

`wrangler deploy` will automatically:
1. Run the `[build]` command – `npm install && npm run build` inside `app/` – to produce `app/dist/`.
2. Bundle `worker/src/index.ts` as the Worker script.
3. Upload `app/dist/` as static assets bound to the Worker.
4. Deploy everything and print the live URL.

Expected output (last few lines):

```
✨ Success! Uploaded 1 files (1.23 sec)
✨ Deployment complete! Take a look over at https://opensource-contribs-data.<subdomain>.workers.dev
```

### Step 5 – Verify

| URL | Expected result |
|-----|----------------|
| `https://<worker-url>/` | Dashboard UI loads |
| `https://<worker-url>/activity.json` | Raw JSON response |
| `https://<worker-url>/activity.json?refresh=1` | Bypasses the 24-hour edge cache and fetches fresh data from GitHub |

### Step 6 – (Optional) Add a custom domain

1. In the [Cloudflare dashboard](https://dash.cloudflare.com/) go to **Workers & Pages → your worker → Settings → Domains & Routes**.
2. Click **Add Custom Domain** and enter your domain (the domain must be on Cloudflare DNS).
3. Cloudflare provisions a TLS certificate automatically.

### Re-deploying after data or code changes

```bash
cd dashboard
npx wrangler deploy
```

The same command re-builds the frontend and re-deploys. The edge cache for `/activity.json` resets automatically on each new deployment, or you can force a refresh at any time by hitting `/activity.json?refresh=1`.
