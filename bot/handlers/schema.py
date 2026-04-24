"""Schema handler - inspect deployed contract methods and argument types."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.genlayer_rpc import genlayer_rpc


async def schema_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /schema <address> command."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /schema <contract_address>\n\n"
            "Example:\n"
            "/schema 0x1234abcd1234abcd1234abcd1234abcd1234abcd"
        )
        return

    address = context.args[0].strip()
    if not (address.startswith("0x") and len(address) == 42):
        await update.message.reply_text("❌ Invalid address format. Expected 0x followed by 40 hex characters.")
        return

    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(f"Inspecting schema on {network}...")

    result = await genlayer_rpc.get_schema(address, network=network)
    if result.get("error"):
        await update.message.reply_text(f"❌ Schema lookup failed:\n<pre>{result['error']}</pre>", parse_mode="HTML")
        return

    schema = result.get("result", "")
    if len(schema) > 3500:
        schema = schema[:3500] + "\n... (truncated)"
    await update.message.reply_text(f"📋 Schema for <code>{address}</code>\n\n<pre>{schema}</pre>", parse_mode="HTML")
