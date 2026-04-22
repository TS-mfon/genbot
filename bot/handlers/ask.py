"""Natural language query handler."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc

ASK_STATE = 30


async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /ask command - prompt for contract address."""
    await update.message.reply_text(
        "Enter the contract address you want to query:\n\n"
        "Send /cancel to abort."
    )
    return ASK_STATE


async def ask_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive contract address, prompt for natural language query."""
    address = update.message.text.strip()
    context.user_data["ask_address"] = address
    await update.message.reply_text(
        f"Contract: `{address}`\n\n"
        "Now type your question in plain English.\n"
        "Example: \"What is the current vote count?\"\n\n"
        "Send /cancel to abort.",
        parse_mode="Markdown",
    )
    return ASK_STATE + 1


async def ask_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Route natural language query to the contract."""
    address = context.user_data.get("ask_address", "")
    query = update.message.text.strip()

    await update.message.reply_text("Processing your query...")

    try:
        result = await genlayer_rpc.call_contract(
            contract_address=address,
            method="ask",
            args=[query],
        )

        if result.get("error"):
            await update.message.reply_text(f"Error:\n{result['error']}")
        else:
            data = result.get("result", "No response received.")
            await update.message.reply_text(f"Answer:\n\n{data}")
    except Exception as e:
        await update.message.reply_text(f"Query failed: {str(e)}")

    return ConversationHandler.END
