"""Password handler - let users set a password for their genlayer account."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.wallet_service import wallet_service

PASSWORD_STATE = 60


async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /password command - prompt user to set account password."""
    await update.message.reply_text(
        "Enter a password for your GenLayer account.\n"
        "This password will be used to encrypt your keystore and\n"
        "is required when deploying contracts.\n\n"
        "Your message will be deleted after reading for security.\n\n"
        "Send /cancel to abort."
    )
    return PASSWORD_STATE


async def password_receive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and store the user's password."""
    password = update.message.text.strip()

    # Delete the password message for security
    try:
        await update.message.delete()
    except Exception:
        pass

    if len(password) < 4:
        await update.message.reply_text(
            "Password too short (minimum 4 characters). Try again or /cancel."
        )
        return PASSWORD_STATE

    # Store password in user_data (session-only, not persisted to DB)
    context.user_data["account_password"] = password

    await update.message.reply_text(
        "Password set for this session.\n"
        "You can now deploy contracts with /deploy.\n\n"
        "Note: you will need to set your password again if you restart the bot."
    )
    return ConversationHandler.END
