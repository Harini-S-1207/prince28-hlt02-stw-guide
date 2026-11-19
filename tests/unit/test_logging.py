import json
import logging

from stw_guide.logging_setup import JSONFormatter, configure_logging


def make_record(message="Test message"):
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_formatter_basic_fields():
    formatter = JSONFormatter()
    record = make_record()

    result = json.loads(formatter.format(record))

    assert result["level"] == "INFO"
    assert result["msg"] == "Test message"
    assert "timestamp" in result
    assert "request_id" not in result
    assert "records" not in result
    assert "exception" not in result


def test_json_formatter_includes_request_id_and_records():
    formatter = JSONFormatter()
    record = make_record()

    record.request_id = "request-123"
    record.records = 20

    result = json.loads(formatter.format(record))

    assert result["request_id"] == "request-123"
    assert result["records"] == 20


def test_json_formatter_includes_exception():
    formatter = JSONFormatter()

    try:
        raise ValueError("Test exception")
    except ValueError:
        import sys

        record = make_record()
        record.exc_info = sys.exc_info()

    result = json.loads(formatter.format(record))

    assert "exception" in result
    assert "ValueError: Test exception" in result["exception"]


def test_configure_logging_replaces_handlers_and_sets_level():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level

    try:
        configure_logging("DEBUG")

        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    finally:
        root.handlers.clear()
        root.handlers.extend(original_handlers)
        root.setLevel(original_level)
