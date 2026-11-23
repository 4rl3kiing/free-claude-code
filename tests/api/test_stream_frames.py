"""SSE frames keep their line endings and decimal precision on every path."""

from decimal import Decimal

import pytest

from free_claude_code.api.stream_frames import (
    frame_data,
    frame_lines,
    replace_frame_data,
)
from free_claude_code.core.json_types import DecimalJsonValue


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        ("event: a\ndata: {}\n\n", ["event: a", "data: {}", "", ""]),
        ("event: a\r\ndata: {}\r\n\r\n", ["event: a", "data: {}", "", ""]),
        ("event: a\rdata: {}\r\r", ["event: a", "data: {}", "", ""]),
        ("event: a\r\ndata: {}\n\r", ["event: a", "data: {}", "", ""]),
    ],
)
def test_frame_lines_splits_every_line_ending(frame: str, expected: list[str]) -> None:
    assert frame_lines(frame) == expected


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_frame_data_reads_multiline_data_with_any_ending(ending: str) -> None:
    frame = ending.join(["event: x", 'data: {"a":', "data: 1.10}", "", ""])
    assert frame_data(frame) == {"a": Decimal("1.10")}


def test_frame_data_ignores_frames_without_an_object() -> None:
    assert frame_data(": keepalive\n\n") is None
    assert frame_data("data: [DONE]\n\n") is None


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
def test_replace_frame_data_keeps_fields_and_line_endings(ending: str) -> None:
    frame = ending.join(["event: x", "data: {}", "id: 7", "", ""])
    replaced = replace_frame_data(frame, {"a": Decimal("1.10")})
    assert replaced == ending.join(["event: x", 'data: {"a": 1.10}', "id: 7", "", ""])


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1.10, "b": 1e400, "c": -0.0, "d": [1, 2.5, "x"], "e": null}',
        '{"text": "ñ 你好 \\u2028 \\ud83d\\ude00", "nested": {"k": true}}',
        '{"big": 123456789012345678901234567890, "small": 0.000000000000000001}',
    ],
)
def test_shared_codec_matches_simplejson_defaults(text: str) -> None:
    import simplejson

    expected: DecimalJsonValue = simplejson.loads(text, use_decimal=True)
    assert isinstance(expected, dict)
    frame = f"event: x\ndata: {text}\n\n"
    assert frame_data(frame) == expected
    replaced = replace_frame_data(frame, expected)
    assert replaced == (
        "event: x\ndata: "
        + simplejson.dumps(expected, use_decimal=True, ensure_ascii=False)
        + "\n\n"
    )


def test_shared_codec_rejects_nan_like_simplejson() -> None:
    with pytest.raises(ValueError):
        replace_frame_data("data: {}\n\n", {"x": float("nan")})
