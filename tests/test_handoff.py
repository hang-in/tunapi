"""Tests for core/handoff.py."""

from __future__ import annotations

from tunapi.core.handoff import HandoffURI, build_handoff_uri, parse_handoff_uri


class TestBuildHandoffURI:
    def test_project_only(self):
        h = HandoffURI(project="myproj")
        uri = build_handoff_uri(h)
        assert uri.startswith("tunapi://open?")
        assert "project=myproj" in uri

    def test_all_fields(self):
        h = HandoffURI(
            project="myproj",
            session_id="sess1",
            branch_id="br1",
            focus="disc1",
            pending_run_id="run1",
        )
        uri = build_handoff_uri(h)
        assert "project=myproj" in uri
        assert "session=sess1" in uri
        assert "branch=br1" in uri
        assert "focus=disc1" in uri
        assert "run=run1" in uri

    def test_none_fields_omitted(self):
        h = HandoffURI(project="p", session_id=None, branch_id="br1")
        uri = build_handoff_uri(h)
        assert "session" not in uri
        assert "branch=br1" in uri
        assert "focus" not in uri
        assert "run" not in uri


class TestParseHandoffURI:
    def test_roundtrip(self):
        original = HandoffURI(
            project="myproj",
            session_id="sess1",
            branch_id="br1",
            focus="disc1",
            pending_run_id="run1",
        )
        uri = build_handoff_uri(original)
        parsed = parse_handoff_uri(uri)
        assert parsed == original

    def test_project_only_roundtrip(self):
        original = HandoffURI(project="myproj")
        uri = build_handoff_uri(original)
        parsed = parse_handoff_uri(uri)
        assert parsed == original

    def test_partial_fields_roundtrip(self):
        original = HandoffURI(project="p", branch_id="br1", focus="review_42")
        uri = build_handoff_uri(original)
        parsed = parse_handoff_uri(uri)
        assert parsed == original

    def test_invalid_scheme(self):
        assert parse_handoff_uri("https://open?project=p") is None

    def test_invalid_host(self):
        assert parse_handoff_uri("tunapi://wrong?project=p") is None

    def test_missing_project(self):
        assert parse_handoff_uri("tunapi://open?session=s") is None

    def test_empty_string(self):
        assert parse_handoff_uri("") is None

    def test_garbage(self):
        assert parse_handoff_uri("not a uri at all") is None

    def test_special_characters_in_values(self):
        h = HandoffURI(project="my project", focus="disc/123")
        uri = build_handoff_uri(h)
        parsed = parse_handoff_uri(uri)
        assert parsed is not None
        assert parsed.project == "my project"
        assert parsed.focus == "disc/123"

    def test_engine_and_conv_id_roundtrip(self):
        h = HandoffURI(
            project="p",
            engine="claude",
            conversation_id="conv_abc",
        )
        uri = build_handoff_uri(h)
        assert "engine=claude" in uri
        assert "conv_id=conv_abc" in uri
        parsed = parse_handoff_uri(uri)
        assert parsed is not None
        assert parsed.engine == "claude"
        assert parsed.conversation_id == "conv_abc"

    def test_all_fields_roundtrip(self):
        original = HandoffURI(
            project="myproj",
            session_id="sess1",
            branch_id="br1",
            focus="disc1",
            pending_run_id="run1",
            engine="gemini",
            conversation_id="conv_xyz",
        )
        uri = build_handoff_uri(original)
        parsed = parse_handoff_uri(uri)
        assert parsed == original

    def test_engine_and_conv_id_absent_by_default(self):
        h = HandoffURI(project="p")
        uri = build_handoff_uri(h)
        assert "engine" not in uri
        assert "conv_id" not in uri
        parsed = parse_handoff_uri(uri)
        assert parsed is not None
        assert parsed.engine is None
        assert parsed.conversation_id is None
