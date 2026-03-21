"""Per-channel preferences store (shared by Mattermost/Slack; Telegram uses its own)."""

from __future__ import annotations

from pathlib import Path

import msgspec
import msgspec.structs

from ..context import RunContext
from ..logging import get_logger
from ..state_store import JsonStateStore

logger = get_logger(__name__)

STATE_VERSION = 1


class Persona(msgspec.Struct, forbid_unknown_fields=False):
    """A reusable persona definition (global, not per-channel)."""

    name: str
    prompt: str


class _ChatPrefs(msgspec.Struct, forbid_unknown_fields=False):
    default_engine: str | None = None
    engine_locked: bool = False  # True: engine change blocked after first run
    trigger_mode: str | None = None  # "all" | "mentions"
    context_project: str | None = None
    context_branch: str | None = None
    engine_models: dict[str, str] = msgspec.field(default_factory=dict)


class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    chats: dict[str, _ChatPrefs] = msgspec.field(default_factory=dict)
    personas: dict[str, Persona] = msgspec.field(default_factory=dict)


class ChatPrefsStore(JsonStateStore[_State]):
    """Persistent per-channel preferences (engine, trigger mode, context)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            version=STATE_VERSION,
            state_type=_State,
            state_factory=_State,
            log_prefix="chat_prefs",
            logger=logger,
        )

    def _get(self, channel_id: str) -> _ChatPrefs:
        return self._state.chats.get(channel_id, _ChatPrefs())

    def _set(self, channel_id: str, prefs: _ChatPrefs) -> None:
        if prefs == _ChatPrefs():
            self._state.chats.pop(channel_id, None)
        else:
            self._state.chats[channel_id] = prefs

    # -- Public API --

    async def get_default_engine(self, channel_id: str) -> str | None:
        async with self._lock:
            self._reload_locked_if_needed()
            return self._get(channel_id).default_engine

    async def set_default_engine(
        self, channel_id: str, engine: str, *, lock: bool = False
    ) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            cur = self._get(channel_id)
            prefs = msgspec.structs.replace(
                cur,
                default_engine=engine,
                engine_locked=lock or cur.engine_locked,
            )
            self._set(channel_id, prefs)
            self._save_locked()

    async def is_engine_locked(self, channel_id: str) -> bool:
        async with self._lock:
            self._reload_locked_if_needed()
            return self._get(channel_id).engine_locked

    async def lock_engine(self, channel_id: str) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            prefs = msgspec.structs.replace(
                self._get(channel_id), engine_locked=True
            )
            self._set(channel_id, prefs)
            self._save_locked()

    async def get_trigger_mode(self, channel_id: str) -> str | None:
        async with self._lock:
            self._reload_locked_if_needed()
            return self._get(channel_id).trigger_mode

    async def set_trigger_mode(self, channel_id: str, mode: str) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            prefs = msgspec.structs.replace(self._get(channel_id), trigger_mode=mode)
            self._set(channel_id, prefs)
            self._save_locked()

    async def get_context(self, channel_id: str) -> RunContext | None:
        async with self._lock:
            self._reload_locked_if_needed()
            prefs = self._get(channel_id)
            if prefs.context_project is None:
                return None
            return RunContext(
                project=prefs.context_project,
                branch=prefs.context_branch,
            )

    async def set_context(self, channel_id: str, context: RunContext) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            prefs = msgspec.structs.replace(
                self._get(channel_id),
                context_project=context.project,
                context_branch=context.branch,
            )
            self._set(channel_id, prefs)
            self._save_locked()

    # -- Per-engine model override API --

    async def get_engine_model(self, channel_id: str, engine: str) -> str | None:
        async with self._lock:
            self._reload_locked_if_needed()
            return self._get(channel_id).engine_models.get(engine)

    async def set_engine_model(
        self, channel_id: str, engine: str, model: str
    ) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            prefs = self._get(channel_id)
            models = dict(prefs.engine_models)
            models[engine] = model
            new_prefs = msgspec.structs.replace(prefs, engine_models=models)
            self._set(channel_id, new_prefs)
            self._save_locked()

    async def clear_engine_model(self, channel_id: str, engine: str) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            prefs = self._get(channel_id)
            models = dict(prefs.engine_models)
            if engine in models:
                del models[engine]
                new_prefs = msgspec.structs.replace(prefs, engine_models=models)
                self._set(channel_id, new_prefs)
                self._save_locked()

    async def get_all_engine_models(self, channel_id: str) -> dict[str, str]:
        async with self._lock:
            self._reload_locked_if_needed()
            return dict(self._get(channel_id).engine_models)

    # -- Persona API (global, not per-channel) --

    async def get_persona(self, name: str) -> Persona | None:
        async with self._lock:
            self._reload_locked_if_needed()
            return self._state.personas.get(name)

    async def list_personas(self) -> dict[str, Persona]:
        async with self._lock:
            self._reload_locked_if_needed()
            return dict(self._state.personas)

    async def add_persona(self, name: str, prompt: str) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            self._state.personas[name] = Persona(name=name, prompt=prompt)
            self._save_locked()

    async def remove_persona(self, name: str) -> bool:
        async with self._lock:
            self._reload_locked_if_needed()
            if name not in self._state.personas:
                return False
            del self._state.personas[name]
            self._save_locked()
            return True
