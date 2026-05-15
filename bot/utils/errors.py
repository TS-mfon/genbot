"""User-facing Telegram error handling."""

from __future__ import annotations

import html
import logging
import traceback
from dataclasses import dataclass
from typing import Any

from telegram import Update
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ErrorGuide:
    title: str
    explanation: str
    next_steps: tuple[str, ...]


def _support_code(error: BaseException) -> str:
    return hex(abs(hash((type(error).__name__, str(error)))) % 0xFFFFFF)[2:].upper().zfill(6)


def _classify(error: BaseException) -> ErrorGuide:
    text = str(error).lower()

    if isinstance(error, (TimedOut, TimeoutError)) or "timeout" in text or "timed out" in text:
        return ErrorGuide(
            "Request timed out",
            "The bot did not receive a response from Telegram, GenLayer CLI, or the RPC endpoint in time.",
            (
                "Try the same command again in a minute.",
                "For deployments, use a smaller contract file and check /network.",
                "If it keeps failing, run /commands and retry the exact command format.",
            ),
        )

    if isinstance(error, NetworkError) or "connection" in text or "dns" in text or "rpc" in text:
        return ErrorGuide(
            "Network or RPC issue",
            "The bot could not reach an external service needed for this command.",
            (
                "Retry shortly; RPC and CLI endpoints can be temporarily unavailable.",
                "Check /network before deploy/call/write commands.",
                "If you were deploying, keep your contract file and resend it after /deploy.",
            ),
        )

    if isinstance(error, BadRequest):
        return ErrorGuide(
            "Telegram rejected the response",
            "The generated response was too long or contained formatting Telegram could not parse.",
            (
                "Try a shorter input or upload the contract as a .py file.",
                "Use /guide for the supported input format.",
                "If viewing output, use /schema or /tx to inspect smaller pieces.",
            ),
        )

    if isinstance(error, Forbidden):
        return ErrorGuide(
            "Bot cannot message this chat",
            "Telegram blocked the bot from replying to the chat.",
            (
                "Open the bot directly and press Start.",
                "If this is a group, make sure the bot is still a member.",
            ),
        )

    if isinstance(error, (ValueError, TypeError)) or "invalid" in text or "expected" in text:
        return ErrorGuide(
            "Input format problem",
            "The command arguments were not in the format GenBot expected.",
            (
                "Run /guide for examples.",
                "Use /schema <contract> before /call or /write.",
                "For calls, use: /call <address> <method>(arg1, arg2).",
            ),
        )

    if "insufficient" in text or "balance" in text or "private key" in text or "wallet" in text:
        return ErrorGuide(
            "Wallet or balance issue",
            "The command needs a usable wallet and enough funds for the selected network.",
            (
                "Run /start to confirm your wallet exists.",
                "Check that you are on the right network with /network.",
                "Fund the wallet shown by the bot before write/deploy operations.",
            ),
        )

    if "genlayer" in text or "cli" in text or "deploy" in text:
        return ErrorGuide(
            "GenLayer CLI issue",
            "The GenLayer CLI returned an error while processing the command.",
            (
                "Confirm the contract starts with the pinned Depends header.",
                "Use /template for a lint-clean contract structure.",
                "Run /guide and retry with the documented deploy/call/write format.",
            ),
        )

    return ErrorGuide(
        "Unexpected bot error",
        "The command failed unexpectedly, but the bot is still running.",
        (
            "Retry the command once.",
            "Run /commands to confirm the supported command list.",
            "If it repeats, include the support code when reporting it.",
        ),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log full diagnostics and send a concise recovery guide to the user."""
    error = context.error or RuntimeError("Unknown error")
    support_code = _support_code(error)
    logger.error(
        "Unhandled update error support_code=%s update=%r\n%s",
        support_code,
        update,
        "".join(traceback.format_exception(type(error), error, error.__traceback__)),
    )

    if not isinstance(update, Update):
        return

    guide = _classify(error)
    lines = [
        f"<b>{html.escape(guide.title)}</b>",
        html.escape(guide.explanation),
        "",
        "<b>What to do next</b>",
    ]
    lines.extend(f"- {html.escape(step)}" for step in guide.next_steps)
    lines.extend(
        [
            "",
            f"<b>Support code:</b> <code>{support_code}</code>",
        ]
    )
    message = "\n".join(lines)

    target = update.effective_message
    try:
        if target:
            await target.reply_text(message, parse_mode="HTML")
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to send user-facing error message support_code=%s", support_code)
