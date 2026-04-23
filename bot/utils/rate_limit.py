"""Per-user in-memory rate limiter for Telegram handlers."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

MAX_CMDS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
WINDOW_SECONDS = 60

_user_calls: dict[int, deque] = defaultdict(deque)


def rate_limited(func: Callable):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None:
            return await func(update, context, *args, **kwargs)

        uid = user.id
        now = time.monotonic()
        calls = _user_calls[uid]

        while calls and calls[0] < now - WINDOW_SECONDS:
            calls.popleft()

        if len(calls) >= MAX_CMDS_PER_MINUTE:
            try:
                await update.message.reply_text(
                    f"⚠️ Slow down! Max {MAX_CMDS_PER_MINUTE} commands per minute."
                )
            except Exception:
                pass
            return

        calls.append(now)
        return await func(update, context, *args, **kwargs)

    return wrapper
