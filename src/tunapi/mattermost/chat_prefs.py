"""Per-channel preferences store for Mattermost transport."""

from __future__ import annotations

from pathlib import Path

import anyio
import msgspec

from ..context import RunContext
from ..logging import get_logger

logger = get_logger(__name__)

STATE_VERSION = 1


class Persona(msgspec.Struct, forbid_unknown_fields=False):
    """A reusable persona definition (global, not per-channel)."""

    name: str
    prompt: str


class _ChatPrefs(msgspec.Struct, forbid_unknown_fields=False):
    default_engine: str | None = None
    trigger_mode: str | None = None  # "all" | "mentions"
    context_project: str | None = None
    context_branch: str | None = None


class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    chats: dict[str, _ChatPrefs] = msgspec.field(default_factory=dict)
    personas: dict[str, Persona] = msgspec.field(default_factory=dict)


_DECODER = msgspec.json.Decoder(_State)
_ENCODER = msgspec.json.Encoder()


class ChatPrefsStore:
    """Persistent per-channel preferences (engine, trigger mode, context)."""

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
                logger.warning("chat_prefs.load_error", path=str(self._path))
                self._state = _State()
        self._loaded = True

    async def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = msgspec.to_builtins(self._state)
        raw = msgspec.json.encode(data)
        self._path.write_bytes(raw)

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
            await self._load()
            return self._get(channel_id).default_engine

    async def set_default_engine(self, channel_id: str, engine: str) -> None:
        async with self._lock:
            await self._load()
            prefs = self._get(channel_id)
            prefs = _ChatPrefs(
                default_engine=engine,
                trigger_mode=prefs.trigger_mode,
                context_project=prefs.context_project,
                context_branch=prefs.context_branch,
            )
            self._set(channel_id, prefs)
            await self._save()

    async def get_trigger_mode(self, channel_id: str) -> str | None:
        async with self._lock:
            await self._load()
            return self._get(channel_id).trigger_mode

    async def set_trigger_mode(
        self, channel_id: str, mode: str
    ) -> None:
        async with self._lock:
            await self._load()
            prefs = self._get(channel_id)
            prefs = _ChatPrefs(
                default_engine=prefs.default_engine,
                trigger_mode=mode,
                context_project=prefs.context_project,
                context_branch=prefs.context_branch,
            )
            self._set(channel_id, prefs)
            await self._save()

    async def get_context(self, channel_id: str) -> RunContext | None:
        async with self._lock:
            await self._load()
            prefs = self._get(channel_id)
            if prefs.context_project is None:
                return None
            return RunContext(
                project=prefs.context_project,
                branch=prefs.context_branch,
            )

    async def set_context(
        self, channel_id: str, context: RunContext
    ) -> None:
        async with self._lock:
            await self._load()
            prefs = self._get(channel_id)
            prefs = _ChatPrefs(
                default_engine=prefs.default_engine,
                trigger_mode=prefs.trigger_mode,
                context_project=context.project,
                context_branch=context.branch,
            )
            self._set(channel_id, prefs)
            await self._save()

    # -- Persona API (global, not per-channel) --

    async def get_persona(self, name: str) -> Persona | None:
        async with self._lock:
            await self._load()
            return self._state.personas.get(name)

    async def list_personas(self) -> dict[str, Persona]:
        async with self._lock:
            await self._load()
            return dict(self._state.personas)

    async def add_persona(self, name: str, prompt: str) -> None:
        async with self._lock:
            await self._load()
            self._state.personas[name] = Persona(name=name, prompt=prompt)
            await self._save()

    async def remove_persona(self, name: str) -> bool:
        async with self._lock:
            await self._load()
            if name not in self._state.personas:
                return False
            del self._state.personas[name]
            await self._save()
            return True
