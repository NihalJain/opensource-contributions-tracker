import { describe, expect, it } from 'vitest';
import { parseCsv, parseCsvRecords } from './csv.mjs';

describe('parseCsv', () => {
  it('splits plain rows and fields', () => {
    expect(parseCsv('a,b,c\n1,2,3\n')).toEqual([
      ['a', 'b', 'c'],
      ['1', '2', '3'],
    ]);
  });

  it('keeps commas inside quoted fields', () => {
    expect(parseCsv('name,desc\nhbase,"Apache HBase, the Hadoop database"\n')).toEqual([
      ['name', 'desc'],
      ['hbase', 'Apache HBase, the Hadoop database'],
    ]);
  });

  it('unescapes doubled quotes', () => {
    expect(parseCsv('a\n"say ""hi"""\n')).toEqual([['a'], ['say "hi"']]);
  });

  it('keeps newlines inside quoted fields', () => {
    expect(parseCsv('a,b\n"line1\nline2",x\n')).toEqual([
      ['a', 'b'],
      ['line1\nline2', 'x'],
    ]);
  });

  it('handles CRLF line endings and a missing trailing newline', () => {
    expect(parseCsv('a,b\r\n1,2')).toEqual([
      ['a', 'b'],
      ['1', '2'],
    ]);
  });

  it('keeps empty fields, including a trailing one', () => {
    expect(parseCsv('a,b,c\n1,,\n')).toEqual([
      ['a', 'b', 'c'],
      ['1', '', ''],
    ]);
  });

  it('ignores a UTF-8 byte order mark', () => {
    expect(parseCsv('﻿a,b\n1,2\n')[0]).toEqual(['a', 'b']);
  });

  it('skips blank lines', () => {
    expect(parseCsv('a\n\n1\n')).toEqual([['a'], ['1']]);
  });
});

describe('parseCsvRecords', () => {
  it('keys each row by the header row', () => {
    expect(parseCsvRecords('x,y\n1,2\n3,4\n')).toEqual([
      { x: '1', y: '2' },
      { x: '3', y: '4' },
    ]);
  });

  it('returns no records for an empty file', () => {
    expect(parseCsvRecords('')).toEqual([]);
  });
});
