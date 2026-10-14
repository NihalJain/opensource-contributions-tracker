import { useMemo } from 'react';
import { BarList, type BarRow } from '../charts/BarList';
import type { ProjectBreakdown } from '../data/aggregate';
import { formatCompact, formatInt, plural } from '../data/format';
import { ChartFrame, DataTable } from './ChartFrame';

interface Props {
  breakdown: ProjectBreakdown;
  selectedProjects: string[];
  selectedRepos: string[];
  onToggleProject: (project: string) => void;
  onToggleRepo: (repo: string) => void;
}

const n = (value: number, measure: ProjectBreakdown['measure']) => (measure === 'score' ? formatCompact(value) : formatInt(value));

export function Projects({ breakdown, selectedProjects, selectedRepos, onToggleProject, onToggleRepo }: Props) {
  const { measure, projects } = breakdown;

  const rows = useMemo<BarRow[]>(() => {
    const out: BarRow[] = [];
    for (const project of projects) {
      const parts = [
        project.reviews > 0 ? plural(project.reviews, 'review') : null,
        project.commits > 0 ? plural(project.commits, 'commit') : null,
        project.merged > 0 ? `${formatInt(project.merged)} merged` : null,
      ].filter(Boolean);
      out.push({
        key: `p:${project.project}`,
        label: project.project,
        value: project.value,
        display: n(project.value, measure),
        detail: parts.join(', '),
      });
      if (selectedProjects.includes(project.project) && project.repos.length > 1) {
        for (const repo of project.repos) {
          out.push({
            key: `r:${repo.repo}`,
            label: repo.repo,
            value: repo.value,
            display: n(repo.value, measure),
            nested: true,
            detail: repo.rank ? `Ranked #${formatInt(repo.rank)} among contributors` : repo.description || undefined,
          });
        }
      }
    }
    return out;
  }, [projects, selectedProjects, measure]);

  const table = (
    <DataTable
      caption="Projects and repositories"
      head={['Repository', 'Project', measure === 'score' ? 'Score' : 'Items', 'Reviews', 'Commits', 'Merged PRs', 'Rank']}
      rows={projects.flatMap((p) =>
        p.repos.map((r) => [
          r.repo,
          p.project,
          formatInt(r.value),
          formatInt(r.reviews),
          formatInt(r.commits),
          formatInt(r.merged),
          r.rank ? `#${formatInt(r.rank)}` : 'Unranked',
        ]),
      )}
    />
  );

  return (
    <ChartFrame
      title="Projects and repositories"
      description={
        measure === 'score'
          ? 'Ranked by contribution score. Select a project to filter the page and see its repositories.'
          : 'Ranked by pull requests and issues. Select a project to filter the page and see its repositories.'
      }
      table={table}
    >
      <BarList
        rows={rows}
        ariaLabel="Projects ranked by contribution"
        selected={[...selectedProjects.map((p) => `p:${p}`), ...selectedRepos.map((r) => `r:${r}`)]}
        onSelect={(key) => (key.startsWith('p:') ? onToggleProject(key.slice(2)) : onToggleRepo(key.slice(2)))}
      />
    </ChartFrame>
  );
}
