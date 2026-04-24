"""Network selection handler - switch between StudioNet and Bradbury Testnet."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

NETWORKS = {
    "net_studionet": {
        "key": "studionet",
        "name": "StudioNet",
        "description": "GenLayer development network",
    },
    "net_bradbury": {
        "key": "testnet-bradbury",
        "name": "Bradbury Testnet",
        "description": "GenLayer public testnet",
    },
    "net_asimov": {
        "key": "testnet-asimov",
        "name": "Asimov Testnet",
        "description": "Alternative GenLayer public testnet",
    },
}


async def network_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /network command - show network selection buttons."""
    current = context.user_data.get("network", "studionet")
    current_name = next(
        (net["name"] for net in NETWORKS.values() if net["key"] == current),
        "StudioNet",
    )

    keyboard = [
        [InlineKeyboardButton("StudioNet", callback_data="net_studionet")],
        [InlineKeyboardButton("Bradbury Testnet", callback_data="net_bradbury")],
        [InlineKeyboardButton("Asimov Testnet", callback_data="net_asimov")],
    ]
    await update.message.reply_text(
        f"Current network: <b>{current_name}</b>\n\n"
        "Select your GenLayer network:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def network_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle network selection button press."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data not in NETWORKS:
        await query.edit_message_text("Unknown network selection.")
        return

    net = NETWORKS[data]
    context.user_data["network"] = net["key"]

    await query.edit_message_text(
        f"Network set to: <b>{net['name']}</b>\n"
        f"{net['description']}\n\n"
        f"All future deploy, call, write, schema, and tx commands will use this network.",
        parse_mode="HTML",
    )
