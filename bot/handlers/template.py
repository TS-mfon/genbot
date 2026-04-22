"""Template handler - provide starter contract templates."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.template_service import template_service

TEMPLATE_STATE = 40


async def template_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /template command - show available templates as buttons."""
    templates = template_service.list_templates()
    keyboard = []
    for i, t in enumerate(templates):
        keyboard.append(
            [InlineKeyboardButton(
                f"{t['name']} - {t['description']}",
                callback_data=f"tpl_{t['key']}",
            )]
        )

    await update.message.reply_text(
        "Select a GenLayer contract template:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def template_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle template selection button press."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("tpl_"):
        return

    key = data[4:]  # strip "tpl_" prefix
    templates = template_service.list_templates()
    template = next((t for t in templates if t["key"] == key), None)

    if template is None:
        await query.edit_message_text("Template not found.")
        return

    code = template_service.get_template_code(key)

    if not code or code == "# Template not found":
        await query.edit_message_text(
            "Sorry, this template is not available yet."
        )
        return

    # Send template name first
    await query.edit_message_text(
        f"<b>Template: {template['name']}</b>\n"
        f"{template['description']}",
        parse_mode="HTML",
    )

    # Send code in a separate message to avoid length issues
    # Split long code into chunks if needed (Telegram max 4096 chars)
    code_msg = f"<pre>{_escape_html(code)}</pre>"
    if len(code_msg) <= 4096:
        await query.message.reply_text(code_msg, parse_mode="HTML")
    else:
        # Split by lines to avoid breaking mid-line
        lines = code.split("\n")
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 3900:
                await query.message.reply_text(
                    f"<pre>{_escape_html(chunk)}</pre>",
                    parse_mode="HTML",
                )
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk.strip():
            await query.message.reply_text(
                f"<pre>{_escape_html(chunk)}</pre>",
                parse_mode="HTML",
            )

    await query.message.reply_text(
        "Upload this code as a .py file and use /deploy to deploy it!"
    )


async def template_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle template selection by number (legacy text-based)."""
    choice = update.message.text.strip()
    templates = template_service.list_templates()

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(templates):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"Please enter a number between 1 and {len(templates)}."
        )
        return TEMPLATE_STATE

    template = templates[idx]
    code = template_service.get_template_code(template["key"])

    # Send code using HTML to avoid markdown escaping issues
    code_msg = f"<pre>{_escape_html(code)}</pre>"
    if len(code_msg) <= 4096:
        await update.message.reply_text(
            f"<b>Template: {template['name']}</b>\n\n{code_msg}\n\n"
            "Upload this code as a .py file and use /deploy to deploy it!",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"<b>Template: {template['name']}</b>",
            parse_mode="HTML",
        )
        lines = code.split("\n")
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 3900:
                await update.message.reply_text(
                    f"<pre>{_escape_html(chunk)}</pre>",
                    parse_mode="HTML",
                )
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk.strip():
            await update.message.reply_text(
                f"<pre>{_escape_html(chunk)}</pre>",
                parse_mode="HTML",
            )
        await update.message.reply_text(
            "Upload this code as a .py file and use /deploy to deploy it!"
        )

    return ConversationHandler.END


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
