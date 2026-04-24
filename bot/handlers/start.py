"""Start and help command handlers with wallet creation."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.wallet_service import wallet_service

BOT_COMMANDS = [
    ("start", "Create your wallet and show the overview"),
    ("commands", "List available bot commands"),
    ("help", "Show the main overview"),
    ("guide", "Show exact input formats and examples"),
    ("network", "Switch GenLayer network"),
    ("deploy", "Deploy a GenLayer contract"),
    ("schema", "Inspect a deployed contract schema"),
    ("call", "Read from a deployed contract"),
    ("write", "Write to a deployed contract"),
    ("contracts", "List your deployed contracts"),
    ("tx", "Inspect a transaction receipt"),
    ("template", "Get starter contract templates"),
    ("audit", "Audit contract code"),
    ("validators", "View validator status"),
    ("faucet", "Request testnet funds"),
]

WELCOME_TEXT = """
Welcome to GenBot - Your GenLayer Intelligent Contract Assistant!

I can help you deploy and interact with GenLayer Intelligent Contracts right from Telegram.

Commands:
  /deploy     - Deploy a new Intelligent Contract
  /call       - Read from a deployed contract
  /write      - Write a transaction to a contract
  /schema     - Inspect contract methods before interacting
  /ask        - Natural language query to a contract
  /contracts  - List your deployed contracts
  /tx         - Look up a transaction by hash
  /template   - Get starter contract templates
  /audit      - AI-powered contract security audit
  /faucet     - Request testnet tokens
  /validators - View validator status
  /network    - Switch between StudioNet / Bradbury / Asimov
  /guide      - See exact input formats and examples
  /help       - Show this help message

Best flow:
  1. /network
  2. /deploy
  3. /schema <address>
  4. /call or /write
""".strip()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command - create wallet and show welcome."""
    user_id = update.effective_user.id

    # Create or retrieve wallet
    wallet = await wallet_service.get_or_create_wallet(user_id)
    is_new = context.user_data.get("wallet_shown") is None

    await update.message.reply_text(WELCOME_TEXT)

    if is_new:
        # Show wallet info with private key (only on first /start)
        context.user_data["wallet_shown"] = True
        await update.message.reply_text(
            f"<b>Your GenLayer Wallet</b>\n\n"
            f"Address: <code>{wallet['address']}</code>\n\n"
            f"<b>SAVE YOUR PRIVATE KEY NOW:</b>\n"
            f"<tg-spoiler>{wallet['private_key']}</tg-spoiler>\n\n"
            f"Tap the hidden text above to reveal your private key.\n"
            f"Store it safely - you will need it to manage your account.\n\n"
            f"Use /guide for exact deploy, call, and write input examples.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"Wallet: <code>{wallet['address']}</code>",
            parse_mode="HTML",
        )

    return -1  # ConversationHandler.END


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(WELCOME_TEXT)


async def commands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /commands command."""
    await update.message.reply_text(WELCOME_TEXT)
