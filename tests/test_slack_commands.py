"""Tests for Slack command dispatch consistency and doctor/backend contracts."""

from __future__ import annotations

import re

import anyio

from tunapi.slack.commands import handle_help, parse_command
from tunapi.transport import RenderedMessage


def _extract_help_commands(help_text: str) -> set[str]:
    """Extract command names from help table rows (lines starting with |)."""
    commands: set[str] = set()
    for line in help_text.splitlines():
        if line.startswith("|") and "`!" in line:
            matches = re.findall(r"`!(\w+)", line)
            commands.update(matches)
    return commands


# The commands that _try_dispatch_command() actually handles
_DISPATCHER_COMMANDS = {
    "new",
    "help",
    "model",
    "models",
    "trigger",
    "project",
    "persona",
    "memory",
    "branch",
    "review",
    "context",
    "rt",
    "file",
    "status",
    "cancel",
}


def _get_help_text() -> str:
    """Run handle_help and return the captured text."""
    captured: list[str] = []

    async def fake_send(msg: RenderedMessage) -> None:
        captured.append(msg.text)

    class FakeRuntime:
        def available_engine_ids(self):
            return ["claude"]

        def project_aliases(self):
            return []

    async def _run():
        await handle_help(runtime=FakeRuntime(), send=fake_send)

    anyio.run(_run)
    assert captured
    return captured[0]


class TestHelpDispatcherConsistency:
    def test_help_commands_match_dispatcher(self):
        """Every command in help text must have a dispatcher case."""
        help_text = _get_help_text()
        help_commands = _extract_help_commands(help_text)
        assert help_commands, "should have extracted at least one command"

        undispatched = help_commands - _DISPATCHER_COMMANDS
        assert not undispatched, (
            f"Commands in help but not in dispatcher: {undispatched}"
        )

    def test_rt_in_help(self):
        """!rt should appear in help."""
        assert "!rt" in _get_help_text()

    def test_file_in_help(self):
        """!file should appear in help."""
        assert "!file" in _get_help_text()


class TestParseCommand:
    def test_slash_command_not_parsed(self):
        cmd, args = parse_command("/help")
        assert cmd is None

    def test_bang_command(self):
        cmd, args = parse_command("!model claude")
        assert cmd == "model"
        assert args == "claude"

    def test_no_command(self):
        cmd, args = parse_command("hello world")
        assert cmd is None

    def test_empty(self):
        cmd, args = parse_command("")
        assert cmd is None


class TestDoctorChannelIdContract:
    def test_doctor_accepts_allowed_channel_ids(self):
        """doctor slack checks must accept allowed_channel_ids parameter."""
        import inspect

        from tunapi.cli.doctor import _doctor_slack_checks

        sig = inspect.signature(_doctor_slack_checks)
        params = list(sig.parameters.keys())
        assert "allowed_channel_ids" in params
