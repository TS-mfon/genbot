"""Transaction lookup handler."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.genlayer_rpc import genlayer_rpc


async def tx_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tx <hash> command - look up a transaction."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /tx <transaction_hash>\n\n"
            "Example:\n"
            "/tx 0xabc123...",
        )
        return

    tx_hash = context.args[0].strip()
    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(f"Looking up transaction on {network}...")

    try:
        result = await genlayer_rpc.get_transaction(tx_hash, network=network)

        if result.get("error"):
            await update.message.reply_text(
                f"❌ Transaction lookup failed:\n<pre>{result['error']}</pre>",
                parse_mode="HTML",
            )
            return

        receipt = result.get("result", "")
        if len(receipt) > 3500:
            receipt = receipt[:3500] + "\n... (truncated)"
        await update.message.reply_text(
            f"🧾 Receipt for <code>{tx_hash}</code>\n\n<pre>{receipt}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"Lookup failed: {str(e)}")
