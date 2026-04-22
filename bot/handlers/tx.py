"""Transaction lookup handler."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.genlayer_rpc import genlayer_rpc


async def tx_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tx <hash> command - look up a transaction."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/tx <transaction_hash>`\n\n"
            "Example: `/tx 0xabc123...`",
            parse_mode="Markdown",
        )
        return

    tx_hash = context.args[0].strip()
    await update.message.reply_text(f"Looking up transaction `{tx_hash}`...", parse_mode="Markdown")

    try:
        result = await genlayer_rpc.get_transaction(tx_hash)

        if result.get("error"):
            await update.message.reply_text(f"Error: {result['error']}")
            return

        tx = result.get("result", {})
        status = tx.get("status", "unknown")
        from_addr = tx.get("from", "unknown")
        to_addr = tx.get("to", "unknown")
        method = tx.get("method", "N/A")
        block = tx.get("block_number", "N/A")

        msg = (
            f"Transaction Details:\n\n"
            f"Hash: `{tx_hash}`\n"
            f"Status: {status}\n"
            f"From: `{from_addr}`\n"
            f"To: `{to_addr}`\n"
            f"Method: {method}\n"
            f"Block: {block}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Lookup failed: {str(e)}")
