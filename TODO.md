# Task: Build a Svelte 5 Frontend for an Aeneid Reader

Build a clean, minimal, responsive frontend for reading Virgil's *Aeneid*, using **Svelte 5 + Vite + JavaScript**.

The backend already exists and is implemented in Flask with SQLite and SQLAlchemy. Do not modify the backend, database models, or import scripts.

The frontend must use the existing REST APIs.

## 1. Technology

- Svelte 5, using modern runes (`$state`, `$derived`, `$effect`) where appropriate.
- Vite for development and building.
- Plain JavaScript, not TypeScript.
- Plain CSS. No Tailwind, Bootstrap, or component libraries.
- No SvelteKit.
- No routing library.
- Use native `fetch()` for API requests.
- Keep dependencies minimal.

Create the frontend in `./frontend/`.

Build output must go to `./static/`, where Flask serves the compiled application.

Configure Vite with:

- `base: '/static/'`
- `build.outDir: '../static'`
- `build.emptyOutDir: true`
- Development proxy `/api` to `http://127.0.0.1:5000`

The Flask server redirects `/` to `/static/index.html`.

## 2. Overall Page Layout

The application occupies the entire browser viewport.

There are three main regions:

```text
+-------------------------------------------------------+
| AENEID                               English | Latin  |
+-------------------------------------------------------+
|                                                       |
|                                                       |
|                   MAIN TEXT                           |
|                                                       |
|               (English or Latin)                      |
|                                                       |
|                                                       |
|                                                       |
+-------------------------------------------------------+
|                                                       |
|                PARSE / EXPLANATION                    |
|                                                       |
+-------------------------------------------------------+
```

### A. Title Pane (Top)

A very narrow horizontal header, approximately 40–48 px tall.

Left side:

- Application title: "Aeneid"
- Current location: "Book I · Lines 1–7"

Right side:

- A compact two-option mode switch: `English | Latin`
- The selected mode should be clearly indicated.
- Default mode is English.

Keep the title pane minimal. No large logo, banner, or decorative elements.

### B. Main Text Pane (Upper Area)

This is the primary reading area.

It occupies approximately 70–75% of the available vertical space below the title pane.

The remaining space is reserved for the lower explanation pane.

The main text pane must scroll independently when the passage is long.

#### English Mode

Display the entire English translation of the current Card.

- Use the `english` field from the Card API.
- Preserve the original line breaks.
- Use elegant, readable typography suitable for classical literature.
- Prefer a serif font.
- Comfortable font size and line spacing.
- Center the text column horizontally, with a maximum width of approximately 800 px.
- Text itself should be left-aligned.
- No word-level interaction is required in English mode.

#### Latin Mode

Display the corresponding Latin verse lines from `card.lines`.

- Each Latin verse line appears on its own line.
- Preserve Latin punctuation and original line breaks.
- Display Latin line numbers subtly in the margin.
- Use a serif font consistent with English mode.
- Every Latin word should be rendered as a separate token element, ready for future clicking.

Latin word parsing is NOT implemented yet.

However, prepare the component structure so each word can eventually support:

- Clicking to select a word.
- Morphological parsing.
- Lemma and part of speech.
- English gloss.
- Grammatical explanations.

For now, a clicked word may simply become visually selected, or word clicking may remain disabled.

Do not generate artificial morphological data.

### C. Parse / Explanation Pane (Bottom)

A persistent panel occupying approximately 25–30% of the available space below the title pane.

It should remain visible while the main text scrolls.

Separate it from the main text pane with a subtle horizontal divider.

In English mode:

Show a placeholder:

"English passage explanation will appear here."

In Latin mode:

Show a placeholder:

"Select a Latin word to view its morphological analysis."

If word selection is implemented as a UI-only interaction, show the selected word and a message indicating that parsing is not yet available.

Do not call any AI APIs.

The panel should be able to display richer content later, but do not implement that content now.

## 3. Navigation

Reading is organized by **Card**, not by individual lines.

Each Card contains an English passage and its corresponding Latin line range.

Provide Previous and Next navigation controls.

Navigation should be compact and unobtrusive.

Place Previous / Next controls near the main text area, preferably in a small navigation row above or below the passage.

The layout should not require scrolling the entire page to navigate.

The backend already supplies `prev` and `next` as Card IDs.

- `prev === null`: disable Previous.
- `next === null`: disable Next.
- Clicking either loads the corresponding Card via `/api/cards/{id}`.
- Preserve the currently selected language mode when navigating.
- Reset the selected Latin word when the Card changes.
- Scroll the main text pane to the top when the Card changes.

Do not assume Card IDs are consecutive.

## 4. Backend API

The Flask server exposes the following endpoints.

All API endpoints are under `/api/`.

### GET /api/health

Check backend/database availability.

Example:

```json
{
  "status": "ok",
  "database": "connected"
}
```

### GET /api/works

List available literary works.

Example:

```json
{
  "works": [
    {
      "id": 1,
      "title": "Aeneid",
      "author": "Publius Vergilius Maro",
      "cts_urn": "urn:cts:latinLit:phi0690.phi003"
    }
  ]
}
```

### GET /api/works/{work_id}

Get a work and its Book directory.

Example:

```json
{
  "id": 1,
  "title": "Aeneid",
  "author": "Publius Vergilius Maro",
  "cts_urn": "urn:cts:latinLit:phi0690.phi003",
  "books": [
    {
      "number": 1,
      "line_count": 756,
      "card_count": 100,
      "first_card_id": 1
    }
  ]
}
```

The card count is illustrative; use actual API data.

Use `first_card_id` to identify the initial Card.

Do not hardcode Card IDs if they can be obtained through the API.

### GET /api/works/{work_id}/books/{book}/cards

Returns a lightweight Card directory for a Book.

Example:

```json
{
  "work_id": 1,
  "book": 1,
  "cards": [
    {
      "id": 1,
      "number": 1,
      "latin_start": 1,
      "latin_end": 7
    },
    {
      "id": 2,
      "number": 8,
      "latin_start": 8,
      "latin_end": 11
    }
  ]
}
```

A full card selection interface is not necessary for the first version, but organize the frontend so a Book/Card navigator can be added later.

### GET /api/cards/{card_id}

**This is the primary API for the reading interface.**

Returns the full Card, English translation, corresponding Latin lines, existing annotations, and navigation IDs.

Example:

```json
{
  "id": 1,
  "work_id": 1,
  "book": 1,
  "number": 1,
  "latin_start": 1,
  "latin_end": 7,
  "english": "Arms and the man I sing...\n...",
  "lines": [
    {
      "id": 1,
      "number": 1,
      "latin": "Arma virumque cano, Troiae qui primus ab oris",
      "annotation": null
    },
    {
      "id": 2,
      "number": 2,
      "latin": "Italiam, fato profugus, Laviniaque venit",
      "annotation": null
    }
  ],
  "prev": null,
  "next": 2
}
```

Important:

- `prev` and `next` are integer Card IDs or `null`.
- Navigation can cross Book boundaries.
- Never calculate adjacent Card IDs yourself.
- The `english` field is an entire translated passage.
- `lines` contains the corresponding Latin verse lines.
- Some lines may contain an `annotation` object in the future.
- Currently, annotations are generally `null`.

### GET /api/lines/{line_id}

Returns an individual Latin line.

Example:

```json
{
  "id": 1,
  "work_id": 1,
  "book": 1,
  "number": 1,
  "latin": "Arma virumque cano, Troiae qui primus ab oris",
  "annotation": null
}
```

This endpoint is available but is not needed for normal Card reading because `/api/cards/{id}` already returns the relevant lines.

## 5. Latin–English Alignment Placeholder

The database currently does not contain word-level alignment between Latin and English.

Do NOT implement automatic alignment.

Do NOT call an LLM to produce alignment.

However, design the frontend so this can be added later.

Create a clear placeholder interface or component, for example:

`AlignmentLayer.svelte`

Its future responsibility will be to associate Latin tokens with English words or phrases.

For now:

- It may render nothing.
- It should not affect layout.
- It should not invent alignment information.
- Include brief comments documenting where alignment data will be integrated.

Keep alignment logic separate from morphological parsing.

## 6. Suggested Component Structure

```text
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js
    ├── App.svelte
    ├── app.css
    ├── api.js
    └── components/
        ├── TitlePane.svelte
        ├── CardReader.svelte
        ├── EnglishText.svelte
        ├── LatinText.svelte
        ├── LatinWord.svelte
        ├── ParsePanel.svelte
        └── AlignmentLayer.svelte
```

This is a suggested organization. Adjust if necessary, but avoid unnecessary abstraction.

Responsibilities:

- `App.svelte`: Card loading, navigation, selected language mode, selected Latin word.
- `TitlePane.svelte`: Narrow title bar and language mode switch.
- `CardReader.svelte`: Main text area and Card navigation.
- `EnglishText.svelte`: English passage rendering.
- `LatinText.svelte`: Latin lines and tokenization for display.
- `LatinWord.svelte`: Individual Latin token, future selection/parsing.
- `ParsePanel.svelte`: Bottom explanation pane.
- `AlignmentLayer.svelte`: Placeholder for future Latin–English alignment.
- `api.js`: Centralized API requests.

## 7. Visual Style

The application should feel like a serious scholarly reading tool, not a dashboard.

Design principles:

- Minimalist.
- Quiet, distraction-free interface.
- Light background, dark text.
- Excellent typography.
- Comfortable reading margins.
- Subtle borders and dividers.
- No colorful cards or decorative gradients.
- No unnecessary shadows or animations.
- No icons unless they serve a clear purpose.
- Use available system fonts; do not require external font services.

The English and Latin text should be the visual focus.

The title pane must remain narrow.

The bottom parse panel must remain visible.

Use responsive CSS so the application works on desktop and mobile.

On desktop, keep the vertical split layout.

On mobile, the parse panel may become shorter, but should remain accessible.

## 8. Implementation Details

- Use modern Svelte 5 syntax.
- Avoid deprecated Svelte patterns.
- Use asynchronous API loading.
- Show a simple loading indicator during Card fetching.
- Handle failed API requests gracefully with a retry option.
- Ensure rapid Previous/Next clicks cannot cause older requests to overwrite newer responses.
- Preserve English/Latin mode when switching Cards.
- Use semantic HTML and accessible buttons.
- Do not use `{@html}` to render database text.
- Render the English passage as plain text, preserving line breaks with CSS (`white-space: pre-line` or equivalent).
- Preserve Latin punctuation accurately when splitting into clickable tokens; do not alter the visible Latin text.
- No authentication.
- No local persistence required.
- No AI integration at this stage.

## 9. Development and Build

The existing Flask application serves compiled files at `/static/`.

Vite must proxy `/api` to Flask during development.

Expected commands:

```bash
cd frontend
npm install
npm run dev
```

For production build:

```bash
cd frontend
npm run build
```

The build must generate:

```text
static/
├── index.html
└── assets/
```

The Flask application must then serve the frontend at:

`http://127.0.0.1:5000/`

Do not modify `server.py`.

## 10. Completion Criteria

Implement the frontend fully, not merely a mockup.

The completed frontend must:

1. Load a real Card from the Flask API.
2. Display the English translation by default.
3. Switch between English and Latin modes.
4. Display the corresponding Latin verse lines with line numbers.
5. Navigate Previous/Next using the IDs supplied by the backend.
6. Keep the narrow title pane and bottom parse/explanation pane visible.
7. Include placeholders for morphological parsing and Latin–English word alignment.
8. Handle loading, errors, and missing navigation gracefully.
9. Build successfully with `npm run build`.
10. Work without any AI calls or backend modifications.

Inspect the existing repository and API implementation before writing code. Follow the actual backend response structure rather than assuming the example values are exact.

Keep the implementation small, readable, and easy to extend.
