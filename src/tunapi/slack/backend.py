"""Slack TransportBackend — entry point for the plugin system."""

from __future__ import annotations

import os
from pathlib import Path

import anyio

from ..backends import EngineBackend
from ..logging import get_logger
from ..runner_bridge import ExecBridgeConfig
from ..transport_runtime import TransportRuntime
from ..transports import SetupResult, TransportBackend
from .bridge import SlackBridgeConfig, SlackPresenter, SlackTransport
from .client import SlackClient

logger = get_logger(__name__)


def _build_startup_message(
    runtime: TransportRuntime,
    *,
    startup_pwd: str,
    session_mode: str,
    show_resume_line: bool,
) -> str:
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

    return (
        f"*tunapi is ready*\n\n"
        f"default: `{runtime.default_engine}`\n"
        f"engines: `{engine_list}`\n"
        f"projects: `{project_list}`\n"
        f"mode: `{session_mode}`\n"
        f"resume lines: `{resume_label}`\n"
        f"working in: `{startup_pwd}`"
    )


class SlackBackend(TransportBackend):
    id = "slack"
    description = "Slack bot (Socket Mode)"

    def check_setup(
        self,
        engine_backend: EngineBackend,
        *,
        transport_override: str | None = None,
    ) -> SetupResult:
        # Minimal check — full validation is in `tunapi doctor`
        from ..config import HOME_CONFIG_PATH

        return SetupResult(issues=[], config_path=HOME_CONFIG_PATH)

    async def interactive_setup(self, *, force: bool) -> bool:
        return False  # Not implemented for Slack

    def lock_token(self, *, transport_config: object, _config_path: Path) -> str | None:
        if isinstance(transport_config, dict):
            return transport_config.get("bot_token")
        return getattr(transport_config, "bot_token", None)

    def build_and_run(
        self,
        *,
        transport_config: object,
        config_path: Path,
        runtime: TransportRuntime,
        final_notify: bool,
        default_engine_override: str | None,
    ) -> None:
        if not isinstance(transport_config, dict):
            raise TypeError("transport_config must be a dict for Slack")

        bot_token = transport_config.get("bot_token", "")
        app_token = transport_config.get("app_token", "")
        channel_id = transport_config.get("channel_id") or None
        session_mode = transport_config.get("session_mode", "stateless")
        show_resume_line = transport_config.get("show_resume_line", True)
        message_overflow = transport_config.get("message_overflow", "trim")
        allowed_channel_ids = tuple(transport_config.get("allowed_channel_ids", []))
        allowed_user_ids = tuple(transport_config.get("allowed_user_ids", []))
        trigger_mode = transport_config.get("trigger_mode", "mentions")

        files_cfg = transport_config.get("files", {})
        voice_cfg = transport_config.get("voice", {})
        files_enabled = (
            files_cfg.get("enabled", False) if isinstance(files_cfg, dict) else False
        )
        voice_enabled = (
            voice_cfg.get("enabled", False) if isinstance(voice_cfg, dict) else False
        )

        if files_enabled:
            logger.warning(
                "slack.files_not_implemented",
                detail="files.enabled=true but Slack file transfer is not yet implemented",
            )
        if voice_enabled:
            logger.warning(
                "slack.voice_not_implemented",
                detail="voice.enabled=true but Slack voice transcription is not yet implemented",
            )

        if not bot_token or not app_token:
            raise ValueError("Slack transport requires bot_token and app_token")

        startup_msg = _build_startup_message(
            runtime,
            startup_pwd=os.getcwd(),
            session_mode=session_mode,
            show_resume_line=show_resume_line,
        )

        bot = SlackClient(bot_token, app_token)
        transport = SlackTransport(bot)
        presenter = SlackPresenter(
            message_overflow=message_overflow,
            show_resume_line=show_resume_line,
        )
        exec_cfg = ExecBridgeConfig(
            transport=transport,
            presenter=presenter,
            final_notify=final_notify,
        )

        async def run_loop() -> None:
            auth = await bot.auth_test()
            if not auth.ok:
                raise RuntimeError(f"Slack auth failed: {auth.error}")
            bot_user_id = auth.user_id or ""
            bot_username = auth.user or ""
            if not bot_user_id:
                logger.warning("slack.no_bot_user_id")

            logger.info(
                "slack.connected",
                bot_user_id=bot_user_id,
                bot_username=bot_username,
            )

            cfg = SlackBridgeConfig(
                bot=bot,
                bot_user_id=bot_user_id,
                bot_username=bot_username,
                runtime=runtime,
                channel_id=channel_id,
                startup_msg=startup_msg,
                exec_cfg=exec_cfg,
                session_mode=session_mode,
                show_resume_line=show_resume_line,
                allowed_channel_ids=allowed_channel_ids,
                allowed_user_ids=allowed_user_ids,
                message_overflow=message_overflow,
                trigger_mode=trigger_mode,
                files_enabled=files_enabled,
                voice_enabled=voice_enabled,
                projects_root=runtime.projects_root,
            )

            from .loop import run_main_loop

            try:
                await run_main_loop(
                    cfg,
                    watch_config=runtime.watch_config,
                    default_engine_override=default_engine_override,
                    transport_id=self.id,
                    transport_config=transport_config,
                )
            finally:
                await transport.close()

        anyio.run(run_loop)


slack_backend = SlackBackend()
BACKEND = slack_backend
