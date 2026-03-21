"""Tests for channel-name-based auto project binding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from tunapi.config import ProjectConfig, ProjectsConfig
from tunapi.mattermost.api_models import Channel


# ---------------------------------------------------------------------------
# ProjectsConfig.register_discovered
# ---------------------------------------------------------------------------


class TestRegisterDiscovered:
    def _empty_config(self) -> ProjectsConfig:
        return ProjectsConfig(projects={}, chat_map={})

    def test_registers_new_project(self) -> None:
        cfg = self._empty_config()
        cfg.register_discovered("myProj", Path("/tmp/myProj"), "chan123")

        assert "myproj" in cfg.projects
        assert cfg.chat_map["chan123"] == "myproj"
        assert cfg.projects["myproj"].path == Path("/tmp/myProj")

    def test_skips_if_project_key_exists(self) -> None:
        cfg = ProjectsConfig(
            projects={
                "myproj": ProjectConfig(
                    alias="myProj",
                    path=Path("/tmp/old"),
                    worktrees_dir=Path(".worktrees"),
                )
            },
            chat_map={},
        )
        cfg.register_discovered("myProj", Path("/tmp/new"), "chan123")

        # Should not overwrite the project config, but should add the chat_id mapping
        assert cfg.projects["myproj"].path == Path("/tmp/old")
        assert cfg.chat_map["chan123"] == "myproj"

    def test_skips_if_chat_id_exists(self) -> None:
        cfg = ProjectsConfig(
            projects={},
            chat_map={"chan123": "other"},
        )
        cfg.register_discovered("myProj", Path("/tmp/myProj"), "chan123")

        assert "myproj" not in cfg.projects
        assert cfg.chat_map["chan123"] == "other"

    def test_default_engine(self) -> None:
        cfg = self._empty_config()
        cfg.register_discovered(
            "proj", Path("/tmp/proj"), "ch1", default_engine="gemini"
        )
        assert cfg.projects["proj"].default_engine == "gemini"


# ---------------------------------------------------------------------------
# _auto_bind_channel_project
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.anyio


def _make_cfg(
    projects_root: str | None, projects: ProjectsConfig | None = None
) -> MagicMock:
    """Build a minimal MattermostBridgeConfig mock."""
    cfg = MagicMock()
    cfg.runtime = MagicMock()
    cfg.runtime.projects_root = projects_root
    cfg.runtime._projects = projects or ProjectsConfig(projects={}, chat_map={})
    cfg.bot = MagicMock()
    cfg.bot._client = MagicMock()
    cfg.bot._client.get_channel = AsyncMock()
    return cfg


class TestAutoBindChannelProject:
    async def test_binds_matching_directory(self, tmp_path: Path) -> None:
        from tunapi.mattermost.loop import _auto_bind_channel_project

        # Create a subdirectory matching the channel name
        (tmp_path / "tunadish").mkdir()
        cfg = _make_cfg(str(tmp_path))
        cfg.bot._client.get_channel.return_value = Channel(id="ch1", name="tunadish")

        await _auto_bind_channel_project("ch1", cfg)

        projects = cfg.runtime._projects
        assert "tunadish" in projects.projects
        assert projects.chat_map["ch1"] == "tunadish"

    async def test_case_insensitive_match(self, tmp_path: Path) -> None:
        from tunapi.mattermost.loop import _auto_bind_channel_project

        (tmp_path / "TunaDish").mkdir()
        cfg = _make_cfg(str(tmp_path))
        cfg.bot._client.get_channel.return_value = Channel(id="ch1", name="tunadish")

        await _auto_bind_channel_project("ch1", cfg)

        projects = cfg.runtime._projects
        assert "tunadish" in projects.projects
        assert projects.projects["tunadish"].path == tmp_path / "TunaDish"

    async def test_no_match_does_nothing(self, tmp_path: Path) -> None:
        from tunapi.mattermost.loop import _auto_bind_channel_project

        (tmp_path / "other_project").mkdir()
        cfg = _make_cfg(str(tmp_path))
        cfg.bot._client.get_channel.return_value = Channel(id="ch1", name="tunadish")

        await _auto_bind_channel_project("ch1", cfg)

        assert len(cfg.runtime._projects.projects) == 0

    async def test_skips_when_already_bound(self, tmp_path: Path) -> None:
        from tunapi.mattermost.loop import _auto_bind_channel_project

        (tmp_path / "tunadish").mkdir()
        projects = ProjectsConfig(projects={}, chat_map={"ch1": "existing_project"})
        cfg = _make_cfg(str(tmp_path), projects)

        await _auto_bind_channel_project("ch1", cfg)

        # get_channel should not be called
        cfg.bot._client.get_channel.assert_not_called()

    async def test_skips_when_no_projects_root(self) -> None:
        from tunapi.mattermost.loop import _auto_bind_channel_project

        cfg = _make_cfg(None)

        await _auto_bind_channel_project("ch1", cfg)

        cfg.bot._client.get_channel.assert_not_called()

    async def test_skips_when_channel_lookup_fails(self, tmp_path: Path) -> None:
        from tunapi.mattermost.loop import _auto_bind_channel_project

        (tmp_path / "tunadish").mkdir()
        cfg = _make_cfg(str(tmp_path))
        cfg.bot._client.get_channel.return_value = None

        await _auto_bind_channel_project("ch1", cfg)

        assert len(cfg.runtime._projects.projects) == 0
