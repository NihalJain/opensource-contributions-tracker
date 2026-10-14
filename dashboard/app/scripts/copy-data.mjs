// Copies the generated activity feed into public/ so Vite publishes it next to index.html.
// Runs automatically before `npm run dev` and `npm run build` (see package.json).
//
// Source defaults to the report generator's output. Set ACTIVITY_DATA_FILE to publish a
// different file; a relative path is resolved from the app directory.
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(appDir, process.env.ACTIVITY_DATA_FILE ?? '../../output/github_activity_data.json');
const target = resolve(appDir, 'public/activity.json');

if (!existsSync(source)) {
  console.error(
    `Activity data not found at ${source}\n` +
      'Run generate_report.py first, or set ACTIVITY_DATA_FILE to the JSON file to publish.',
  );
  process.exit(1);
}

mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);
console.log(`Copied ${source} -> ${target}`);
