"""Read and replace SSE data without losing framing or decimal precision."""

import re
from collections.abc import Mapping

import simplejson

from free_claude_code.core.json_types import DecimalJsonObject, DecimalJsonValue

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_LINE_BREAK_KEPT = re.compile(r"(\r\n|\r|\n)")


def frame_lines(frame: str) -> list[str]:
    """Split an SSE frame on any line ending; the common LF-only frame skips regex."""
    if "\r" not in frame:
        return frame.split("\n")
    return _LINE_BREAK.split(frame)


def frame_data(frame: str) -> DecimalJsonObject | None:
    """Read only SSE data, retaining decimal precision for envelope edits."""
    text = "\n".join(
        line[5:].lstrip(" ") for line in frame_lines(frame) if line.startswith("data:")
    )
    try:
        value: DecimalJsonValue = simplejson.loads(text, use_decimal=True)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def replace_frame_data(frame: str, payload: Mapping[str, object]) -> str:
    """Replace data lines while preserving other SSE fields and line endings."""
    lines = _LINE_BREAK_KEPT.split(frame)
    replacement = "data: " + simplejson.dumps(
        payload, use_decimal=True, ensure_ascii=False
    )
    parts: list[str] = []
    replaced = False
    for index in range(0, len(lines), 2):
        line = lines[index]
        ending = lines[index + 1] if index + 1 < len(lines) else ""
        if line.startswith("data:"):
            if replaced:
                continue
            line = replacement
            replaced = True
        parts.extend((line, ending))
    return "".join(parts)
