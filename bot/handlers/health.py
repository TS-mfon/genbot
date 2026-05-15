"""Health and fallback handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.genlayer_rpc import genlayer_rpc


async def health_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a lightweight runtime health response."""
    network = context.user_data.get("network", "studionet")
    try:
        cli_version = await genlayer_rpc.get_cli_version()
    except Exception as exc:
        cli_version = f"unavailable ({exc})"

    await update.message.reply_text(
        "✅ <b>GenBot is online</b>\n\n"
        f"Network: <code>{network}</code>\n"
        f"GenLayer CLI: <code>{cli_version}</code>\n\n"
        "<b>Try this flow</b>\n"
        "1. /examples\n"
        "2. /template\n"
        "3. /deploy\n"
        "4. /schema &lt;address&gt;\n"
        "5. /call or /write\n\n"
        "If a contract is visible in the explorer but not callable, run:\n"
        "<code>/doctor &lt;contract_address&gt;</code>",
        parse_mode="HTML",
    )


async def unknown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to unsupported commands instead of silently ignoring them."""
    command = update.message.text.split()[0] if update.message and update.message.text else "that command"
    if command == "/faucet":
        detail = (
            "The old /faucet command was removed because the GenLayer RPC faucet method is not supported."
        )
    else:
        detail = "I do not recognize that command."

    await update.message.reply_text(
        f"⚠️ <b>{detail}</b>\n\n"
        "<b>Use these instead</b>\n"
        "• /commands - full command list\n"
        "• /examples - copyable examples with values\n"
        "• /health - check if GenBot is online\n"
        "• /doctor &lt;contract_address&gt; - diagnose call/deploy issues\n\n"
        "<b>Common flow</b>\n"
        "1. /network\n"
        "2. /deploy\n"
        "3. /schema &lt;address&gt;\n"
        "4. /call or /write",
        parse_mode="HTML",
    )


async def plain_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guide plain text sent outside a command/conversation."""
    await update.message.reply_text(
        "I’m online, but I need a command to know what to do.\n\n"
        "<b>Start here</b>\n"
        "• /examples - step-by-step examples with real values\n"
        "• /commands - all available commands\n"
        "• /health - confirm bot and GenLayer CLI status\n\n"
        "<b>If you are trying to interact with a contract</b>\n"
        "Use /call or /write first, then paste the address and method when I ask.",
        parse_mode="HTML",
    )
