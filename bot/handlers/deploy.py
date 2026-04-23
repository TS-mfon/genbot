"""Deploy contract handler - supports file upload and text paste."""

import ast
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.contract_registry import contract_registry
from bot.services.wallet_service import wallet_service
from bot.utils.rate_limit import rate_limited

logger = logging.getLogger(__name__)

DEPLOY_STATE = 10
MAX_CONTRACT_SIZE = 200_000  # 200KB


@rate_limited
async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(
        f"🚀 <b>Deploy to GenLayer ({network})</b>\n\n"
        f"Upload a <b>.py</b> file or paste the full Python source code.\n\n"
        f"Your contract should start with:\n"
        f"<code># {{\"Depends\": \"py-genlayer:test\"}}</code>\n\n"
        f"If missing, it will be auto-prepended.\n\n"
        f"Use /network to change network. Send /cancel to abort.",
        parse_mode="HTML",
    )
    return DEPLOY_STATE


async def deploy_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle .py file upload."""
    document = update.message.document
    if not document:
        await update.message.reply_text("Please upload a .py file.")
        return DEPLOY_STATE

    if not document.file_name.endswith(".py"):
        await update.message.reply_text("❌ File must have a .py extension.")
        return DEPLOY_STATE

    if document.file_size > MAX_CONTRACT_SIZE:
        await update.message.reply_text(f"❌ File too large (max {MAX_CONTRACT_SIZE//1000}KB).")
        return DEPLOY_STATE

    try:
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        code = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        await update.message.reply_text("❌ File is not valid UTF-8 text.")
        return DEPLOY_STATE
    except Exception as e:
        logger.exception("file download failed")
        await update.message.reply_text(f"❌ Failed to download file: {e}")
        return DEPLOY_STATE

    return await _validate_and_deploy(update, context, code)


async def deploy_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive pasted contract code."""
    code = update.message.text.strip()

    # Strip markdown code fences
    if code.startswith("```"):
        code = code.lstrip("`")
        for prefix in ("python\n", "py\n", "\n"):
            if code.startswith(prefix):
                code = code[len(prefix):]
                break
        if code.endswith("```"):
            code = code[:-3].rstrip()

    return await _validate_and_deploy(update, context, code)


async def _validate_and_deploy(
    update: Update, context: ContextTypes.DEFAULT_TYPE, code: str
) -> int:
    user_id = update.effective_user.id

    # Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        await update.message.reply_text(
            f"❌ <b>Syntax error:</b>\nLine {e.lineno}: {e.msg}",
            parse_mode="HTML",
        )
        return DEPLOY_STATE

    # Semantic check
    if "genlayer" not in code and "gl." not in code:
        await update.message.reply_text(
            "⚠️ This doesn't look like a GenLayer contract.\n"
            "Expected: <code>from genlayer import *</code>",
            parse_mode="HTML",
        )
        return DEPLOY_STATE

    network = context.user_data.get("network", "studionet")

    await update.message.reply_text(
        f"✅ Code validated.\n\n"
        f"⏳ Deploying to <b>{network}</b> via genlayer CLI...\n"
        f"This takes 30-90 seconds.",
        parse_mode="HTML",
    )

    try:
        wallet = await wallet_service.get_or_create_wallet(user_id)
        result = await genlayer_rpc.deploy_contract(
            code=code,
            user_id=user_id,
            private_key=wallet["private_key"],
            network=network,
        )

        if result.get("success"):
            addr = result.get("address", "")
            tx = result.get("tx_hash", "")

            if addr:
                try:
                    await contract_registry.register_contract(
                        user_id=user_id,
                        contract_address=addr,
                        code_snippet=code[:200],
                        tx_hash=tx,
                    )
                except Exception:
                    logger.exception("registry save failed (non-fatal)")

                msg = (
                    f"🎉 <b>Contract Deployed!</b>\n\n"
                    f"Address: <code>{addr}</code>\n"
                    f"Network: {network}\n"
                )
                if tx:
                    msg += f"Tx: <code>{tx}</code>\n"
                msg += "\nUse /call or /write to interact with it."

                await update.message.reply_text(msg, parse_mode="HTML")
            else:
                await update.message.reply_text(
                    f"⚠️ Deploy succeeded but no address returned.\n\n"
                    f"<pre>{result.get('output', '')[:1000]}</pre>",
                    parse_mode="HTML",
                )
        else:
            err = result.get("error", "Unknown error")
            await update.message.reply_text(
                f"❌ <b>Deployment failed:</b>\n<pre>{err[:1500]}</pre>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("deploy exception")
        await update.message.reply_text(f"❌ Error: {str(e)[:500]}")

    return ConversationHandler.END
