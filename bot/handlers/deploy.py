"""Deploy contract handler - supports file upload and text paste."""

import ast

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.contract_registry import contract_registry
from bot.services.wallet_service import wallet_service
from bot.utils.code_validator import validate_contract_code
from bot.utils.formatting import truncate

DEPLOY_STATE = 10
DEPLOY_PASSWORD_STATE = 11


async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /deploy command - prompt user for contract code or file."""
    await update.message.reply_text(
        "Upload a <b>.py</b> file containing your GenLayer Intelligent Contract,\n"
        "or paste the full Python source code below.\n\n"
        "Use <code>from genlayer import *</code> at the top.\n\n"
        "Send /cancel to abort.",
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

    return await _validate_and_prepare_deploy(update, context, code)


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

    return await _validate_and_prepare_deploy(update, context, code)


async def _validate_and_prepare_deploy(
    update: Update, context: ContextTypes.DEFAULT_TYPE, code: str
) -> int:
    """Validate code and ask for password before deploying."""
    # Validate syntax
    is_valid, error = validate_contract_code(code)
    if not is_valid:
        await update.message.reply_text(
            f"Syntax error in your contract:\n{error}\n\n"
            "Please fix and resend, or /cancel."
        )
        return DEPLOY_STATE

    # Store code for the password step
    context.user_data["deploy_code"] = code

    await update.message.reply_text(
        "Contract validated.\n\n"
        "Enter your account password to deploy.\n"
        "(Set one first with /password if you have not yet.)\n\n"
        "Send /cancel to abort."
    )
    return DEPLOY_PASSWORD_STATE


async def deploy_password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive password and execute deployment via genlayer CLI."""
    user_id = update.effective_user.id
    password = update.message.text.strip()
    code = context.user_data.get("deploy_code", "")

    if not code:
        await update.message.reply_text("No contract code found. Please start over with /deploy.")
        return ConversationHandler.END

    # Delete the password message for safety
    try:
        await update.message.delete()
    except Exception:
        pass

    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(
        f"Deploying contract to GenLayer ({network})..."
    )

    try:
        wallet = await wallet_service.get_or_create_wallet(user_id)

        result = await genlayer_rpc.deploy_contract(
            code=code,
            user_private_key=wallet["private_key"],
            password=password,
            network=network,
        )

        if result.get("success"):
            contract_address = result["address"]

            await contract_registry.register_contract(
                user_id=user_id,
                contract_address=contract_address,
                code_snippet=truncate(code, 200),
                tx_hash=result.get("output", "")[:64],
            )

            await update.message.reply_text(
                f"Contract deployed!\n\n"
                f"Address: <code>{contract_address}</code>\n"
                f"Network: {network}\n\n"
                f"Use /call or /write to interact with it.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                f"Deployment failed:\n{result.get('error', 'Unknown error')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Deployment error: {str(e)}")

    # Clean up
    context.user_data.pop("deploy_code", None)
    return ConversationHandler.END
