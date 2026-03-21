"""Trigger mode resolution — shared across Slack / Mattermost.

Platform-specific ``should_trigger`` and ``strip_mention`` stay in each
transport because mention syntax differs (``<@U123>`` vs ``@username``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chat_prefs import ChatPrefsStore


async def resolve_trigger_mode(
    channel_id: str,
    chat_prefs: ChatPrefsStore | None,
    *,
    default: str = "all",
) -> str:
    """Return the effective trigger mode for *channel_id*.

    Checks ``chat_prefs`` first; falls back to *default*.
    """
    if chat_prefs is not None:
        mode = await chat_prefs.get_trigger_mode(channel_id)
        if mode:
            return mode
    return default
