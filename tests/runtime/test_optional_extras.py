"""Optional integrations fail with an instruction to install their extra."""

import builtins
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from free_claude_code.runtime.messaging_service import (
    MISSING_MESSAGING_EXTRA,
    messaging_import_error,
)


@pytest.mark.parametrize("module", ["telegram", "telegram.ext", "discord"])
def test_missing_messaging_library_names_the_extra(module: str) -> None:
    assert messaging_import_error(ImportError("x", name=module)) == (
        MISSING_MESSAGING_EXTRA
    )
    assert "free-claude-code[messaging]" in MISSING_MESSAGING_EXTRA


@pytest.mark.parametrize("name", [None, "free_claude_code.messaging.workflow"])
def test_other_import_errors_keep_the_generic_message(name: str | None) -> None:
    message = messaging_import_error(ImportError("x", name=name))
    assert message.startswith("Messaging could not start.")


def test_discord_platform_reports_the_messaging_extra() -> None:
    import free_claude_code.messaging.platforms.discord as discord_mod

    with (
        patch.object(discord_mod, "DISCORD_AVAILABLE", False),
        patch.object(discord_mod, "_discord_module", None),
        pytest.raises(ImportError) as raised,
    ):
        discord_mod._get_discord()
    assert raised.value.name == "discord"
    assert messaging_import_error(raised.value) == MISSING_MESSAGING_EXTRA


def test_nim_voice_without_riva_names_the_extra(tmp_path: Path) -> None:
    from free_claude_code.providers.nvidia_nim.voice import NvidiaNimTranscriber

    real_import = builtins.__import__

    def block_riva(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if name.startswith("riva"):
            raise ImportError(name, name=name)
        return real_import(name, globals, locals, fromlist, level)

    transcriber = NvidiaNimTranscriber(model="nvidia/parakeet-ctc-0.6b-es", api_key="k")
    with (
        patch("builtins.__import__", block_riva),
        pytest.raises(RuntimeError, match=r"free-claude-code\[voice_nim\]"),
    ):
        transcriber._transcribe_sync(tmp_path / "voice.ogg")
