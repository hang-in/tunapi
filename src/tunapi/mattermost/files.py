"""File transfer for Mattermost transport (upload/download)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from ..logging import get_logger

logger = get_logger(__name__)

DEFAULT_DENY_GLOBS = (
    ".git/**",
    ".env",
    ".envrc",
    "*.pem",
    ".ssh/**",
)


def normalize_relative_path(value: str) -> str | None:
    """Validate and normalize a relative path. Returns None if invalid."""
    if not value or not value.strip():
        return None
    path = value.strip().replace("\\", "/")
    if path.startswith("/") or path.startswith("~"):
        return None
    if ".." in path.split("/"):
        return None
    return path


def deny_reason(
    rel_path: str,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
) -> str | None:
    """Return a reason string if the path should be denied, else None."""
    posix = PurePosixPath(rel_path)
    for glob in deny_globs:
        if posix.match(glob):
            return f"path matches deny pattern `{glob}`"
    return None


def resolve_path(rel_path: str, root: Path) -> Path | None:
    """Resolve a relative path within root. Returns None if it escapes."""
    target = (root / rel_path).resolve()
    if not target.is_relative_to(root.resolve()):
        return None
    return target


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Atomically write bytes to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd) if not os.get_inheritable(fd) else None
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


async def handle_file_put(
    *,
    client: Any,  # MattermostClient
    channel_id: str,
    file_ids: list[str],
    target_dir: Path,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
    max_bytes: int = 20 * 1024 * 1024,
) -> list[str]:
    """Download files from a Mattermost post and save to target_dir.

    Returns a list of result messages (one per file).
    """
    results: list[str] = []

    for file_id in file_ids:
        # Get file info
        info = await client._client.get_file_info(file_id) if hasattr(client._client, 'get_file_info') else None

        # Download file bytes
        data = await client.get_file(file_id)
        if data is None:
            results.append(f"failed to download file `{file_id}`")
            continue

        if len(data) > max_bytes:
            results.append(f"file too large ({format_bytes(len(data))}, max {format_bytes(max_bytes)})")
            continue

        # Use file_id as filename if info not available
        filename = file_id
        if info and hasattr(info, 'name'):
            filename = info.name

        rel = normalize_relative_path(filename)
        if rel is None:
            results.append(f"invalid filename `{filename}`")
            continue

        reason = deny_reason(rel, deny_globs)
        if reason:
            results.append(f"denied: `{filename}` — {reason}")
            continue

        target = resolve_path(rel, target_dir)
        if target is None:
            results.append(f"path escape: `{filename}`")
            continue

        write_bytes_atomic(target, data)
        results.append(f"saved `{rel}` ({format_bytes(len(data))})")
        logger.info("file.put", filename=rel, size=len(data))

    return results


async def handle_file_get(
    *,
    client: Any,  # MattermostClient
    channel_id: str,
    rel_path: str,
    root: Path,
    deny_globs: tuple[str, ...] = DEFAULT_DENY_GLOBS,
    max_bytes: int = 50 * 1024 * 1024,
) -> tuple[str | None, str | None, bytes | None]:
    """Read a file and return (filename, error, content).

    Returns (filename, None, bytes) on success or (None, error_msg, None) on failure.
    """
    reason = deny_reason(rel_path, deny_globs)
    if reason:
        return None, f"denied: `{rel_path}` — {reason}", None

    target = resolve_path(rel_path, root)
    if target is None:
        return None, f"path escape: `{rel_path}`", None

    if not target.exists():
        return None, f"not found: `{rel_path}`", None

    if target.is_dir():
        return None, f"`{rel_path}` is a directory (zip not yet supported)", None

    size = target.stat().st_size
    if size > max_bytes:
        return None, f"too large: {format_bytes(size)} (max {format_bytes(max_bytes)})", None

    data = target.read_bytes()
    filename = target.name
    logger.info("file.get", filename=rel_path, size=len(data))
    return filename, None, data
