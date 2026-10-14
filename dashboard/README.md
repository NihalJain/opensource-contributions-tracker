# OSS Contributions Dashboard

An interactive dashboard for the activity feed produced by the report generator, built with **Vite + React + TypeScript + Tailwind CSS + ECharts + TanStack Table**.

The dashboard is a plain static site. The feed (`output/github_activity_data.json`) is copied into the build, so there is no server and no runtime API. It can be hosted anywhere that serves static files.

---

## How it works

```
generate_report.py ──► output/github_activity_data.json
                                   │   npm run build  (copies the feed to public/activity.json)
                                   ▼
                          dashboard/app/dist/   ──►  any static host
```

The data shown is whatever was in `output/` when the site was last built. The nightly workflow regenerates the report and then redeploys the dashboard: to GitHub Pages by default, and to Cloudflare too when credentials are set. Pull requests that touch `dashboard/` build it as a check but never publish.

---

## Folder structure

```
dashboard/
├── README.md
├── wrangler.toml            ← optional Cloudflare deploy config (static assets only)
└── app/                     ← Vite React frontend
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── index.html
    ├── scripts/
    │   └── copy-data.mjs    ← copies the feed into public/ before dev and build
    ├── public/
    │   └── _headers         ← CORS header for /activity.json (Cloudflare)
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── types.ts
        ├── hooks/useActivity.ts
        ├── utils/normalize.ts
        └── components/
            ├── KpiCards.tsx
            ├── FilterDrawer.tsx
            ├── Charts.tsx
            └── ActivityTable.tsx
```

---

## Local development

```bash
python generate_report.py      # optional: the repository ships with a sample feed in output/
cd dashboard/app
npm install
npm run dev                    # http://localhost:5173
```

`npm run dev` and `npm run build` first run `scripts/copy-data.mjs`, which copies `output/github_activity_data.json` to `app/public/activity.json` (git-ignored). To preview a different feed:

```bash
ACTIVITY_DATA_FILE=/path/to/feed.json npm run dev
```

---

## Configuration

| Variable | Used by | Default | Description |
|---|---|---|---|
| `ACTIVITY_DATA_FILE` | `npm run dev` / `build` | `../../output/github_activity_data.json` | Feed to publish. A relative path is resolved from `dashboard/app`. |
| `VITE_ACTIVITY_API_URL` | build (Vite) | `./activity.json` | Load the feed from another URL instead of the bundled file. That host must send `Access-Control-Allow-Origin`. Rarely needed. |

The page keeps the last feed in `localStorage` for 24 hours. The **Refresh** button bypasses that copy and fetches the published file again.

---

## Hosting your own copy (fork checklist)

Nothing in this repository is tied to a specific domain or account.

1. **Fork the repository** and configure `input/github.json` (see the root README).
2. **Generate your data.** Run the **Open Source Contribution Tracker Job** workflow from the Actions tab (or `python generate_report.py` locally) so `output/` holds your feed.
3. **Publish the site.**
   - **GitHub Pages (default):** forks have workflows disabled until you enable them on the **Actions** tab. Then open **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**, and run **Actions → Deploy Dashboard → Run workflow**. The site is served at `https://<your-user>.github.io/<repo>/` and is redeployed on every push that touches `dashboard/` and after each nightly report.
   - **Cloudflare:** follow [Deploying to Cloudflare](#deploying-to-cloudflare).
   - **Any other static host** (Netlify, S3, ...): build and upload the `dist` folder.

     ```bash
     cd dashboard/app
     npm ci
     npm run build      # output: dashboard/app/dist/
     ```

---

## Deploying to Cloudflare

The site is deployed as Workers **static assets**: `wrangler deploy` runs the `[build]` command from `wrangler.toml` (which copies the feed and builds the app) and uploads `app/dist`. No Worker script is involved.

| Method | When to use |
|--------|-------------|
| [A – CLI](#method-a--cli-wrangler-deploy) | One-off or manual deploy from your laptop |
| [B – GitHub Actions](#method-b--github-actions-automated-deploy) | Redeploy automatically after every nightly report |
| [C – Cloudflare dashboard UI](#method-c--cloudflare-dashboard-ui) | Inspect deployments, view logs, add a custom domain |

### Method A – CLI (`wrangler deploy`)

Prerequisites: a free [Cloudflare account](https://dash.cloudflare.com/sign-up) and Node.js 22+ (required by wrangler 4).

```bash
cd dashboard
npx wrangler@4 login            # once per machine; opens a browser
npx wrangler@4 deploy
```

The last lines print your URL, `https://<name>.<your-subdomain>.workers.dev`. To use a different name, change `name` in `wrangler.toml` before deploying.

| URL | Expected result |
|-----|----------------|
| `https://<url>/` | Dashboard UI loads |
| `https://<url>/activity.json` | The raw feed (JSON) |

To publish new data, regenerate the report and run `npx wrangler@4 deploy` again.

### Method B – GitHub Actions (automated deploy)

The **Deploy Dashboard** workflow (`.github/workflows/deploy-dashboard.yml`) also deploys to Cloudflare whenever both secrets exist. It runs on pushes that touch `dashboard/`, and the nightly report workflow calls it after committing fresh data. Without the secrets the Cloudflare job is skipped, with a notice in the run log.

1. **Create an API token:** [dash.cloudflare.com](https://dash.cloudflare.com) → **My Profile → API Tokens → Create Token**, choose the **Edit Cloudflare Workers** template, select your account, and copy the token.
2. **Find your Account ID:** **Workers & Pages** → copy **Account ID** from the right-hand sidebar.
3. **Add repository secrets** under **Settings → Secrets and variables → Actions**:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
4. **Run it once:** **Actions → Deploy Dashboard → Run workflow**.

The nightly workflow calls the deploy workflow directly because pushes made with `GITHUB_TOKEN` do not trigger other workflows.

### Method C – Cloudflare dashboard UI

Use the dashboard to manage a site already deployed with Method A or B. It cannot create the deployment itself, because uploading the built files needs `wrangler`.

| Task | Where in the dashboard |
|------|------------------------|
| View deployment history / roll back | **Workers & Pages → your project → Deployments** |
| Inspect real-time logs | **Workers & Pages → your project → Logs** |
| Add or remove a custom domain | **Workers & Pages → your project → Settings → Domains & Routes → Add Custom Domain** |
| View request analytics | **Workers & Pages → your project → Metrics** |

To add a custom domain, open **Settings → Domains & Routes → Add Custom Domain** and enter a domain that is already on Cloudflare DNS (for example `dashboard.example.com`). The certificate is provisioned automatically. The domain belongs to your Cloudflare account and is not stored in this repository.

Cloudflare's own Git integration also works: connect the repository, set the root directory to `dashboard`, and use `npx wrangler deploy` as the deploy command. It runs the same `[build]` step on every push, including the report workflow's commits.
