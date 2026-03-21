"""File transfer for Slack transport (upload/download).

Downloads files from Slack using ``url_private_download`` with Bearer auth,
then delegates validation and saving to :mod:`tunapi.core.files`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from ..core.files import (
    DEFAULT_DENY_GLOBS,
    FilePutResult,
    read_file,
    save_file,
)
from ..logging import get_logger

logger = get_logger(__name__)


async def _download_slack_file(
    url: str,
    bot_token: str,
    *,
    max_bytes: int = 20 * 1024 * 1024,
    timeout_s: float = 60,
) -> bytes | None:
    """Download a file from Slack's ``url_private_download``."""
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {bot_token}"},
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.content
            if len(data) > max_bytes:
                logger.warning(
                    "slack.file_too_large",
                    size=len(data),
                    max=max_bytes,
                )
                return None
            return data
    except Exception as exc:  # noqa: BLE001
        logger.error("slack.file_download_error", error=str(exc))
        return None


async def handle_file_put(
    *,
    bot_token: str,
    files: list[dict[str, Any]],
    target_dir: Path,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
    max_bytes: int = 20 * 1024 * 1024,
) -> list[FilePutResult]:
    """Download files from a Slack message and save to *target_dir*.

    *files* is the ``files`` list from a Slack event payload.  Each dict
    should contain at least ``name`` and ``url_private_download``.
    """
    results: list[FilePutResult] = []

    for file_info in files:
        url = file_info.get("url_private_download")
        filename = file_info.get("name") or file_info.get("id", "unknown")

        if not url:
            results.append(FilePutResult(message=f"no download URL for `{filename}`"))
            continue

        data = await _download_slack_file(url, bot_token, max_bytes=max_bytes)
        if data is None:
            results.append(FilePutResult(message=f"failed to download `{filename}`"))
            continue

        results.append(
            save_file(
                filename,
                data,
                target_dir,
                deny_globs=deny_globs,
                max_bytes=max_bytes,
            )
        )

    return results


async def handle_file_get(
    *,
    rel_path: str,
    root: Path,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
    max_bytes: int = 50 * 1024 * 1024,
) -> tuple[str | None, str | None, bytes | None]:
    """Read a file and return (filename, error, content).

    Returns (filename, None, bytes) on success or (None, error_msg, None)
    on failure.
    """
    return read_file(rel_path, root, deny_globs=deny_globs, max_bytes=max_bytes)
