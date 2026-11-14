#!/usr/bin/env python3
"""Generate and cache Book One glosses in card order.

Each card is processed separately, in batches of at most 30 lines within it.

Run: python generate_book_one_gloss.py
Existing valid glosses are reused by the server, so interrupted runs can be rerun.
Requires only the Python standard library; start server.py separately.
"""

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(base_url, path, timeout, retries, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            message = f"{path}: HTTP {exc.code}: {detail}"
            retryable = exc.code == 429 or exc.code >= 500
        except (URLError, TimeoutError, OSError) as exc:
            message = f"{path}: {exc}"
            retryable = True
        if not retryable or attempt == retries:
            raise RuntimeError(message)
        delay = min(2 ** (attempt + 1), 30)
        print(f"{message}\nRetrying in {delay}s…", file=sys.stderr, flush=True)
        time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5000")
    parser.add_argument("--work-id", type=int, help="Default: discover the Aeneid")
    parser.add_argument("--timeout", type=float, default=600, help="Seconds per request (default: 600)")
    parser.add_argument("--retries", type=int, default=2, help="Retries per failed request (default: 2)")
    args = parser.parse_args()
    if args.timeout <= 0 or args.retries < 0:
        parser.error("--timeout must be positive and --retries nonnegative")
    if args.work_id is not None and args.work_id < 1:
        parser.error("--work-id must be positive")

    def api(path, payload=None):
        return request_json(args.base_url, path, args.timeout, args.retries, payload)

    work_id = args.work_id
    if work_id is None:
        works = api("/api/works")["works"]
        matches = [work for work in works if "aeneid" in work["title"].lower()]
        if len(matches) != 1:
            raise RuntimeError("Could not identify a unique Aeneid work; specify --work-id.")
        work_id = matches[0]["id"]
    work = api(f"/api/works/{work_id}")
    book = next((book for book in work["books"] if book["number"] == 1), None)
    if book is None or book["line_count"] < 1:
        raise RuntimeError("Book One has no Latin lines.")
    cards = api(f"/api/works/{work_id}/books/1/cards")["cards"]
    cards = sorted(cards, key=lambda card: (card["number"], card["id"]))
    if not cards:
        raise RuntimeError("Book One has no cards.")
    total = len(cards)
    print(f"{work['title']}, Book One: {total} cards at {args.base_url}", flush=True)
    generated = cached = 0
    for index, card in enumerate(cards, 1):
        card_generated = card_cached = 0
        for start in range(card["latin_start"], card["latin_end"] + 1, 30):
            end = min(start + 29, card["latin_end"])
            print(f"Generating card {card['number']} ({index}/{total}), lines {start}–{end}…", flush=True)
            result = api("/api/gloss", {"work_id": work_id, "book": 1, "start": start, "end": end})
            lines = result["lines"]
            if [line["number"] for line in lines] != list(range(start, end + 1)):
                raise RuntimeError(f"Server returned incomplete lines for {start}–{end}.")
            reused = sum(bool(line["cached"]) for line in lines)
            card_cached += reused
            card_generated += len(lines) - reused
        cached += card_cached
        generated += card_generated
        print(f"Completed card {index}/{total}: {card_generated} generated, {card_cached} cached", flush=True)
    print(f"Done: {generated} generated, {cached} cached. Glosses are saved by the server.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Rerun to resume using cached glosses.", file=sys.stderr)
        sys.exit(130)
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
