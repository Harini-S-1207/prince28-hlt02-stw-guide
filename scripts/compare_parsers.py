"""Compare two parsers on selected difficult files and record the results."""

import json
import re
import sys
import time
from pathlib import Path

from stw_guide.ingest.parse import (
    ParseError,
    finish,
    headings_in,
    parse_file,
    split_pages,
)

MANIFEST = Path("data/manifest.jsonl")
NOTES = Path("NOTES.md")

START = "<!-- parsers:start -->"
END = "<!-- parsers:end -->"


def strip_tags(path: Path):
    """Naive HTML parser: remove tags and retain visible text."""
    html = path.read_text(encoding="utf-8", errors="replace")
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return finish("strip-tags", "html", "", split_pages(text))


def measure(parser, path: Path) -> dict:
    """Measure parser output, quality indicators and execution time."""
    started = time.perf_counter()

    try:
        doc = parser(path)
    except ParseError as error:
        return {
            "ok": False,
            "note": error.reason,
            "seconds": time.perf_counter() - started,
        }

    text = "\n".join(page.text for page in doc.pages)

    return {
        "ok": True,
        "pages": len(doc.pages),
        "chars": len(text),
        "headings": len(headings_in(text)[0]),
        "tables": sum(page.tables for page in doc.pages),
        "seconds": time.perf_counter() - started,
    }


def pick_files() -> list[Path]:
    """Select the ten largest available PDF and HTML files."""
    records = [
        json.loads(line)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    files = {
        record["path"]: record.get("bytes", 0)
        for record in records
        if record.get("status") == "downloaded"
    }

    existing = [path for path in files if Path(path).is_file()]

    rich = [
        path
        for path in existing
        if Path(path).suffix.lower() in {".pdf", ".html", ".htm"}
    ]

    selected = sorted(
        rich or existing,
        key=lambda path: -files[path],
    )[:10]

    return [Path(path) for path in selected]


def cells(result: dict | None) -> str:
    if result is None:
        return "-"

    if not result["ok"]:
        return f"FAILED: {result['note']}"

    return (
        f"{result['chars']:,} chars, "
        f"{result['headings']} headings, "
        f"{result['tables']} tables"
    )


def main() -> int:
    sys.stdout.reconfigure(errors="replace")

    files = [Path(arg) for arg in sys.argv[1:]] or pick_files()

    if not files:
        print("No suitable downloaded files found.")
        return 1

    rows = []

    for path in files:
        if not path.is_file():
            print(f"Missing file: {path}")
            continue

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            first = measure(parse_file, path)
            second = measure(
                lambda p: parse_file(p, pdf_parser="pypdf"),
                path,
            )
            names = "PyMuPDF / pypdf"

        elif suffix in {".html", ".htm"}:
            first = measure(parse_file, path)
            second = measure(strip_tags, path)
            names = "trafilatura / strip tags"

        else:
            first = measure(parse_file, path)
            second = None
            names = "plain (check by eye)"

        pages = first.get("pages", "-")
        speed = f"{first['seconds']:.2f} s"

        if second:
            speed += f" / {second['seconds']:.2f} s"

        row = (
            f"| {path.name[:48]} | {names} | {pages} | "
            f"{cells(first)} | {cells(second)} | {speed} | |"
        )

        rows.append(row)
        print(row)

    if not rows:
        print("No files could be compared.")
        return 1

    table = "\n".join(
        [
            START,
            "| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |",
            "|---|---|---|---|---|---|---|",
            *rows,
            END,
        ]
    )

    existing = NOTES.read_text(encoding="utf-8") if NOTES.exists() else "# Notes\n"

    if START in existing and END in existing:
        before = existing[: existing.index(START)]
        after = existing[existing.index(END) + len(END) :]
        updated = before + table + after
    else:
        updated = (
            existing.rstrip()
            + "\n\n## Milestone 5 — Parser comparison\n\n"
            + table
            + "\n"
        )

    NOTES.write_text(updated, encoding="utf-8")

    print(f"compared {len(rows)} files -> table written to NOTES.md")
    print("Fill in the final column after manual inspection.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
