"""Deploy contract handler - supports file upload and text paste."""

import ast
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.contract_registry import contract_registry
from bot.services.wallet_service import wallet_service

logger = logging.getLogger(__name__)

DEPLOY_STATE = 10


async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /deploy command - prompt user for contract code or file."""
    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(
        f"<b>Deploy to GenLayer ({network})</b>\n\n"
        f"Upload a <b>.py</b> file containing your Intelligent Contract,\n"
        f"or paste the full Python source code.\n\n"
        f"Your contract must start with:\n"
        f"<code># {{\"Depends\": \"py-genlayer:test\"}}</code>\n\n"
        f"Use /network to change network before deploying.\n"
        f"Send /cancel to abort.",
        parse_mode="HTML",
    )
    return DEPLOY_STATE


async def deploy_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle .py file upload for deployment."""
    document = update.message.document
    if not document.file_name.endswith(".py"):
        await update.message.reply_text(
            "Please upload a .py file (GenLayer intelligent contract)."
        )
        return DEPLOY_STATE

    file = await document.get_file()
    file_bytes = await file.download_as_bytearray()
    code = file_bytes.decode("utf-8")

    return await _validate_and_deploy(update, context, code)


async def deploy_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive pasted contract code for deployment."""
    code = update.message.text.strip()

    # Remove markdown code fences if present
    if code.startswith("```") and code.endswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1])
    elif code.startswith("```"):
        code = code.lstrip("`").lstrip("python").lstrip("\n")
        if code.endswith("```"):
            code = code[:-3]

    return await _validate_and_deploy(update, context, code)


async def _validate_and_deploy(
    update: Update, context: ContextTypes.DEFAULT_TYPE, code: str
) -> int:
    """Validate code and deploy directly via RPC (no password needed on studionet)."""
    user_id = update.effective_user.id

    # Validate Python syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        await update.message.reply_text(
            f"<b>Syntax error in your contract:</b>\n"
            f"Line {e.lineno}: {e.msg}\n\n"
            f"Please fix and resend, or /cancel.",
            parse_mode="HTML",
        )
        return DEPLOY_STATE

    # Ensure contract has the required header
    if not code.strip().startswith("#"):
        code = '# {"Depends": "py-genlayer:test"}\n' + code

    # Check for genlayer imports
    if "genlayer" not in code and "gl." not in code:
        await update.message.reply_text(
            "This doesn't look like a GenLayer contract.\n"
            "Make sure it imports from genlayer:\n"
            "<code>from genlayer import *</code>",
            parse_mode="HTML",
        )
        return DEPLOY_STATE

    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(
        f"✅ Code validated.\n\n"
        f"Deploying to <b>{network}</b>...\n"
        f"This may take 30-60 seconds.",
        parse_mode="HTML",
    )

    try:
        wallet = await wallet_service.get_or_create_wallet(user_id)

        result = await genlayer_rpc.deploy_contract(
            code=code,
            from_address=wallet["address"],
            network=network,
        )

        if result.get("success"):
            contract_address = result.get("address", "")
            tx_hash = result.get("tx_hash", "")

            if contract_address:
                await contract_registry.register_contract(
                    user_id=user_id,
                    contract_address=contract_address,
                    code_snippet=code[:200],
                    tx_hash=tx_hash,
                )

                await update.message.reply_text(
                    f"<b>✅ Contract Deployed!</b>\n\n"
                    f"Address: <code>{contract_address}</code>\n"
                    f"Network: {network}\n"
                    f"Tx: <code>{tx_hash}</code>\n\n"
                    f"Use /call or /write to interact with it.",
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text(
                    f"<b>Transaction submitted!</b>\n\n"
                    f"Tx: <code>{tx_hash}</code>\n"
                    f"Network: {network}\n\n"
                    f"Use /tx {tx_hash} to check deployment status.\n"
                    f"{result.get('note', '')}",
                    parse_mode="HTML",
                )
        else:
            error = result.get("error", "Unknown error")
            await update.message.reply_text(
                f"<b>❌ Deployment failed</b>\n\n{error}",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"Deploy error: {e}", exc_info=True)
        await update.message.reply_text(f"Deployment error: {str(e)}")

    return ConversationHandler.END
