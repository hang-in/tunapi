"""Tests for core/conversation_branch.py."""

from __future__ import annotations

import pytest

from tunapi.core.conversation_branch import ConversationBranch, ConversationBranchStore

pytestmark = pytest.mark.anyio


class TestConversationBranchStore:
    async def test_create_and_get(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        branch = await store.create(
            "proj",
            "experiment: new auth flow",
            parent_branch_id=None,
            git_branch="feat/auth",
        )
        assert isinstance(branch, ConversationBranch)
        assert branch.label == "experiment: new auth flow"
        assert branch.status == "active"
        assert branch.git_branch == "feat/auth"
        assert branch.parent_branch_id is None
        assert branch.created_at != ""
        assert branch.branch_id  # non-empty

        fetched = await store.get("proj", branch.branch_id)
        assert fetched is not None
        assert fetched.branch_id == branch.branch_id
        assert fetched.label == branch.label

    async def test_get_nonexistent(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        assert await store.get("proj", "nope") is None

    async def test_create_with_parent(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        parent = await store.create("proj", "main discussion")
        child = await store.create(
            "proj", "sub-topic", parent_branch_id=parent.branch_id
        )
        assert child.parent_branch_id == parent.branch_id

    async def test_list_all(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        await store.create("proj", "A")
        await store.create("proj", "B")
        branches = await store.list("proj")
        assert len(branches) == 2

    async def test_list_filter_status(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        b1 = await store.create("proj", "A")
        await store.create("proj", "B")
        await store.merge("proj", b1.branch_id)

        active = await store.list("proj", status="active")
        assert len(active) == 1
        assert active[0].label == "B"

        adopted = await store.list("proj", status="adopted")
        assert len(adopted) == 1
        assert adopted[0].branch_id == b1.branch_id

    async def test_merge(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        b = await store.create("proj", "X")
        result = await store.merge("proj", b.branch_id)
        assert result is not None
        assert result.status == "adopted"  # merge() now maps to adopted
        assert result.updated_at >= result.created_at

    async def test_discard(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        b = await store.create("proj", "X")
        result = await store.discard("proj", b.branch_id)
        assert result is not None
        assert result.status == "discarded"

    async def test_transition_nonexistent(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        assert await store.merge("proj", "nope") is None
        assert await store.discard("proj", "nope") is None

    async def test_link_session(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        b = await store.create("proj", "X")
        assert await store.link_session("proj", b.branch_id, "sess_123") is True

        fetched = await store.get("proj", b.branch_id)
        assert fetched is not None
        assert fetched.session_id == "sess_123"

    async def test_link_session_nonexistent(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        assert await store.link_session("proj", "nope", "s") is False

    async def test_link_git_branch(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        b = await store.create("proj", "X")
        assert await store.link_git_branch("proj", b.branch_id, "feat/new") is True

        fetched = await store.get("proj", b.branch_id)
        assert fetched is not None
        assert fetched.git_branch == "feat/new"

    async def test_link_git_branch_nonexistent(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        assert await store.link_git_branch("proj", "nope", "x") is False

    async def test_persistence(self, tmp_path):
        store1 = ConversationBranchStore(tmp_path)
        b = await store1.create("proj", "persisted")

        store2 = ConversationBranchStore(tmp_path)
        fetched = await store2.get("proj", b.branch_id)
        assert fetched is not None
        assert fetched.label == "persisted"

    async def test_projects_isolated(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        await store.create("a", "A branch")
        await store.create("b", "B branch")
        a_list = await store.list("a")
        b_list = await store.list("b")
        assert len(a_list) == 1
        assert len(b_list) == 1
        assert a_list[0].label == "A branch"
        assert b_list[0].label == "B branch"

    async def test_branch_id_is_unique(self, tmp_path):
        store = ConversationBranchStore(tmp_path)
        b1 = await store.create("proj", "A")
        b2 = await store.create("proj", "B")
        assert b1.branch_id != b2.branch_id
