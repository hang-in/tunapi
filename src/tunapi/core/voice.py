"""Voice/audio transcription — shared across transports."""

from __future__ import annotations

from io import BytesIO

from ..logging import get_logger

logger = get_logger(__name__)

AUDIO_MIME_TYPES = frozenset(
    {
        "audio/ogg",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/wav",
        "audio/webm",
        "audio/x-wav",
        "audio/flac",
    }
)


def is_audio_file(mime_type: str) -> bool:
    return mime_type.lower() in AUDIO_MIME_TYPES


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    *,
    model: str = "gpt-4o-mini-transcribe",
    base_url: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """Transcribe audio bytes using OpenAI's transcription API."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("voice.openai_not_installed")
        return None

    try:
        kwargs: dict = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        client = AsyncOpenAI(**kwargs)

        buf = BytesIO(audio_bytes)
        buf.name = filename

        result = await client.audio.transcriptions.create(
            model=model,
            file=buf,
        )
        text = result.text.strip() if hasattr(result, "text") else str(result).strip()
        logger.info("voice.transcribed", length=len(text), model=model)
        return text or None
    except Exception as exc:  # noqa: BLE001
        logger.error("voice.transcription_error", error=str(exc))
        return None
