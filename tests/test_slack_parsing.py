"""Tests for Slack event parsing and access control filtering."""

from __future__ import annotations


from tunapi.slack.api_models import SocketModeEnvelope
from tunapi.slack.parsing import SlackMessageEvent, SlackReactionEvent, parse_envelope


def _make_message_envelope(
    *,
    user: str = "U123",
    channel: str = "C456",
    text: str = "hello",
    ts: str = "1234567890.123456",
    thread_ts: str | None = None,
    bot_id: str | None = None,
    subtype: str | None = None,
) -> SocketModeEnvelope:
    event: dict = {
        "type": "message",
        "user": user,
        "channel": channel,
        "text": text,
        "ts": ts,
    }
    if thread_ts:
        event["thread_ts"] = thread_ts
    if bot_id:
        event["bot_id"] = bot_id
    if subtype:
        event["subtype"] = subtype

    return SocketModeEnvelope(
        envelope_id="env-1",
        type="events_api",
        payload={"event": event},
    )


def _make_reaction_envelope(
    *,
    user: str = "U123",
    channel: str = "C456",
    reaction: str = "thumbsup",
    item_ts: str = "1234567890.123456",
) -> SocketModeEnvelope:
    return SocketModeEnvelope(
        envelope_id="env-2",
        type="events_api",
        payload={
            "event": {
                "type": "reaction_added",
                "user": user,
                "reaction": reaction,
                "event_ts": "1234567891.000000",
                "item": {
                    "type": "message",
                    "channel": channel,
                    "ts": item_ts,
                },
            }
        },
    )


class TestParseEnvelopeBasic:
    def test_message_event(self):
        envelope = _make_message_envelope()
        result = parse_envelope(envelope, bot_user_id="BBOT")
        assert isinstance(result, SlackMessageEvent)
        assert result.channel_id == "C456"
        assert result.user_id == "U123"
        assert result.text == "hello"

    def test_reaction_event(self):
        envelope = _make_reaction_envelope()
        result = parse_envelope(envelope, bot_user_id="BBOT")
        assert isinstance(result, SlackReactionEvent)
        assert result.emoji == "thumbsup"

    def test_non_events_api_ignored(self):
        envelope = SocketModeEnvelope(envelope_id="env-3", type="hello", payload=None)
        assert parse_envelope(envelope, bot_user_id="BBOT") is None

    def test_bot_message_filtered(self):
        envelope = _make_message_envelope(bot_id="B999")
        assert parse_envelope(envelope, bot_user_id="BBOT") is None

    def test_bot_subtype_filtered(self):
        envelope = _make_message_envelope(subtype="bot_message")
        assert parse_envelope(envelope, bot_user_id="BBOT") is None

    def test_message_changed_subtype_filtered(self):
        envelope = _make_message_envelope(subtype="message_changed")
        assert parse_envelope(envelope, bot_user_id="BBOT") is None

    def test_file_share_subtype_allowed(self):
        envelope = _make_message_envelope(subtype="file_share")
        result = parse_envelope(envelope, bot_user_id="BBOT")
        assert isinstance(result, SlackMessageEvent)


class TestAccessControl:
    def test_bot_own_message_filtered(self):
        envelope = _make_message_envelope(user="BBOT")
        assert parse_envelope(envelope, bot_user_id="BBOT") is None

    def test_bot_own_reaction_filtered(self):
        envelope = _make_reaction_envelope(user="BBOT")
        assert parse_envelope(envelope, bot_user_id="BBOT") is None

    def test_allowed_channel(self):
        envelope = _make_message_envelope(channel="C_OK")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=["C_OK"],
        )
        assert isinstance(result, SlackMessageEvent)

    def test_disallowed_channel(self):
        envelope = _make_message_envelope(channel="C_BAD")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=["C_OK"],
        )
        assert result is None

    def test_dm_always_allowed(self):
        """DM channels (starting with 'D') bypass channel filter."""
        envelope = _make_message_envelope(channel="D_DM_CHANNEL")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=["C_OK"],
        )
        assert isinstance(result, SlackMessageEvent)

    def test_allowed_user(self):
        envelope = _make_message_envelope(user="U_OK")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_user_ids=["U_OK"],
        )
        assert isinstance(result, SlackMessageEvent)

    def test_disallowed_user(self):
        envelope = _make_message_envelope(user="U_BAD")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_user_ids=["U_OK"],
        )
        assert result is None

    def test_empty_allowed_lists_allow_all(self):
        """Empty lists = no restriction (allow all)."""
        envelope = _make_message_envelope()
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=[],
            allowed_user_ids=[],
        )
        assert isinstance(result, SlackMessageEvent)

    def test_none_allowed_lists_allow_all(self):
        """None = no restriction (allow all)."""
        envelope = _make_message_envelope()
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=None,
            allowed_user_ids=None,
        )
        assert isinstance(result, SlackMessageEvent)

    def test_reaction_channel_filter(self):
        envelope = _make_reaction_envelope(channel="C_BAD")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=["C_OK"],
        )
        assert result is None

    def test_reaction_user_filter(self):
        envelope = _make_reaction_envelope(user="U_BAD")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_user_ids=["U_OK"],
        )
        assert result is None

    def test_combined_filters(self):
        """Both channel and user must be allowed."""
        envelope = _make_message_envelope(user="U_OK", channel="C_OK")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=["C_OK"],
            allowed_user_ids=["U_OK"],
        )
        assert isinstance(result, SlackMessageEvent)

    def test_combined_filters_user_denied(self):
        envelope = _make_message_envelope(user="U_BAD", channel="C_OK")
        result = parse_envelope(
            envelope,
            bot_user_id="BBOT",
            allowed_channel_ids=["C_OK"],
            allowed_user_ids=["U_OK"],
        )
        assert result is None


class TestDisconnectEnvelope:
    def test_disconnect_returns_none(self):
        """disconnect envelopes should not produce events (handled in client_api)."""
        envelope = SocketModeEnvelope(
            envelope_id="env-disc",
            type="disconnect",
            payload={"reason": "link_disabled"},
        )
        result = parse_envelope(envelope, bot_user_id="BBOT")
        assert result is None
