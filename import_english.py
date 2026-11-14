#!/usr/bin/env python3
"""
Import the English translation of Virgil's Aeneid
from Perseus TEI XML.

Translator: Theodore C. Williams (1910)

Each Perseus card becomes one Card database record.

Requirements:
    - models.py
    - aeneid.db
    - Latin lines already imported by import_latin.py

Safe to rerun:
    - Existing cards are updated if necessary.
    - No duplicate cards are created.
    - Latin lines and AI annotations are untouched.
"""

from pathlib import Path
import re

from lxml import etree
from sqlalchemy import select, func

from models import (
    Base,
    Work,
    Card,
    Line,
    SessionLocal,
    engine,
)


ROOT = Path(__file__).resolve().parent

ENGLISH_FILE = (
    ROOT / "data" / "phi0690.phi003.perseus-eng2.xml"
)

CTS_URN = "urn:cts:latinLit:phi0690.phi003"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0"
}


def clean_text(element):
    """
    Extract all text, including nested TEI elements
    such as placeName and persName.
    """
    raw = "".join(element.itertext())
    return re.sub(r"\s+", " ", raw).strip()


def extract_cards(path):
    """
    Parse English TEI XML.

    Returns:
        dict[book_number] = [
            {
                "number": int,
                "english": str,
            },
            ...
        ]
    """
    if not path.is_file():
        raise FileNotFoundError(path)

    tree = etree.parse(str(path))

    books = tree.xpath(
        "//tei:text/tei:body//tei:div"
        "[@subtype='book'][@n]",
        namespaces=NS,
    )

    if len(books) != 12:
        raise ValueError(
            f"Expected 12 books, found {len(books)}"
        )

    result = {}

    for book in books:
        book_number = int(book.get("n"))

        card_elements = book.xpath(
            "./tei:div[@subtype='card'][@n]",
            namespaces=NS,
        )

        cards = []
        seen = set()

        for element in card_elements:
            card_number = int(element.get("n"))

            if card_number in seen:
                raise ValueError(
                    f"Duplicate card: "
                    f"Book {book_number}, Card {card_number}"
                )

            seen.add(card_number)

            # Preserve English verse line breaks.
            english_lines = []

            for line in element.xpath(
                ".//tei:l",
                namespaces=NS,
            ):
                content = clean_text(line)
                if content:
                    english_lines.append(content)

            if not english_lines:
                raise ValueError(
                    f"Empty card: "
                    f"Book {book_number}, Card {card_number}"
                )

            cards.append({
                "number": card_number,
                "english": "\n".join(english_lines),
            })

        cards.sort(key=lambda c: c["number"])

        if not cards:
            raise ValueError(
                f"No cards found in Book {book_number}"
            )

        result[book_number] = cards

        print(
            f"Book {book_number}: {len(cards)} cards"
        )

    if set(result) != set(range(1, 13)):
        raise ValueError("Missing or duplicate book numbers")

    return result


def import_english():
    print(f"Reading {ENGLISH_FILE}")

    english_books = extract_cards(ENGLISH_FILE)

    Base.metadata.create_all(engine)

    inserted = 0
    updated = 0
    skipped = 0

    with SessionLocal.begin() as session:

        # Find the existing Aeneid work.
        work = session.scalar(
            select(Work).where(
                Work.cts_urn == CTS_URN
            )
        )

        if work is None:
            raise RuntimeError(
                "Aeneid not found in database. "
                "Run import_latin.py first."
            )

        # Load Latin line numbers, grouped by book.
        latin_numbers = {
            book: set()
            for book in range(1, 13)
        }

        for book, number in session.execute(
            select(Line.book, Line.number)
            .where(Line.work_id == work.id)
        ):
            latin_numbers[book].add(number)

        # Load existing cards for idempotent import.
        existing = {
            (card.book, card.number): card
            for card in session.scalars(
                select(Card).where(
                    Card.work_id == work.id
                )
            )
        }

        for book_number, cards in sorted(
            english_books.items()
        ):
            numbers = latin_numbers[book_number]

            if not numbers:
                raise ValueError(
                    f"No Latin lines for Book {book_number}"
                )

            last_latin_line = max(numbers)

            for index, item in enumerate(cards):
                start = item["number"]

                if index + 1 < len(cards):
                    end = cards[index + 1]["number"] - 1
                else:
                    end = last_latin_line

                if start > end:
                    raise ValueError(
                        f"Invalid range: "
                        f"Book {book_number}, "
                        f"Lines {start}-{end}"
                    )

                # Ensure all referenced Latin lines exist.
                missing = [
                    n for n in range(start, end + 1)
                    if n not in numbers
                ]

                if missing:
                    raise ValueError(
                        f"Missing Latin lines in "
                        f"Book {book_number}: {missing[:10]}"
                    )

                key = (book_number, item["number"])

                if key in existing:
                    card = existing[key]

                    if (
                        card.latin_start == start
                        and card.latin_end == end
                        and card.english == item["english"]
                    ):
                        skipped += 1
                        continue

                    card.latin_start = start
                    card.latin_end = end
                    card.english = item["english"]

                    updated += 1

                else:
                    session.add(
                        Card(
                            work_id=work.id,
                            book=book_number,
                            number=item["number"],
                            latin_start=start,
                            latin_end=end,
                            english=item["english"],
                        )
                    )
                    inserted += 1

    print()
    print(f"Cards inserted: {inserted}")
    print(f"Cards updated:  {updated}")
    print(f"Cards skipped:  {skipped}")
    print("Import complete.")


if __name__ == "__main__":
    import_english()

