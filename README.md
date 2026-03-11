# OpenSource Contributions Tracker

A tool that fetches contribution data from the GitHub API and produces a rich markdown report for one user or a whole
team. Designed for developers and organizations who want a centralized, automated view of their open-source activity.

## Features

Tracks the following metrics across all configured repositories for each user, within a configurable date range:

| Metric | Description |
|--------|-------------|
| **Commits** | Commits merged into the default branch |
| **Pull Requests (Open / Closed)** | PRs authored by each user |
| **Issues (Open / Closed)** | Issues opened by each user |
| **Code Reviews** | Unique PRs formally reviewed (`reviewed-by:`) |
| **Lines Added / Removed** | Line-level changes for merged commits and open PRs, with optional refactor filtering |

The report includes:
- Overall summary table with totals for every metric
- Per-project and per-user contribution breakdowns with pie charts
- Detailed row-level table (project / repository / user / rank / all metrics)
- Activity detail section listing every individual PR and issue with status, dates, and labels

You control which metrics count toward the **Overall Contribution** score via `contribution_config`.

## How it works

1. **Data retrieval** — fetches commits, PRs, issues, code reviews, and (optionally) per-commit/per-PR line stats from the GitHub REST API, handling pagination and rate-limit headers automatically.
2. **Data processing** — aggregates raw counts per user per repository, applies the `contribution_config` scoring weights, and optionally filters large refactor commits/PRs via `refactor_threshold`.
3. **Report generation** — writes `output/github_contributions_report.md` (markdown), `output/github_contribution_data.csv` (raw data), and two PNG pie charts.
4. **Automated execution** — a GitHub Actions workflow runs the report on a schedule and commits the output. See [GitHub Actions](#github-actions-automated-workflow).

## Quick start (fork & go)

1. **Fork this repository.**
2. **Edit `input/github.json`** — set `start_date`, add your GitHub usernames, and map projects to repositories. See [Configuration](#configuration) for all options.
3. **Push the changes** — the GitHub Actions workflow will run automatically on the next scheduled cycle, or you can [trigger it manually](#steps-to-trigger-the-workflow-manually).
4. **View the report** — open `output/github_contributions_report.md` in the repository.

> **Local run**: skip steps 3–4 and run `python generate_report.py` after completing the [Local Setup](#local-setup).

## Demo

A live sample report is available at [output/github_contributions_report.md](output/github_contributions_report.md).
It shows the full report structure: summary table, pie charts, per-project and per-user breakdowns, and the activity
detail section with individual PRs and issues.

## Local Setup

### Prerequisites

- Python 3.10+
- A GitHub personal access token with at least `public_repo` scope (add `repo` scope for private repositories).
  Set it as the `GITHUB_TOKEN` environment variable.

### Installation

1. **Clone the repository**:
    ```sh
    git clone https://github.com/NihalJain/opensource-contributions-tracker.git
    cd opensource-contributions-tracker
    ```

2. **Install dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

3. **Set environment variables**:
    ```sh
    export GITHUB_TOKEN=your_personal_access_token
    # Optional — only needed if behind a corporate proxy:
    export HTTP_PROXY=http://proxy.example.com:8080
    export HTTPS_PROXY=http://proxy.example.com:8080
    ```

### Configuration

The input file is `input/github.json`. The only required fields are `start_date` and `users`.

**Minimal structure (single contributor, all repositories auto-detected):**
```json
{
    "start_date": "YYYY-MM-DD",
    "users": ["user1"]
}
```

**Full structure:**
```json
{
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "contribution_config": {
        "commits":       { "enabled": true,  "count_towards_score": true  },
        "open_prs":      { "enabled": true,  "count_towards_score": true  },
        "closed_prs":    { "enabled": true,  "count_towards_score": false },
        "open_issues":   { "enabled": true,  "count_towards_score": true  },
        "closed_issues": { "enabled": true,  "count_towards_score": true  },
        "code_reviews":  { "enabled": true,  "count_towards_score": true  },
        "line_stats":    { "enabled": false, "refactor_threshold": 0.1   }
    },
    "users": ["user1", "user2"],
    "project_to_repo_dict": {
        "Project1": ["owner/repo1", "owner/repo2"],
        "Project2": ["owner/repo3"]
    }
}
```

**Field reference:**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `start_date` | Yes | — | Start of the reporting period (`YYYY-MM-DD`) |
| `end_date` | No | Tomorrow | End of the reporting period (`YYYY-MM-DD`, inclusive) |
| `users` | Yes | — | List of GitHub usernames to track |
| `project_to_repo_dict` | No | Auto-detected | Maps project display names to lists of `owner/repo` strings. If omitted, repositories are discovered from each user's PR history (capped at 1 000 results by the GitHub Search API) |
| `contribution_config` | No | All enabled | Per-metric configuration object. Omitting it or any key within it uses the defaults shown below |
| &nbsp;&nbsp;`commits` | No | — | Config for merged commits |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `true` | Collect and display this metric |
| &nbsp;&nbsp;&nbsp;&nbsp;`count_towards_score` | No | `true` | Add to the Overall Contribution score |
| &nbsp;&nbsp;`open_prs` | No | — | Config for open pull requests |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `true` | Collect and display |
| &nbsp;&nbsp;&nbsp;&nbsp;`count_towards_score` | No | `true` | Add to score |
| &nbsp;&nbsp;`closed_prs` | No | — | Config for closed pull requests |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `true` | Collect and display |
| &nbsp;&nbsp;&nbsp;&nbsp;`count_towards_score` | No | `true` | Add to score |
| &nbsp;&nbsp;`open_issues` | No | — | Config for open issues |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `true` | Collect and display |
| &nbsp;&nbsp;&nbsp;&nbsp;`count_towards_score` | No | `true` | Add to score |
| &nbsp;&nbsp;`closed_issues` | No | — | Config for closed issues |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `true` | Collect and display |
| &nbsp;&nbsp;&nbsp;&nbsp;`count_towards_score` | No | `true` | Add to score |
| &nbsp;&nbsp;`code_reviews` | No | — | Config for PRs formally reviewed |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `true` | Collect and display |
| &nbsp;&nbsp;&nbsp;&nbsp;`count_towards_score` | No | `true` | Add to score |
| &nbsp;&nbsp;`line_stats` | No | — | Config for lines added/removed. Expensive: one extra API call per commit and per open PR |
| &nbsp;&nbsp;&nbsp;&nbsp;`enabled` | No | `false` | Fetch and display line stats. Set to `false` to skip (recommended for large datasets) |
| &nbsp;&nbsp;&nbsp;&nbsp;`refactor_threshold` | No | Disabled | Float (0–1). Commits/PRs where net-change ratio is below this are excluded from line counts |

**Output files** written to `output/`:

| File | Description |
|------|-------------|
| `github_contributions_report.md` | Full markdown report |
| `github_contribution_data.csv` | Raw per-user-per-repo numeric data |
| `github_activity_data.json` | Cached PR and issue objects used for the Activity Details section |
| `project_wise_contribution.png` | Pie chart of contributions by project |
| `user_wise_contribution.png` | Pie chart of contributions by user |

**Re-generate the report from cached data** (no API calls) — both output files must exist:
```sh
# In generate_report.py, comment out generate_report() and uncomment:
generate_report_with_local_data()
```

## GitHub Actions (Automated workflow)

The repository includes a GitHub Actions workflow at `.github/workflows/main.yml` that:
- Runs automatically on a schedule (default: every 24 hours — adjust the `cron` expression to suit your needs).
- Commits the generated report and CSV back to the repository.

To update the configuration, edit `input/github.json` and push — the next workflow run picks up the changes automatically.

### Steps to trigger the workflow manually

1. Go to the **Actions** tab of your forked repository.
2. Select the **Open Source Contribution Tracker Job** workflow.
3. Click **Run workflow**, choose the branch, and confirm.
4. Once the run completes, the updated report is committed to the `output/` directory.

## Contributing

1. Fork the repository and create a feature branch:
    ```sh
    git checkout -b feature/my-improvement
    ```
2. Make your changes and verify the script runs correctly:
    ```sh
    export GITHUB_TOKEN=your_token
    python generate_report.py
    ```
3. Commit, push, and open a pull request against `main`.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

## Contact

For questions or suggestions, please [open an issue](https://github.com/NihalJain/opensource-contributions-tracker/issues)
or reach out to the repository owner [Nihal Jain](https://www.linkedin.com/in/nihaljain/).