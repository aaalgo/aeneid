# Task: Extend Database Schema for Latin Morphological Parsing

We are developing an Aeneid Reader using Flask, SQLAlchemy 2.0, SQLite, and Svelte 5.

The existing project contains:

- `models.py`: SQLAlchemy ORM models.
- `server.py`: Flask REST API.
- `aeneid.db`: Existing SQLite database containing imported Latin and English texts.
- `import_latin.py` and `import_english.py`: Data import scripts.

The database already includes `Work`, `Card`, `Line`, `Annotation`, and possibly `InterlinearGloss`.

## Objective

Extend the existing database schema to store **offline morphological analysis produced by Stanza**.

Stanza will process the Latin text one Card at a time, but results must be stored **one database record per Latin Line**.

Each line contains multiple tokens, and each token may contain one or more Stanza word analyses.

**This task is database schema preparation only. Do not implement morphological computation, API endpoints, or frontend changes.**

## 1. Add a Morphology Model

Add the following SQLAlchemy model to `models.py`, adapting imports and naming conventions to the existing code:

```python
class Morphology(Base):
    __tablename__ = "morphology"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id"),
        nullable=False,
        unique=True,
    )

    data: Mapped[dict] = mapped_column(JSON)

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="stanza-perseus",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    line: Mapped["Line"] = relationship(
        back_populates="morphology"
    )
```

Use `data: Mapped[dict]`, because the intended JSON contains a top-level `tokens` array.

## 2. Add Relationship to Line

Modify the existing `Line` model to include:

```python
morphology: Mapped["Morphology | None"] = relationship(
    back_populates="line",
    uselist=False,
    cascade="all, delete-orphan",
)
```

Do not change the existing relationships between `Work`, `Card`, `Line`, `Annotation`, or `InterlinearGloss`.

## 3. JSON Data Structure

TBD

## 4. Preserve Existing Database

The existing `aeneid.db` contains imported text and possibly AI-generated gloss data.

Do not delete, recreate, or overwrite it.

Use the existing SQLAlchemy engine and session infrastructure.

Ensure:

```python
Base.metadata.create_all(engine)
```

creates the new `morphology` table without modifying existing tables or data.

Do not introduce Alembic or another migration framework for this single additive change.

Do not modify existing columns.

## 5. Compatibility

Preserve all existing functionality.

Specifically:

- Do not modify `server.py`.
- Do not modify the import scripts.
- Do not change existing API response formats.
- Do not change the meaning of `Annotation`.
- Do not merge Morphology with InterlinearGloss.
- Do not change the existing tokenization implementation.
- Do not add dependencies other than those already needed by SQLAlchemy.
- Do not invoke Stanza or OpenAI.

The new model must be importable by future offline processing scripts.

## 6. Verification

After modifying `models.py`:

1. Ensure the module imports successfully.
2. Run the existing `init_db()` or equivalent initialization function.
3. Verify the `morphology` table exists.
4. Verify its `line_id` foreign key references `lines.id`.
5. Verify `line_id` is unique.
6. Verify existing tables and row counts remain unchanged.
7. Verify the `Line.morphology` relationship is correctly configured.
8. Run a minimal insert/read test in a transaction that is rolled back, leaving the database unchanged.

Do not delete or reset the database to perform testing.

## 7. Completion Criteria

The task is complete when:

- `models.py` contains the new `Morphology` model.
- `Line` has a one-to-one relationship with `Morphology`.
- The database contains the new `morphology` table.
- Existing tables and data are preserved.
- Existing Flask and import scripts remain compatible.
- No morphology data has been generated yet.

Keep changes minimal and focused on database schema preparation.
