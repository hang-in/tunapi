"""Tests for multi-transport settings resolution, CLI orchestration, and DTO/Handoff regression."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tunapi import cli
from tunapi.backends import EngineBackend
from tunapi.core.handoff import HandoffURI, build_handoff_uri, parse_handoff_uri
from tunapi.settings import TunapiSettings
from tunapi.transports import SetupResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _DummyLock:
    released: bool = False
    transport_id: str | None = None

    def release(self) -> None:
        self.released = True


class _FakeTransport:
    id = "fake"
    description = "fake"

    def __init__(self, tid: str = "fake") -> None:
        self.id = tid
        self.build_calls: list[dict] = []
        self._prepare_only = False
        self._prepared = False

    def check_setup(self, engine_backend, *, transport_override=None):
        return SetupResult(issues=[], config_path=Path("."))

    def interactive_setup(self, *, force: bool) -> bool:
        return True

    def lock_token(self, *, transport_config, _config_path):
        return f"lock_{self.id}"

    def build_and_run(
        self,
        *,
        transport_config,
        config_path,
        runtime,
        final_notify,
        default_engine_override,
    ):
        self.build_calls.append(
            {
                "transport_config": transport_config,
                "runtime": runtime,
            }
        )
        self._prepared = True

    async def async_run(self):
        pass


def _engine_backend():
    return EngineBackend(id="codex", build_runner=lambda _cfg, _path: None)


# ---------------------------------------------------------------------------
# 1. Settings resolution tests
# ---------------------------------------------------------------------------


class TestResolveTransportIds:
    def test_single_transport_default(self):
        s = TunapiSettings.model_validate(
            {
                "transport": "mattermost",
                "transports": {},
            }
        )
        assert s.resolve_transport_ids() == ["mattermost"]

    def test_cli_override_wins(self):
        s = TunapiSettings.model_validate(
            {
                "transport": "mattermost",
                "transports_enabled": ["mattermost", "slack"],
                "transports": {},
            }
        )
        assert s.resolve_transport_ids(override="telegram") == ["telegram"]

    def test_transports_enabled_list(self):
        s = TunapiSettings.model_validate(
            {
                "transport": "mattermost",
                "transports_enabled": ["mattermost", "slack"],
                "transports": {},
            }
        )
        assert s.resolve_transport_ids() == ["mattermost", "slack"]

    def test_transports_enabled_empty_falls_back(self):
        s = TunapiSettings.model_validate(
            {
                "transport": "telegram",
                "transports_enabled": [],
                "transports": {},
            }
        )
        # Empty list is falsy → falls back to transport
        assert s.resolve_transport_ids() == ["telegram"]

    def test_transports_enabled_none_falls_back(self):
        s = TunapiSettings.model_validate(
            {
                "transport": "slack",
                "transports": {},
            }
        )
        assert s.resolve_transport_ids() == ["slack"]


# ---------------------------------------------------------------------------
# 2. CLI orchestration tests
# ---------------------------------------------------------------------------


def _setup_monkeypatch(
    monkeypatch, tmp_path, *, transport_ids=None, settings_extra=None
):
    """Wire up CLI mocks for _run_auto_router."""
    settings_dict = {
        "transport": "fake",
        "transports": {},
    }
    if settings_extra:
        settings_dict.update(settings_extra)
    settings = TunapiSettings.model_validate(settings_dict)
    # Patch transport_config to return empty dict for any transport
    settings.transport_config = lambda tid, **kw: {}
    config_path = tmp_path / "tunapi.toml"

    transports = {}
    if transport_ids:
        for tid in transport_ids:
            transports[tid] = _FakeTransport(tid)
    else:
        transports["fake"] = _FakeTransport("fake")

    locks: list[_DummyLock] = []

    def fake_get_transport(tid, allowlist=None):
        if tid not in transports:
            transports[tid] = _FakeTransport(tid)
        return transports[tid]

    def fake_lock(path, token, transport_id=None):
        lock = _DummyLock(transport_id=transport_id)
        locks.append(lock)
        return lock

    class _Spec:
        def to_runtime(self, *, config_path):
            return "runtime"

    monkeypatch.setattr(
        cli,
        "_resolve_setup_engine",
        lambda _override: (None, None, None, "codex", _engine_backend()),
    )
    monkeypatch.setattr(cli, "_resolve_transport_id", lambda _override: "fake")
    monkeypatch.setattr(cli, "get_transport", fake_get_transport)
    monkeypatch.setattr(cli, "load_settings", lambda: (settings, config_path))
    monkeypatch.setattr(cli, "setup_logging", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "build_runtime_spec", lambda **_kwargs: _Spec())
    monkeypatch.setattr(cli, "acquire_config_lock", fake_lock)

    return transports, locks, settings


class TestCLISingleTransport:
    def test_single_transport_calls_build_and_run(self, monkeypatch, tmp_path):
        transports, locks, _ = _setup_monkeypatch(monkeypatch, tmp_path)
        cli._run_auto_router(
            default_engine_override=None,
            transport_override="fake",
            final_notify=True,
            debug=False,
            onboard=False,
        )
        assert len(transports["fake"].build_calls) == 1
        assert len(locks) == 1
        assert locks[0].released

    def test_single_transport_lock_released_on_success(self, monkeypatch, tmp_path):
        _, locks, _ = _setup_monkeypatch(monkeypatch, tmp_path)
        cli._run_auto_router(
            default_engine_override=None,
            transport_override="fake",
            final_notify=True,
            debug=False,
            onboard=False,
        )
        assert all(lk.released for lk in locks)


class TestCLIMultiTransport:
    def test_multi_transport_prepares_all(self, monkeypatch, tmp_path):
        transports, locks, _ = _setup_monkeypatch(
            monkeypatch,
            tmp_path,
            transport_ids=["mm", "slack"],
            settings_extra={"transports_enabled": ["mm", "slack"]},
        )
        cli._run_auto_router(
            default_engine_override=None,
            transport_override=None,
            final_notify=True,
            debug=False,
            onboard=False,
        )
        # Both transports should have build_and_run called
        assert transports["mm"]._prepared
        assert transports["slack"]._prepared

    def test_multi_transport_acquires_separate_locks(self, monkeypatch, tmp_path):
        _, locks, _ = _setup_monkeypatch(
            monkeypatch,
            tmp_path,
            transport_ids=["mm", "slack"],
            settings_extra={"transports_enabled": ["mm", "slack"]},
        )
        cli._run_auto_router(
            default_engine_override=None,
            transport_override=None,
            final_notify=True,
            debug=False,
            onboard=False,
        )
        assert len(locks) == 2
        assert all(lk.released for lk in locks)

    def test_multi_transport_sets_prepare_only(self, monkeypatch, tmp_path):
        transports, _, _ = _setup_monkeypatch(
            monkeypatch,
            tmp_path,
            transport_ids=["mm", "slack"],
            settings_extra={"transports_enabled": ["mm", "slack"]},
        )
        cli._run_auto_router(
            default_engine_override=None,
            transport_override=None,
            final_notify=True,
            debug=False,
            onboard=False,
        )
        # _prepare_only should have been set before build_and_run
        assert transports["mm"]._prepare_only
        assert transports["slack"]._prepare_only


# ---------------------------------------------------------------------------
# 3. Backend prepare_only tests
# ---------------------------------------------------------------------------


class TestBackendPrepareOnly:
    def test_mattermost_prepare_only(self):
        from tunapi.mattermost.backend import MattermostBackend

        b = MattermostBackend()
        assert b._prepared is False
        assert b._prepare_only is False

    def test_slack_prepare_only(self):
        from tunapi.slack.backend import SlackBackend

        b = SlackBackend()
        assert b._prepared is False
        assert b._prepare_only is False

    def test_telegram_prepare_only(self):
        from tunapi.telegram.backend import TelegramBackend

        b = TelegramBackend()
        assert b._prepared is False
        assert b._prepare_only is False


# ---------------------------------------------------------------------------
# 4. DTO/Handoff regression tests
# ---------------------------------------------------------------------------


class TestDTORegression:
    async def test_dto_has_project_metadata_fields(self, tmp_path):
        from tunapi.core.memory_facade import ProjectMemoryFacade

        facade = ProjectMemoryFacade(tmp_path)
        dto = await facade.get_project_context_dto(
            "proj", project_path="/home/user/proj", default_engine="claude"
        )
        assert dto.project_alias == "proj"
        assert dto.project_path == "/home/user/proj"
        assert dto.default_engine == "claude"

    async def test_dto_backward_compat(self, tmp_path):
        from tunapi.core.memory_facade import ProjectMemoryFacade

        facade = ProjectMemoryFacade(tmp_path)
        # No project_path/default_engine → None
        dto = await facade.get_project_context_dto("proj")
        assert dto.project_alias == "proj"
        assert dto.project_path is None
        assert dto.default_engine is None


class TestHandoffRegression:
    def test_roundtrip_with_new_fields(self):
        h = HandoffURI(
            project="p",
            engine="claude",
            conversation_id="conv1",
        )
        uri = build_handoff_uri(h)
        parsed = parse_handoff_uri(uri)
        assert parsed == h

    def test_roundtrip_without_new_fields(self):
        h = HandoffURI(project="p")
        uri = build_handoff_uri(h)
        parsed = parse_handoff_uri(uri)
        assert parsed == h
        assert parsed.engine is None
        assert parsed.conversation_id is None

    def test_full_roundtrip(self):
        h = HandoffURI(
            project="myproj",
            session_id="s1",
            branch_id="b1",
            focus="f1",
            pending_run_id="r1",
            engine="gemini",
            conversation_id="conv_xyz",
        )
        assert parse_handoff_uri(build_handoff_uri(h)) == h


pytestmark = pytest.mark.anyio
