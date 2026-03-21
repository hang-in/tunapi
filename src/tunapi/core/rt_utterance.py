"""Roundtable utterance — structured per-turn record.

Replaces flat ``list[tuple[str, str]]`` transcript with typed records
that track stage, participant, reply chain, and input context.
"""

from __future__ import annotations

import time
from typing import Literal

import msgspec

from .project_memory import generate_entry_id
from .rt_participant import RoundtableParticipant

Phase = Literal["opinion", "comment", "synthesis", "refinement"]


class Utterance(msgspec.Struct, forbid_unknown_fields=False):
    utterance_id: str
    stage: str  # "round_1", "framing", "critique", etc. (display, backward compat)
    participant_id: str
    engine: str
    role: str
    output_text: str
    input_summary: str = ""
    reply_to: str | None = None  # previous utterance_id
    round_idx: int = 0  # 라운드 번호
    phase: Phase = "opinion"  # 구조화된 phase
    branch_id: str | None = None  # 브랜치 연결
    created_at: str = ""


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def transcript_to_utterances(
    transcript: list[tuple[str, str]],
    participants: list[RoundtableParticipant],
    *,
    total_rounds: int = 1,
) -> list[Utterance]:
    """Convert a flat transcript to structured utterances.

    Each ``(engine, answer)`` pair is matched to a participant by
    engine id (first match).  Stages are assigned as ``"round_N"``
    based on participant count per round.
    """
    # Build engine → participant lookup (first match per engine)
    engine_to_participant: dict[str, RoundtableParticipant] = {}
    for p in participants:
        if p.engine not in engine_to_participant:
            engine_to_participant[p.engine] = p

    engines_per_round = (
        len(participants) if participants else len({e for e, _ in transcript})
    )
    if engines_per_round == 0:
        engines_per_round = 1

    utterances: list[Utterance] = []
    prev_id: str | None = None

    for i, (engine, answer) in enumerate(transcript):
        round_num = (i // engines_per_round) + 1
        stage = f"round_{round_num}"

        participant = engine_to_participant.get(engine)
        participant_id = participant.participant_id if participant else ""
        role = participant.role if participant else engine

        uid = generate_entry_id()
        utterances.append(
            Utterance(
                utterance_id=uid,
                stage=stage,
                participant_id=participant_id,
                engine=engine,
                role=role,
                output_text=answer,
                reply_to=prev_id,
                round_idx=round_num,
                phase="opinion",
                created_at=_now_iso(),
            )
        )
        prev_id = uid

    return utterances


def utterances_to_transcript(
    utterances: list[Utterance],
) -> list[tuple[str, str]]:
    """Convert utterances back to flat transcript (backward compat)."""
    return [(u.engine, u.output_text) for u in utterances]
