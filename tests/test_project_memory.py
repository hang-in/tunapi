"""Tests for core/project_memory.py."""

from __future__ import annotations

import pytest

from tunapi.core.project_memory import (
    MemoryEntry,
    ProjectMemoryStore,
    generate_entry_id,
)

pytestmark = pytest.mark.anyio


def test_generate_entry_id_format():
    eid = generate_entry_id()
    parts = eid.split("_")
    assert len(parts) == 2
    assert parts[0].isdigit()
    assert len(parts[1]) == 8


def test_generate_entry_id_uniqueness():
    ids = {generate_entry_id() for _ in range(500)}
    assert len(ids) == 500


class TestProjectMemoryStore:
    async def test_add_and_get(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        entry = await store.add_entry(
            "myproject",
            type="decision",
            title="Use PostgreSQL",
            content="Chose PostgreSQL over MySQL for JSON support.",
            source="claude",
            tags=["db", "architecture"],
        )
        assert isinstance(entry, MemoryEntry)
        assert entry.type == "decision"
        assert entry.title == "Use PostgreSQL"
        assert entry.tags == ["db", "architecture"]

        fetched = await store.get_entry("myproject", entry.id)
        assert fetched is not None
        assert fetched.id == entry.id
        assert fetched.content == entry.content

    async def test_get_entry_not_found(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        assert await store.get_entry("myproject", "nonexistent") is None

    async def test_list_entries_newest_first(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        e1 = await store.add_entry(
            "p", type="idea", title="A", content="first", source="user"
        )
        e2 = await store.add_entry(
            "p", type="idea", title="B", content="second", source="user"
        )
        entries = await store.list_entries("p")
        assert len(entries) == 2
        assert entries[0].id == e2.id  # newest first
        assert entries[1].id == e1.id

    async def test_list_entries_filter_by_type(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        await store.add_entry(
            "p", type="decision", title="D1", content="d", source="user"
        )
        await store.add_entry("p", type="idea", title="I1", content="i", source="user")
        decisions = await store.list_entries("p", type="decision")
        assert len(decisions) == 1
        assert decisions[0].type == "decision"

    async def test_list_entries_limit(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        for i in range(10):
            await store.add_entry(
                "p", type="idea", title=f"Idea {i}", content="x", source="user"
            )
        entries = await store.list_entries("p", limit=3)
        assert len(entries) == 3

    async def test_search(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        await store.add_entry(
            "p",
            type="decision",
            title="DB choice",
            content="PostgreSQL for JSON support",
            source="user",
            tags=["database"],
        )
        await store.add_entry(
            "p", type="idea", title="Redis cache", content="Add caching", source="user"
        )

        results = await store.search("p", "postgresql")
        assert len(results) == 1
        assert results[0].title == "DB choice"

        results = await store.search("p", "database")
        assert len(results) == 1  # tag match

    async def test_delete_entry(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        entry = await store.add_entry(
            "p", type="context", title="T", content="C", source="user"
        )
        assert await store.delete_entry("p", entry.id) is True
        assert await store.get_entry("p", entry.id) is None
        assert await store.delete_entry("p", entry.id) is False

    async def test_get_context_summary(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        await store.add_entry(
            "p", type="decision", title="Use Rust", content="Performance", source="user"
        )
        await store.add_entry(
            "p", type="idea", title="Add cache", content="Redis layer", source="user"
        )
        summary = await store.get_context_summary("p")
        assert "Decision" in summary
        assert "Use Rust" in summary
        assert "Idea" in summary
        assert "Add cache" in summary

    async def test_get_context_summary_empty_project(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        assert await store.get_context_summary("empty") == ""

    async def test_persistence_across_instances(self, tmp_path):
        store1 = ProjectMemoryStore(tmp_path)
        entry = await store1.add_entry(
            "p", type="review", title="PR review", content="LGTM", source="gemini"
        )

        store2 = ProjectMemoryStore(tmp_path)
        fetched = await store2.get_entry("p", entry.id)
        assert fetched is not None
        assert fetched.title == "PR review"

    async def test_projects_isolated(self, tmp_path):
        store = ProjectMemoryStore(tmp_path)
        await store.add_entry(
            "proj_a", type="idea", title="A idea", content="x", source="user"
        )
        await store.add_entry(
            "proj_b", type="idea", title="B idea", content="y", source="user"
        )
        a_entries = await store.list_entries("proj_a")
        b_entries = await store.list_entries("proj_b")
        assert len(a_entries) == 1
        assert len(b_entries) == 1
        assert a_entries[0].title == "A idea"
        assert b_entries[0].title == "B idea"
