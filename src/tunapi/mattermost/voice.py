"""Voice/audio transcription for Mattermost transport.

Core logic lives in :mod:`tunapi.core.voice`; this module re-exports
for backward compatibility.
"""

from __future__ import annotations

from ..core.voice import AUDIO_MIME_TYPES, is_audio_file, transcribe_audio

__all__ = ["AUDIO_MIME_TYPES", "is_audio_file", "transcribe_audio"]
