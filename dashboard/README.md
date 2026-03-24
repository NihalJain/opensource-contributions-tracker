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

There are three ways to deploy, depending on your preference:

| Method | When to use |
|--------|-------------|
| [A – CLI (`wrangler deploy`)](#method-a--cli-wrangler-deploy) | One-off or manual deploy from your laptop |
| [B – GitHub Actions (automated)](#method-b--github-actions-automated-deploy) | Every push to `main` triggers a deploy automatically — no CLI needed |
| [C – Cloudflare dashboard UI](#method-c--cloudflare-dashboard-ui) | Inspect, roll back, add custom domains, view logs after deployment |

> **Note:** The Cloudflare dashboard UI alone cannot deploy this project because uploading the frontend static assets requires either `wrangler` (Method A) or an automated pipeline (Method B). Use Method C *alongside* one of the other two methods.

### Method A – CLI (`wrangler deploy`)

#### Prerequisites

- A free [Cloudflare account](https://dash.cloudflare.com/sign-up).
- Node.js 18+ and npm installed locally.
- `wrangler` available – it is a dev-dependency of the worker package, so `npx wrangler` works without a global install.

#### Step 1 – Install Worker dependencies

```bash
cd dashboard
npm install --prefix worker
```

#### Step 2 – Authenticate wrangler with your Cloudflare account

```bash
cd dashboard
npx wrangler login
```

This opens a browser window. Log in and click **Allow** to grant wrangler access to your account. You only need to do this once per machine.

To confirm authentication succeeded:

```bash
npx wrangler whoami
```

#### Step 3 – (Optional) Set the Worker name

The Worker is deployed as `opensource-contribs-data` by default (see `name` in `wrangler.toml`).  
If you want a different name, edit that field before deploying:

```toml
# dashboard/wrangler.toml
name = "my-custom-worker-name"
```

Your live URL will be `https://<name>.<your-subdomain>.workers.dev`.

#### Step 4 – Deploy

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

#### Step 5 – Verify

| URL | Expected result |
|-----|----------------|
| `https://<worker-url>/` | Dashboard UI loads |
| `https://<worker-url>/activity.json` | Raw JSON response |
| `https://<worker-url>/activity.json?refresh=1` | Bypasses the 24-hour edge cache and fetches fresh data from GitHub |

#### Re-deploying after data or code changes

```bash
cd dashboard
npx wrangler deploy
```

The same command re-builds the frontend and re-deploys. The edge cache for `/activity.json` resets automatically on each new deployment, or you can force a refresh at any time by hitting `/activity.json?refresh=1`.

---

### Method B – GitHub Actions (automated deploy)

This method runs `wrangler deploy` automatically on every push to `main` using GitHub Actions, so you never need to run any CLI commands yourself after the initial setup.

#### Step 1 – Create a Cloudflare API token

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **My Profile** (top-right avatar) → **API Tokens**.
2. Click **Create Token**.
3. Choose the **Edit Cloudflare Workers** template.
4. Under **Account Resources**, select your account.
5. Under **Zone Resources**, leave as *All zones* (or scope to a specific zone if preferred).
6. Click **Continue to summary → Create Token**.
7. **Copy the token** – you will not be able to see it again.

#### Step 2 – Add the token as a GitHub secret

1. Open the repository on GitHub.
2. Go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Set:
   - **Name:** `CLOUDFLARE_API_TOKEN`
   - **Value:** the token you copied in Step 1
4. Click **Add secret**.

You also need your **Cloudflare Account ID**:

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → select any domain (or go to **Workers & Pages**).
2. In the right-hand sidebar, copy the **Account ID**.
3. Add another secret:
   - **Name:** `CLOUDFLARE_ACCOUNT_ID`
   - **Value:** the Account ID you copied

#### Step 3 – Add the workflow file

Create `.github/workflows/deploy-worker.yml` in the repository root:

```yaml
name: Deploy Cloudflare Worker

on:
  push:
    branches: [main]
    paths:
      - "dashboard/**"
      - "output/**"
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: dashboard/worker/package-lock.json

      - name: Install Worker dependencies
        run: npm ci
        working-directory: dashboard/worker

      - name: Deploy
        run: npx wrangler deploy
        working-directory: dashboard
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

#### Step 4 – Trigger a deploy

Push any change to the `dashboard/` or `output/` directories on `main` (for example, update the JSON data file, or simply push a whitespace change to `wrangler.toml`). The Actions tab in GitHub will show the workflow running and print the live URL when it finishes.

To trigger a deploy manually without a code change:

1. Go to **Actions → Deploy Cloudflare Worker** in the GitHub UI.
2. Click **Run workflow → Run workflow**.

#### Step 5 – Verify

Same verification table as Method A:

| URL | Expected result |
|-----|----------------|
| `https://<worker-url>/` | Dashboard UI loads |
| `https://<worker-url>/activity.json` | Raw JSON response |
| `https://<worker-url>/activity.json?refresh=1` | Bypasses the 24-hour edge cache |

---

### Method C – Cloudflare dashboard UI

The Cloudflare dashboard is useful for **managing** a Worker that was already deployed via Method A or B. It cannot create the full deployment on its own (uploading static assets requires `wrangler`).

#### What you can do in the UI

| Task | Where in the dashboard |
|------|------------------------|
| View deployment history / roll back | **Workers & Pages → your worker → Deployments** |
| Inspect real-time logs | **Workers & Pages → your worker → Logs** |
| Edit and test simple Worker scripts | **Workers & Pages → your worker → Edit code** (not recommended for this project — use `wrangler deploy` to avoid overwriting the asset binding) |
| Add or remove a custom domain | **Workers & Pages → your worker → Settings → Domains & Routes → Add Custom Domain** |
| Set environment variables / secrets | **Workers & Pages → your worker → Settings → Variables and Secrets** |
| View CPU and request analytics | **Workers & Pages → your worker → Metrics** |

#### Adding a custom domain (UI steps)

1. Open [dash.cloudflare.com](https://dash.cloudflare.com) and go to **Workers & Pages**.
2. Click on **opensource-contribs-data** (or your custom worker name).
3. Go to **Settings → Domains & Routes → Add Custom Domain**.
4. Enter your domain (e.g. `dashboard.example.com`). The domain must already be on Cloudflare DNS.
5. Cloudflare provisions a TLS certificate automatically — no further action needed.
