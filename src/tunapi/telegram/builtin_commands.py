"""Builtin command router for the Telegram event loop.

Extracted from ``loop.py``.  Routes ``/file``, ``/ctx``, ``/new``,
``/topic``, ``/model``, ``/agent``, ``/reasoning``, ``/trigger``
to their respective handler coroutines.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from .commands.handlers import (
    handle_agent_command,
    handle_chat_ctx_command,
    handle_ctx_command,
    handle_file_command,
    handle_model_command,
    handle_new_command,
    handle_reasoning_command,
    handle_topic_command,
    handle_trigger_command,
)
from .topics import _topic_key

if TYPE_CHECKING:
    from .loop_state import TelegramCommandContext


def dispatch_builtin_command(
    *,
    ctx: TelegramCommandContext,
    command_id: str,
) -> bool:
    """Route a builtin command.  Returns True if dispatched."""
    cfg = ctx.cfg
    msg = ctx.msg
    args_text = ctx.args_text
    ambient_context = ctx.ambient_context
    topic_store = ctx.topic_store
    chat_prefs = ctx.chat_prefs
    resolved_scope = ctx.resolved_scope
    scope_chat_ids = ctx.scope_chat_ids
    reply = ctx.reply
    task_group = ctx.task_group

    if command_id == "file":
        if not cfg.files.enabled:
            handler = partial(
                reply,
                text="file transfer disabled; enable `[transports.telegram.files]`.",
            )
        else:
            handler = partial(
                handle_file_command,
                cfg,
                msg,
                args_text,
                ambient_context,
                topic_store,
            )
        task_group.start_soon(handler)
        return True

    if command_id == "ctx":
        topic_key = (
            _topic_key(msg, cfg, scope_chat_ids=scope_chat_ids)
            if cfg.topics.enabled and topic_store is not None
            else None
        )
        if topic_key is not None:
            handler = partial(
                handle_ctx_command,
                cfg,
                msg,
                args_text,
                topic_store,
                resolved_scope=resolved_scope,
                scope_chat_ids=scope_chat_ids,
            )
        else:
            handler = partial(
                handle_chat_ctx_command,
                cfg,
                msg,
                args_text,
                chat_prefs,
            )
        task_group.start_soon(handler)
        return True

    if cfg.topics.enabled and topic_store is not None:
        if command_id == "new":
            handler = partial(
                handle_new_command,
                cfg,
                msg,
                topic_store,
                resolved_scope=resolved_scope,
                scope_chat_ids=scope_chat_ids,
            )
        elif command_id == "topic":
            handler = partial(
                handle_topic_command,
                cfg,
                msg,
                args_text,
                topic_store,
                resolved_scope=resolved_scope,
                scope_chat_ids=scope_chat_ids,
            )
        else:
            handler = None
        if handler is not None:
            task_group.start_soon(handler)
            return True

    if command_id == "model":
        handler = partial(
            handle_model_command,
            cfg,
            msg,
            args_text,
            ambient_context,
            topic_store,
            chat_prefs,
            resolved_scope=resolved_scope,
            scope_chat_ids=scope_chat_ids,
        )
        task_group.start_soon(handler)
        return True

    if command_id == "agent":
        handler = partial(
            handle_agent_command,
            cfg,
            msg,
            args_text,
            ambient_context,
            topic_store,
            chat_prefs,
            resolved_scope=resolved_scope,
            scope_chat_ids=scope_chat_ids,
        )
        task_group.start_soon(handler)
        return True

    if command_id == "reasoning":
        handler = partial(
            handle_reasoning_command,
            cfg,
            msg,
            args_text,
            ambient_context,
            topic_store,
            chat_prefs,
            resolved_scope=resolved_scope,
            scope_chat_ids=scope_chat_ids,
        )
        task_group.start_soon(handler)
        return True

    if command_id == "trigger":
        handler = partial(
            handle_trigger_command,
            cfg,
            msg,
            args_text,
            ambient_context,
            topic_store,
            chat_prefs,
            resolved_scope=resolved_scope,
            scope_chat_ids=scope_chat_ids,
        )
        task_group.start_soon(handler)
        return True

    return False
