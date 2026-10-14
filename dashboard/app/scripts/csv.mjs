// A small RFC 4180 CSV parser: quoted fields, doubled quotes, embedded commas and newlines.
// It exists because report descriptions contain commas, which a split(',') would break.

/**
 * @param {string} text
 * @returns {string[][]} rows of fields, blank lines skipped
 */
export function parseCsv(text) {
  const input = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;

  const endField = () => {
    row.push(field);
    field = '';
  };
  const endRow = () => {
    endField();
    // A row holding a single empty field is a blank line.
    if (row.length > 1 || row[0] !== '') rows.push(row);
    row = [];
  };

  for (let i = 0; i < input.length; i += 1) {
    const ch = input[i];
    if (quoted) {
      if (ch === '"') {
        if (input[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          quoted = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      endField();
    } else if (ch === '\n') {
      endRow();
    } else if (ch === '\r') {
      if (input[i + 1] === '\n') i += 1;
      endRow();
    } else {
      field += ch;
    }
  }
  if (field !== '' || row.length > 0) endRow();
  return rows;
}

/**
 * Parse CSV text into objects keyed by the header row.
 * @param {string} text
 * @returns {Record<string, string>[]}
 */
export function parseCsvRecords(text) {
  const [header, ...rows] = parseCsv(text);
  if (!header) return [];
  return rows.map((cells) => Object.fromEntries(header.map((name, i) => [name, cells[i] ?? ''])));
}
