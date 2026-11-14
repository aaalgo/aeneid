
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.types import JSON


DATABASE_URL = f"sqlite:///{Path(__file__).resolve().parent / 'aeneid.db'}"


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Work(Base):
    """
    A literary work, e.g. Virgil's Aeneid.
    """

    __tablename__ = "works"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255))

    cts_urn: Mapped[str | None] = mapped_column(
        String(255), unique=True
    )

    cards: Mapped[list["Card"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
        order_by="(Card.book, Card.number)",
    )

    lines: Mapped[list["Line"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
        order_by="(Line.book, Line.number)",
    )


class Card(Base):
    """
    One English reading unit from Perseus.

    A card contains a passage of English translation
    and identifies the corresponding range of
    Latin verse lines.

    Cards define the UI navigation units.
    """

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id"), nullable=False
    )

    book: Mapped[int] = mapped_column(Integer)

    # Original Perseus XML card @n value.
    number: Mapped[int] = mapped_column(Integer)

    # Corresponding Latin verse range, inclusive.
    latin_start: Mapped[int] = mapped_column(Integer)
    latin_end: Mapped[int] = mapped_column(Integer)

    # Complete English translation of this card.
    english: Mapped[str] = mapped_column(Text)

    work: Mapped["Work"] = relationship(
        back_populates="cards"
    )

    __table_args__ = (
        UniqueConstraint(
            "work_id", "book", "number",
            name="uq_work_book_card",
        ),
    )


class Line(Base):
    """
    One original Latin verse line.

    Lines are independent of cards. AI annotations
    are cached per line rather than per card.
    """

    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id"), nullable=False
    )

    book: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)

    # Original Latin text.
    latin: Mapped[str] = mapped_column(Text)

    # Optional line-level reference translation.
    # Usually NULL for the Williams translation.
    english: Mapped[str | None] = mapped_column(Text)

    work: Mapped["Work"] = relationship(
        back_populates="lines"
    )

    annotation: Mapped["Annotation | None"] = relationship(
        back_populates="line",
        uselist=False,
        cascade="all, delete-orphan",
    )

    interlinear_gloss: Mapped["InterlinearGloss | None"] = relationship(
        back_populates="line",
        uselist=False,
        cascade="all, delete-orphan",
    )

    morphology: Mapped["Morphology | None"] = relationship(
        back_populates="line",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "work_id", "book", "number",
            name="uq_work_book_line",
        ),
    )


class Annotation(Base):
    """
    AI-generated annotation for one Latin verse line.

    Contains word-level English glosses, lemmas,
    morphological parsing, and explanations.

    One annotation per Latin line.
    """

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id"),
        nullable=False,
        unique=True,
    )

    # JSON structure:
    #
    # {
    #   "tokens": [
    #     {
    #       "surface": "Arma",
    #       "lemma": "arma",
    #       "gloss": "arms",
    #       "pos": "noun",
    #       "morph": {
    #         "case": "accusative",
    #         "number": "plural",
    #         "gender": "neuter"
    #       },
    #       "explanation": "Direct object of cano."
    #     }
    #   ]
    # }
    data: Mapped[dict] = mapped_column(JSON)

    # AI model used to generate the annotation.
    model: Mapped[str] = mapped_column(String(100))

    # Version of the annotation prompt.
    prompt_version: Mapped[int] = mapped_column(
        Integer, default=1
    )

    # complete, pending, failed
    status: Mapped[str] = mapped_column(
        String(20), default="complete"
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
        back_populates="annotation"
    )


class InterlinearGloss(Base):
    """Contextual English glosses, independent of morphological annotations."""

    __tablename__ = "interlinear_glosses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id"), nullable=False, unique=True
    )
    data: Mapped[list] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    line: Mapped["Line"] = relationship(back_populates="interlinear_gloss")


class Morphology(Base):
    """Offline morphological analysis for one Latin verse line."""

    __tablename__ = "morphology"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id"), nullable=False, unique=True
    )
    # One {word, parse} object per original Latin word, in source order.
    data: Mapped[list] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="stanza-perseus"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    line: Mapped["Line"] = relationship(back_populates="morphology")


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def init_db():
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DATABASE_URL}")

