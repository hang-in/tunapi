"""Persistent chat session store for Mattermost transport.

Stores resume tokens per channel so that conversations survive server
restarts.  Follows the same pattern as ``ChatPrefsStore``.
"""

from __future__ import annotations

from pathlib import Path

import anyio
import msgspec

from ..logging import get_logger
from ..model import ResumeToken

logger = get_logger(__name__)

STATE_VERSION = 1


class _SessionEntry(msgspec.Struct, forbid_unknown_fields=False):
    engine: str
    value: str


class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    sessions: dict[str, _SessionEntry] = msgspec.field(default_factory=dict)


_DECODER = msgspec.json.Decoder(_State)


class ChatSessionStore:
    """Persistent per-channel resume-token store.

    Backed by a JSON file at *path* (typically
    ``~/.tunapi/mattermost_sessions.json``).
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._state = _State()
        self._lock = anyio.Lock()
        self._loaded = False

    async def _load(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                raw = self._path.read_bytes()
                self._state = _DECODER.decode(raw)
            except Exception:  # noqa: BLE001
                logger.warning("chat_sessions.load_error", path=str(self._path))
                self._state = _State()
        self._loaded = True

    async def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = msgspec.to_builtins(self._state)
        raw = msgspec.json.encode(data)
        self._path.write_bytes(raw)

    async def get(self, channel_id: str) -> ResumeToken | None:
        async with self._lock:
            await self._load()
            entry = self._state.sessions.get(channel_id)
            if entry is None:
                return None
            return ResumeToken(engine=entry.engine, value=entry.value)

    async def set(self, channel_id: str, token: ResumeToken) -> None:
        async with self._lock:
            await self._load()
            self._state.sessions[channel_id] = _SessionEntry(
                engine=token.engine,
                value=token.value,
            )
            await self._save()

    async def clear(self, channel_id: str) -> None:
        async with self._lock:
            await self._load()
            if self._state.sessions.pop(channel_id, None) is not None:
                await self._save()
