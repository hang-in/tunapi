"""Slack API models using msgspec."""

from __future__ import annotations

from typing import Any, Literal

from msgspec import Struct


class SlackUser(Struct, omit_defaults=True):
    id: str
    name: str | None = None
    real_name: str | None = None
    is_bot: bool = False


class SlackChannel(Struct, omit_defaults=True):
    id: str
    name: str | None = None
    is_channel: bool = True
    is_group: bool = False
    is_im: bool = False


class SlackFile(Struct, omit_defaults=True):
    id: str
    name: str | None = None
    mimetype: str | None = None
    size: int | None = None
    url_private: str | None = None


class SlackMessage(Struct, omit_defaults=True):
    type: str = "message"
    channel: str | None = None
    user: str | None = None
    text: str | None = None
    ts: str | None = None
    thread_ts: str | None = None
    root_ts: str | None = None  # Sometimes used in some contexts
    files: list[SlackFile] | None = None
    bot_id: str | None = None
    subtype: str | None = None


class SlackResponse(Struct, omit_defaults=True):
    ok: bool
    error: str | None = None
    needed: str | None = None
    provided: str | None = None


class AuthTestResponse(SlackResponse):
    url: str | None = None
    team: str | None = None
    user: str | None = None
    team_id: str | None = None
    user_id: str | None = None
    bot_id: str | None = None


class ChatPostMessageResponse(SlackResponse):
    channel: str | None = None
    ts: str | None = None
    message: SlackMessage | None = None


class ReactionsAddResponse(SlackResponse):
    pass


class FilesUploadResponse(SlackResponse):
    file: SlackFile | None = None


class FilesGetUploadURLExternalResponse(SlackResponse):
    upload_url: str | None = None
    file_id: str | None = None


class FilesCompleteUploadExternalResponse(SlackResponse):
    files: list[dict[str, Any]] | None = None


# Socket Mode Models
class SocketModeEnvelope(Struct, omit_defaults=True):
    type: Literal["hello", "events_api", "disconnect", "slash_commands", "interactive"]
    envelope_id: str | None = None
    payload: dict[str, Any] | None = None
    accept_response_payload: dict[str, Any] | None = None
    retry_attempt: int = 0
    retry_reason: str | None = None
