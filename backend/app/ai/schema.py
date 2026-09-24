"""Converts a Pydantic model's JSON Schema into the OpenAPI-subset Schema
object Gemini's `generationConfig.responseSchema` accepts (uppercase `type`,
no `$ref`/`title`/`$defs`)."""

from typing import Any

from pydantic import BaseModel

_KEEP = ("description", "enum")


def gemini_response_schema(model: type[BaseModel], *, enums: dict[str, list[str]] | None = None) -> dict:
    """`enums` overrides/sets an enum on top-level string properties, e.g.
    the active category slugs, which are only known at call time."""
    raw = model.model_json_schema()
    schema = _convert(raw, raw.get("$defs", {}))
    for prop, values in (enums or {}).items():
        schema["properties"][prop]["enum"] = values
    return schema


def _convert(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        target = defs[node["$ref"].rsplit("/", 1)[-1]]
        merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        return _convert(merged, defs)

    out: dict[str, Any] = {"type": node["type"].upper()}
    for key in _KEEP:
        if key in node:
            out[key] = node[key]

    if node["type"] == "object":
        props = node.get("properties", {})
        out["properties"] = {name: _convert(sub, defs) for name, sub in props.items()}
        out["required"] = list(node.get("required", []))
        out["propertyOrdering"] = list(props)
    elif node["type"] == "array":
        out["items"] = _convert(node["items"], defs)
    return out
