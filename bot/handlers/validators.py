"""Validators handler - show validator info."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.genlayer_rpc import genlayer_rpc


async def validators_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /validators command - show validator count and status."""
    await update.message.reply_text("Fetching validator information...")

    try:
        result = await genlayer_rpc.get_validators()

        if result.get("error"):
            await update.message.reply_text(f"Error: {result['error']}")
            return

        validators = result.get("result", [])
        total = len(validators) if isinstance(validators, list) else validators.get("total", 0)

        active = 0
        if isinstance(validators, list):
            active = sum(1 for v in validators if v.get("status") == "active")
            validator_list = validators
        else:
            active = validators.get("active", 0)
            validator_list = validators.get("validators", [])

        msg_lines = [
            "GenLayer Validator Status:\n",
            f"Total Validators: {total}",
            f"Active: {active}",
        ]

        # Show up to 10 validators
        if validator_list:
            msg_lines.append("\nRecent validators:")
            for v in validator_list[:10]:
                addr = v.get("address", "unknown")[:16] + "..."
                status = v.get("status", "unknown")
                stake = v.get("stake", "N/A")
                msg_lines.append(f"  {addr} | {status} | stake: {stake}")

        await update.message.reply_text("\n".join(msg_lines))
    except Exception as e:
        await update.message.reply_text(f"Failed to fetch validators: {str(e)}")
