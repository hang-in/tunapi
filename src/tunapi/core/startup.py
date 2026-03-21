"""Startup summary message builder — shared across Slack / Mattermost."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..transport_runtime import TransportRuntime


def build_startup_message(
    runtime: TransportRuntime,
    *,
    startup_pwd: str,
    session_mode: str,
    show_resume_line: bool,
    bold: str = "**",
    line_break: str = "  \n",
) -> str:
    """Build a startup summary string.

    *bold* wraps the header (``**`` for Mattermost Markdown, ``*`` for
    Slack mrkdwn).  *line_break* is appended to each info line
    (``"  \\n"`` for Mattermost hard-break, ``"\\n"`` for Slack).
    """
    available_engines = list(runtime.available_engine_ids())
    missing_engines = list(runtime.missing_engine_ids())

    engine_list = ", ".join(available_engines) if available_engines else "none"
    notes: list[str] = []
    if missing_engines:
        notes.append(f"not installed: {', '.join(missing_engines)}")
    misconfigured = list(runtime.engine_ids_with_status("bad_config"))
    if misconfigured:
        notes.append(f"misconfigured: {', '.join(misconfigured)}")
    if notes:
        engine_list = f"{engine_list} ({'; '.join(notes)})"

    project_aliases = sorted(set(runtime.project_aliases()), key=str.lower)
    project_list = ", ".join(project_aliases) if project_aliases else "none"
    resume_label = "shown" if show_resume_line else "hidden"

    lb = line_break
    return (
        f"{bold}tunapi is ready{bold}\n\n"
        f"default: `{runtime.default_engine}`{lb}"
        f"engines: `{engine_list}`{lb}"
        f"projects: `{project_list}`{lb}"
        f"mode: `{session_mode}`{lb}"
        f"resume lines: `{resume_label}`{lb}"
        f"working in: `{startup_pwd}`"
    )
