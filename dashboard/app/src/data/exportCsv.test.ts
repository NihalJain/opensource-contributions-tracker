import { describe, expect, it } from 'vitest';
import { makeItem } from './fixtures';
import { toCsv } from './exportCsv';

describe('toCsv', () => {
  it('writes a header and one row per item', () => {
    const csv = toCsv([makeItem({ number: 7, title: 'Fix scanner', outcome: 'merged', labels: ['bug', 'backport'] })]);
    const [header, row] = csv.trimEnd().split('\r\n');
    expect(header).toBe('Type,Status,Project,Repository,Number,Title,Labels,Opened,Merged,Days to merge,URL');
    expect(row).toContain('Pull request,Merged,Apache HBase,apache/hbase,7,Fix scanner,bug; backport,2024-03-01');
  });

  it('quotes fields containing commas, quotes and newlines', () => {
    const csv = toCsv([makeItem({ number: 1, title: 'Handle "null", then\nretry' })]);
    expect(csv).toContain('"Handle ""null"", then\nretry"');
  });

  it('neutralises spreadsheet formulas in titles', () => {
    const csv = toCsv([makeItem({ number: 1, title: '=HYPERLINK("http://evil")' })]);
    expect(csv).toContain("\"'=HYPERLINK(\"\"http://evil\"\")\"");
  });

  it('leaves merge fields empty for unmerged work', () => {
    const csv = toCsv([makeItem({ number: 2, outcome: 'open' })]);
    const row = csv.trimEnd().split('\r\n')[1];
    expect(row).toMatch(/,2024-03-01,,,https:/);
  });
});
