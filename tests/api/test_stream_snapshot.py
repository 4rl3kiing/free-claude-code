"""Rollback snapshots copy stream state exactly, with or without pickle."""

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy

from free_claude_code.api.stream_delivery import PublicResponseStream
from free_claude_code.core.stream_delivery import StreamDeliveryState
from free_claude_code.core.stream_output import StreamOutput

FRAMES = (
    'event: message_start\ndata: {"type":"message_start","message":{"id":"m1",'
    '"type":"message","role":"assistant","model":"x","content":[],'
    '"stop_reason":null,"usage":{"input_tokens":1,"output_tokens":1}}}\n\n',
    'event: content_block_start\ndata: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"text","text":""}}\n\n',
    'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"hola 1.10"}}\n\n',
)


async def _started_stream() -> PublicResponseStream:
    async def body() -> AsyncIterator[StreamOutput]:
        for frame in FRAMES:
            yield StreamOutput((frame,))

    stream = PublicResponseStream(
        body(),
        StreamDeliveryState(),
        wire_api="messages",
        first_chunk=StreamOutput(()),
        terminal_frame=None,
        terminal_failure_observer=None,
    )
    await anext(stream)
    await anext(stream)
    return stream


def test_pickle_snapshot_matches_deepcopy() -> None:
    stream = asyncio.run(_started_stream())
    state: dict[str, object] = stream.__dict__
    values = {
        key: value
        for key, value in state.items()
        if key in {"_delivered", "_continuation", "_decoder", "_published_starts"}
    }
    copied = stream._snapshot(values)
    assert stream._pickle_snapshots
    assert copied.keys() == values.keys()
    for key in values:
        assert copied[key] is not values[key]
    # Shared references stay shared, as with deepcopy.
    continuation: dict[str, object] = vars(copied["_continuation"])
    assert continuation.get("_delivered", copied["_delivered"]) is copied["_delivered"]
    assert repr(copied["_published_starts"]) == repr(
        deepcopy(values)["_published_starts"]
    )


def test_unpicklable_state_falls_back_to_deepcopy() -> None:
    stream = asyncio.run(_started_stream())
    values: dict[str, object] = {"callback": lambda: None, "items": [1, 2]}
    copied = stream._snapshot(values)
    assert not stream._pickle_snapshots
    assert copied["callback"] is values["callback"]
    assert copied["items"] == [1, 2]
    assert copied["items"] is not values["items"]
