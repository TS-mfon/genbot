"""Call and write handlers for interacting with deployed contracts."""

import json
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.wallet_service import wallet_service
from bot.utils.rate_limit import rate_limited

logger = logging.getLogger(__name__)
CALL_STATE = 20


# ---------- Safe arg parsing ----------

def _parse_args(args_str: str) -> list:
    """Safely parse method arguments as JSON.

    Accepts a comma-separated list of JSON literals. For convenience,
    bare strings (identifiers, 0x-prefixed hex, non-numeric tokens)
    are auto-quoted before parsing.

    Raises ValueError on failure.
    """
    s = args_str.strip()
    if not s:
        return []

    # Auto-quote bare tokens that aren't JSON literals
    parts = _split_top_level_commas(s)
    json_parts = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if _looks_like_json(p):
            json_parts.append(p)
        else:
            # Treat as a string literal
            escaped = p.replace("\\", "\\\\").replace('"', '\\"')
            json_parts.append(f'"{escaped}"')

    try:
        return json.loads(f"[{','.join(json_parts)}]")
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse args. Use JSON format: 42, true, \"string\", [1,2,3].\n"
            f"Error: {e}"
        )


def _split_top_level_commas(s: str) -> list[str]:
    """Split on commas that are NOT inside nested brackets, quotes, or braces."""
    out, buf, depth = [], [], 0
    in_str = False
    str_char = ""
    for ch in s:
        if in_str:
            buf.append(ch)
            if ch == str_char and (not buf or buf[-2] != "\\"):
                in_str = False
            continue
        if ch in '"\'':
            in_str = True
            str_char = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def _looks_like_json(p: str) -> bool:
    """Heuristic: does this look like a valid JSON literal?"""
    p = p.strip()
    if not p:
        return False
    if p in ("true", "false", "null"):
        return True
    if p.startswith(("[", "{", '"')):
        return True
    # number
    if re.match(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$", p):
        return True
    return False


def _parse_method_call(raw: str) -> tuple[str | None, list]:
    """Parse 'method_name(arg1, arg2)' into (method_name, args)."""
    raw = raw.strip()
    if not raw:
        return None, []
    if "(" not in raw:
        # Bare method name - no args
        return raw, []

    try:
        paren_idx = raw.index("(")
        method_name = raw[:paren_idx].strip()
        if not method_name.replace("_", "").isalnum():
            return None, []
        # Strip final ')'
        args_str = raw[paren_idx + 1:]
        if args_str.endswith(")"):
            args_str = args_str[:-1]

        args = _parse_args(args_str)
        return method_name, args
    except ValueError as ve:
        raise ve
    except Exception as e:
        logger.warning("Parse failed: %s", e)
        return None, []


# ---------- Handlers ----------

@rate_limited
async def call_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["rpc_mode"] = "call"
    await update.message.reply_text(
        "📖 <b>Read from a contract</b>\n\n"
        "Enter the contract address:",
        parse_mode="HTML",
    )
    return CALL_STATE


@rate_limited
async def write_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["rpc_mode"] = "write"
    await update.message.reply_text(
        "✍️ <b>Write to a contract</b>\n\n"
        "Enter the contract address:",
        parse_mode="HTML",
    )
    return CALL_STATE


async def call_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = update.message.text.strip()
    if not (address.startswith("0x") and len(address) == 42):
        await update.message.reply_text(
            "❌ Invalid address format. Must be 0x followed by 40 hex chars.\n"
            "Try again or /cancel."
        )
        return CALL_STATE

    context.user_data["contract_address"] = address
    mode = context.user_data.get("rpc_mode", "call")
    action = "read" if mode == "call" else "write"

    await update.message.reply_text(
        f"Contract: <code>{address}</code>\n\n"
        f"Enter the method and args to {action}.\n\n"
        f"<b>Format:</b> <code>method_name(arg1, arg2, ...)</code>\n\n"
        f"<b>Examples:</b>\n"
        f"• <code>get_count()</code>\n"
        f"• <code>get_balance(\"0xabc...\")</code>\n"
        f"• <code>increment(42)</code>\n\n"
        f"<i>Args are parsed as JSON. Bare words are auto-quoted as strings.</i>",
        parse_mode="HTML",
    )
    return CALL_STATE + 1


async def call_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    raw = update.message.text.strip()
    address = context.user_data.get("contract_address", "")
    mode = context.user_data.get("rpc_mode", "call")
    network = context.user_data.get("network", "studionet")

    try:
        method_name, args = _parse_method_call(raw)
    except ValueError as ve:
        await update.message.reply_text(f"❌ {ve}")
        return CALL_STATE + 1

    if method_name is None:
        await update.message.reply_text(
            "❌ Invalid syntax. Use: <code>method_name(arg1, arg2)</code>",
            parse_mode="HTML",
        )
        return CALL_STATE + 1

    await update.message.reply_text(
        f"⏳ Executing <code>{method_name}({len(args)} args)</code> on {network}…",
        parse_mode="HTML",
    )

    try:
        if mode == "call":
            result = await genlayer_rpc.call_contract(
                contract_address=address,
                method=method_name,
                args=args,
                network=network,
            )
        else:
            wallet = await wallet_service.get_or_create_wallet(user_id)
            result = await genlayer_rpc.write_contract(
                from_address=wallet["address"],
                contract_address=address,
                method=method_name,
                args=args,
                network=network,
            )

        if result.get("error"):
            await update.message.reply_text(f"❌ RPC Error:\n<pre>{result['error'][:1000]}</pre>", parse_mode="HTML")
        else:
            data = result.get("result", result)
            text = json.dumps(data, indent=2, default=str) if not isinstance(data, str) else data
            if len(text) > 3500:
                text = text[:3500] + "\n... (truncated)"
            await update.message.reply_text(
                f"✅ Result:\n<pre>{text}</pre>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("call/write failed")
        await update.message.reply_text(f"❌ Error: {str(e)[:500]}")

    context.user_data.pop("contract_address", None)
    context.user_data.pop("rpc_mode", None)
    return ConversationHandler.END
