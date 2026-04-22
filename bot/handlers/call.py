"""Call and write handlers for interacting with deployed contracts."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.wallet_service import wallet_service

CALL_STATE = 20


async def call_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /call command - prompt for contract address."""
    context.user_data["rpc_mode"] = "call"
    await update.message.reply_text(
        "Enter the contract address to read from:\n\n"
        "Send /cancel to abort."
    )
    return CALL_STATE


async def write_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /write command - prompt for contract address."""
    context.user_data["rpc_mode"] = "write"
    await update.message.reply_text(
        "Enter the contract address to write to:\n\n"
        "Send /cancel to abort."
    )
    return CALL_STATE


async def call_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive contract address, ask for method and args."""
    address = update.message.text.strip()
    context.user_data["contract_address"] = address

    mode = context.user_data.get("rpc_mode", "call")
    action = "read" if mode == "call" else "write"

    await update.message.reply_text(
        f"Contract: `{address}`\n\n"
        f"Enter the method name and arguments to {action}.\n"
        f"Format: `method_name(arg1, arg2, ...)`\n\n"
        f"Example: `get_balance(\"0xabc...\")`\n\n"
        f"Send /cancel to abort.",
        parse_mode="Markdown",
    )
    return CALL_STATE + 1


async def call_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive method call and execute it."""
    user_id = update.effective_user.id
    raw = update.message.text.strip()
    address = context.user_data.get("contract_address", "")
    mode = context.user_data.get("rpc_mode", "call")

    # Parse method_name(args)
    method_name, args = _parse_method_call(raw)
    if method_name is None:
        await update.message.reply_text("Could not parse method call. Use format: `method_name(arg1, arg2)`")
        return CALL_STATE + 1

    try:
        if mode == "call":
            result = await genlayer_rpc.call_contract(
                contract_address=address,
                method=method_name,
                args=args,
            )
        else:
            wallet = await wallet_service.get_or_create_wallet(user_id)
            result = await genlayer_rpc.write_contract(
                from_address=wallet["address"],
                contract_address=address,
                method=method_name,
                args=args,
            )

        if result.get("error"):
            await update.message.reply_text(f"RPC Error:\n{result['error']}")
        else:
            data = result.get("result", result)
            await update.message.reply_text(
                f"Result:\n```\n{data}\n```",
                parse_mode="Markdown",
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

    return ConversationHandler.END


def _parse_method_call(raw: str) -> tuple:
    """Parse 'method_name(arg1, arg2)' into (method_name, [args])."""
    raw = raw.strip()
    if "(" not in raw:
        return raw, []

    try:
        paren_idx = raw.index("(")
        method_name = raw[:paren_idx].strip()
        args_str = raw[paren_idx + 1 :].rstrip(")")
        if not args_str.strip():
            return method_name, []

        # Safely evaluate arguments
        import ast
        args_raw = f"[{args_str}]"
        args = ast.literal_eval(args_raw)
        return method_name, args
    except Exception:
        return raw.split("(")[0].strip(), []
