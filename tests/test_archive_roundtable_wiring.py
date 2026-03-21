"""Integration tests for _archive_roundtable project-memory wiring.

Tests the archive path in both Mattermost and Slack loop modules to
verify that:
1. facade.save_roundtable() is called when project + facade are present
2. journal archive always happens regardless
3. facade absence / project absence → no project-memory write
4. facade exceptions are suppressed without affecting journal or send
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tunapi.core.memory_facade import ProjectMemoryFacade
from tunapi.core.roundtable import RoundtableSession

# Import the _archive_roundtable from both transports
from tunapi.mattermost.loop import (
    _archive_roundtable as mm_archive_roundtable,
)
from tunapi.slack.loop import (
    _archive_roundtable as slack_archive_roundtable,
)

pytestmark = pytest.mark.anyio


def _make_session(
    thread_id: str = "t1",
    channel_id: str = "ch1",
    topic: str = "API design",
) -> RoundtableSession:
    return RoundtableSession(
        thread_id=thread_id,
        channel_id=channel_id,
        topic=topic,
        engines=["claude", "gemini"],
        total_rounds=1,
        current_round=1,
        transcript=[("claude", "answer A"), ("gemini", "answer B")],
    )


def _make_send() -> AsyncMock:
    return AsyncMock()


def _make_journal() -> AsyncMock:
    journal = AsyncMock()
    journal.append = AsyncMock()
    return journal


# ── Run the same 4 scenarios against both transports ──────────────


_ARCHIVES = [
    pytest.param(mm_archive_roundtable, id="mattermost"),
    pytest.param(slack_archive_roundtable, id="slack"),
]


class TestProjectAndFacadePresent:
    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_facade_save_called(self, archive_fn, tmp_path):
        """facade.save_roundtable() IS called when project + facade present."""
        facade = ProjectMemoryFacade(tmp_path)
        journal = _make_journal()
        send = _make_send()
        session = _make_session()

        await archive_fn(
            session,
            journal,
            send,
            facade=facade,
            project="myproj",
            branch="feat/x",
        )

        # Journal was written
        journal.append.assert_called_once()

        # Send was called (user notification)
        send.assert_called_once()

        # Discussion record was persisted in project memory
        records = await facade.discussions.list_records("myproj")
        assert len(records) == 1
        assert records[0].discussion_id == "t1"
        assert records[0].topic == "API design"
        assert records[0].branch_name == "feat/x"
        assert len(records[0].transcript) == 2

        # Synthesis artifact was auto-created (auto_synthesis=True in loop)
        artifacts = await facade.synthesis.list("myproj")
        assert len(artifacts) == 1
        assert artifacts[0].source_id == "t1"

        # Structured session was auto-created (auto_structured=True in loop)
        structured = await facade.rt_structured.list("myproj")
        assert len(structured) == 1
        assert structured[0].session_id == "t1"
        assert structured[0].status == "completed"

    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_facade_save_without_branch(self, archive_fn, tmp_path):
        """branch=None → record saved but no branch link."""
        facade = ProjectMemoryFacade(tmp_path)
        journal = _make_journal()
        send = _make_send()
        session = _make_session()

        await archive_fn(
            session,
            journal,
            send,
            facade=facade,
            project="myproj",
            branch=None,
        )

        records = await facade.discussions.list_records("myproj")
        assert len(records) == 1
        assert records[0].branch_name is None


class TestProjectAbsent:
    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_no_project_no_save(self, archive_fn, tmp_path):
        """project=None → facade.save_roundtable() NOT called."""
        facade = ProjectMemoryFacade(tmp_path)
        journal = _make_journal()
        send = _make_send()
        session = _make_session()

        await archive_fn(
            session,
            journal,
            send,
            facade=facade,
            project=None,
        )

        # Journal still written
        journal.append.assert_called_once()
        send.assert_called_once()

        # No discussion record created
        records = await facade.discussions.list_records("myproj")
        assert len(records) == 0


class TestFacadeAbsent:
    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_no_facade_journal_only(self, archive_fn):
        """facade=None → journal archive only, no exception."""
        journal = _make_journal()
        send = _make_send()
        session = _make_session()

        await archive_fn(
            session,
            journal,
            send,
            facade=None,
            project="myproj",
        )

        journal.append.assert_called_once()
        send.assert_called_once()

    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_no_facade_no_project(self, archive_fn):
        """Both absent → clean execution."""
        journal = _make_journal()
        send = _make_send()
        session = _make_session()

        await archive_fn(session, journal, send)

        journal.append.assert_called_once()
        send.assert_called_once()


class TestFacadeException:
    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_facade_error_suppressed(self, archive_fn):
        """facade.save_roundtable() raises → exception suppressed,
        journal + send still complete."""
        facade = AsyncMock()
        facade.save_roundtable = AsyncMock(side_effect=RuntimeError("disk full"))

        journal = _make_journal()
        send = _make_send()
        session = _make_session()

        # Must not raise
        await archive_fn(
            session,
            journal,
            send,
            facade=facade,
            project="myproj",
        )

        # Journal was still written
        journal.append.assert_called_once()
        # User notification was still sent
        send.assert_called_once()
        # facade.save_roundtable was attempted
        facade.save_roundtable.assert_called_once()

    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_journal_error_does_not_block_facade(self, archive_fn, tmp_path):
        """journal.append raises → facade still runs (both suppressed)."""
        facade = ProjectMemoryFacade(tmp_path)

        journal = _make_journal()
        journal.append = AsyncMock(side_effect=RuntimeError("journal broken"))

        send = _make_send()
        session = _make_session()

        await archive_fn(
            session,
            journal,
            send,
            facade=facade,
            project="myproj",
        )

        # Send still completed
        send.assert_called_once()

        # Facade still saved (journal error didn't block it)
        records = await facade.discussions.list_records("myproj")
        assert len(records) == 1


class TestEmptyTranscript:
    @pytest.mark.parametrize("archive_fn", _ARCHIVES)
    async def test_empty_transcript_skips_both(self, archive_fn, tmp_path):
        """Empty transcript → neither journal nor facade write."""
        facade = ProjectMemoryFacade(tmp_path)
        journal = _make_journal()
        send = _make_send()

        session = RoundtableSession(
            thread_id="t2",
            channel_id="ch1",
            topic="empty",
            engines=["claude"],
            total_rounds=1,
        )
        # transcript is empty by default

        await archive_fn(
            session,
            journal,
            send,
            facade=facade,
            project="myproj",
        )

        journal.append.assert_not_called()
        send.assert_called_once()

        records = await facade.discussions.list_records("myproj")
        assert len(records) == 0
