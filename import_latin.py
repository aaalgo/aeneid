#!/usr/bin/env python3
"""
Import Virgil's Aeneid Latin text from Perseus TEI XML.

Each Latin verse line is stored as one Line record.

Safe to rerun:
- Existing identical lines are skipped.
- Existing AI annotations are preserved.
- Changed source text raises an error.
"""

from pathlib import Path
import re

from lxml import etree
from sqlalchemy import select

from models import (
    Base,
    Work,
    Line,
    SessionLocal,
    engine,
)


ROOT = Path(__file__).resolve().parent
LATIN_FILE = (
    ROOT / "data" / "phi0690.phi003.perseus-lat2.xml"
)

CTS_URN = "urn:cts:latinLit:phi0690.phi003"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0"
}


def clean_text(element):
    """
    Extract text from a TEI element, including
    nested markup, and normalize whitespace.
    """
    raw = "".join(element.itertext())
    return re.sub(r"\s+", " ", raw).strip()


def extract_latin(path):
    """
    Parse Perseus TEI XML.

    Returns:
        dict[(book_number, line_number)] = latin_text
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

        lines = book.xpath(
            ".//tei:l[@n]",
            namespaces=NS,
        )

        for element in lines:
            label = element.get("n")
            # Perseus splits some verses at card boundaries (10.62/62b).
            # Keep the fragments together under the original verse number.
            continuation = re.fullmatch(r"([0-9]+)[a-z]+", label)
            line_number = int(continuation.group(1) if continuation else label)
            latin = clean_text(element)

            key = (book_number, line_number)

            if not latin:
                raise ValueError(
                    f"Empty line: Book {book_number}, "
                    f"Line {label}"
                )

            if continuation:
                if element.get("part") not in {"M", "F"} or key not in result:
                    raise ValueError(
                        f"Invalid continuation: Book {book_number}, Line {label}"
                    )
                result[key] += " " + latin
                continue

            if key in result:
                raise ValueError(
                    f"Duplicate line: Book {book_number}, "
                    f"Line {line_number}"
                )

            result[key] = latin

        print(
            f"Book {book_number}: "
            f"{sum(book == book_number for book, _ in result)} lines"
        )

    return result


def import_latin():
    print(f"Reading {LATIN_FILE}")

    latin_lines = extract_latin(LATIN_FILE)

    Base.metadata.create_all(engine)

    with SessionLocal.begin() as session:

        work = session.scalar(
            select(Work).where(
                Work.cts_urn == CTS_URN
            )
        )

        if work is None:
            work = Work(
                title="Aeneid",
                author="Publius Vergilius Maro",
                cts_urn=CTS_URN,
            )
            session.add(work)
            session.flush()

        existing = {
            (line.book, line.number): line
            for line in session.scalars(
                select(Line).where(
                    Line.work_id == work.id
                )
            )
        }

        inserted = 0
        skipped = 0

        for (book, number), latin in sorted(
            latin_lines.items()
        ):
            key = (book, number)

            if key in existing:
                if existing[key].latin != latin:
                    raise ValueError(
                        f"Source mismatch: "
                        f"Book {book}, Line {number}\n"
                        f"Database: {existing[key].latin}\n"
                        f"XML:      {latin}"
                    )

                skipped += 1
                continue

            session.add(
                Line(
                    work_id=work.id,
                    book=book,
                    number=number,
                    latin=latin,
                    english=None,
                )
            )
            inserted += 1

    print()
    print(f"Total Latin lines: {len(latin_lines)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")
    print("Import complete.")


if __name__ == "__main__":
    import_latin()

