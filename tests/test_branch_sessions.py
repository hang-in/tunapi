"""Tests for core/branch_sessions.py."""

from __future__ import annotations

import pytest

from tunapi.core.branch_sessions import BranchRecord, BranchSessionStore

pytestmark = pytest.mark.anyio


class TestBranchSessionStore:
    async def test_create_and_get(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        record = await store.create_branch(
            "proj",
            "feat/login",
            parent_branch="main",
            description="Login feature",
        )
        assert isinstance(record, BranchRecord)
        assert record.branch_name == "feat/login"
        assert record.project_alias == "proj"
        assert record.status == "active"
        assert record.parent_branch == "main"
        assert record.description == "Login feature"
        assert record.created_at > 0

        fetched = await store.get_branch("proj", "feat/login")
        assert fetched is not None
        assert fetched.branch_name == "feat/login"

    async def test_get_nonexistent(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        assert await store.get_branch("proj", "no-such") is None

    async def test_list_branches_all(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("proj", "feat/a", description="A")
        await store.create_branch("proj", "feat/b", description="B")
        branches = await store.list_branches("proj")
        assert len(branches) == 2

    async def test_list_branches_filter_status(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("proj", "feat/a")
        await store.create_branch("proj", "feat/b")
        await store.merge_branch("proj", "feat/a")

        active = await store.list_branches("proj", status="active")
        assert len(active) == 1
        assert active[0].branch_name == "feat/b"

        merged = await store.list_branches("proj", status="merged")
        assert len(merged) == 1
        assert merged[0].branch_name == "feat/a"

    async def test_merge_branch(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("proj", "feat/x")
        result = await store.merge_branch("proj", "feat/x")
        assert result is not None
        assert result.status == "merged"
        assert result.updated_at >= result.created_at

    async def test_abandon_branch(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("proj", "feat/x")
        result = await store.abandon_branch("proj", "feat/x")
        assert result is not None
        assert result.status == "abandoned"

    async def test_transition_nonexistent(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        assert await store.merge_branch("proj", "nope") is None
        assert await store.abandon_branch("proj", "nope") is None

    async def test_link_entry(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("proj", "feat/x")
        assert await store.link_entry("proj", "feat/x", "entry_001") is True

        record = await store.get_branch("proj", "feat/x")
        assert record is not None
        assert "entry_001" in record.related_entry_ids

    async def test_link_entry_idempotent(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("proj", "feat/x")
        await store.link_entry("proj", "feat/x", "e1")
        await store.link_entry("proj", "feat/x", "e1")
        record = await store.get_branch("proj", "feat/x")
        assert record is not None
        assert record.related_entry_ids.count("e1") == 1

    async def test_link_entry_nonexistent_branch(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        assert await store.link_entry("proj", "nope", "e1") is False

    async def test_persistence(self, tmp_path):
        store1 = BranchSessionStore(tmp_path)
        await store1.create_branch("proj", "feat/y", description="Y")

        store2 = BranchSessionStore(tmp_path)
        fetched = await store2.get_branch("proj", "feat/y")
        assert fetched is not None
        assert fetched.description == "Y"

    async def test_projects_isolated(self, tmp_path):
        store = BranchSessionStore(tmp_path)
        await store.create_branch("a", "feat/x")
        await store.create_branch("b", "feat/x")
        a_branches = await store.list_branches("a")
        b_branches = await store.list_branches("b")
        assert len(a_branches) == 1
        assert a_branches[0].project_alias == "a"
        assert len(b_branches) == 1
        assert b_branches[0].project_alias == "b"
