"""Evaluate the quality of extracted document pages."""

from dataclasses import dataclass, field

from stw_guide.ingest.parse import ParsedDoc, headings_in

KNOWN_BOILERPLATE_TEXT = {"stw.icmr.org.in"}


def is_known_boilerplate(text: str) -> bool:
    """Identify verified non-content markers in the current corpus."""
    normalized = text.strip()

    if normalized.startswith("# "):
        normalized = normalized[2:].strip()

    return normalized.casefold() in KNOWN_BOILERPLATE_TEXT


@dataclass
class QualityReport:
    """Measurable quality results for one parsed document."""

    total_pages: int
    empty_pages: list[int]
    short_pages: list[int]
    boilerplate_pages: list[int]
    total_characters: int
    heading_count: int
    pages_with_headings: int
    pages_with_heading_context: int
    table_count: int
    warnings: list[str] = field(default_factory=list)

    @property
    def heading_coverage(self) -> float:
        """Percentage of pages containing explicit headings."""
        if self.total_pages == 0:
            return 0.0
        return round(self.pages_with_headings / self.total_pages * 100, 2)

    @property
    def status(self) -> str:
        """Return passed when no quality warnings need review."""
        return "review" if self.warnings else "passed"


def evaluate_quality(
    document: ParsedDoc,
    min_page_chars: int = 50,
) -> QualityReport:
    """Evaluate page-level text, heading, and table extraction quality."""
    if min_page_chars < 0:
        raise ValueError("min_page_chars cannot be negative")

    empty_pages = []
    short_pages = []
    boilerplate_pages = []
    total_characters = 0
    heading_count = 0
    pages_with_headings = 0
    pages_with_heading_context = 0
    table_count = 0

    for page in document.pages:
        text = page.text.strip()
        char_count = len(text)

        total_characters += char_count
        table_count += page.tables

        found, _ = headings_in(page.text)
        heading_count += len(found)

        if found:
            pages_with_headings += 1

        if page.headings:
            pages_with_heading_context += 1

        if not text:
            empty_pages.append(page.page_no)
        elif is_known_boilerplate(text):
            boilerplate_pages.append(page.page_no)
        elif char_count < min_page_chars:
            short_pages.append(page.page_no)

    warnings = []

    if not document.pages:
        warnings.append("Document contains no pages")

    if empty_pages:
        warnings.append(f"{len(empty_pages)} empty page(s) detected")

    if short_pages:
        warnings.append(
            f"{len(short_pages)} page(s) contain fewer than {min_page_chars} characters"
        )

    return QualityReport(
        total_pages=len(document.pages),
        empty_pages=empty_pages,
        short_pages=short_pages,
        boilerplate_pages=boilerplate_pages,
        total_characters=total_characters,
        heading_count=heading_count,
        pages_with_headings=pages_with_headings,
        pages_with_heading_context=pages_with_heading_context,
        table_count=table_count,
        warnings=warnings,
    )
