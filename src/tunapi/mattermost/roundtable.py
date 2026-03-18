"""Roundtable: sequential multi-agent opinion collection in a thread.

v0 — automatic rounds with transcript context.  No in-thread follow-up;
the user triggers via ``!rt "topic"`` and agents run to completion.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import anyio

from ..context import RunContext
from ..logging import bind_run_context, get_logger
from ..runner_bridge import IncomingMessage, handle_message
from ..transport import RenderedMessage, SendOptions
from ..transport_runtime import RoundtableConfig

if TYPE_CHECKING:
    from ..runner_bridge import RunningTasks
    from .bridge import MattermostBridgeConfig
    from .chat_prefs import ChatPrefsStore

logger = get_logger(__name__)


@dataclass(slots=True)
class RoundtableSession:
    thread_id: str
    channel_id: str
    topic: str
    engines: list[str]
    total_rounds: int
    current_round: int = 0
    transcript: list[tuple[str, str]] = field(default_factory=list)
    cancel_event: anyio.Event = field(default_factory=anyio.Event)


class RoundtableStore:
    """In-memory store mapping thread_id → active roundtable session."""

    def __init__(self) -> None:
        self._sessions: dict[str, RoundtableSession] = {}

    def get(self, thread_id: str) -> RoundtableSession | None:
        return self._sessions.get(thread_id)

    def put(self, session: RoundtableSession) -> None:
        self._sessions[session.thread_id] = session

    def remove(self, thread_id: str) -> RoundtableSession | None:
        return self._sessions.pop(thread_id, None)


def parse_rt_args(
    args: str,
    rt_config: RoundtableConfig,
) -> tuple[str, int, str | None]:
    """Parse ``!rt "topic" --rounds N``.

    Returns (topic, rounds, error_message | None).
    """
    try:
        tokens = shlex.split(args)
    except ValueError as exc:
        return "", 0, f"Parse error: {exc}"

    if not tokens:
        return "", 0, None  # show usage

    topic_parts: list[str] = []
    rounds = rt_config.rounds
    i = 0
    while i < len(tokens):
        if tokens[i] == "--rounds" and i + 1 < len(tokens):
            try:
                rounds = int(tokens[i + 1])
            except ValueError:
                return "", 0, f"Invalid rounds value: `{tokens[i + 1]}`"
            i += 2
            continue
        topic_parts.append(tokens[i])
        i += 1

    topic = " ".join(topic_parts).strip()
    if not topic:
        return "", 0, None  # show usage

    if rounds < 1:
        return "", 0, "Rounds must be at least 1."
    if rounds > rt_config.max_rounds:
        return "", 0, f"Maximum {rt_config.max_rounds} rounds allowed."

    return topic, rounds, None


def _build_round_prompt(
    topic: str,
    transcript: list[tuple[str, str]],
    round_num: int,
) -> str:
    """Build the prompt for a given round.

    Round 1: just the topic.
    Round 2+: previous responses as context + original topic.
    """
    if round_num <= 1 or not transcript:
        return topic

    context_lines: list[str] = []
    for engine, answer in transcript:
        # Truncate very long answers to keep prompt manageable
        trimmed = answer[:4000] + "..." if len(answer) > 4000 else answer
        context_lines.append(f"**[{engine}]**:\n{trimmed}")

    context_block = "\n\n".join(context_lines)
    return (
        f"이전 라운드 응답:\n\n{context_block}\n\n"
        f"---\n\n"
        f"위 의견들을 참고하여 다시 답변해주세요: {topic}"
    )


async def run_roundtable(
    session: RoundtableSession,
    *,
    cfg: MattermostBridgeConfig,
    chat_prefs: ChatPrefsStore | None,
    running_tasks: RunningTasks,
    ambient_context: RunContext | None,
) -> None:
    """Run all rounds of a roundtable session."""
    runtime = cfg.runtime
    transport = cfg.exec_cfg.transport
    send_opts = SendOptions(thread_id=session.thread_id)

    for round_num in range(1, session.total_rounds + 1):
        if session.cancel_event.is_set():
            await transport.send(
                channel_id=session.channel_id,
                message=RenderedMessage(text="🛑 Roundtable cancelled."),
                options=send_opts,
            )
            break

        session.current_round = round_num
        round_transcript: list[tuple[str, str]] = []

        if session.total_rounds > 1:
            await transport.send(
                channel_id=session.channel_id,
                message=RenderedMessage(
                    text=f"**--- Round {round_num}/{session.total_rounds} ---**",
                ),
                options=send_opts,
            )

        prompt = _build_round_prompt(
            session.topic, session.transcript, round_num,
        )

        for engine_id in session.engines:
            if session.cancel_event.is_set():
                break

            # Resolve runner
            resolved = runtime.resolve_runner(
                resume_token=None,
                engine_override=engine_id,
            )
            if resolved.issue:
                await transport.send(
                    channel_id=session.channel_id,
                    message=RenderedMessage(
                        text=f"⚠️ **[{engine_id}]**: {resolved.issue}",
                    ),
                    options=send_opts,
                )
                continue

            # Resolve context and cwd
            context = ambient_context
            context_line = runtime.format_context_line(context)
            try:
                cwd = runtime.resolve_run_cwd(context)
            except Exception as exc:  # noqa: BLE001
                logger.error("roundtable.resolve_cwd_error", error=str(exc))
                await transport.send(
                    channel_id=session.channel_id,
                    message=RenderedMessage(text=f"⚠️ {exc}"),
                    options=send_opts,
                )
                continue

            if cwd:
                bind_run_context(project=context.project if context else None)

            # Engine label in context line
            engine_label = f"`🤖 {engine_id}`"
            full_context = (
                f"{context_line} | {engine_label}"
                if context_line
                else engine_label
            )

            incoming = IncomingMessage(
                channel_id=session.channel_id,
                message_id=session.thread_id,
                text=prompt,
                thread_id=session.thread_id,
            )

            try:
                answer = await handle_message(
                    cfg.exec_cfg,
                    runner=resolved.runner,
                    incoming=incoming,
                    resume_token=None,
                    context=context,
                    context_line=full_context,
                    running_tasks=running_tasks,
                )
                if answer:
                    round_transcript.append((engine_id, answer))
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "roundtable.agent_error",
                    engine=engine_id,
                    error=str(exc),
                )
                await transport.send(
                    channel_id=session.channel_id,
                    message=RenderedMessage(
                        text=f"⚠️ **[{engine_id}]** error: {exc}",
                    ),
                    options=send_opts,
                )

        session.transcript.extend(round_transcript)

    # Completion marker
    if not session.cancel_event.is_set():
        rounds_label = f"{session.current_round}/{session.total_rounds} rounds"
        await transport.send(
            channel_id=session.channel_id,
            message=RenderedMessage(
                text=f"🏁 **Roundtable 완료** ({rounds_label})",
            ),
            options=send_opts,
        )
