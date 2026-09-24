"""Turns a model's grounded answer into what the UI shows: only citations of
retrieved articles survive, and markers are renumbered [1], [2], ... to
match the returned sources list. Pure function, unit-tested."""

import re

# "[12]", and grouped forms the model sometimes emits: "[12, 7]", "[12; 7]".
_MARKER_RE = re.compile(r"\s*\[(\d+(?:\s*[,;]\s*\d+)*)\]")


def ground_citations(
    answer: str, cited_ids: list[int], retrieved_ids: list[int]
) -> tuple[str | None, list[int]]:
    """The model cites articles by id, `[12]`. Returns (answer with markers
    renumbered to 1-based positions in the returned id list, source ids in
    first-citation order). Markers and cited ids outside the retrieved set
    are dropped. An answer left with no valid citation isn't grounded, so it
    becomes (None, [])."""
    if not answer.strip():
        return None, []

    retrieved = set(retrieved_ids)
    sources: list[int] = []

    def renumber(match: re.Match) -> str:
        ids = [int(n) for n in re.split(r"\s*[,;]\s*", match.group(1))]
        numbers: list[int] = []
        for article_id in ids:
            if article_id not in retrieved:
                continue
            if article_id not in sources:
                sources.append(article_id)
            number = sources.index(article_id) + 1
            if number not in numbers:
                numbers.append(number)
        return "".join(f" [{n}]" for n in numbers)

    text = _MARKER_RE.sub(renumber, answer).strip()

    for article_id in cited_ids:
        if article_id in retrieved and article_id not in sources:
            sources.append(article_id)

    if not sources:
        return None, []
    return text, sources
