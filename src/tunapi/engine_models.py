"""Engine-specific model registry and discovery.

Provides known model lists per engine and a probe mechanism for
CLI-based discovery (currently stub — no CLI supports ``--list-models``).
"""

from __future__ import annotations

import re

from .logging import get_logger

logger = get_logger(__name__)

# -- Known model registry ---------------------------------------------------
# Maintained manually.  Update when new models are released.

KNOWN_MODELS: dict[str, list[str]] = {
    "claude": [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-sonnet-4-5-20250514",
        "claude-opus-4-20250514",
        "claude-haiku-4-5-20251001",
        "claude-haiku-3-5-20241022",
        "sonnet",
        "opus",
        "haiku",
    ],
    "codex": [
        "o3",
        "o4-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
    ],
    "gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
    "opencode": [
        "anthropic:claude-sonnet-4-5-20250514",
        "openai:gpt-4.1",
        "gemini:gemini-2.5-pro",
    ],
    "pi": [
        "claude-sonnet-4-5-20250514",
        "gpt-4.1",
        "gemini-2.5-pro",
    ],
}


def shorten_model(model: str) -> str:
    """Shorten a model ID for display in status lines.

    ``claude-opus-4-6``        → ``opus4.6``
    ``claude-sonnet-4-5-20250514`` → ``sonnet4.5``
    ``claude-opus-4-20250514`` → ``opus4``
    ``opus``                   → ``opus``  (short aliases unchanged)
    ``o4-mini``                → ``o4-mini`` (non-claude unchanged)
    """
    m = re.sub(r"-\d{8}$", "", model)  # strip date suffix
    if not m.startswith("claude-"):
        return m
    m = m[len("claude-"):]  # strip "claude-" prefix
    parts = m.split("-")
    name_parts: list[str] = []
    ver_parts: list[str] = []
    for p in parts:
        if p.isdigit():
            ver_parts.append(p)
        elif not ver_parts:
            name_parts.append(p)
    name = "".join(name_parts)
    ver = ".".join(ver_parts)
    return f"{name}{ver}" if ver else name


def get_models(engine: str) -> tuple[list[str], str]:
    """Return ``(model_list, source)`` for the given engine.

    *source* is ``"registry"`` (from ``KNOWN_MODELS``) or
    ``"unknown"`` if the engine is not recognised.
    """
    models = KNOWN_MODELS.get(engine)
    if models is not None:
        return list(models), "registry"
    return [], "unknown"
