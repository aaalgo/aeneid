# Task: Integrate Morphological Parsing into Aeneid Reader

We have an existing Aeneid Reader with:

- `models.py`: SQLAlchemy 2.0 ORM models.
- `server.py`: Flask REST API.
- `aeneid.db`: SQLite database.
- `frontend/`: Svelte 5 + Vite frontend.
- `static/`: Compiled frontend.

The database contains Latin lines, English translation Cards, and a `Morphology` table for offline Stanza parsing results.

Implement morphology retrieval and display in the existing application.

**Do not implement Stanza processing or AI generation in this task.** Morphology data will be generated separately and stored in SQLite.

Inspect the actual code before making changes. Preserve existing functionality and API compatibility.

## 1. Morphology JSON Format

Each `Morphology` database record corresponds to one Latin line.

The `data` column contains a JSON array of objects, one object per original Latin word.

Each object has two fields:

- `word`: the original Latin surface word, without surrounding punctuation.
- `parse`: a free-text morphological analysis string.

Example for:

`Arma virumque cano, Troiae qui primus ab oris`

```json
[
  {
    "word": "Arma",
    "parse": "arma | NOUN | Case=Acc, Number=Plur, Gender=Neut"
  },
  {
    "word": "virumque",
    "parse": "vir | NOUN | Case=Acc, Number=Sing, Gender=Masc; que | CCONJ"
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

### Rules

1. Each entry represents one original Latin word.
2. Preserve the original surface spelling in `word`.
3. `parse` is free text, not structured morphology.
4. If Stanza splits one original word into multiple tokens, concatenate their parsing results using `; `.
5. Do not include punctuation as separate entries.
6. Preserve original word order.
7. An unsuccessful parse may be represented by an empty string.
8. Do not invent or correct morphological analysis.
9. The `word` field is the lookup key for matching clicked words.

Do not introduce nested token structures, dependency trees, or detailed grammatical objects.

Use the existing `Morphology` model and its `data` JSON column. Make only the minimal model changes required to support this format.

## 2. Update GET /api/cards/{card_id}

Extend the existing Card API response to include morphology for each Latin line.

The existing response structure is:

```json
{
  "id": 1,
  "work_id": 1,
  "book": 1,
  "number": 1,
  "latin_start": 1,
  "latin_end": 7,
  "english": "...",
  "lines": [
    {
      "id": 1,
      "number": 1,
      "latin": "Arma virumque cano, Troiae qui primus ab oris",
      "annotation": null
    }
  ],
  "prev": null,
  "next": 2
}
```

Add a new `morphology` field to each object in `lines`.

Expected response:

```json
{
  "id": 1,
  "work_id": 1,
  "book": 1,
  "number": 1,
  "latin_start": 1,
  "latin_end": 7,
  "english": "...",
  "lines": [
    {
      "id": 1,
      "number": 1,
      "latin": "Arma virumque cano, Troiae qui primus ab oris",
      "annotation": null,
      "morphology": [
        {
          "word": "Arma",
          "parse": "arma | NOUN | Case=Acc, Number=Plur, Gender=Neut"
        },
        {
          "word": "virumque",
          "parse": "vir | NOUN | Case=Acc, Number=Sing; que | CCONJ"
        }
      ]
    },
    {
      "id": 2,
      "number": 2,
      "latin": "Italiam, fato profugus, Laviniaque venit",
      "annotation": null,
      "morphology": null
    }
  ],
  "prev": null,
  "next": 2
}
```

The morphology array in the example is abbreviated.

### Important requirements

- `morphology` is a property of each Latin line, not of the Card itself.
- If a line has a Morphology database record, return its `data` array.
- If no Morphology record exists, return `null`.
- Do not return an empty array merely because morphology is missing.
- Preserve the existing `annotation` property.
- Preserve all existing Card metadata and navigation fields.
- Keep `prev` and `next` as integer IDs or `null`.
- Do not change other existing response fields.
- Never trigger morphological computation from this endpoint.

### SQLAlchemy

Load morphology efficiently using `selectinload()` or an appropriate eager-loading strategy.

Avoid an N+1 query for Cards containing multiple Latin lines.

The response must not depend on a database session remaining open after serialization.

## 3. Update GET /api/lines/{line_id}

Apply the same extension to the individual Line API.

Example:

```json
{
  "id": 1,
  "work_id": 1,
  "book": 1,
  "number": 1,
  "latin": "Arma virumque cano, Troiae qui primus ab oris",
  "annotation": null,
  "morphology": [
    {
      "word": "Arma",
      "parse": "arma | NOUN | Case=Acc, Number=Plur, Gender=Neut"
    }
  ]
}
```

Return `morphology: null` when no record exists.

Prefer reusing the same line serialization logic between the Card and Line endpoints while preserving their existing fields.

## 4. Frontend: Click a Latin Word to Display Morphology

Update the existing Svelte 5 frontend.

The frontend already has an English/Latin mode switch and a bottom Parse / Explanation panel.

In Latin mode:

1. Render Latin words as clickable elements, preserving the original text and punctuation.
2. When the user clicks a word, identify the Latin line containing it.
3. Search that line's `morphology` array for a matching `word`.
4. If a matching entry exists and `parse` is nonempty, display its free-text parse in the bottom panel.
5. If morphology is missing, or the word cannot be found, display a simple unavailable message.
6. Highlight the selected word.
7. Clear the selection when navigating to another Card.

Do not request morphology from another endpoint. The Card API already returns everything required.

Do not call AI or Stanza from the frontend.

## 5. Word Matching — Important

**Do not assume frontend tokenization is identical to backend tokenization.**

In particular, do not assume:

```javascript
line.morphology[tokenIndex]
```

is the correct morphological result.

Instead, search the morphology array by the clicked Latin word's surface spelling.

Example:

```javascript
function normalizeLatinWord(word) {
  return word
    .normalize('NFC')
    .trim()
    .replace(/^[^\p{L}]+|[^\p{L}]+$/gu, '')
    .toLocaleLowerCase();
}

function findMorphology(line, clickedWord) {
  if (!Array.isArray(line.morphology)) {
    return null;
  }

  const target = normalizeLatinWord(clickedWord);

  if (!target) {
    return null;
  }

  const matches = line.morphology.filter(
    item =>
      item &&
      typeof item.word === 'string' &&
      normalizeLatinWord(item.word) === target
  );

  if (matches.length === 0) {
    return null;
  }

  // Do not arbitrarily choose between ambiguous matches.
  if (matches.length > 1) {
    return null;
  }

  const parse = matches[0].parse;

  return typeof parse === 'string' && parse.trim()
    ? parse
    : null;
}
```

### Matching rules

- Search only within the clicked word's Latin line.
- Match by normalized surface spelling, not lemma.
- Ignore leading and trailing punctuation.
- Ignore case.
- Normalize Unicode.
- Do not use approximate or fuzzy matching.
- Do not use substring matching.
- Do not guess when there is no exact normalized match.

### Repeated Words

A Latin line may contain the same surface word more than once.

For example:

`et ... et ...`

Two occurrences may have different contextual analyses.

Because morphology entries preserve their original order, use occurrence-based disambiguation:

- Determine which occurrence of the normalized word was clicked within the displayed Latin line.
- Find matching morphology entries with the same normalized word.
- Select the corresponding occurrence in the morphology array.
- Do not rely on absolute token indices.
- If the occurrence cannot be determined reliably, show morphology unavailable rather than displaying a potentially incorrect parse.

Example:

```text
Displayed Latin:
et ... et ...

Morphology entries:
et → conjunction
et → conjunction

Clicking the second "et" should select the second matching entry.
```

This is occurrence-based matching, not an assumption that frontend and backend tokenization are identical.

## 6. Parse Panel

Keep the existing bottom pane and overall page layout.

In Latin mode, when a word is selected and a parse is available, display:

```text
MORPHOLOGICAL PARSE

virumque

vir | NOUN | Case=Acc, Number=Sing, Gender=Masc;
que | CCONJ
```

The parse text should preserve the original free-text content.

Use CSS such as `white-space: pre-wrap` if necessary.

Do not parse the free-text morphology into separate UI fields.

When no parse is available:

```text
virumque

Morphological analysis unavailable.
```

When no word is selected:

```text
Select a Latin word to view its morphological analysis.
```

In English mode, preserve the existing explanation placeholder.

Do not modify the application's primary reading layout.

## 7. Svelte 5 Implementation

Use modern Svelte 5 syntax and existing component conventions.

Likely affected components:

- `App.svelte`
- `CardReader.svelte`
- `LatinText.svelte`
- `LatinWord.svelte`
- `ParsePanel.svelte`
- `api.js` if necessary

Do not rewrite components unnecessarily.

Use a clear selection object containing:

- Selected word surface text.
- Selected line ID.
- Selected morphology parse string, if available.

Keep the lookup logic centralized rather than duplicating it across components.

No new frontend dependencies are necessary.

## 8. Error Handling

Handle these cases gracefully:

- Card has no morphology data.
- Only some lines have morphology.
- A word is absent from the morphology array.
- An entry has an empty parse string.
- The clicked word includes punctuation.
- The same word occurs multiple times within a line.
- Unicode normalization differences.
- Invalid or malformed morphology JSON.

Do not crash the reading interface because of missing or malformed morphology.

Continue displaying the original Latin text normally.

## 9. Testing

Add focused tests for both backend and frontend.

Backend tests:

1. A Card whose lines all have morphology.
2. A Card with partially populated morphology.
3. A Card with no morphology.
4. Individual Line API morphology retrieval.
5. Existing API fields remain unchanged.
6. Existing navigation remains unchanged.

Frontend tests:

1. Click a word with a matching parse.
2. Click a word when morphology is null.
3. Click a word not found in morphology.
4. Click words with punctuation.
5. Click the second occurrence of a repeated word.
6. Navigate to another Card and confirm selection resets.
7. Switch English/Latin modes.
8. Handle an empty parse string.

Use test fixtures or an isolated database. Do not erase existing production data.

## 10. Scope Restrictions

Do not:

- Implement Stanza parsing.
- Call OpenAI.
- Implement Latin–English word alignment.
- Change the interlinear gloss generation API.
- Modify original Latin text.
- Change the meaning of existing annotation records.
- Add new database tables unless strictly necessary.
- Introduce a new tokenization dependency.
- Change the Flask URL structure.

## 11. Completion Criteria

The task is complete when:

1. `GET /api/cards/{id}` returns morphology per Latin line.
2. Missing morphology is represented by `null`.
3. `GET /api/lines/{id}` also returns morphology.
4. The Svelte frontend can display a word's free-text parse when clicked.
5. Word matching does not depend on identical frontend/backend token indices.
6. Repeated words are handled through occurrence-based matching.
7. Missing or ambiguous matches fail gracefully.
8. Existing English reading, Latin reading, navigation, and page layout continue working.
9. The frontend builds successfully with `npm run build`.
10. Existing backend tests and new morphology tests pass.

Keep the solution simple, robust, and consistent with the current codebase.
