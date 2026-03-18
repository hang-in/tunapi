"""Slash command handlers for Mattermost transport.

Mattermost's native slash commands require external integration URLs.
Instead, we detect `/command` prefixes in regular messages and handle
them before passing to the engine dispatcher.
"""

from __future__ import annotations

from typing import Any

from ..logging import get_logger
from ..transport import RenderedMessage
from .chat_prefs import ChatPrefsStore

logger = get_logger(__name__)


def parse_slash_command(text: str) -> tuple[str | None, str]:
    """Parse a /command from message text.

    Returns (command_name, remaining_args).
    If not a slash command, returns (None, original_text).
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None, text
    parts = stripped.split(None, 1)
    cmd = parts[0][1:].lower()  # strip leading /
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


async def handle_help(
    *,
    runtime: Any,
    send: Any,
) -> None:
    """Show available commands."""
    engines = list(runtime.available_engine_ids())
    projects = sorted(set(runtime.project_aliases()), key=str.lower)

    lines = [
        "**tunapi commands**",
        "",
        "| Command | Description |",
        "|---------|-------------|",
        "| `/help` | Show this help |",
        "| `/new` | Start a new session |",
        "| `/model <engine>` | Switch default engine |",
        "| `/trigger <all\\|mentions>` | Set trigger mode |",
        "| `/file put` | Upload attached files to project |",
        "| `/file get <path>` | Download a file from project |",
        "| `/status` | Show current session info |",
        "| `/cancel` | Cancel running task |",
        "",
        f"**Engines:** {', '.join(f'`{e}`' for e in engines) or 'none'}",
        "",
        f"**Projects:** {', '.join(f'`{p}`' for p in projects) or 'none'}",
        "",
        "Prefix a message with `/<engine>` or `/<project>` to target directly.",
    ]
    await send(RenderedMessage(text="\n".join(lines)))


async def handle_model(
    args: str,
    *,
    channel_id: str,
    runtime: Any,
    chat_prefs: ChatPrefsStore | None,
    send: Any,
) -> None:
    """Switch the default engine for this channel."""
    engine = args.strip().lower()
    available = list(runtime.available_engine_ids())

    if not engine:
        current = None
        if chat_prefs:
            current = await chat_prefs.get_default_engine(channel_id)
        current_display = current or runtime.default_engine
        engine_list = ", ".join(f"`{e}`" for e in available)
        await send(RenderedMessage(
            text=f"Current engine: `{current_display}`\nAvailable: {engine_list}\n\nUsage: `/model <engine>`"
        ))
        return

    engine_map = {e.lower(): e for e in available}
    if engine not in engine_map:
        await send(RenderedMessage(
            text=f"Unknown engine `{engine}`. Available: {', '.join(f'`{e}`' for e in available)}"
        ))
        return

    if chat_prefs:
        await chat_prefs.set_default_engine(channel_id, engine_map[engine])

    await send(RenderedMessage(text=f"Default engine set to `{engine_map[engine]}`"))
    logger.info("command.model", channel_id=channel_id, engine=engine_map[engine])


async def handle_trigger(
    args: str,
    *,
    channel_id: str,
    chat_prefs: ChatPrefsStore | None,
    send: Any,
) -> None:
    """Set trigger mode for this channel."""
    mode = args.strip().lower()

    if mode not in ("all", "mentions"):
        current = "all"
        if chat_prefs:
            current = await chat_prefs.get_trigger_mode(channel_id) or "all"
        await send(RenderedMessage(
            text=f"Current trigger mode: `{current}`\n\nUsage: `/trigger all` or `/trigger mentions`"
        ))
        return

    if chat_prefs:
        await chat_prefs.set_trigger_mode(channel_id, mode)

    desc = "respond to all messages" if mode == "all" else "respond only when @mentioned"
    await send(RenderedMessage(text=f"Trigger mode set to `{mode}` — {desc}"))
    logger.info("command.trigger", channel_id=channel_id, mode=mode)


async def handle_status(
    *,
    channel_id: str,
    runtime: Any,
    chat_prefs: ChatPrefsStore | None,
    session_engine: str | None,
    has_session: bool,
    send: Any,
) -> None:
    """Show current session info."""
    engine = runtime.default_engine
    trigger = "all"
    if chat_prefs:
        engine = await chat_prefs.get_default_engine(channel_id) or engine
        trigger = await chat_prefs.get_trigger_mode(channel_id) or "all"

    lines = [
        "**Session status**",
        "",
        f"- Engine: `{engine}`",
        f"- Trigger: `{trigger}`",
        f"- Session: {'active' if has_session else 'none'}",
        f"- Channel: `{channel_id}`",
    ]
    await send(RenderedMessage(text="\n".join(lines)))


async def handle_cancel(
    *,
    channel_id: str,
    running_tasks: dict,
    send: Any,
) -> None:
    """Cancel the running task in this channel."""
    cancelled = False
    for ref, task in list(running_tasks.items()):
        if str(ref.channel_id) == channel_id:
            task.cancel_requested.set()
            cancelled = True
            break

    if cancelled:
        await send(RenderedMessage(text="Task cancelled."))
    else:
        await send(RenderedMessage(text="No running task to cancel."))
