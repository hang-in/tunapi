"""Trigger mode logic for Slack transport."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .parsing import SlackMessageEvent

if TYPE_CHECKING:
    from .chat_prefs import ChatPrefsStore


async def resolve_trigger_mode(
    channel_id: str,
    chat_prefs: ChatPrefsStore | None,
) -> str:
    """Resolve the effective trigger mode for a channel."""
    if chat_prefs:
        mode = await chat_prefs.get_trigger_mode(channel_id)
        if mode:
            return mode
    return "mentions"  # Slack default is mentions


def should_trigger(
    event: SlackMessageEvent,
    *,
    bot_user_id: str,
    trigger_mode: str,
) -> bool:
    """Check if the bot should respond to an incoming message."""
    # Always trigger on direct messages (IM)
    # Note: IM channel IDs start with 'D' in Slack
    if event.channel_id.startswith("D"):
        return True

    if trigger_mode == "all":
        return True

    # Otherwise, only trigger if the bot is mentioned
    # Slack app_mention events are handled separately or text contains <@bot_user_id>
    return f"<@{bot_user_id}>" in event.text


def strip_mention(text: str, bot_user_id: str) -> str:
    """Remove the bot's mention from the message text."""
    mention = f"<@{bot_user_id}>"
    return text.replace(mention, "").strip()
