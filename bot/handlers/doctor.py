"""Doctor command for diagnosing GenLayer contract interaction issues."""

from __future__ import annotations

import html

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.contract_registry import contract_registry
from bot.services.genlayer_rpc import genlayer_rpc
from bot.services.genlayer_errors import render_cli_error_html


async def doctor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /doctor <contract_address>."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /doctor <contract_address>\n\n"
            "Example:\n"
            "/doctor 0x25d3D67Ac4C5b3108355D7D72660E6Cd3140C3C6"
        )
        return

    address = context.args[0].strip()
    if not (address.startswith("0x") and len(address) == 42):
        await update.message.reply_text("Invalid address. Use a 0x address with 40 hex characters.")
        return

    current_network = context.user_data.get("network", "studionet")
    await update.message.reply_text(
        f"🩺 Checking <code>{address}</code> on <b>{current_network}</b>...",
        parse_mode="HTML",
    )

    registered = await contract_registry.get_contract_by_address(address)
    schema = await genlayer_rpc.get_schema(address, network=current_network)
    code = await genlayer_rpc.get_code(address, network=current_network)

    lines = [
        "🩺 <b>GenLayer Contract Doctor</b>",
        "",
        f"Address: <code>{html.escape(address)}</code>",
        f"Current network: <code>{html.escape(current_network)}</code>",
    ]

    if registered:
        lines.extend(
            [
                f"Saved network: <code>{html.escape(registered.get('network', 'studionet'))}</code>",
                f"Saved tx: <code>{html.escape(registered.get('tx_hash') or '(none)')}</code>",
                f"Saved deploy args: <code>{html.escape(registered.get('constructor_args') or '[]')}</code>",
                f"Saved status: <code>{html.escape(registered.get('status') or 'unknown')}</code>",
            ]
        )
        if registered.get("network") and registered["network"] != current_network:
            lines.extend(
                [
                    "",
                    "⚠️ <b>Network mismatch detected.</b>",
                    "This is the most common reason for “contract not found”.",
                    f"Use /network and switch to <code>{html.escape(registered['network'])}</code>, then retry.",
                ]
            )
    else:
        lines.extend(
            [
                "Saved locally: <code>no</code>",
                "If you deployed outside this bot, make sure /network matches that deployment.",
            ]
        )

    if schema.get("error"):
        lines.extend(
            [
                "",
                "Schema check: ❌ failed",
                "The contract is not callable from the currently selected network yet.",
                "",
                render_cli_error_html(
                    operation="schema lookup",
                    stdout=schema.get("stdout", ""),
                    stderr=schema.get("stderr", schema.get("error", "")),
                    returncode=schema.get("returncode"),
                    address=address,
                    network=current_network,
                    include_debug=False,
                ),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Schema check: ✅ available",
                "Next: use /call for view methods or /write for state-changing methods.",
                "",
                "<b>Example calls</b>",
                "<pre>get_state()\nget_count()\nincrement()\nrename(\"Demo counter\")</pre>",
            ]
        )

    if code:
        lines.append("Code check: ✅ source available")
    else:
        lines.append("Code check: ⚠️ source unavailable from current network")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n... (truncated)"
    await update.message.reply_text(text, parse_mode="HTML")
