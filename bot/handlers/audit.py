"""AI audit handler - uses Claude to analyze contract code."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.audit_service import audit_service

AUDIT_STATE = 50


async def audit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /audit command - prompt for contract code."""
    await update.message.reply_text(
        "Paste the GenLayer contract code you want audited.\n\n"
        "I will analyze it for security issues, best practices, "
        "and potential improvements using AI.\n\n"
        "Send /cancel to abort."
    )
    return AUDIT_STATE


async def audit_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive contract code and perform AI audit."""
    code = update.message.text.strip()

    # Strip code fences
    if code.startswith("```") and code.endswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1])
    elif code.startswith("```"):
        code = code.lstrip("`").lstrip("python").lstrip("\n")
        if code.endswith("```"):
            code = code[:-3]

    await update.message.reply_text("Analyzing your contract... This may take a moment.")

    try:
        report = await audit_service.audit_contract(code)
        # Split long messages if needed
        if len(report) > 4000:
            for i in range(0, len(report), 4000):
                await update.message.reply_text(report[i : i + 4000])
        else:
            await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"Audit failed: {str(e)}")

    return ConversationHandler.END
