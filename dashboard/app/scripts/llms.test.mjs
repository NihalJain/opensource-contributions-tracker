import { describe, expect, it } from 'vitest';
import { buildLlmsTxt } from './llms.mjs';

describe('buildLlmsTxt', () => {
  const text = buildLlmsTxt({ title: 'Ada’s open source work' });

  it('starts with the site title as its one H1', () => {
    expect(text.startsWith('# Ada’s open source work\n')).toBe(true);
    expect(text.match(/^# /gm)).toHaveLength(1);
  });

  it('has a one-paragraph summary as a blockquote', () => {
    expect(text).toMatch(/\n> A dashboard of open source contributions/);
  });

  it('links every published data file', () => {
    for (const file of ['activity.json', 'contributions.json', 'meta.json']) {
      expect(text).toContain(`](${file})`);
    }
  });
});
