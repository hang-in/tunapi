"""Tests for core/discussion_records.py."""

from __future__ import annotations

from dataclasses import dataclass, field

import anyio
import pytest

from tunapi.core.discussion_records import (
    DiscussionRecord,
    DiscussionRecordStore,
    _transcript_to_json,
    _transcript_to_tuples,
)

pytestmark = pytest.mark.anyio

_SAMPLE_TRANSCRIPT: list[tuple[str, str]] = [
    ("claude", "Claude says hello"),
    ("gemini", "Gemini responds"),
]


class TestTranscriptConversion:
    def test_tuple_to_json(self):
        result = _transcript_to_json(_SAMPLE_TRANSCRIPT)
        assert result == [
            ["claude", "Claude says hello"],
            ["gemini", "Gemini responds"],
        ]

    def test_json_to_tuples(self):
        json_form = [["claude", "hi"], ["gemini", "hey"]]
        result = _transcript_to_tuples(json_form)
        assert result == [("claude", "hi"), ("gemini", "hey")]

    def test_roundtrip(self):
        json_form = _transcript_to_json(_SAMPLE_TRANSCRIPT)
        tuples = _transcript_to_tuples(json_form)
        assert tuples == _SAMPLE_TRANSCRIPT


class TestDiscussionRecordStore:
    async def test_create_and_get(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        record = await store.create_record(
            "proj",
            topic="API design",
            participants=["claude", "gemini"],
            rounds=1,
            transcript=_SAMPLE_TRANSCRIPT,
            summary="Agreed on REST",
        )
        assert isinstance(record, DiscussionRecord)
        assert record.topic == "API design"
        assert record.participants == ["claude", "gemini"]
        assert record.rounds == 1
        assert record.summary == "Agreed on REST"
        assert record.status == "open"
        assert len(record.transcript) == 2

        fetched = await store.get_record("proj", record.discussion_id)
        assert fetched is not None
        assert fetched.topic == "API design"

    async def test_create_with_explicit_id(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        record = await store.create_record(
            "proj",
            discussion_id="rt:thread123",
            topic="Topic",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "answer")],
        )
        assert record.discussion_id == "rt:thread123"

    async def test_get_nonexistent(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        assert await store.get_record("proj", "nope") is None

    async def test_list_records(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        await store.create_record(
            "proj",
            topic="T1",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "a")],
        )
        await store.create_record(
            "proj",
            topic="T2",
            participants=["gemini"],
            rounds=1,
            transcript=[("gemini", "b")],
        )
        records = await store.list_records("proj")
        assert len(records) == 2

    async def test_list_records_filter_status(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        r1 = await store.create_record(
            "proj",
            topic="T1",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "a")],
        )
        await store.create_record(
            "proj",
            topic="T2",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "b")],
        )
        await store.update_resolution("proj", r1.discussion_id, "Done")

        open_records = await store.list_records("proj", status="open")
        assert len(open_records) == 1
        assert open_records[0].topic == "T2"

        resolved = await store.list_records("proj", status="resolved")
        assert len(resolved) == 1
        assert resolved[0].topic == "T1"

    async def test_update_resolution(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        r = await store.create_record(
            "proj",
            topic="T",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "a")],
        )
        updated = await store.update_resolution(
            "proj", r.discussion_id, "Use PostgreSQL"
        )
        assert updated is not None
        assert updated.resolution == "Use PostgreSQL"
        assert updated.status == "resolved"

    async def test_update_resolution_nonexistent(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        assert await store.update_resolution("proj", "nope", "x") is None

    async def test_add_action_item(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        r = await store.create_record(
            "proj",
            topic="T",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "a")],
        )
        item = await store.add_action_item(
            "proj", r.discussion_id, "Write tests", assignee="claude"
        )
        assert item is not None
        assert item.description == "Write tests"
        assert item.assignee == "claude"
        assert item.done is False

        fetched = await store.get_record("proj", r.discussion_id)
        assert fetched is not None
        assert len(fetched.action_items) == 1

    async def test_add_action_item_nonexistent(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        assert await store.add_action_item("proj", "nope", "x") is None

    async def test_complete_action_item(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        r = await store.create_record(
            "proj",
            topic="T",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "a")],
        )
        item = await store.add_action_item("proj", r.discussion_id, "Do it")
        assert item is not None
        assert (
            await store.complete_action_item("proj", r.discussion_id, item.id) is True
        )

        fetched = await store.get_record("proj", r.discussion_id)
        assert fetched is not None
        assert fetched.action_items[0].done is True

    async def test_complete_action_item_nonexistent(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        assert await store.complete_action_item("proj", "nope", "nope") is False

    async def test_archive_record(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        r = await store.create_record(
            "proj",
            topic="T",
            participants=["claude"],
            rounds=1,
            transcript=[("claude", "a")],
        )
        assert await store.archive_record("proj", r.discussion_id) is True
        fetched = await store.get_record("proj", r.discussion_id)
        assert fetched is not None
        assert fetched.status == "archived"

    async def test_archive_nonexistent(self, tmp_path):
        store = DiscussionRecordStore(tmp_path)
        assert await store.archive_record("proj", "nope") is False

    async def test_persistence(self, tmp_path):
        store1 = DiscussionRecordStore(tmp_path)
        r = await store1.create_record(
            "proj",
            topic="T",
            participants=["claude"],
            rounds=1,
            transcript=_SAMPLE_TRANSCRIPT,
        )

        store2 = DiscussionRecordStore(tmp_path)
        fetched = await store2.get_record("proj", r.discussion_id)
        assert fetched is not None
        assert fetched.topic == "T"
        assert len(fetched.transcript) == 2


class TestFromRoundtableSession:
    def test_factory(self):
        @dataclass
        class FakeSession:
            thread_id: str = "t1"
            topic: str = "test topic"
            engines: list[str] = field(default_factory=lambda: ["claude", "gemini"])
            current_round: int = 2
            transcript: list[tuple[str, str]] = field(
                default_factory=lambda: [("claude", "hi"), ("gemini", "hey")]
            )
            cancel_event: object = field(default_factory=lambda: anyio.Event())
            completed: bool = True

        session = FakeSession()
        record = DiscussionRecordStore.from_roundtable_session(session, "proj")
        assert record.discussion_id == "t1"
        assert record.project_alias == "proj"
        assert record.topic == "test topic"
        assert record.participants == ["claude", "gemini"]
        assert record.rounds == 2
        assert len(record.transcript) == 2
        assert record.status == "open"
        assert record.summary is None

    def test_factory_with_summary(self):
        @dataclass
        class FakeSession:
            thread_id: str = "t2"
            topic: str = "design"
            engines: list[str] = field(default_factory=lambda: ["claude"])
            current_round: int = 1
            transcript: list[tuple[str, str]] = field(
                default_factory=lambda: [("claude", "answer")]
            )
            cancel_event: object = field(default_factory=lambda: anyio.Event())
            completed: bool = True

        session = FakeSession()
        record = DiscussionRecordStore.from_roundtable_session(
            session, "proj", summary="Decided on REST"
        )
        assert record.summary == "Decided on REST"
