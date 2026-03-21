"""Command parsing — shared across Slack / Mattermost.

Slack/Mattermost use ``!`` prefix only.
Telegram uses its own parser (``telegram/commands/parse.py``) because
it supports only ``/`` prefix, handles multiline input, and strips
``@botname`` suffixes.
"""

from __future__ import annotations

COMMAND_PREFIX = "!"


def parse_command(text: str) -> tuple[str | None, str]:
    """Parse a ``!command`` from message text.

    Returns ``(command_name, remaining_args)``.
    If not a command, returns ``(None, original_text)``.
    """
    stripped = text.strip()
    if not stripped or stripped[0] != COMMAND_PREFIX:
        return None, text
    parts = stripped.split(None, 1)
    cmd = parts[0][1:].lower()  # strip leading prefix char
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args
