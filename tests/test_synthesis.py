"""Tests for core/synthesis.py."""

from __future__ import annotations

import pytest

from tunapi.core.discussion_records import ActionItem, DiscussionRecord
from tunapi.core.synthesis import SynthesisArtifact, SynthesisStore

pytestmark = pytest.mark.anyio


class TestSynthesisStore:
    async def test_create_and_get(self, tmp_path):
        store = SynthesisStore(tmp_path)
        artifact = await store.create(
            "proj",
            source_type="roundtable",
            source_id="rt:t1",
            thesis="Use REST for MVP",
            agreements=["REST is simpler"],
            disagreements=["GraphQL has better DX"],
            open_questions=["Migration path?"],
        )
        assert isinstance(artifact, SynthesisArtifact)
        assert artifact.source_type == "roundtable"
        assert artifact.source_id == "rt:t1"
        assert artifact.thesis == "Use REST for MVP"
        assert artifact.version == 1
        assert artifact.agreements == ["REST is simpler"]
        assert artifact.disagreements == ["GraphQL has better DX"]
        assert artifact.open_questions == ["Migration path?"]
        assert artifact.created_at != ""

        fetched = await store.get("proj", artifact.artifact_id)
        assert fetched is not None
        assert fetched.thesis == "Use REST for MVP"

    async def test_get_nonexistent(self, tmp_path):
        store = SynthesisStore(tmp_path)
        assert await store.get("proj", "nope") is None

    async def test_create_with_action_items(self, tmp_path):
        store = SynthesisStore(tmp_path)
        items = [
            ActionItem(id="a1", description="Write spec"),
            ActionItem(id="a2", description="Review PR", assignee="claude"),
        ]
        artifact = await store.create(
            "proj",
            source_type="discussion",
            source_id="d1",
            thesis="Agreed",
            action_items=items,
        )
        assert len(artifact.action_items) == 2
        assert artifact.action_items[0].description == "Write spec"
        assert artifact.action_items[1].assignee == "claude"

    async def test_list_all(self, tmp_path):
        store = SynthesisStore(tmp_path)
        await store.create("proj", source_type="roundtable", source_id="r1", thesis="A")
        await store.create("proj", source_type="discussion", source_id="d1", thesis="B")
        artifacts = await store.list("proj")
        assert len(artifacts) == 2

    async def test_list_filter_source_type(self, tmp_path):
        store = SynthesisStore(tmp_path)
        await store.create("proj", source_type="roundtable", source_id="r1", thesis="A")
        await store.create("proj", source_type="discussion", source_id="d1", thesis="B")
        await store.create("proj", source_type="manual", source_id="m1", thesis="C")

        rt_only = await store.list("proj", source_type="roundtable")
        assert len(rt_only) == 1
        assert rt_only[0].thesis == "A"

        manual_only = await store.list("proj", source_type="manual")
        assert len(manual_only) == 1
        assert manual_only[0].thesis == "C"

    async def test_update_version(self, tmp_path):
        store = SynthesisStore(tmp_path)
        artifact = await store.create(
            "proj",
            source_type="roundtable",
            source_id="r1",
            thesis="v1 thesis",
            agreements=["old agreement"],
        )
        assert artifact.version == 1

        updated = await store.update_version(
            "proj",
            artifact.artifact_id,
            thesis="v2 thesis",
            agreements=["new agreement"],
            open_questions=["new question"],
        )
        assert updated is not None
        assert updated.version == 2
        assert updated.thesis == "v2 thesis"
        assert updated.agreements == ["new agreement"]
        assert updated.open_questions == ["new question"]
        # Unchanged fields preserved
        assert updated.disagreements == []

    async def test_update_version_partial(self, tmp_path):
        store = SynthesisStore(tmp_path)
        artifact = await store.create(
            "proj",
            source_type="discussion",
            source_id="d1",
            thesis="original",
            agreements=["keep this"],
        )
        updated = await store.update_version(
            "proj",
            artifact.artifact_id,
            thesis="revised",
        )
        assert updated is not None
        assert updated.thesis == "revised"
        assert updated.agreements == ["keep this"]  # not overwritten

    async def test_update_version_nonexistent(self, tmp_path):
        store = SynthesisStore(tmp_path)
        assert await store.update_version("proj", "nope", thesis="x") is None

    async def test_persistence(self, tmp_path):
        store1 = SynthesisStore(tmp_path)
        artifact = await store1.create(
            "proj", source_type="manual", source_id="m1", thesis="persisted"
        )

        store2 = SynthesisStore(tmp_path)
        fetched = await store2.get("proj", artifact.artifact_id)
        assert fetched is not None
        assert fetched.thesis == "persisted"

    async def test_projects_isolated(self, tmp_path):
        store = SynthesisStore(tmp_path)
        await store.create("a", source_type="manual", source_id="1", thesis="A")
        await store.create("b", source_type="manual", source_id="2", thesis="B")
        assert len(await store.list("a")) == 1
        assert len(await store.list("b")) == 1


class TestFromDiscussionRecord:
    def test_maps_summary_to_thesis(self):
        record = DiscussionRecord(
            discussion_id="d1",
            project_alias="proj",
            topic="API design",
            participants=["claude", "gemini"],
            rounds=2,
            transcript=[["claude", "hi"], ["gemini", "hey"]],
            created_at=1.0,
            summary="Use REST",
            action_items=[
                ActionItem(id="a1", description="Write spec"),
            ],
        )
        artifact = SynthesisStore.from_discussion_record(record)
        assert artifact.source_type == "discussion"
        assert artifact.source_id == "d1"
        assert artifact.thesis == "Use REST"
        assert artifact.version == 1
        assert len(artifact.action_items) == 1
        assert artifact.action_items[0].description == "Write spec"

    def test_none_summary_maps_to_empty_thesis(self):
        record = DiscussionRecord(
            discussion_id="d2",
            project_alias="proj",
            topic="T",
            participants=["claude"],
            rounds=1,
            transcript=[["claude", "a"]],
            created_at=1.0,
            summary=None,
        )
        artifact = SynthesisStore.from_discussion_record(record)
        assert artifact.thesis == ""
        assert artifact.action_items == []
