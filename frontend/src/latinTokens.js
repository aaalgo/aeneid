// Keep original punctuation and spacing while numbering lexical words only.
// Once loaded, server token identities are authoritative.
export function latinSegments(text, gloss) {
  const tokens = gloss ?? Array.from(
    text.matchAll(/[\p{L}][\p{L}\p{M}]*(?:['’][\p{L}][\p{L}\p{M}]*)*['’]?/gu),
    (match, index) => ({ index, token: match[0] }),
  );
  const segments = [];
  let offset = 0;
  for (const token of tokens) {
    const start = text.indexOf(token.token, offset);
    if (start < offset) continue;
    if (start > offset) segments.push({ text: text.slice(offset, start) });
    segments.push({ text: token.token, index: token.index, english: token.english });
    offset = start + token.token.length;
  }
  if (offset < text.length) segments.push({ text: text.slice(offset) });
  return segments;
}
