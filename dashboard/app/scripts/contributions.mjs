// Maps rows of output/github_contribution_data.csv (keyed by the report's column headers)
// to the typed objects the dashboard loads from contributions.json.

const count = (value) => {
  const n = Number(value);
  return value !== undefined && value !== '' && Number.isFinite(n) ? n : 0;
};

/** The report writes -1 when a user's rank in a repository could not be determined. */
const rank = (value) => {
  const n = count(value);
  return n > 0 ? n : null;
};

/**
 * @param {Record<string, string>[]} records
 */
export function toContributions(records) {
  return records.map((r) => ({
    project: r['Project Key'] ?? '',
    repo: r.Repository ?? '',
    repoUrl: r['Repository URL'] ?? '',
    description: r['Repository Description'] ?? '',
    repoAvatar: r['Repository Avatar'] ?? '',
    user: r.User ?? '',
    commits: count(r.Commits),
    prsOpen: count(r['Pull Requests (Open)']),
    prsClosed: count(r['Pull Requests (Closed)']),
    issuesOpen: count(r['Issues (Open)']),
    issuesClosed: count(r['Issues (Closed)']),
    reviews: count(r['Code Reviews']),
    linesAdded: count(r['Lines Added']),
    linesRemoved: count(r['Lines Removed']),
    rank: rank(r.Rank),
    score: count(r['Overall Contribution']),
  }));
}
