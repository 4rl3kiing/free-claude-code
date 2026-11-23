"""Instance-owned local Whisper transcription."""

import asyncio
from pathlib import Path
from typing import Protocol, TypedDict

from loguru import logger

_MODEL_MAP: dict[str, str] = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large-v2": "openai/whisper-large-v2",
    "large-v3": "openai/whisper-large-v3",
    "large-v3-turbo": "openai/whisper-large-v3-turbo",
}
# Pinned Hugging Face commits for the built-in names: a moved "main" branch can
# never swap the weights or code we download. Custom model ids stay unpinned.
_MODEL_REVISIONS: dict[str, str] = {
    "openai/whisper-tiny": "169d4a4341b33bc18d8881c4b69c2e104e1cc0af",
    "openai/whisper-base": "e37978b90ca9030d5170a5c07aadb050351a65bb",
    "openai/whisper-small": "973afd24965f72e36ca33b3055d56a652f456b4d",
    "openai/whisper-medium": "abdf7c39ab9d0397620ccaea8974cc764cd0953e",
    "openai/whisper-large-v2": "ae4642769ce2ad8fc292556ccea8e901f1530655",
    "openai/whisper-large-v3": "06f233fe06e710322aca913c1bc4249a0d71fce1",
    "openai/whisper-large-v3-turbo": "41f01f3fe87f28c78e2fbf8b568835947dd65ed9",
}
_WHISPER_SAMPLE_RATE = 16000


class _AudioInput(TypedDict):
    array: object
    sampling_rate: int


class _TranscriptionResult(TypedDict, total=False):
    text: str | list[str]


class _TranscriptionPipeline(Protocol):
    def __call__(
        self, audio: _AudioInput, /, *, generate_kwargs: dict[str, str]
    ) -> _TranscriptionResult: ...


class TranscriptionService:
    """Own one lazily loaded local Whisper pipeline."""

    def __init__(
        self,
        *,
        model: str,
        device: str,
        huggingface_api_key: str | None = None,
    ) -> None:
        if device not in {"cpu", "cuda"}:
            raise ValueError(
                f"Local Whisper device must be 'cpu' or 'cuda', got {device!r}"
            )
        self._model_id = _MODEL_MAP.get(model, model)
        self._device = device
        self._huggingface_api_key = huggingface_api_key
        self._pipeline: _TranscriptionPipeline | None = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def transcribe(self, file_path: Path) -> str:
        """Transcribe one audio file without blocking the event loop."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("Transcription service is closed.")
            worker = asyncio.create_task(
                asyncio.to_thread(self._transcribe_sync, file_path)
            )
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                await _wait_for_thread_exit(worker)
                raise

    async def close(self) -> None:
        """Prevent new work and release the owned model pipeline."""
        self._closed = True
        async with self._lock:
            self._pipeline = None
            self._huggingface_api_key = None

    def _transcribe_sync(self, file_path: Path) -> str:
        pipe = self._get_pipeline()
        audio = _load_audio(file_path)
        result = pipe(audio, generate_kwargs={"language": "en", "task": "transcribe"})
        text = result.get("text", "") or ""
        if isinstance(text, list):
            text = " ".join(text) if text else ""
        result_text = text.strip()
        logger.debug("Local transcription: {} chars", len(result_text))
        return result_text or "(no speech detected)"

    def _get_pipeline(self) -> _TranscriptionPipeline:
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        except ImportError as exc:
            raise ImportError(
                "Local Whisper requires the voice_local extra. "
                "Install with: uv sync --extra voice_local"
            ) from exc

        token = self._huggingface_api_key
        use_cuda = self._device == "cuda" and torch.cuda.is_available()
        pipeline_device = "cuda:0" if use_cuda else "cpu"
        model_dtype = torch.float16 if use_cuda else torch.float32
        revision = _MODEL_REVISIONS.get(self._model_id)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self._model_id,
            revision=revision,
            dtype=model_dtype,
            low_cpu_mem_usage=True,
            attn_implementation="sdpa",
            token=token,
        )
        model = model.to(pipeline_device)
        processor = AutoProcessor.from_pretrained(
            self._model_id, revision=revision, token=token
        )
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            device=pipeline_device,
        )
        logger.debug(
            "Loaded Whisper pipeline: model={} device={}",
            self._model_id,
            pipeline_device,
        )
        return self._pipeline


async def _wait_for_thread_exit(worker: asyncio.Task[str]) -> None:
    """Wait through repeated caller cancellation without cancelling thread work."""
    while not worker.done():
        try:
            await asyncio.shield(asyncio.wait((worker,)))
        except asyncio.CancelledError:
            continue
    if not worker.cancelled():
        worker.exception()


def _load_audio(file_path: Path) -> _AudioInput:
    """Load an audio file into the waveform shape expected by Whisper."""
    import librosa

    waveform, sample_rate = librosa.load(
        str(file_path), sr=_WHISPER_SAMPLE_RATE, mono=True
    )
    return {"array": waveform, "sampling_rate": sample_rate}
