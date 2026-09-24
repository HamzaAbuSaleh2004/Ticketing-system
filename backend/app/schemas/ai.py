from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import TicketPriority

EmbedTask = Literal["document", "query"]

# Fields an agent can accept/override from a triage suggestion.
TriageField = Literal["category", "priority", "one_line_summary", "suggested_response_draft"]


class TriageSuggestion(BaseModel):
    """Doubles as the Gemini responseSchema (see ai/schema.py); `category`
    gets an enum of the active category slugs injected at call time."""

    category: str = Field(description="Slug of the best-matching category from the allowed list.")
    priority: TicketPriority = Field(description="How urgently support needs to act.")
    one_line_summary: str = Field(
        description="A neutral one-line summary of the problem, under 120 characters."
    )
    suggested_response_draft: str = Field(
        description="A short, polite first reply to the customer. No placeholders, no promises."
    )

    @field_validator("one_line_summary")
    @classmethod
    def _truncate_summary(cls, value: str) -> str:
        # Truncate rather than reject: one over-long summary shouldn't throw
        # away an otherwise good triage for the keyword fallback.
        value = " ".join(value.split())
        return value if len(value) <= 200 else value[:197].rstrip() + "..."


class GroundedAnswer(BaseModel):
    answer: str = Field(
        description="The answer, using only the provided articles, citing them inline by id, e.g. [12]. "
        "Empty string if the articles don't answer the question."
    )
    cited_article_ids: list[int] = Field(
        description="The id of every article cited in the answer. Empty if the answer is empty."
    )


@dataclass(frozen=True)
class CategoryOption:
    slug: str
    name: str


@dataclass(frozen=True)
class KbContext:
    id: int
    title: str
    body: str


@dataclass(frozen=True)
class TriageResult:
    suggestion: TriageSuggestion
    # Which model produced it, e.g. "gemini-3.6-flash", "fake", or
    # "fake-fallback" when Gemini failed and the fake stepped in.
    model: str
