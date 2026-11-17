"""Load and manage STW document records."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RecordStore:
    """Store and retrieve STW records."""

    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.records: list[dict[str, Any]] = []

    def load(self) -> None:
        """Load records from the JSON file."""
        try:
            with self.data_file.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                raise TypeError("Records file must contain a JSON list")

            self.records = data

            logger.info(
                "records loaded",
                extra={"records": len(self.records)},
            )

        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            logger.exception("could not load records")
            self.records = []
            raise

    def list_records(self) -> list[dict[str, Any]]:
        """Return all records."""
        return self.records

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        """Find a record using its ID."""
        for record in self.records:
            if record.get("id") == record_id:
                return record

        return None
