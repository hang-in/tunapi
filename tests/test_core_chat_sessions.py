from pathlib import Path

import pytest

from tunapi.core.chat_sessions import ChatSessionStore
from tunapi.model import ResumeToken


@pytest.mark.anyio
async def test_chat_sessions_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "mattermost_sessions.json"
    store = ChatSessionStore(path)
    cwd = tmp_path / "repo"
    cwd.mkdir()

    await store.set("chan-1", ResumeToken(engine="claude", value="abc123"), cwd=cwd)

    stored = await store.get("chan-1", "claude", cwd=cwd)
    assert stored == ResumeToken(engine="claude", value="abc123")


@pytest.mark.anyio
async def test_chat_sessions_store_drops_resume_on_cwd_change(tmp_path: Path) -> None:
    path = tmp_path / "mattermost_sessions.json"
    dir1 = tmp_path / "repo1"
    dir2 = tmp_path / "repo2"
    dir1.mkdir()
    dir2.mkdir()

    store = ChatSessionStore(path)
    await store.set("chan-1", ResumeToken(engine="claude", value="abc123"), cwd=dir1)
    assert await store.get("chan-1", "claude", cwd=dir1) == ResumeToken(
        engine="claude",
        value="abc123",
    )

    store2 = ChatSessionStore(path)
    assert await store2.get("chan-1", "claude", cwd=dir2) is None
    assert await store2.has_any("chan-1") is False
