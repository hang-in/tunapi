"""Roundtable participant — engine + role separation.

Decouples "who speaks" (participant with a role and instruction)
from "what runs" (engine).  The same engine can appear multiple
times with different roles.
"""

from __future__ import annotations

import msgspec

from .project_memory import generate_entry_id


class RoundtableParticipant(msgspec.Struct, forbid_unknown_fields=False):
    participant_id: str
    engine: str
    role: str
    instruction: str = ""
    order: int = 0
    enabled: bool = True
    model_override: str | None = None  # 엔진 내 특정 모델 지정


def build_participants_from_engines(
    engines: list[str],
) -> list[RoundtableParticipant]:
    """Build participants from a flat engine list (backward compat).

    Each engine becomes a participant whose role equals the engine id.
    """
    return [
        RoundtableParticipant(
            participant_id=generate_entry_id(),
            engine=engine,
            role=engine,
            order=i,
        )
        for i, engine in enumerate(engines)
    ]


def build_participants_from_config(
    config: list[dict],
) -> list[RoundtableParticipant]:
    """Build participants from explicit config dicts.

    Each dict should have at least ``engine`` and ``role``.
    Optional: ``instruction``, ``order``, ``enabled``.

    Example::

        [
            {"engine": "claude", "role": "architect", "instruction": "Focus on API design"},
            {"engine": "gemini", "role": "critic"},
            {"engine": "claude", "role": "implementer", "instruction": "Write code"},
        ]
    """
    participants: list[RoundtableParticipant] = []
    for i, entry in enumerate(config):
        participants.append(
            RoundtableParticipant(
                participant_id=generate_entry_id(),
                engine=entry["engine"],
                role=entry.get("role", entry["engine"]),
                instruction=entry.get("instruction", ""),
                order=entry.get("order", i),
                enabled=entry.get("enabled", True),
                model_override=entry.get("model_override") or entry.get("model"),
            )
        )
    return participants
