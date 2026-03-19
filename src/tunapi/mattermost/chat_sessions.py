"""Persistent chat session store for Mattermost transport.

Stores resume tokens per channel so that conversations survive server
restarts.  Uses ``JsonStateStore`` for versioned, atomic JSON persistence.
"""

from __future__ import annotations

from pathlib import Path

import msgspec

from ..logging import get_logger
from ..model import ResumeToken
from ..state_store import JsonStateStore

logger = get_logger(__name__)

STATE_VERSION = 1


class _SessionEntry(msgspec.Struct, forbid_unknown_fields=False):
    engine: str
    value: str


class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    sessions: dict[str, _SessionEntry] = msgspec.field(default_factory=dict)


class ChatSessionStore(JsonStateStore[_State]):
    """Persistent per-channel resume-token store.

    Backed by a JSON file at *path* (typically
    ``~/.tunapi/mattermost_sessions.json``).
    """

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            version=STATE_VERSION,
            state_type=_State,
            state_factory=_State,
            log_prefix="chat_sessions",
            logger=logger,
        )

    async def get(self, channel_id: str) -> ResumeToken | None:
        async with self._lock:
            self._reload_locked_if_needed()
            entry = self._state.sessions.get(channel_id)
            if entry is None:
                return None
            return ResumeToken(engine=entry.engine, value=entry.value)

    async def set(self, channel_id: str, token: ResumeToken) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            self._state.sessions[channel_id] = _SessionEntry(
                engine=token.engine,
                value=token.value,
            )
            self._save_locked()

    async def clear(self, channel_id: str) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            if self._state.sessions.pop(channel_id, None) is not None:
                self._save_locked()
