// Publishes the report generator's output next to index.html so the dashboard is a static site.
// Runs automatically before `npm run dev` and `npm run build` (see package.json).
//
//   output/github_activity_data.json     -> public/activity.json       (every PR and issue)
//   output/github_contribution_data.csv  -> public/contributions.json  (commits, reviews, score, rank)
//                                        -> public/meta.json           (when the site was built)
//                                        -> public/llms.txt            (what the site is, for language-model tools)
//
// Override the sources with ACTIVITY_DATA_FILE and CONTRIBUTIONS_DATA_FILE. A relative path is
// resolved from the app directory. The site title comes from site.config.json.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { toContributions } from './contributions.mjs';
import { parseCsvRecords } from './csv.mjs';
import { buildLlmsTxt } from './llms.mjs';

/**
 * @param {{ activityFile: string, contributionsFile: string, outDir: string, title?: string, now?: Date }} options
 */
export function prepareData({
  activityFile,
  contributionsFile,
  outDir,
  title = 'Open source contributions',
  now = new Date(),
}) {
  if (!existsSync(activityFile)) {
    throw new Error(
      `Activity data not found at ${activityFile}\n` +
        'Run generate_report.py first, or set ACTIVITY_DATA_FILE to the JSON file to publish.',
    );
  }

  mkdirSync(outDir, { recursive: true });
  copyFileSync(activityFile, join(outDir, 'activity.json'));

  let contributions = [];
  if (existsSync(contributionsFile)) {
    contributions = toContributions(parseCsvRecords(readFileSync(contributionsFile, 'utf8')));
  }
  writeFileSync(join(outDir, 'contributions.json'), JSON.stringify(contributions));
  writeFileSync(join(outDir, 'meta.json'), JSON.stringify({ builtAt: now.toISOString() }));
  writeFileSync(join(outDir, 'llms.txt'), buildLlmsTxt({ title }));

  return { contributions: contributions.length, hasContributionsFile: existsSync(contributionsFile) };
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const options = {
    activityFile: resolve(appDir, process.env.ACTIVITY_DATA_FILE ?? '../../output/github_activity_data.json'),
    contributionsFile: resolve(
      appDir,
      process.env.CONTRIBUTIONS_DATA_FILE ?? '../../output/github_contribution_data.csv',
    ),
    outDir: resolve(appDir, 'public'),
    title: JSON.parse(readFileSync(resolve(appDir, 'site.config.json'), 'utf8')).title,
  };
  try {
    const result = prepareData(options);
    console.log(`Published ${options.activityFile}`);
    if (result.hasContributionsFile) {
      console.log(`Published ${result.contributions} contribution rows from ${options.contributionsFile}`);
    } else {
      console.warn(`No contribution CSV at ${options.contributionsFile}; commits, reviews and scores will be hidden.`);
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  }
}
