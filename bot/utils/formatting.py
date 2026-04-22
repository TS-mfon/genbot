"""Text formatting utilities for Telegram messages."""

import re


def escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", text)


def truncate(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_address(address: str, show_chars: int = 8) -> str:
    """Format an address to show first and last N chars."""
    if len(address) <= show_chars * 2 + 2:
        return address
    return f"{address[:show_chars + 2]}...{address[-show_chars:]}"


def format_code_block(code: str, language: str = "python") -> str:
    """Wrap code in a Telegram markdown code block."""
    return f"```{language}\n{code}\n```"


def format_json(data: dict, indent: int = 2) -> str:
    """Format a dict as a readable JSON string."""
    import json
    return json.dumps(data, indent=indent, default=str)
