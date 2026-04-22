"""List user's deployed contracts."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.contract_registry import contract_registry


async def contracts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /contracts command - list user's deployed contracts."""
    user_id = update.effective_user.id

    contracts = await contract_registry.get_user_contracts(user_id)

    if not contracts:
        await update.message.reply_text(
            "You have no deployed contracts yet.\n"
            "Use /deploy to deploy one, or /template to get started!"
        )
        return

    lines = ["Your deployed contracts:\n"]
    for i, c in enumerate(contracts, 1):
        lines.append(
            f"{i}. `{c['address']}`\n"
            f"   TX: `{c['tx_hash']}`\n"
            f"   Code: {c['code_snippet']}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
