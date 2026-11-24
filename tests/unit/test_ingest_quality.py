"""Tests for document extraction quality evaluation."""

import pytest

from stw_guide.ingest.parse import ParsedDoc, ParsedPage
from stw_guide.ingest.quality import evaluate_quality


def make_document(pages):
    return ParsedDoc(
        parser="pymupdf",
        kind="pdf",
        title="Test document",
        pages=pages,
    )


def test_quality_report_for_healthy_document():
    document = make_document(
        [
            ParsedPage(
                1,
                "# Introduction\n" + "A" * 100,
                headings=["Introduction"],
                tables=1,
            ),
            ParsedPage(
                2,
                "## Treatment\n" + "B" * 120,
                headings=["Introduction", "Treatment"],
            ),
        ]
    )

    report = evaluate_quality(document)

    assert report.total_pages == 2
    assert report.empty_pages == []
    assert report.short_pages == []
    assert report.boilerplate_pages == []
    assert report.total_characters == 220 + len("# Introduction\n") + len(
        "## Treatment\n"
    )
    assert report.heading_count == 2
    assert report.pages_with_headings == 2
    assert report.pages_with_heading_context == 2
    assert report.heading_coverage == 100.0
    assert report.table_count == 1
    assert report.warnings == []
    assert report.status == "passed"


def test_quality_report_detects_empty_pages():
    document = make_document(
        [
            ParsedPage(1, "A" * 100),
            ParsedPage(2, ""),
            ParsedPage(3, "B" * 100),
        ]
    )

    report = evaluate_quality(document)

    assert report.empty_pages == [2]
    assert "1 empty page(s) detected" in report.warnings
    assert report.status == "review"


def test_quality_report_detects_short_pages():
    document = make_document(
        [
            ParsedPage(1, "A" * 100),
            ParsedPage(2, "Short text"),
        ]
    )

    report = evaluate_quality(document)

    assert report.short_pages == [2]
    assert report.boilerplate_pages == []
    assert "1 page(s) contain fewer than 50 characters" in report.warnings


def test_empty_page_is_not_also_counted_as_short():
    document = make_document([ParsedPage(1, "")])

    report = evaluate_quality(document)

    assert report.empty_pages == [1]
    assert report.short_pages == []
    assert report.boilerplate_pages == []


def test_heading_count_and_context_are_distinguished():
    document = make_document(
        [
            ParsedPage(1, "# Introduction\n" + "A" * 100),
            ParsedPage(2, "B" * 100, headings=["Introduction"]),
            ParsedPage(
                3,
                "## Treatment\n" + "C" * 100,
                headings=["Introduction"],
            ),
            ParsedPage(4, "D" * 100, headings=["Introduction", "Treatment"]),
        ]
    )

    report = evaluate_quality(document)

    assert report.heading_count == 2
    assert report.pages_with_headings == 2
    assert report.pages_with_heading_context == 3
    assert report.heading_coverage == 50.0


def test_document_without_pages_needs_review():
    document = make_document([])

    report = evaluate_quality(document)

    assert report.total_pages == 0
    assert report.heading_coverage == 0.0
    assert report.warnings == ["Document contains no pages"]
    assert report.status == "review"


def test_custom_minimum_page_characters():
    document = make_document([ParsedPage(1, "A" * 75)])

    report = evaluate_quality(document, min_page_chars=100)

    assert report.short_pages == [1]


def test_negative_minimum_page_characters_is_rejected():
    document = make_document([ParsedPage(1, "Some content")])

    with pytest.raises(ValueError, match="cannot be negative"):
        evaluate_quality(document, min_page_chars=-1)


def test_known_icmr_website_marker_is_boilerplate():
    document = make_document([ParsedPage(2, "# stw.icmr.org.in")])

    report = evaluate_quality(document)

    assert report.boilerplate_pages == [2]
    assert report.short_pages == []
    assert report.empty_pages == []
    assert report.warnings == []
    assert report.status == "passed"


def test_unrecognized_short_page_still_needs_review():
    document = make_document([ParsedPage(2, "Important clinical information")])

    report = evaluate_quality(document)

    assert report.boilerplate_pages == []
    assert report.short_pages == [2]
    assert report.status == "review"
