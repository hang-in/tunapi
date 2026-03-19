"""Persistent chat session store for Slack transport."""

from __future__ import annotations

from pathlib import Path

import msgspec

from ..logging import get_logger
from ..model import ResumeToken
from ..state_store import JsonStateStore

logger = get_logger(__name__)

STATE_VERSION = 2


class _SessionEntry(msgspec.Struct, forbid_unknown_fields=False):
    value: str


class _ChannelSessions(msgspec.Struct, forbid_unknown_fields=False):
    sessions: dict[str, _SessionEntry] = msgspec.field(default_factory=dict)


class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    channels: dict[str, _ChannelSessions] = msgspec.field(default_factory=dict)


class ChatSessionStore(JsonStateStore[_State]):
    """Persistent per-channel, per-engine resume-token store."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            version=STATE_VERSION,
            state_type=_State,
            state_factory=_State,
            log_prefix="slack_sessions",
            logger=logger,
        )

    async def get(self, channel_id: str, engine: str) -> ResumeToken | None:
        """Get resume token for a specific channel+engine pair."""
        async with self._lock:
            self._reload_locked_if_needed()
            channel = self._state.channels.get(channel_id)
            if channel is None:
                return None
            entry = channel.sessions.get(engine)
            if entry is None:
                return None
            return ResumeToken(engine=engine, value=entry.value)

    async def set(self, channel_id: str, token: ResumeToken) -> None:
        """Store a resume token (uses token.engine as key)."""
        async with self._lock:
            self._reload_locked_if_needed()
            channel = self._state.channels.get(channel_id)
            if channel is None:
                channel = _ChannelSessions()
                self._state.channels[channel_id] = channel
            channel.sessions[token.engine] = _SessionEntry(value=token.value)
            self._save_locked()

    async def clear(self, channel_id: str) -> None:
        """Clear all engine sessions for a channel (/new)."""
        async with self._lock:
            self._reload_locked_if_needed()
            if self._state.channels.pop(channel_id, None) is not None:
                self._save_locked()

    async def clear_engine(self, channel_id: str, engine: str) -> None:
        """Clear a specific engine session for a channel."""
        async with self._lock:
            self._reload_locked_if_needed()
            channel = self._state.channels.get(channel_id)
            if channel is None:
                return
            if channel.sessions.pop(engine, None) is not None:
                if not channel.sessions:
                    del self._state.channels[channel_id]
                self._save_locked()

    async def has_any(self, channel_id: str) -> bool:
        """Check if channel has any active session (for /status)."""
        async with self._lock:
            self._reload_locked_if_needed()
            channel = self._state.channels.get(channel_id)
            return channel is not None and bool(channel.sessions)
