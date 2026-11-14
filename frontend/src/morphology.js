export function normalizeLatinWord(word) {
  return word.normalize('NFC').trim()
    .replace(/^[^\p{L}\p{M}]+|[^\p{L}\p{M}]+$/gu, '').toLocaleLowerCase('la');
}

// Match surface spelling and occurrence, never absolute morphology indices.
export function selectLatinWord(line, segments, position) {
  const segment = segments[position];
  const selection = { text: segment.text, lineId: line.id, lineNumber: line.number,
    index: segment.index, parse: null };
  const target = normalizeLatinWord(segment.text);
  if (!target || !Array.isArray(line.morphology)) return selection;
  const displayed = segments.filter(s => s.index != null && normalizeLatinWord(s.text) === target);
  const matches = line.morphology.filter(item => item && typeof item.word === 'string'
    && normalizeLatinWord(item.word) === target);
  // Unequal counts make contextual occurrence matching unreliable.
  if (displayed.length !== matches.length) return selection;
  const occurrence = segments.slice(0, position).filter(s => s.index != null
    && normalizeLatinWord(s.text) === target).length;
  const parse = matches[occurrence]?.parse;
  if (typeof parse === 'string' && parse.trim()) selection.parse = parse;
  return selection;
}
