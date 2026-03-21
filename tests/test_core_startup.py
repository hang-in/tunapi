"""Tests for core/startup.py."""

from tunapi.core.startup import build_startup_message


class _FakeRuntime:
    default_engine = "claude"

    def __init__(
        self,
        *,
        available: list[str] | None = None,
        missing: list[str] | None = None,
        bad_config: list[str] | None = None,
        projects: list[str] | None = None,
    ):
        self._available = available or ["claude", "gemini"]
        self._missing = missing or []
        self._bad_config = bad_config or []
        self._projects = projects or []

    def available_engine_ids(self):
        return self._available

    def missing_engine_ids(self):
        return self._missing

    def engine_ids_with_status(self, status):
        if status == "bad_config":
            return self._bad_config
        return []

    def project_aliases(self):
        return self._projects


class TestBuildStartupMessage:
    def test_basic(self):
        msg = build_startup_message(
            _FakeRuntime(),
            startup_pwd="/home/user",
            session_mode="chat",
            show_resume_line=True,
        )
        assert "tunapi is ready" in msg
        assert "claude" in msg
        assert "gemini" in msg
        assert "chat" in msg
        assert "shown" in msg
        assert "/home/user" in msg

    def test_slack_bold(self):
        msg = build_startup_message(
            _FakeRuntime(),
            startup_pwd="/tmp",
            session_mode="stateless",
            show_resume_line=False,
            bold="*",
            line_break="\n",
        )
        assert msg.startswith("*tunapi is ready*")
        assert "hidden" in msg

    def test_mattermost_bold(self):
        msg = build_startup_message(
            _FakeRuntime(),
            startup_pwd="/tmp",
            session_mode="chat",
            show_resume_line=True,
        )
        assert msg.startswith("**tunapi is ready**")

    def test_missing_engines(self):
        msg = build_startup_message(
            _FakeRuntime(missing=["codex"]),
            startup_pwd="/tmp",
            session_mode="chat",
            show_resume_line=True,
        )
        assert "not installed" in msg
        assert "codex" in msg

    def test_bad_config_engines(self):
        msg = build_startup_message(
            _FakeRuntime(bad_config=["pi"]),
            startup_pwd="/tmp",
            session_mode="chat",
            show_resume_line=True,
        )
        assert "misconfigured" in msg
        assert "pi" in msg

    def test_with_projects(self):
        msg = build_startup_message(
            _FakeRuntime(projects=["myproj", "other"]),
            startup_pwd="/tmp",
            session_mode="chat",
            show_resume_line=True,
        )
        assert "myproj" in msg
        assert "other" in msg

    def test_no_engines(self):
        msg = build_startup_message(
            _FakeRuntime(available=[]),
            startup_pwd="/tmp",
            session_mode="chat",
            show_resume_line=True,
        )
        assert "none" in msg
