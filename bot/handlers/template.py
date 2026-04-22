"""Template handler - provide starter contract templates."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.services.template_service import template_service

TEMPLATE_STATE = 40


async def template_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /template command - show available templates."""
    templates = template_service.list_templates()
    lines = ["Available GenLayer contract templates:\n"]
    for i, t in enumerate(templates, 1):
        lines.append(f"  {i}. {t['name']} - {t['description']}")

    lines.append("\nReply with the template number to get the code.")
    lines.append("Send /cancel to abort.")

    await update.message.reply_text("\n".join(lines))
    return TEMPLATE_STATE


async def template_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle template selection."""
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

    await update.message.reply_text(
        f"Template: {template['name']}\n\n```python\n{code}\n```\n\n"
        f"Copy this code and use /deploy to deploy it!",
        parse_mode="Markdown",
    )
    return ConversationHandler.END
