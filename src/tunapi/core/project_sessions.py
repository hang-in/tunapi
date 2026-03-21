"""Unified project-level session store.

Replaces per-transport ``ChatSessionStore`` with a single shared store
keyed by *project* instead of *(channel_id, engine)*.  Any transport can
resume a session started from any other transport for the same project.

Storage layout (version 1)::

    {
      "version": 1,
      "projects": {
        "<project_key>": {
          "engine": "claude",
          "token": "<resume_token_value>",
          "cwd": "/path/to/project"
        }
      }
    }

File: ``~/.tunapi/sessions.json``
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from ..logging import get_logger
from ..model import ResumeToken
from ..state_store import JsonStateStore

if TYPE_CHECKING:
    from .chat_prefs import ChatPrefsStore
    from .chat_sessions import ChatSessionStore

logger = get_logger(__name__)

STATE_VERSION = 1


class _ProjectEntry(msgspec.Struct, forbid_unknown_fields=False):
    engine: str
    token: str
    cwd: str | None = None


class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    projects: dict[str, _ProjectEntry] = msgspec.field(default_factory=dict)


class ProjectSessionStore(JsonStateStore[_State]):
    """Unified per-project resume-token store.

    Backed by a JSON file at *path* (typically ``~/.tunapi/sessions.json``).
    """

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            version=STATE_VERSION,
            state_type=_State,
            state_factory=_State,
            log_prefix="project_sessions",
            logger=logger,
        )

    @staticmethod
    def _normalize_cwd(cwd: Path | None) -> str | None:
        if cwd is None:
            return None
        return str(cwd.expanduser().resolve())

    @staticmethod
    def _normalize_key(project: str) -> str:
        return project.lower()

    async def get(self, project: str, *, cwd: Path | None = None) -> ResumeToken | None:
        """Get resume token for a project."""
        key = self._normalize_key(project)
        async with self._lock:
            self._reload_locked_if_needed()
            entry = self._state.projects.get(key)
            if entry is None:
                return None
            expected_cwd = self._normalize_cwd(cwd)
            if expected_cwd is not None and expected_cwd != entry.cwd:
                self._state.projects.pop(key, None)
                self._save_locked()
                return None
            return ResumeToken(engine=entry.engine, value=entry.token)

    async def set(
        self, project: str, token: ResumeToken, *, cwd: Path | None = None
    ) -> None:
        """Store a resume token for a project."""
        key = self._normalize_key(project)
        async with self._lock:
            self._reload_locked_if_needed()
            self._state.projects[key] = _ProjectEntry(
                engine=token.engine,
                token=token.value,
                cwd=self._normalize_cwd(cwd),
            )
            self._save_locked()

    async def clear(self, project: str) -> None:
        """Clear project session (!new)."""
        key = self._normalize_key(project)
        async with self._lock:
            self._reload_locked_if_needed()
            if self._state.projects.pop(key, None) is not None:
                self._save_locked()

    async def get_engine(self, project: str) -> str | None:
        """Get the project's stored engine."""
        key = self._normalize_key(project)
        async with self._lock:
            self._reload_locked_if_needed()
            entry = self._state.projects.get(key)
            return entry.engine if entry else None

    async def has_active(self, project: str) -> bool:
        """Check if project has an active session."""
        key = self._normalize_key(project)
        async with self._lock:
            self._reload_locked_if_needed()
            return key in self._state.projects


async def migrate_legacy_sessions(
    legacy_stores: list[ChatSessionStore],
    chat_prefs: ChatPrefsStore,
    target: ProjectSessionStore,
) -> int:
    """Migrate legacy per-transport session files into the unified store.

    Returns the number of sessions migrated.
    """
    count = 0
    for store in legacy_stores:
        async with store._lock:
            store._reload_locked_if_needed()
            for channel_id, channel_data in store._state.channels.items():
                ctx = await chat_prefs.get_context(channel_id)
                if not ctx or not ctx.project:
                    continue
                for engine, entry in channel_data.sessions.items():
                    # Only migrate if target doesn't already have an entry
                    existing = await target.get(ctx.project)
                    if existing is None:
                        await target.set(
                            ctx.project,
                            ResumeToken(engine=engine, value=entry.value),
                            cwd=Path(entry.cwd) if entry.cwd else None,
                        )
                        count += 1
    return count
