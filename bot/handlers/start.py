"""Start and help command handlers."""

from telegram import Update
from telegram.ext import ContextTypes

WELCOME_TEXT = """
Welcome to GenBot - Your GenLayer Intelligent Contract Assistant!

I can help you deploy and interact with GenLayer Intelligent Contracts right from Telegram.

Commands:
  /deploy     - Deploy a new Intelligent Contract
  /call       - Read from a deployed contract
  /write      - Write a transaction to a contract
  /ask        - Natural language query to a contract
  /contracts  - List your deployed contracts
  /tx         - Look up a transaction by hash
  /template   - Get starter contract templates
  /audit      - AI-powered contract security audit
  /faucet     - Request testnet tokens
  /validators - View validator status
  /help       - Show this help message

Get started by deploying a contract with /deploy or grab a template with /template!
""".strip()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command."""
    await update.message.reply_text(WELCOME_TEXT)
    return -1  # ConversationHandler.END


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(WELCOME_TEXT)
