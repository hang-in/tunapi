"""Tests for core/review.py."""

from __future__ import annotations

import pytest

from tunapi.core.review import ReviewRequest, ReviewStore

pytestmark = pytest.mark.anyio


class TestReviewStore:
    async def test_request_and_get(self, tmp_path):
        store = ReviewStore(tmp_path)
        review = await store.request_review(
            "proj", artifact_id="art_1", artifact_version=1
        )
        assert isinstance(review, ReviewRequest)
        assert review.artifact_id == "art_1"
        assert review.artifact_version == 1
        assert review.status == "pending"
        assert review.reviewer_comment == ""
        assert review.resolved_at is None
        assert review.created_at != ""

        fetched = await store.get("proj", review.review_id)
        assert fetched is not None
        assert fetched.review_id == review.review_id

    async def test_get_nonexistent(self, tmp_path):
        store = ReviewStore(tmp_path)
        assert await store.get("proj", "nope") is None

    async def test_list_all(self, tmp_path):
        store = ReviewStore(tmp_path)
        await store.request_review("proj", artifact_id="a1")
        await store.request_review("proj", artifact_id="a2")
        reviews = await store.list("proj")
        assert len(reviews) == 2

    async def test_list_filter_status(self, tmp_path):
        store = ReviewStore(tmp_path)
        r1 = await store.request_review("proj", artifact_id="a1")
        await store.request_review("proj", artifact_id="a2")
        await store.approve("proj", r1.review_id)

        pending = await store.list("proj", status="pending")
        assert len(pending) == 1
        assert pending[0].artifact_id == "a2"

        approved = await store.list("proj", status="approved")
        assert len(approved) == 1
        assert approved[0].review_id == r1.review_id

    async def test_approve(self, tmp_path):
        store = ReviewStore(tmp_path)
        r = await store.request_review("proj", artifact_id="a1")
        result = await store.approve("proj", r.review_id, comment="LGTM")
        assert result is not None
        assert result.status == "approved"
        assert result.reviewer_comment == "LGTM"
        assert result.resolved_at is not None

    async def test_reject(self, tmp_path):
        store = ReviewStore(tmp_path)
        r = await store.request_review("proj", artifact_id="a1")
        result = await store.reject("proj", r.review_id, comment="Needs work")
        assert result is not None
        assert result.status == "rejected"
        assert result.reviewer_comment == "Needs work"
        assert result.resolved_at is not None

    async def test_approve_without_comment(self, tmp_path):
        store = ReviewStore(tmp_path)
        r = await store.request_review("proj", artifact_id="a1")
        result = await store.approve("proj", r.review_id)
        assert result is not None
        assert result.status == "approved"
        assert result.reviewer_comment == ""

    async def test_resolve_nonexistent(self, tmp_path):
        store = ReviewStore(tmp_path)
        assert await store.approve("proj", "nope") is None
        assert await store.reject("proj", "nope") is None

    async def test_artifact_version(self, tmp_path):
        store = ReviewStore(tmp_path)
        r = await store.request_review("proj", artifact_id="a1", artifact_version=3)
        assert r.artifact_version == 3

    async def test_persistence(self, tmp_path):
        store1 = ReviewStore(tmp_path)
        r = await store1.request_review("proj", artifact_id="a1")

        store2 = ReviewStore(tmp_path)
        fetched = await store2.get("proj", r.review_id)
        assert fetched is not None
        assert fetched.artifact_id == "a1"

    async def test_projects_isolated(self, tmp_path):
        store = ReviewStore(tmp_path)
        await store.request_review("a", artifact_id="x")
        await store.request_review("b", artifact_id="y")
        assert len(await store.list("a")) == 1
        assert len(await store.list("b")) == 1
