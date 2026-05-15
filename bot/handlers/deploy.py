"""Deploy contract handler - supports file upload and text paste."""

import ast
import html
import json
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.contract_registry import contract_registry
from bot.services.genlayer_errors import render_cli_error_html
from bot.services.wallet_service import wallet_service
from bot.utils.rate_limit import rate_limited
from bot.handlers.call import _parse_args

logger = logging.getLogger(__name__)

DEPLOY_STATE = 10
DEPLOY_ARGS_STATE = 11
MAX_CONTRACT_SIZE = 200_000  # 200KB
GENLAYER_DEPENDS_HEADER = '# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }'
_DEPENDS_RE = re.compile(r'^\s*#?\s*\{\s*"Depends"\s*:\s*"py-genlayer:[^"]+"\s*\}\s*\n?', re.I)
_CONTRACT_CLASS_RE = re.compile(r"class\s+\w+\s*\([^)]*\bgl\.Contract\b[^)]*\)\s*:")


def normalize_contract_code(code: str) -> str:
    """Ensure the official GenLayer dependency magic comment is the first line."""
    code = code.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").lstrip()
    code = _DEPENDS_RE.sub("", code, count=1).lstrip()
    return f"{GENLAYER_DEPENDS_HEADER}\n{code}"


def contract_guidance_warnings(code: str) -> list[str]:
    """Return high-signal guidance from the GenLayer write-contract skill."""
    warnings: list[str] = []

    if "@gl.contract" in code:
        warnings.append("Use <code>class MyContract(gl.Contract)</code>; do not use the old <code>@gl.contract</code> decorator.")
    if not _CONTRACT_CLASS_RE.search(code):
        warnings.append("Define exactly one contract class that extends <code>gl.Contract</code>.")
    if "@gl.public.view" not in code and "@gl.public.write" not in code:
        warnings.append("Add at least one public method decorated with <code>@gl.public.view</code> or <code>@gl.public.write</code>.")
    if re.search(r"self\.\w+\s*:\s*\w+\s*=", code):
        warnings.append("Declare storage fields as class-level type annotations, not typed assignments inside <code>__init__</code>.")
    if re.search(r"self\.\w+\s*=\s*(\[\]|\{\}|list\(|dict\()", code):
        warnings.append("Use GenLayer storage types like <code>DynArray[T]</code> or <code>TreeMap[K, V]</code>, not Python list/dict for persisted state.")
    if "gl.nondet.exec_prompt" in code and 'response_format="json"' not in code and "response_format='json'" not in code:
        warnings.append("For LLM calls, use <code>gl.nondet.exec_prompt(..., response_format=\"json\")</code> and validate the returned shape.")
    if "strict_eq" in code and ("exec_prompt" in code or "nondet.web" in code or "get_webpage" in code):
        warnings.append("Use <code>strict_eq</code> only for deterministic/canonicalized outputs; LLM and variable web data need a custom validator.")
    if "raise Exception" in code:
        warnings.append("Use <code>gl.vm.UserError</code> with expected/transient error prefixes instead of bare exceptions.")

    return warnings


def _constructor_params(code: str) -> list[str]:
    """Return required constructor params excluding self."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_contract = any(
                isinstance(base, ast.Attribute)
                and isinstance(base.value, ast.Name)
                and base.value.id == "gl"
                and base.attr == "Contract"
                for base in node.bases
            )
            if not is_contract:
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    args = item.args.args[1:]  # skip self
                    default_count = len(item.args.defaults)
                    required_count = max(0, len(args) - default_count)
                    return [arg.arg for arg in args[:required_count]]
    return []


@rate_limited
async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    network = context.user_data.get("network", "studionet")
    await update.message.reply_text(
        f"🚀 <b>Deploy to GenLayer ({network})</b>\n\n"
        f"Upload a <b>.py</b> file or paste the full Python source code.\n\n"
        f"Your contract should start with:\n"
        f"<code>{GENLAYER_DEPENDS_HEADER}</code>\n\n"
        f"If missing or malformed, GenBot will normalize it before deployment.\n\n"
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
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    code: str,
    deploy_args: list | None = None,
) -> int:
    user_id = update.effective_user.id

    code = normalize_contract_code(code)

    # Syntax check after header normalization.
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

    warnings = contract_guidance_warnings(code)
    blocking = [
        warning for warning in warnings
        if "extends <code>gl.Contract</code>" in warning
        or "public method decorated" in warning
        or "old <code>@gl.contract</code>" in warning
    ]
    if blocking:
        await update.message.reply_text(
            "❌ <b>Contract structure needs fixing:</b>\n\n"
            + "\n".join(f"• {warning}" for warning in blocking)
            + "\n\nUse /template for a correct starter contract.",
            parse_mode="HTML",
        )
        return DEPLOY_STATE

    network = context.user_data.get("network", "studionet")
    required_ctor_args = _constructor_params(code)
    if required_ctor_args and deploy_args is None:
        context.user_data["pending_deploy_code"] = code
        context.user_data["pending_deploy_warnings"] = warnings
        context.user_data["pending_deploy_network"] = network
        example_values = []
        for name in required_ctor_args:
            if "label" in name.lower() or "name" in name.lower():
                example_values.append('"Demo counter"')
            elif "amount" in name.lower() or "supply" in name.lower() or "count" in name.lower():
                example_values.append("100")
            elif "enabled" in name.lower() or name.lower().startswith("is_"):
                example_values.append("true")
            else:
                example_values.append(f'"example_{name}"')
        await update.message.reply_text(
            "🧩 <b>This contract needs constructor arguments before deployment.</b>\n\n"
            f"Required value(s): <code>{html.escape(', '.join(required_ctor_args))}</code>\n\n"
            "Send the values only, comma-separated, using JSON-style formatting.\n\n"
            "<b>Example for this contract:</b>\n"
            f"<code>{html.escape(', '.join(example_values))}</code>\n\n"
            "<b>StorageCounter example:</b>\n"
            "<code>\"Demo counter\"</code>\n\n"
            "Send /cancel to abort.",
            parse_mode="HTML",
        )
        return DEPLOY_ARGS_STATE

    deploy_args = deploy_args or []

    await update.message.reply_text(
        f"✅ Code validated.\n\n"
        f"⏳ Deploying to <b>{network}</b> via genlayer CLI...\n"
        f"This takes 30-90 seconds.",
        parse_mode="HTML",
    )

    if warnings:
        await update.message.reply_text(
            "GenLayer contract quality notes:\n\n"
            + "\n".join(f"• {warning}" for warning in warnings[:5]),
            parse_mode="HTML",
        )

    try:
        wallet = await wallet_service.get_or_create_wallet(user_id)
        result = await genlayer_rpc.deploy_contract(
            code=code,
            user_id=user_id,
            private_key=wallet["private_key"],
            network=network,
            args=deploy_args,
        )

        if result.get("success"):
            addr = result.get("address", "")
            tx = result.get("tx_hash", "")

            if addr:
                readiness = "unknown"
                schema_check = await genlayer_rpc.get_schema(addr, network=network)
                if schema_check.get("error"):
                    readiness = "finalizing"
                else:
                    readiness = "ready"

                try:
                    await contract_registry.register_contract(
                        user_id=user_id,
                        contract_address=addr,
                        code_snippet=code[:200],
                        tx_hash=tx,
                        network=network,
                        constructor_args=deploy_args,
                        status=readiness,
                    )
                except Exception:
                    logger.exception("registry save failed (non-fatal)")

                msg = (
                    f"🎉 <b>Contract Deployed!</b>\n\n"
                    f"Address: <code>{addr}</code>\n"
                    f"Network: {network}\n"
                    f"Constructor args: <code>{html.escape(json.dumps(deploy_args))}</code>\n"
                    f"Status: <b>{readiness}</b>\n"
                )
                if tx:
                    msg += f"Tx: <code>{tx}</code>\n"
                msg += (
                    "\n<b>Next steps</b>\n"
                    f"1. Run <code>/schema {addr}</code>\n"
                    f"2. Use <code>/call</code> → paste address → <code>get_state()</code> or another view method\n"
                    f"3. Use <code>/write</code> only for state-changing methods\n\n"
                    "If schema/call says not found, wait 1-2 minutes or run "
                    f"<code>/doctor {addr}</code>."
                )

                await update.message.reply_text(msg, parse_mode="HTML")
            else:
                await update.message.reply_text(
                    f"⚠️ Deploy succeeded but no address returned.\n\n"
                    f"<pre>{result.get('output', '')[:1000]}</pre>",
                    parse_mode="HTML",
                )
        else:
            await update.message.reply_text(
                render_cli_error_html(
                    operation="deployment",
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", result.get("error", "")),
                    returncode=result.get("returncode"),
                    network=network,
                ),
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("deploy exception")
        await update.message.reply_text(f"❌ Error: {str(e)[:500]}")

    return ConversationHandler.END


async def deploy_args_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive constructor args for a pending deployment."""
    raw = update.message.text.strip()
    code = context.user_data.get("pending_deploy_code")
    if not code:
        await update.message.reply_text("No pending deployment found. Use /deploy to start again.")
        return ConversationHandler.END

    if raw.lower() in {"none", "no args", "no_args", "[]"}:
        deploy_args = []
    else:
        try:
            deploy_args = _parse_args(raw)
        except ValueError as exc:
            await update.message.reply_text(
                "❌ <b>Constructor args could not be parsed.</b>\n\n"
                f"{html.escape(str(exc))}\n\n"
                "<b>Examples</b>\n"
                "<code>\"Demo counter\"</code>\n"
                "<code>\"Token\", \"TKN\", 1000</code>\n"
                "<code>42, true, \"hello\"</code>",
                parse_mode="HTML",
            )
            return DEPLOY_ARGS_STATE

    context.user_data.pop("pending_deploy_code", None)
    context.user_data.pop("pending_deploy_warnings", None)
    context.user_data.pop("pending_deploy_network", None)
    return await _validate_and_deploy(update, context, code, deploy_args=deploy_args)
