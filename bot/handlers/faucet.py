"""Faucet handler - request testnet tokens."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.wallet_service import wallet_service


async def faucet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faucet command - request testnet tokens."""
    user_id = update.effective_user.id

    try:
        wallet = await wallet_service.get_or_create_wallet(user_id)
        address = wallet["address"]

        await update.message.reply_text(
            f"Requesting testnet tokens for your wallet...\n"
            f"Address: `{address}`",
            parse_mode="Markdown",
        )

        result = await genlayer_rpc.request_faucet(address)

        if result.get("error"):
            await update.message.reply_text(f"Faucet error: {result['error']}")
        else:
            amount = result.get("result", {}).get("amount", "some")
            await update.message.reply_text(
                f"Testnet tokens sent to `{address}`!\n"
                f"Amount: {amount}\n\n"
                f"You can now deploy contracts with /deploy.",
                parse_mode="Markdown",
            )
    except Exception as e:
        await update.message.reply_text(f"Faucet request failed: {str(e)}")
