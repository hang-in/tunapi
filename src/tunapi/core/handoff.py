"""Handoff URI — async re-entry deep links for tunaDish.

A handoff URI encodes enough state to resume work on another device
or after a break: project, session, branch, and focus target.

Format: ``tunapi://open?project=X&session=Y&branch=Z&focus=W&run=R``

This is NOT real-time synchronization — it is "bookmark the current
work context so it can be picked up later".
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse


_SCHEME = "tunapi"
_HOST = "open"


@dataclass(frozen=True, slots=True)
class HandoffURI:
    """Minimal context needed to resume work."""

    project: str
    session_id: str | None = None
    branch_id: str | None = None  # conversation branch id
    focus: str | None = None  # discussion_id, review_id, etc.
    pending_run_id: str | None = None
    engine: str | None = None
    conversation_id: str | None = None


def build_handoff_uri(h: HandoffURI) -> str:
    """Serialize a :class:`HandoffURI` to a URI string."""
    params: dict[str, str] = {"project": h.project}
    if h.session_id is not None:
        params["session"] = h.session_id
    if h.branch_id is not None:
        params["branch"] = h.branch_id
    if h.focus is not None:
        params["focus"] = h.focus
    if h.pending_run_id is not None:
        params["run"] = h.pending_run_id
    if h.engine is not None:
        params["engine"] = h.engine
    if h.conversation_id is not None:
        params["conv_id"] = h.conversation_id
    return f"{_SCHEME}://{_HOST}?{urlencode(params)}"


def parse_handoff_uri(uri: str) -> HandoffURI | None:
    """Parse a URI string back into a :class:`HandoffURI`.

    Returns ``None`` if the URI is not a valid handoff URI.
    """
    parsed = urlparse(uri)
    if parsed.scheme != _SCHEME or parsed.netloc != _HOST:
        return None
    qs = parse_qs(parsed.query, keep_blank_values=False)

    project_list = qs.get("project")
    if not project_list:
        return None

    def _first(key: str) -> str | None:
        vals = qs.get(key)
        return vals[0] if vals else None

    return HandoffURI(
        project=project_list[0],
        session_id=_first("session"),
        branch_id=_first("branch"),
        focus=_first("focus"),
        pending_run_id=_first("run"),
        engine=_first("engine"),
        conversation_id=_first("conv_id"),
    )
