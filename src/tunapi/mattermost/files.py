"""File transfer for Mattermost transport (upload/download).

Pure validation and I/O helpers live in :mod:`tunapi.core.files`;
this module provides the Mattermost-specific download integration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.files import (
    DEFAULT_DENY_GLOBS,
    FilePutResult,
    deny_reason,
    format_bytes,
    normalize_relative_path,
    read_file,
    resolve_path,
    save_file,
    write_bytes_atomic,
)
from ..logging import get_logger

logger = get_logger(__name__)

# Re-export core symbols for backward compatibility
__all__ = [
    "DEFAULT_DENY_GLOBS",
    "FilePutResult",
    "deny_reason",
    "format_bytes",
    "handle_file_get",
    "handle_file_put",
    "normalize_relative_path",
    "read_file",
    "resolve_path",
    "save_file",
    "write_bytes_atomic",
]


async def handle_file_put(
    *,
    client: Any,  # MattermostClient
    channel_id: str,
    file_ids: list[str],
    target_dir: Path,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
    max_bytes: int = 20 * 1024 * 1024,
) -> list[FilePutResult]:
    """Download files from a Mattermost post and save to target_dir.

    Returns a list of :class:`FilePutResult` (one per file).
    """
    results: list[FilePutResult] = []

    for file_id in file_ids:
        # Get file info
        info = (
            await client._client.get_file_info(file_id)
            if hasattr(client._client, "get_file_info")
            else None
        )

        # Download file bytes
        data = await client.get_file(file_id)
        if data is None:
            results.append(
                FilePutResult(message=f"failed to download file `{file_id}`")
            )
            continue

        # Use file_id as filename if info not available
        filename = file_id
        if info and hasattr(info, "name"):
            filename = info.name

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
    client: Any,  # MattermostClient  (unused, kept for interface compat)
    channel_id: str,
    rel_path: str,
    root: Path,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
    max_bytes: int = 50 * 1024 * 1024,
) -> tuple[str | None, str | None, bytes | None]:
    """Read a file and return (filename, error, content).

    Returns (filename, None, bytes) on success or (None, error_msg, None) on failure.
    """
    return read_file(rel_path, root, deny_globs=deny_globs, max_bytes=max_bytes)
