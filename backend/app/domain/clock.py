"""A single indirection point for "now" so integration tests can freeze
time by monkeypatching `now` here, instead of every call site importing
`datetime.now` directly."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
