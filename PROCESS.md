# Task: Offline Morphological Analysis of the Aeneid Using Stanza

Implement `compute_morphology.py`, a Python script that computes morphological analyses for the entire *Aeneid* offline, processing one Card at a time.

The project already contains:

- `models.py` — SQLAlchemy 2.0 database models.
- `server.py` — Flask REST API.
- `aeneid.db` — SQLite database containing the Latin text, English translations, and morphology cache.
- `test_stanza.py` — **existing working example demonstrating how to initialize and use Stanza**.
- `data/` — original Perseus XML files.
- `frontend/` — Svelte 5 frontend.

**Inspect `models.py` and `test_stanza.py` before implementing anything.**

Reuse the Stanza initialization and model configuration from `test_stanza.py`. Do not invent a new model configuration or download a different model unnecessarily.

This is an offline data-processing task. Do not modify the frontend or Flask API.

## 1. Objective

Process the full Latin text of Virgil's *Aeneid* using Stanza.

The processing unit is a **Card**, which contains several consecutive Latin verse lines.

For each Card:

1. Load its Latin lines from SQLite.
2. Concatenate the lines into one passage.
3. Run Stanza once on the entire passage.
4. Align Stanza's output back to the original Latin words.
5. Generate a free-text morphological parse for each original word.
6. Save the results in SQLite, one Morphology record per Latin line.

The full work should be processed incrementally, with persistent caching so the script can be interrupted and resumed.

Do not call OpenAI or any other external AI API.

## 2. Relevant Database Structure

The existing SQLAlchemy models are approximately:

### Work

```python
class Work(Base):
    __tablename__ = "works"

    id: Mapped[int]
    title: Mapped[str]
    author: Mapped[str]
    cts_urn: Mapped[str | None]
```

### Card

```python
class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int]
    work_id: Mapped[int]
    book: Mapped[int]
    number: Mapped[int]
    latin_start: Mapped[int]
    latin_end: Mapped[int]
    english: Mapped[str]
```

The Card identifies a Latin verse range within a Book.

### Line

```python
class Line(Base):
    __tablename__ = "lines"

    id: Mapped[int]
    work_id: Mapped[int]
    book: Mapped[int]
    number: Mapped[int]
    latin: Mapped[str]
```

Retrieve a Card's Latin lines by:

```python
select(Line).where(
    Line.work_id == card.work_id,
    Line.book == card.book,
    Line.number >= card.latin_start,
    Line.number <= card.latin_end,
).order_by(Line.number)
```

### Morphology

The existing morphology table stores one record per Latin line.

Its structure is approximately:

```python
class Morphology(Base):
    __tablename__ = "morphology"

    id: Mapped[int]
    line_id: Mapped[int]
    data: Mapped[list]
    model: Mapped[str]
```

Use the actual model definition in `models.py`.

Do not recreate or migrate the database unless strictly necessary.

Do not modify the imported Latin text, Cards, or Interlinear Gloss data.

## 3. Morphology JSON Format

Morphology data is deliberately simple.

Each line stores a JSON array of objects, one object per original Latin word.

Each object contains:

- `word`: original Latin surface word.
- `parse`: free-text morphology.

Example:

Latin:

`Arma virumque cano, Troiae qui primus ab oris`

JSON:

```json
[
  {
    "word": "Arma",
    "parse": "arma | NOUN | Case=Acc, Number=Plur, Gender=Neut"
  },
  {
    "word": "virumque",
    "parse": "vir | NOUN | Case=Acc, Number=Sing, Gender=Masc\nque | CCONJ"
  },
  {
    "word": "cano",
    "parse": "cano | VERB | Person=1, Number=Sing, Tense=Pres, Mood=Ind, Voice=Act"
  },
  {
    "word": "Troiae",
    "parse": "Troia | PROPN | Case=Gen, Number=Sing"
  },
  {
    "word": "qui",
    "parse": "qui | PRON | Case=Nom, Number=Sing"
  },
  {
    "word": "primus",
    "parse": "primus | ADJ | Case=Nom, Number=Sing"
  },
  {
    "word": "ab",
    "parse": "ab | ADP"
  },
  {
    "word": "oris",
    "parse": "ora | NOUN | Case=Abl, Number=Plur"
  }
]
```

This is an illustrative format, not necessarily the exact output of Stanza.

### Formatting rules

For each Stanza word, format:

`lemma | UPOS | morphological features`

For example:

`venio | VERB | Mood=Ind, Number=Sing, Person=3, Tense=Perf, Voice=Act`

Sort morphological features alphabetically for consistent output.

If morphological features are absent, omit that section:

`et | CCONJ`

If a Stanza token contains multiple Stanza words, produce multiple parse lines, separated by `\n`.

For example:

```text
vir | NOUN | Case=Acc, Gender=Masc, Number=Sing
que | CCONJ
```

The stored JSON string contains the newline character.

Do not store sentence IDs, dependency heads, token indices, or dependency relations.

Do not add grammatical explanations.

Do not correct Stanza's potentially inaccurate analyses. Preserve the actual model predictions.

If analysis fails for an original word, save an empty `parse` string and log the failure.

## 4. Original Word Extraction

The original Latin text is authoritative.

Create a deterministic original-word extractor.

Requirements:

- Preserve the surface spelling.
- Ignore punctuation-only elements.
- Do not include line numbers as words.
- Treat enclitic forms as one original word.
- For example, `virumque` is one word.
- `Tantaene` is one word.
- `quidve` is one word.
- Do not split Latin words based on Stanza's tokenization.

Use Unicode-aware processing.

The extractor should return both the original surface word and its character span.

Conceptually:

```python
[
    {
        "word": "Arma",
        "start": 0,
        "end": 4
    },
    {
        "word": "virumque",
        "start": 5,
        "end": 13
    }
]
```

Character offsets are internal processing metadata and must not be included in the final Morphology JSON.

Ensure that the extracted words match the words displayed in the original text.

The frontend does not guarantee identical tokenization, so the final JSON contains `word` for lookup by surface spelling.

## 5. Process One Card at a Time

Read Cards in canonical reading order:

```python
select(Card).order_by(
    Card.work_id,
    Card.book,
    Card.number,
)
```

For each Card:

1. Fetch the corresponding Latin lines.
2. Build one text passage from those lines.
3. Record the character range occupied by each original line.
4. Extract original words and their absolute character ranges.
5. Run Stanza once on the complete passage.
6. Align Stanza's output to the original words.
7. Split the aligned analyses back into line-level JSON arrays.
8. Save each line's Morphology record.

Example Card text:

```text
Arma virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
```

Do not prepend line numbers to the text passed into Stanza.

The Card may contain multiple Latin sentences, and a sentence may span multiple verse lines.

Do not run Stanza separately on every verse line.

## 6. Alignment Algorithm

This is the most important part of the implementation.

**Do not assume Stanza's tokens correspond one-to-one with the original Latin words.**

Examples:

```text
Original word: virumque
Stanza:        virum + que

Original word: Tantaene
Stanza:        tantae + ne
```

The objective is to map one or more Stanza words to each original word.

### Preferred approach: Character-offset alignment

Stanza tokens generally provide:

- `token.text`
- `token.start_char`
- `token.end_char`
- `token.words`

Use these character offsets to associate Stanza tokens with original surface words.

Important distinction:

- A Stanza Token represents a surface span.
- A Stanza Token may contain multiple Stanza Words.
- The individual Words contain the morphological analysis.

If a Stanza token spans exactly one original word, associate all of its Stanza Words with that original word.

If Stanza creates multiple surface tokens within one original word, associate all overlapping tokens with that original word, preserving their order.

Use the original concatenated Card text as the common coordinate system.

### Fallback: Dynamic-programming sequence alignment

Implement a fallback alignment algorithm for cases where Stanza's offsets are missing, inconsistent, or otherwise insufficient.

Align two sequences:

A. Original Latin surface words.

B. Stanza surface tokens.

The alignment must support:

- One original word ↔ one Stanza token.
- One original word ↔ multiple Stanza tokens.
- Multiple original words ↔ one Stanza token, when unavoidable.
- Skipped punctuation or tokenizer artifacts.

Use dynamic programming to find a minimum-cost, order-preserving alignment.

Suggested similarity logic:

1. Normalize Unicode consistently.
2. Apply case folding.
3. Remove surrounding punctuation.
4. Compare normalized surface strings.
5. For split tokens, compare the concatenation of consecutive Stanza token strings with the original word.
6. Use edit distance only as a fallback.
7. Penalize unmatched words and non-exact mappings.

Example:

```text
Original:  ["Arma", "virumque", "cano"]
Stanza:   ["Arma", "virum", "que", "cano"]

Alignment:

Arma       → Arma
virumque   → virum + que
cano       → cano
```

Do not use naive positional matching.

Prefer a small, well-documented DP implementation over introducing a large dependency.

The algorithm should produce explicit mappings from original words to Stanza tokens.

Where multiple Stanza analyses map to one original word, concatenate them in their original order using newline characters.

### Alignment failure

If an original word cannot be aligned with sufficient confidence:

- Keep the original word in the result.
- Save its `parse` as an empty string.
- Log the Card ID, line number, word, and reason.

Do not shift subsequent analyses to fill the gap.

Do not silently assign a neighboring word's parse.

If alignment is severely inconsistent for a Card, treat the Card as failed rather than persisting misleading results.

## 7. Stanza Integration

Read `test_stanza.py` before implementation.

It contains the working Stanza setup and pipeline configuration.

Reuse that configuration.

Initialize the Stanza pipeline once at the start of the script, not once per Card.

Then call it for each Card:

```python
doc = nlp(card_text)
```

Stanza output should provide:

- `word.text`
- `word.lemma`
- `word.upos`
- `word.feats`

The `feats` field may be a string like:

`Case=Acc|Gender=Masc|Number=Sing`

Convert this to a consistently formatted comma-separated representation.

Example:

`Case=Acc, Gender=Masc, Number=Sing`

Do not include dependency relationships in the final parse.

Handle Stanza tokens that contain multiple words.

Handle tokens without morphological features.

Avoid unnecessary logging from Stanza during batch processing.

## 8. Database Persistence and Resume

The computation may take some time, so make it resumable.

### Default behavior

For each Card:

- Check whether all associated Latin lines already have Morphology records.
- If all lines are complete, skip the Card.
- If some lines are missing, process the entire Card with Stanza to preserve context.
- Save only the missing line records.
- Do not overwrite existing morphology by default.

This is important because morphology is stored per Line even though it is computed per Card.

### Transactions

Use one short database transaction per Card for persistence.

Do not keep a write transaction open while Stanza is running.

Perform validation before saving.

If a Card's analysis fails, log the error, roll back any pending writes for that Card, and continue to the next Card.

### Optional recomputation

Provide a CLI option:

`--force`

When specified:

- Recompute selected Cards.
- Replace existing Morphology data for their lines.
- Do not delete Latin lines or Cards.

Without `--force`, preserve existing results.

### Model metadata

Set the `model` field to identify the Stanza model used.

Use the actual configuration from `test_stanza.py`.

Do not claim to have used a different model.

## 9. Command-Line Interface

Implement the script so it can be run as:

```bash
python compute_morphology.py
```

Support useful CLI options:

```bash
python compute_morphology.py --book 1
```

Process one Book.

```bash
python compute_morphology.py --card 1
```

Process a Card by database ID.

```bash
python compute_morphology.py --book 1 --limit 10
```

Process at most ten selected Cards.

```bash
python compute_morphology.py --force --card 1
```

Recompute an existing Card.

```bash
python compute_morphology.py --dry-run --card 1
```

Run Stanza and show the resulting morphology without modifying the database.

Provide progress reporting:

```text
Book 1, Card 1: 7 lines, 54 words, saved
Book 1, Card 8: 4 lines, 32 words, skipped
Book 1, Card 12: 6 lines, 47 words, saved
...
```

At the end, report totals for:

- Cards processed.
- Cards skipped.
- Cards failed.
- Lines inserted or updated.
- Original words analyzed.
- Words whose alignment failed.

Do not report a Card as successfully processed if persistence failed.

## 10. Verification and Tests

Create focused tests for the processing and alignment logic.

Do not depend on the full Stanza model for most tests.

Use synthetic Stanza-like objects where appropriate.

Test:

1. One original word ↔ one Stanza token.
2. One original word ↔ two Stanza tokens.
3. One Stanza token containing multiple Stanza Words.
4. Punctuation between original words.
5. Repeated words in the same line.
6. A Latin sentence spanning multiple verse lines.
7. Missing or inconsistent character offsets.
8. DP fallback alignment.
9. An unaligned word does not shift subsequent analyses.
10. A Card with partially cached Morphology.
11. Re-running without `--force`.
12. Re-running with `--force`.
13. Correct JSON serialization of multi-line parses.
14. A failed Card does not leave partial inconsistent results.

For integration verification, run a dry-run on a small number of Cards and inspect the output.

Do not overwrite or delete the existing database during testing.

## 11. Scope Restrictions

Do not modify:

- `server.py`
- Frontend source code
- Existing REST API formats
- Latin source text
- English Card translations
- Interlinear Gloss records
- Existing import scripts

Do not call OpenAI.

Do not generate English word glosses.

Do not implement morphological correction or contextual explanations.

Do not introduce a new database schema unless the actual existing models make a small compatibility fix strictly necessary.

## 12. Completion Criteria

The task is complete when:

1. `compute_morphology.py` exists.
2. It loads Latin text from SQLite, Card by Card.
3. It uses the working Stanza configuration from `test_stanza.py`.
4. It runs Stanza once per selected Card.
5. It maps Stanza output back to original Latin words using offsets and DP fallback.
6. Multiple Stanza analyses can be joined into one free-text parse.
7. It stores the expected `[{ "word": ..., "parse": ... }]` JSON format.
8. Morphology is stored per Latin Line in the existing database.
9. The script can resume without recomputing completed Cards.
10. `--force`, `--book`, `--card`, `--limit`, and `--dry-run` work.
11. Alignment failures are visible and never silently corrupt neighboring words.
12. Existing data and APIs remain unchanged.

Keep the implementation clear, deterministic, and easy to audit. Prefer reliable alignment and accurate preservation of Stanza output over aggressive automatic matching.
