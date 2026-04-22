"""GenBot - GenLayer Telegram Bot entry point."""

import logging

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.db.database import init_db
from bot.handlers.start import start_handler, help_handler
from bot.handlers.deploy import (
    deploy_handler,
    deploy_code_handler,
    deploy_file_handler,
    DEPLOY_STATE,
)
from bot.handlers.call import (
    call_handler,
    write_handler,
    call_address_handler,
    call_method_handler,
    CALL_STATE,
)
from bot.handlers.ask import ask_handler, ask_address_handler, ask_query_handler, ASK_STATE
from bot.handlers.contracts import contracts_handler
from bot.handlers.tx import tx_handler
from bot.handlers.template import (
    template_handler,
    template_callback,
    template_choice_handler,
    TEMPLATE_STATE,
)
from bot.handlers.audit import audit_handler, audit_code_handler, AUDIT_STATE
from bot.handlers.faucet import faucet_handler
from bot.handlers.validators import validators_handler
from bot.handlers.network import network_command, network_callback
from bot.handlers.password import password_handler, password_receive_handler, PASSWORD_STATE

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_conversation_handlers():
    """Build conversation handlers for multi-step interactions."""

    deploy_conv = ConversationHandler(
        entry_points=[CommandHandler("deploy", deploy_handler)],
        states={
            DEPLOY_STATE: [
                MessageHandler(filters.Document.ALL, deploy_file_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, deploy_code_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    call_conv = ConversationHandler(
        entry_points=[CommandHandler("call", call_handler)],
        states={
            CALL_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, call_address_handler)],
            CALL_STATE + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, call_method_handler)],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    write_conv = ConversationHandler(
        entry_points=[CommandHandler("write", write_handler)],
        states={
            CALL_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, call_address_handler)],
            CALL_STATE + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, call_method_handler)],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    ask_conv = ConversationHandler(
        entry_points=[CommandHandler("ask", ask_handler)],
        states={
            ASK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address_handler)],
            ASK_STATE + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_query_handler)],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    template_conv = ConversationHandler(
        entry_points=[CommandHandler("template", template_handler)],
        states={
            TEMPLATE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, template_choice_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    audit_conv = ConversationHandler(
        entry_points=[CommandHandler("audit", audit_handler)],
        states={
            AUDIT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, audit_code_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    password_conv = ConversationHandler(
        entry_points=[CommandHandler("password", password_handler)],
        states={
            PASSWORD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, password_receive_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", start_handler)],
        per_user=True,
        per_chat=True,
    )

    return [deploy_conv, call_conv, write_conv, ask_conv, template_conv, audit_conv, password_conv]


async def post_init(application):
    """Initialize database after application starts."""
    await init_db()
    logger.info("Database initialized.")


def main():
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    # Conversation handlers (must be added before simple command handlers)
    for conv in build_conversation_handlers():
        app.add_handler(conv)

    # Simple command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("contracts", contracts_handler))
    app.add_handler(CommandHandler("tx", tx_handler))
    app.add_handler(CommandHandler("faucet", faucet_handler))
    app.add_handler(CommandHandler("validators", validators_handler))
    app.add_handler(CommandHandler("network", network_command))

    # Callback query handlers for inline buttons
    app.add_handler(CallbackQueryHandler(network_callback, pattern=r"^net_"))
    app.add_handler(CallbackQueryHandler(template_callback, pattern=r"^tpl_"))

    # File upload handler (outside of conversation - catch-all for .py uploads)
    app.add_handler(MessageHandler(filters.Document.ALL, _standalone_file_upload))

    logger.info("GenBot starting...")
    app.run_polling(drop_pending_updates=True)


async def _standalone_file_upload(update, context) -> None:
    """Handle .py file uploads outside of /deploy conversation."""
    document = update.message.document
    if document and document.file_name and document.file_name.endswith(".py"):
        await update.message.reply_text(
            "Received a .py file! Use /deploy first, then upload your file\n"
            "during the deployment flow to deploy it to GenLayer."
        )
    else:
        await update.message.reply_text(
            "I can only process .py files for contract deployment.\n"
            "Use /help to see available commands."
        )


if __name__ == "__main__":
    main()
