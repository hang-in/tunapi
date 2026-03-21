"""Codex raw-event → Tunapi event translation.

This module is a **stateless** translation layer: it converts Codex
``ThreadEvent`` / ``ThreadItem`` objects into the ``TunapiEvent`` list that the
UI pipeline expects.  It intentionally owns *no* runner state — all mutable
bookkeeping (``CodexRunState``, ``_AgentMessageSummary``, etc.) stays in
``codex.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..events import EventFactory
from ..model import ActionPhase, EngineId, ResumeToken, TunapiEvent
from ..schemas import codex as codex_schema
from ..utils.paths import relativize_command

__all__ = [
    "translate_codex_event",
]

ENGINE: EngineId = "codex"

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _short_tool_name(server: str | None, tool: str | None) -> str:
    name = ".".join(part for part in (server, tool) if part)
    return name or "tool"


def _summarize_tool_result(result: Any) -> dict[str, Any] | None:
    if isinstance(result, codex_schema.McpToolCallItemResult):
        summary: dict[str, Any] = {}
        content = result.content
        if isinstance(content, list):
            summary["content_blocks"] = len(content)
        elif content is not None:
            summary["content_blocks"] = 1
        summary["has_structured"] = result.structured_content is not None
        return summary or None

    if isinstance(result, dict):
        summary = {}
        content = result.get("content")
        if isinstance(content, list):
            summary["content_blocks"] = len(content)
        elif content is not None:
            summary["content_blocks"] = 1

        structured_key: str | None = None
        if "structured_content" in result:
            structured_key = "structured_content"
        elif "structured" in result:
            structured_key = "structured"

        if structured_key is not None:
            summary["has_structured"] = result.get(structured_key) is not None
        return summary or None

    return None


def _normalize_change_list(changes: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for change in changes:
        path: str | None = None
        kind: str | None = None
        if isinstance(change, codex_schema.FileUpdateChange):
            path = change.path
            kind = change.kind
        elif isinstance(change, dict):
            path = change.get("path")
            kind = change.get("kind")
        if not isinstance(path, str) or not path:
            continue
        entry = {"path": path}
        if isinstance(kind, str) and kind:
            entry["kind"] = kind
        normalized.append(entry)
    return normalized


def _format_change_summary(changes: list[Any]) -> str:
    paths: list[str] = []
    for change in changes:
        if isinstance(change, codex_schema.FileUpdateChange):
            if change.path:
                paths.append(change.path)
            continue
        if isinstance(change, dict):
            path = change.get("path")
            if isinstance(path, str) and path:
                paths.append(path)
    if not paths:
        total = len(changes)
        if total <= 0:
            return "files"
        return f"{total} files"
    return ", ".join(str(path) for path in paths)


@dataclass(frozen=True, slots=True)
class _TodoSummary:
    done: int
    total: int
    next_text: str | None


def _summarize_todo_list(items: Any) -> _TodoSummary:
    if not isinstance(items, list):
        return _TodoSummary(done=0, total=0, next_text=None)

    done = 0
    total = 0
    next_text: str | None = None

    for raw_item in items:
        if isinstance(raw_item, codex_schema.TodoItem):
            total += 1
            if raw_item.completed:
                done += 1
                continue
            if next_text is None:
                next_text = raw_item.text
            continue
        if not isinstance(raw_item, dict):
            continue
        total += 1
        completed = raw_item.get("completed") is True
        if completed:
            done += 1
            continue
        if next_text is None:
            text = raw_item.get("text")
            next_text = str(text) if text is not None else None

    return _TodoSummary(done=done, total=total, next_text=next_text)


def _todo_title(summary: _TodoSummary) -> str:
    if summary.total <= 0:
        return "todo"
    if summary.next_text:
        return f"todo {summary.done}/{summary.total}: {summary.next_text}"
    return f"todo {summary.done}/{summary.total}: done"


# ---------------------------------------------------------------------------
# Item-level translation
# ---------------------------------------------------------------------------


def _translate_item_event(
    phase: ActionPhase, item: codex_schema.ThreadItem, *, factory: EventFactory
) -> list[TunapiEvent]:
    match item:
        case codex_schema.AgentMessageItem(
            id=action_id,
            text=text,
            phase="commentary",
        ):
            detail = {"phase": "commentary"}
            if phase in {"started", "updated"}:
                return [
                    factory.action(
                        phase=phase,
                        action_id=action_id,
                        kind="note",
                        title=text,
                        detail=detail,
                    )
                ]
            if phase == "completed":
                return [
                    factory.action_completed(
                        action_id=action_id,
                        kind="note",
                        title=text,
                        detail=detail,
                        ok=True,
                    )
                ]
            return []
        case codex_schema.AgentMessageItem():
            return []
        case codex_schema.ErrorItem(id=action_id, message=message):
            if phase != "completed":
                return []
            return [
                factory.action_completed(
                    action_id=action_id,
                    kind="warning",
                    title=message,
                    detail={"message": message},
                    ok=False,
                    message=message,
                    level="warning",
                ),
            ]
        case codex_schema.CommandExecutionItem(
            id=action_id,
            command=command,
            exit_code=exit_code,
            status=status,
        ):
            title = relativize_command(command)
            if phase in {"started", "updated"}:
                return [
                    factory.action(
                        phase=phase,
                        action_id=action_id,
                        kind="command",
                        title=title,
                    )
                ]
            if phase == "completed":
                ok = status == "completed"
                if isinstance(exit_code, int):
                    ok = ok and exit_code == 0
                detail = {"exit_code": exit_code, "status": status}
                return [
                    factory.action_completed(
                        action_id=action_id,
                        kind="command",
                        title=title,
                        detail=detail,
                        ok=ok,
                    ),
                ]
        case codex_schema.McpToolCallItem(
            id=action_id,
            server=server,
            tool=tool,
            arguments=arguments,
            status=status,
            result=result,
            error=error,
        ):
            title = _short_tool_name(server, tool)
            detail: dict[str, Any] = {
                "server": server,
                "tool": tool,
                "status": status,
                "arguments": arguments,
            }

            if phase in {"started", "updated"}:
                return [
                    factory.action(
                        phase=phase,
                        action_id=action_id,
                        kind="tool",
                        title=title,
                        detail=detail,
                    )
                ]
            if phase == "completed":
                ok = status == "completed" and error is None
                if error is not None:
                    detail["error_message"] = str(error.message)
                result_summary = _summarize_tool_result(result)
                if result_summary is not None:
                    detail["result_summary"] = result_summary
                return [
                    factory.action_completed(
                        action_id=action_id,
                        kind="tool",
                        title=title,
                        detail=detail,
                        ok=ok,
                    ),
                ]
        case codex_schema.WebSearchItem(id=action_id, query=query):
            detail = {"query": query}
            if phase in {"started", "updated"}:
                return [
                    factory.action(
                        phase=phase,
                        action_id=action_id,
                        kind="web_search",
                        title=query,
                        detail=detail,
                    )
                ]
            if phase == "completed":
                return [
                    factory.action_completed(
                        action_id=action_id,
                        kind="web_search",
                        title=query,
                        detail=detail,
                        ok=True,
                    )
                ]
        case codex_schema.FileChangeItem(id=action_id, changes=changes, status=status):
            if phase != "completed":
                return []
            title = _format_change_summary(changes)
            normalized_changes = _normalize_change_list(changes)
            detail = {
                "changes": normalized_changes,
                "status": status,
                "error": None,
            }
            ok = status == "completed"
            return [
                factory.action_completed(
                    action_id=action_id,
                    kind="file_change",
                    title=title,
                    detail=detail,
                    ok=ok,
                )
            ]
        case codex_schema.TodoListItem(id=action_id, items=items):
            summary = _summarize_todo_list(items)
            title = _todo_title(summary)
            detail = {"done": summary.done, "total": summary.total}
            if phase in {"started", "updated"}:
                return [
                    factory.action(
                        phase=phase,
                        action_id=action_id,
                        kind="note",
                        title=title,
                        detail=detail,
                    )
                ]
            if phase == "completed":
                return [
                    factory.action_completed(
                        action_id=action_id,
                        kind="note",
                        title=title,
                        detail=detail,
                        ok=True,
                    )
                ]
        case codex_schema.ReasoningItem(id=action_id, text=text):
            if phase in {"started", "updated"}:
                return [
                    factory.action(
                        phase=phase,
                        action_id=action_id,
                        kind="note",
                        title=text,
                    )
                ]
            if phase == "completed":
                return [
                    factory.action_completed(
                        action_id=action_id,
                        kind="note",
                        title=text,
                        ok=True,
                    )
                ]
    return []


# ---------------------------------------------------------------------------
# Top-level event translation
# ---------------------------------------------------------------------------


def translate_codex_event(
    event: codex_schema.ThreadEvent,
    *,
    title: str,
    factory: EventFactory,
) -> list[TunapiEvent]:
    match event:
        case codex_schema.ThreadStarted(thread_id=thread_id):
            token = ResumeToken(engine=ENGINE, value=thread_id)
            return [factory.started(token, title=title)]
        case codex_schema.ItemStarted(item=item):
            return _translate_item_event("started", item, factory=factory)
        case codex_schema.ItemUpdated(item=item):
            return _translate_item_event("updated", item, factory=factory)
        case codex_schema.ItemCompleted(item=item):
            return _translate_item_event("completed", item, factory=factory)
        case _:
            return []
