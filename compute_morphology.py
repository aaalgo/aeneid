#!/usr/bin/env python3
"""Offline, resumable Card-level Stanza analysis. No model downloads or schema changes."""
import argparse
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import unicodedata

from sqlalchemy import select
from models import Card, Line, Morphology, SessionLocal

LOG = logging.getLogger(__name__)
MODEL = 'stanza:latincy/la_stanza_latincy'


@dataclass(frozen=True)
class OriginalWord:
    word: str
    start: int
    end: int
    line_id: int = 0
    line_number: int = 0


def extract_words(text, offset=0, line_id=0, line_number=0):
    """Letter/combining-mark runs, preserving Unicode spelling and source spans."""
    result = []
    start = None
    for i, char in enumerate(text + ' '):
        category = unicodedata.category(char)
        if category.startswith('L') or (start is not None and category.startswith('M')):
            if start is None:
                start = i
        elif start is not None:
            result.append(OriginalWord(text[start:i], offset + start, offset + i,
                                       line_id, line_number))
            start = None
    return result


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFC', text).casefold()
                   if unicodedata.category(c)[0] in ('L', 'M'))


def format_word(word):
    parts = [word.lemma or word.text, word.upos or 'X']
    if word.feats and word.feats != '_':
        parts.append(', '.join(sorted(word.feats.split('|'))))
    return ' | '.join(parts)


def edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = new
    return row[-1]


def dp_alignment(originals, tokens):
    """Minimum-cost monotone alignment with skips and bounded grouped matches.

    Exact concatenations cost zero; gaps cost one per element. Edit distance
    helps choose a path but non-exact pairs are never accepted as analyses.
    Groups permit split tokens and merged original words (up to four each).
    Returns explicit original-index -> token-index lists.
    """
    a = [normalize(w.word) for w in originals]
    active = [(i, normalize(t.text)) for i, t in enumerate(tokens) if normalize(t.text)]
    b = [s for _, s in active]
    n, m = len(a), len(b)
    costs = [[float('inf')] * (m + 1) for _ in range(n + 1)]
    back = {}
    costs[0][0] = 0

    def relax(i, j, ni, nj, cost, accepted):
        value = costs[i][j] + cost
        if value < costs[ni][nj]:
            costs[ni][nj] = value
            back[ni, nj] = (i, j, accepted)

    for i in range(n + 1):
        for j in range(m + 1):
            for na in range(1, min(4, n-i) + 1):
                for nb in range(1, min(4, m-j) + 1):
                    # Many-to-many groups hide boundaries and add ambiguity.
                    if na > 1 and nb > 1:
                        continue
                    left, right = ''.join(a[i:i+na]), ''.join(b[j:j+nb])
                    exact = left == right
                    cost = (0 if exact else 1 + edit_distance(left, right) / max(len(left), len(right), 1))
                    cost += .01 * (na + nb - 2)
                    relax(i, j, i+na, j+nb, cost, exact)
            if i < n:
                relax(i, j, i+1, j, 1, False)
            if j < m:
                relax(i, j, i, j+1, 1, False)
    mapping = [[] for _ in originals]
    i, j = n, m
    while i or j:
        pi, pj, accepted = back[i, j]
        if accepted:
            for k in range(pi, i):
                mapping[k] = [active[t][0] for t in range(pj, j)]
        i, j = pi, pj
    return mapping


def align(originals, tokens, text):
    """Use validated surface offsets; fall back to sequence DP as a whole."""
    mapping = [[] for _ in originals]
    previous_end = 0
    valid = True
    for ti, token in enumerate(tokens):
        if not normalize(token.text):
            continue
        start, end = getattr(token, 'start_char', None), getattr(token, 'end_char', None)
        if (not isinstance(start, int) or not isinstance(end, int)
                or not 0 <= start < end <= len(text) or start < previous_end
                or normalize(text[start:end]) != normalize(token.text)):
            valid = False
            break
        previous_end = end
        hits = [i for i, w in enumerate(originals) if w.start < end and w.end > start]
        if len(hits) != 1 or start < originals[hits[0]].start or end > originals[hits[0]].end:
            valid = False
            break
        mapping[hits[0]].append(ti)
    if valid:
        for w, indices in zip(originals, mapping):
            if normalize(w.word) != ''.join(normalize(tokens[i].text) for i in indices):
                valid = False
                break
    return mapping if valid else dp_alignment(originals, tokens)


class AnalysisError(ValueError):
    def __init__(self, message, words=0, failures=0):
        super().__init__(message)
        self.words = words
        self.failures = failures


def analyze_card(card, lines, nlp):
    text = '\n'.join(line.latin for line in lines)
    originals = []
    offset = 0
    for line in lines:
        originals.extend(extract_words(line.latin, offset, line.id, line.number))
        offset += len(line.latin) + 1
    doc = nlp(text)
    tokens = [token for sentence in doc.sentences for token in sentence.tokens]
    mapping = align(originals, tokens, text)
    result = {line.id: [] for line in lines}
    failures = 0
    # A merged surface token can only be divided when its Word boundaries
    # exactly reconstruct the original boundaries. Never duplicate its parse.
    owners = {}
    for i, indices in enumerate(mapping):
        for ti in indices:
            owners.setdefault(ti, []).append(i)
    for i, (original, indices) in enumerate(zip(originals, mapping)):
        analyses = []
        reason = 'no confident surface alignment'
        for ti in indices:
            token = tokens[ti]
            if len(owners[ti]) == 1:
                analyses.extend(token.words)
            else:
                group = owners[ti]
                expected = [normalize(originals[k].word) for k in group]
                actual = [normalize(w.text) for w in token.words]
                if expected == actual:
                    analyses.append(token.words[group.index(i)])
                else:
                    reason = 'merged token has ambiguous Word boundaries'
                    analyses = []
                    break
        parse = '\n'.join(format_word(w) for w in analyses)
        if not parse:
            failures += 1
            LOG.warning('Card %s, line %s, word %r: %s', card.id,
                        original.line_number, original.word, reason)
        result[original.line_id].append({'word': original.word, 'parse': parse})
    # Isolated failures are retained visibly; broad mismatches invalidate a Card.
    if originals and failures / len(originals) > .25:
        raise AnalysisError(
            f'severely inconsistent alignment: {failures}/{len(originals)} words failed',
            words=len(originals), failures=failures)
    json.dumps(result, ensure_ascii=False)  # Validate before entering a write transaction.
    return result, len(originals), failures


def load_pipeline():
    import stanza
    from huggingface_hub import snapshot_download
    model_dir = snapshot_download('latincy/la_stanza_latincy', local_files_only=True)
    return stanza.Pipeline(
        'la', dir=model_dir, download_method=None,
        tokenize_forward_charlm_path=str(Path(model_dir) / 'la/forward_charlm/latincy.pt'),
        verbose=False,
    )


def process_cards(factory, nlp, *, book=None, card=None, limit=None, force=False,
                  dry_run=False):
    totals = dict(processed=0, skipped=0, failed=0, lines=0, words=0, alignment_failed=0)
    query = select(Card).order_by(Card.work_id, Card.book, Card.number)
    if book is not None:
        query = query.where(Card.book == book)
    if card is not None:
        query = query.where(Card.id == card)
    if limit is not None:
        query = query.limit(limit)
    with factory() as session:
        cards = session.scalars(query).all()
    pipeline = nlp
    for selected in cards:
        label = f'Book {selected.book}, Card {selected.id}'
        try:
            with factory() as session:
                lines = session.scalars(select(Line).where(
                    Line.work_id == selected.work_id, Line.book == selected.book,
                    Line.number >= selected.latin_start, Line.number <= selected.latin_end
                ).order_by(Line.number)).all()
                ids = [line.id for line in lines]
                cached = set(session.scalars(select(Morphology.line_id).where(Morphology.line_id.in_(ids))))
            if not lines:
                raise AnalysisError('Card has no Latin lines')
            count = sum(len(extract_words(line.latin)) for line in lines)
            if len(cached) == len(lines) and not force and not dry_run:
                totals['skipped'] += 1
                print(f'{label}: {len(lines)} lines, {count} words, skipped')
                continue
            if pipeline is None:
                pipeline = load_pipeline()
            data, count, failures = analyze_card(selected, lines, pipeline)
            totals['words'] += count
            totals['alignment_failed'] += failures
            changed = 0
            if dry_run:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                # Recheck cache under the short persistence transaction.
                with factory.begin() as session:
                    existing = {row.line_id: row for row in session.scalars(
                        select(Morphology).where(Morphology.line_id.in_(ids)))}
                    for line_id, entries in data.items():
                        row = existing.get(line_id)
                        if row is None:
                            session.add(Morphology(line_id=line_id, data=entries, model=MODEL))
                            changed += 1
                        elif force:
                            row.data, row.model = entries, MODEL
                            changed += 1
            totals['processed'] += 1
            totals['lines'] += changed
            print(f'{label}: {len(lines)} lines, {count} words, {"dry-run" if dry_run else "saved"}')
        except Exception as error:
            if isinstance(error, AnalysisError):
                totals['words'] += error.words
                totals['alignment_failed'] += error.failures
            totals['failed'] += 1
            LOG.exception('%s: failed', label)
    labels = dict(processed='Cards processed', skipped='Cards skipped', failed='Cards failed',
                  lines='Lines inserted or updated', words='Original words analyzed',
                  alignment_failed='Words whose alignment failed')
    print('Totals: ' + ', '.join(f'{labels[key]}={value}' for key, value in totals.items()))
    return totals


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError('must be nonnegative')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book', type=int)
    parser.add_argument('--card', type=int, help='Card database ID')
    parser.add_argument('--limit', type=nonnegative)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='Analyze even cached Cards, without writes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    totals = process_cards(SessionLocal, None, **vars(args))
    return int(totals['failed'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())
