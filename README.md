# Aeneid Reader

A Latin–English reader for Virgil’s *Aeneid*, built with Flask, SQLAlchemy,
SQLite, and Svelte 5. Read the Latin alongside Theodore C. Williams’s English
translation, navigate all twelve books by passage, and select Latin words to
inspect cached morphological analyses. Word glosses are generated through
OpenAI and cached separately from the original text and morphology.

## Quick start

Use Python 3.10 or newer. Run these commands from the project directory:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python import_latin.py
python import_english.py
cd frontend
npm ci
npm run build
cd ..
python server.py
```

Initial frontend setup requires Node.js 22.12 or newer. Open
<http://127.0.0.1:5000/>. Once the database is imported and the frontend is built,
reading needs neither Node.js, Stanza, nor an API key. Missing glosses
show an error with a retry option; the reading interface remains usable.

The generated `aeneid.db` and `static/` directory are ignored by Git. If they
already exist locally, you can skip the imports and frontend build.

The database always resolves to `aeneid.db` beside `models.py`, even when Python
is launched from another directory. Back it up before importing or recomputing
data. Startup creates missing tables without replacing existing records.

`HOST` and `PORT` override the default `127.0.0.1:5000` binding.
Set `FLASK_DEBUG=1` to enable Flask’s development debugger and reloader locally.
The bundled Flask server is intended for local development.

## Import the source texts

If starting without a local database, import Latin before English:

```sh
python import_latin.py
python import_english.py
```

Both scripts read the bundled Perseus TEI XML files in `data/`. The Latin
import preserves existing identical lines and annotations, and rejects changed
source text. The English import updates or creates passage cards without
duplicating them. A **card** is an English passage linked to an inclusive range
of Latin verse lines; it is the reader’s navigation unit.

## Frontend development

Use Node.js 22.12 or newer. Keep Flask running in one terminal, then run:

```sh
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite (the configured base path is `/static/`). Vite
proxies `/api` requests to Flask at `http://127.0.0.1:5000`.

```sh
npm test
npm run build
```

The build replaces the root `static/` directory with the compiled application,
which Flask serves directly. Rebuild after changing frontend source files.

## Optional word glosses

```sh
python -m pip install -r requirements-gloss.txt
export OPENAI_API_KEY='your-api-key'
# Optional: override the server’s default model, gpt-6.1-sol.
export OPENAI_MODEL='your-model-id'
python server.py
```

Export these variables in the shell that starts Flask; `.env` files are not
loaded automatically. The selected model must support strict JSON schema
structured output with Chat Completions.

Opening a passage automatically requests glosses, including when the Gloss
display toggle is off. Uncached requests send Latin context and the reference
English passage to OpenAI and can incur API charges. Valid cached glosses are
reused without an API call. Requests are batched into at most 30 lines and
completed batches remain cached if a later batch fails.

To precompute Book I with the server running:

```sh
python generate_book_one_gloss.py
```

This command is resumable. See `--help` for the server URL, timeout, work ID,
and retry options.

## Optional offline morphology

Stanza processing is separate from the web server. Install its dependencies
and download the LatinCy model once:

```sh
python -m pip install -r requirements-morphology.txt
python -c "from huggingface_hub import snapshot_download; snapshot_download('latincy/la_stanza_latincy')"
python compute_morphology.py --book 1 --limit 1 --dry-run
./compute_all_morphology.sh
```

The processor loads the model from the local Hugging Face cache without
downloading it. It analyzes whole cards and stores results per Latin line.
Existing complete results are skipped; interrupted runs can be resumed.
Use `--book`, `--card` (database card ID), or `--limit` to narrow the work,
`--dry-run` to analyze without writing, and `--force` to replace cached analyses.
Model execution can require substantial memory and processing time.

`python test_stanza.py` runs a manual model demo and may download model files.
Importing that module during unit test discovery does not run the demo.

## Tests

```sh
python -m unittest discover -v
cd frontend
npm test
npm run build
```

Python tests use temporary or in-memory databases for API and persistence
checks and mocked gloss providers; they need neither OpenAI credentials nor
Stanza models. They cover XML parsing, token alignment, morphology caching,
API reads, gloss validation, retries, and overlapping writes. Frontend tests
check gloss and morphology logic; the production build also compiles Svelte.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Database connectivity |
| `GET /api/works` | Available works |
| `GET /api/works/<id>` | Work details and book directory |
| `GET /api/works/<id>/books/<book>/cards` | Passage directory |
| `GET /api/cards/<id>` | Passage text, Latin lines, morphology, and navigation |
| `GET /api/lines/<id>` | One Latin line and its cached analysis |
| `POST /api/gloss` | Generate or reuse word glosses for an inclusive line range |

Gloss requests take JSON such as
`{"work_id":1,"book":1,"start":1,"end":5}`. Reading endpoints do not generate
analyses. Errors use `{"error":{"code":"…","message":"…"}}` with an HTTP
error status. The API has no authentication; keep deployments with enabled
gloss generation restricted to trusted users.

## Project layout and sources

- `models.py`, `server.py`: database schema and HTTP API.
- `import_latin.py`, `import_english.py`, `data/`: source text importers and XML.
- `compute_morphology.py`: resumable Stanza processing and word alignment.
- `generate_book_one_gloss.py`: batch gloss generation through the API.
- `frontend/src/`, `static/`: Svelte source and compiled application.
- `test_*.py`, `frontend/tests/`: automated checks and the manual Stanza demo.
- `treebank_data/`: optional local reference treebank checkout, ignored by Git
  and not needed by the application.
- `TODO.md`, `MOR.md`, `PARSE.md`, `PROCESS.md`: earlier design and task notes;
  some describe implementation stages rather than current behavior.

The bundled TEI files credit the Perseus Project at Tufts University. The
English translation is Theodore C. Williams (1910). Consult each XML file’s
TEI header for edition, attribution, and availability information. No project
software license is currently declared.
