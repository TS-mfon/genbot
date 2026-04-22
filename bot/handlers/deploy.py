"""Deploy contract handler - multi-step conversation."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.contract_registry import contract_registry
from bot.services.wallet_service import wallet_service
from bot.utils.code_validator import validate_contract_code
from bot.utils.formatting import escape_md, truncate

DEPLOY_STATE = 10


async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /deploy command - prompt user for contract code."""
    await update.message.reply_text(
        "Send me your GenLayer Intelligent Contract code.\n\n"
        "Paste the full Python source code below. "
        "Use `from genlayer import *` at the top.\n\n"
        "Send /cancel to abort.",
    )
    return DEPLOY_STATE


async def deploy_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive contract code and deploy it."""
    user_id = update.effective_user.id
    code = update.message.text.strip()

    # Remove markdown code fences if present
    if code.startswith("```") and code.endswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1])
    elif code.startswith("```"):
        code = code.lstrip("`").lstrip("python").lstrip("\n")
        if code.endswith("```"):
            code = code[:-3]

    # Validate syntax
    is_valid, error = validate_contract_code(code)
    if not is_valid:
        await update.message.reply_text(f"Syntax error in your contract:\n{error}\n\nPlease fix and resend, or /cancel.")
        return DEPLOY_STATE

    await update.message.reply_text("Code validated. Deploying contract to GenLayer...")

    try:
        # Ensure user has a wallet
        wallet = await wallet_service.get_or_create_wallet(user_id)

        # Deploy via RPC
        result = await genlayer_rpc.deploy_contract(
            from_address=wallet["address"],
            code=code,
        )

        if result.get("error"):
            await update.message.reply_text(f"Deployment failed:\n{result['error']}")
            return ConversationHandler.END

        contract_address = result.get("result", {}).get("contract_address", "unknown")
        tx_hash = result.get("result", {}).get("transaction_hash", "unknown")

        # Save to registry
        await contract_registry.register_contract(
            user_id=user_id,
            contract_address=contract_address,
            code_snippet=truncate(code, 200),
            tx_hash=tx_hash,
        )

        await update.message.reply_text(
            f"Contract deployed successfully!\n\n"
            f"Address: `{contract_address}`\n"
            f"TX Hash: `{tx_hash}`\n\n"
            f"Use /call or /write to interact with it.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"Deployment error: {str(e)}")

    return ConversationHandler.END
