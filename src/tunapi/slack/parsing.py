"""Parse Slack events into internal representations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ..logging import get_logger
from .api_models import SocketModeEnvelope

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SlackMessageEvent:
    channel_id: str
    user_id: str
    text: str
    ts: str
    thread_ts: str | None = None
    files: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class SlackReactionEvent:
    channel_id: str
    user_id: str
    emoji: str
    ts: str
    item_ts: str


def parse_envelope(
    envelope: SocketModeEnvelope,
    *,
    bot_user_id: str,
    allowed_channel_ids: Iterable[str] | None = None,
    allowed_user_ids: Iterable[str] | None = None,
) -> SlackMessageEvent | SlackReactionEvent | None:
    """Parse a Socket Mode envelope into a specific event object.

    Filters out bot's own messages, disallowed channels, and disallowed users.
    DMs (channel IDs starting with ``D``) are always allowed regardless of
    ``allowed_channel_ids``.
    """
    if envelope.type != "events_api" or not envelope.payload:
        return None

    payload = envelope.payload
    event = payload.get("event")
    if not event:
        return None

    event_type = event.get("type")

    if event_type in ("message", "app_mention"):
        # Filter out bot messages to avoid loops
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return None

        # Ignore message deletions or other subtypes
        subtype = event.get("subtype")
        if subtype and subtype not in ("file_share", "thread_broadcast"):
            return None

        user_id = event.get("user", "")
        channel_id = event.get("channel", "")

        # Filter bot's own messages
        if user_id == bot_user_id:
            return None

        # Channel filter (DMs always allowed)
        if allowed_channel_ids is not None:
            ids = set(allowed_channel_ids)
            if ids and channel_id not in ids:
                is_dm = channel_id.startswith("D")
                if not is_dm:
                    logger.debug(
                        "slack.filtered_channel",
                        channel_id=channel_id,
                        user_id=user_id,
                    )
                    return None

        # User filter
        if allowed_user_ids is not None:
            ids = set(allowed_user_ids)
            if ids and user_id not in ids:
                logger.debug(
                    "slack.filtered_user",
                    channel_id=channel_id,
                    user_id=user_id,
                )
                return None

        return SlackMessageEvent(
            channel_id=channel_id,
            user_id=user_id,
            text=event.get("text", ""),
            ts=event.get("ts", ""),
            thread_ts=event.get("thread_ts"),
            files=event.get("files"),
        )

    if event_type == "reaction_added":
        item = event.get("item", {})
        if item.get("type") != "message":
            return None

        user_id = event.get("user", "")
        channel_id = item.get("channel", "")

        # Filter bot's own reactions
        if user_id == bot_user_id:
            return None

        # Channel filter (DMs always allowed)
        if allowed_channel_ids is not None:
            ids = set(allowed_channel_ids)
            if ids and channel_id not in ids and not channel_id.startswith("D"):
                return None

        # User filter
        if allowed_user_ids is not None:
            ids = set(allowed_user_ids)
            if ids and user_id not in ids:
                return None

        return SlackReactionEvent(
            channel_id=channel_id,
            user_id=user_id,
            emoji=event.get("reaction", ""),
            ts=event.get("event_ts", ""),
            item_ts=item.get("ts", ""),
        )

    return None
