"""Low-level Slack HTTP and WebSocket client using httpx and websockets."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import httpx
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from ..logging import get_logger
from .api_models import (
    AuthTestResponse,
    ChatPostMessageResponse,
    FilesCompleteUploadExternalResponse,
    FilesGetUploadURLExternalResponse,
    ReactionsAddResponse,
    SlackChannel,
    SlackResponse,
    SlackUser,
    SocketModeEnvelope,
)

logger = get_logger(__name__)

_MAX_BACKOFF = 16.0


class SlackRetryAfter(Exception):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"Retry after {retry_after} seconds")


class HttpSlackClient:
    """Low-level Slack HTTP client using httpx."""

    def __init__(
        self,
        bot_token: str,
        app_token: str | None = None,
        *,
        base_url: str = "https://slack.com/api/",
        timeout_s: float = 30,
    ) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=timeout_s,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        use_app_token: bool = False,
    ) -> dict[str, Any]:
        headers = {}
        if use_app_token:
            if not self._app_token:
                raise ValueError("App token required for this request")
            headers["Authorization"] = f"Bearer {self._app_token}"

        response = await self._client.request(
            method, path, json=json_data, params=params, headers=headers
        )

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 1))
            raise SlackRetryAfter(retry_after)

        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            logger.error(
                "slack.api_error",
                method=method,
                path=path,
                error=error,
                data=data,
            )
        return data

    async def auth_test(self) -> AuthTestResponse:
        data = await self._request("POST", "auth.test")
        from msgspec.json import decode

        return decode(json.dumps(data).encode(), type=AuthTestResponse)

    async def post_message(
        self,
        channel: str,
        text: str,
        *,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
    ) -> ChatPostMessageResponse:
        payload = {
            "channel": channel,
            "text": text,
            "thread_ts": thread_ts,
            "reply_broadcast": reply_broadcast,
        }
        data = await self._request("POST", "chat.postMessage", json_data=payload)
        from msgspec.json import decode

        return decode(json.dumps(data).encode(), type=ChatPostMessageResponse)

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
    ) -> ChatPostMessageResponse:
        payload = {
            "channel": channel,
            "ts": ts,
            "text": text,
        }
        data = await self._request("POST", "chat.update", json_data=payload)
        from msgspec.json import decode

        return decode(json.dumps(data).encode(), type=ChatPostMessageResponse)

    async def delete_message(self, channel: str, ts: str) -> SlackResponse:
        payload = {"channel": channel, "ts": ts}
        data = await self._request("POST", "chat.delete", json_data=payload)
        from msgspec.json import decode

        return decode(json.dumps(data).encode(), type=SlackResponse)

    async def add_reaction(
        self, channel: str, timestamp: str, name: str
    ) -> ReactionsAddResponse:
        payload = {"channel": channel, "timestamp": timestamp, "name": name}
        data = await self._request("POST", "reactions.add", json_data=payload)
        from msgspec.json import decode

        return decode(json.dumps(data).encode(), type=ReactionsAddResponse)

    async def get_user_info(self, user: str) -> SlackUser | None:
        data = await self._request("GET", "users.info", params={"user": user})
        if not data.get("ok"):
            return None
        from msgspec.json import decode

        return decode(json.dumps(data["user"]).encode(), type=SlackUser)

    async def get_channel_info(self, channel: str) -> SlackChannel | None:
        data = await self._request(
            "GET", "conversations.info", params={"channel": channel}
        )
        if not data.get("ok"):
            return None
        from msgspec.json import decode

        return decode(json.dumps(data["channel"]).encode(), type=SlackChannel)

    # File uploads (v2)
    async def get_upload_url(
        self, filename: str, length: int, alt_text: str | None = None
    ) -> FilesGetUploadURLExternalResponse:
        params: dict[str, Any] = {"filename": filename, "length": length}
        if alt_text:
            params["alt_text"] = alt_text
        data = await self._request("GET", "files.getUploadURLExternal", params=params)
        from msgspec.json import decode

        return decode(json.dumps(data).encode(), type=FilesGetUploadURLExternalResponse)

    async def complete_upload_external(
        self,
        file_id: str,
        thread_ts: str | None = None,
        channel_id: str | None = None,
    ) -> FilesCompleteUploadExternalResponse:
        files = [{"id": file_id}]
        payload: dict[str, Any] = {"files": files}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        if channel_id:
            payload["channel_id"] = channel_id

        data = await self._request(
            "POST", "files.completeUploadExternal", json_data=payload
        )
        from msgspec.json import decode

        return decode(
            json.dumps(data).encode(), type=FilesCompleteUploadExternalResponse
        )

    async def upload_content(self, url: str, content: bytes) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, content=content)
            resp.raise_for_status()

    # Socket Mode
    async def apps_connections_open(self) -> str | None:
        data = await self._request("POST", "apps.connections.open", use_app_token=True)
        if data.get("ok"):
            return data.get("url")
        return None

    @asynccontextmanager
    async def socket_mode_connect(
        self,
    ) -> AsyncIterator[AsyncIterator[SocketModeEnvelope]]:
        """Connect to Slack Socket Mode with proper reconnection.

        Each reconnection fetches a fresh URL via ``apps.connections.open``.
        The ``disconnect`` envelope triggers an immediate reconnect cycle.
        Exponential backoff (1s → 16s max) is applied on failures, reset on
        successful connection (``hello`` envelope received).
        """

        async def _event_stream() -> AsyncIterator[SocketModeEnvelope]:
            from msgspec.json import decode

            backoff = 1.0

            while True:
                # Get a fresh WebSocket URL for each connection attempt
                try:
                    wss_url = await self.apps_connections_open()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "slack.socket_mode_url_failed",
                        error=str(exc),
                        backoff_s=backoff,
                    )
                    await anyio.sleep(backoff)
                    backoff = min(backoff * 2, _MAX_BACKOFF)
                    continue

                if not wss_url:
                    logger.error("slack.socket_mode_url_empty", backoff_s=backoff)
                    await anyio.sleep(backoff)
                    backoff = min(backoff * 2, _MAX_BACKOFF)
                    continue

                logger.info("slack.socket_mode_connecting", url=wss_url[:60])

                try:
                    async with ws_connect(wss_url) as websocket:
                        async for message in websocket:
                            try:
                                envelope = decode(
                                    message
                                    if isinstance(message, bytes)
                                    else message.encode(),
                                    type=SocketModeEnvelope,
                                )
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "slack.envelope_decode_error",
                                    error=str(exc),
                                )
                                continue

                            # ACK the envelope
                            if envelope.envelope_id:
                                ack: dict[str, Any] = {
                                    "envelope_id": envelope.envelope_id,
                                }
                                if envelope.accept_response_payload:
                                    ack["payload"] = envelope.accept_response_payload
                                await websocket.send(json.dumps(ack))

                            if envelope.type == "hello":
                                # Successful connection — reset backoff
                                backoff = 1.0
                                logger.info("slack.socket_mode_connected")
                                continue

                            if envelope.type == "disconnect":
                                # Slack requests reconnection
                                reason = ""
                                if envelope.payload:
                                    reason = str(envelope.payload.get("reason", ""))
                                logger.info(
                                    "slack.socket_mode_disconnect_requested",
                                    reason=reason,
                                )
                                break  # → outer loop gets new URL

                            yield envelope

                except ConnectionClosed as exc:
                    logger.warning(
                        "slack.socket_mode_connection_closed",
                        code=exc.rcvd.code if exc.rcvd else None,
                        reason=(str(exc.rcvd.reason)[:100] if exc.rcvd else None),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "slack.socket_mode_error",
                        error=str(exc),
                        error_type=exc.__class__.__name__,
                        backoff_s=backoff,
                    )
                    await anyio.sleep(backoff)
                    backoff = min(backoff * 2, _MAX_BACKOFF)
                    continue

                # Normal disconnect or ConnectionClosed — reconnect immediately
                # (backoff only applies to errors above)

        yield _event_stream()
