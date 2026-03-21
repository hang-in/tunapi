"""Roundtable for Mattermost transport.

Core logic lives in :mod:`tunapi.core.roundtable`; this module re-exports
for backward compatibility.
"""

from __future__ import annotations

from ..core.roundtable import (
    _MAX_ANSWER_LENGTH,
    _build_round_prompt,
    RoundtableBridgeCfg,
    RoundtableSession,
    RoundtableStore,
    parse_followup_args,
    parse_rt_args,
    run_followup_round,
    run_roundtable,
)

__all__ = [
    "_MAX_ANSWER_LENGTH",
    "_build_round_prompt",
    "RoundtableBridgeCfg",
    "RoundtableSession",
    "RoundtableStore",
    "parse_followup_args",
    "parse_rt_args",
    "run_followup_round",
    "run_roundtable",
]
