from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

Short = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]

Values = Annotated[list[Short], Field(default_factory=list, max_length=8)]

Kind = Literal[
    "guideline",
    "rule",
    "notice",
    "list",
    "report",
    "faq",
    "form",
    "tutorial",
    "reference",
    "other",
]


class DocMeta(BaseModel):
    """Validated metadata contract for STW Guide documents."""

    model_config = ConfigDict(extra="forbid")

    # Common fields
    doc_kind: Kind
    year: int | None = Field(default=None, ge=1950, le=2027)
    language: Literal["en", "ta", "hi", "other"]
    summary: str = Field(min_length=20, max_length=300)
    topics: Annotated[list[Short], Field(min_length=1, max_length=6)]

    # STW Guide-specific fields
    condition: Values
    specialty: Values
    red_flags: Values
    first_line: Values
    referral_criteria: Values

    @field_validator("topics")
    @classmethod
    def _tidy(cls, value: list[str]) -> list[str]:
        """Lowercase topics and remove duplicates."""
        return list(dict.fromkeys(topic.lower() for topic in value))
