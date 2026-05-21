"""Runtime failover helpers shared by polling/webhook deployments."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

try:
    from redis.asyncio import from_url as redis_from_url
except ImportError:  # pragma: no cover - optional dependency during bootstrap
    redis_from_url = None

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeConfig:
    bot_name: str
    bot_label: str
    runtime_origin: str
    backend_role: str
    runtime_instance_id: str
    redis_url: str
    processed_ttl_seconds: int
    lock_ttl_seconds: int
    notice_cooldown_seconds: int
    fallback_notice_text: str


def build_runtime_config(bot_name: str, bot_label: str) -> RuntimeConfig:
    return RuntimeConfig(
        bot_name=bot_name,
        bot_label=bot_label,
        runtime_origin=os.getenv("RUNTIME_ORIGIN", "vps").strip() or "vps",
        backend_role=os.getenv("BACKEND_ROLE", "primary").strip() or "primary",
        runtime_instance_id=(
            os.getenv("RUNTIME_INSTANCE_ID", "").strip() or uuid.uuid4().hex[:12]
        ),
        redis_url=os.getenv("REDIS_URL", "").strip(),
        processed_ttl_seconds=int(os.getenv("UPDATE_PROCESSED_TTL_SECONDS", "21600")),
        lock_ttl_seconds=int(os.getenv("UPDATE_LOCK_TTL_SECONDS", "120")),
        notice_cooldown_seconds=int(os.getenv("FALLBACK_NOTICE_COOLDOWN_SECONDS", "1800")),
        fallback_notice_text=(
            os.getenv(
                "FALLBACK_NOTICE_TEXT",
                "Our primary backend is currently down. We switched to our Render backup. "
                "Responses may be slower for a while, please bear with us.",
            ).strip()
        ),
    )


class DeliveryStateStore:
    """Cross-runtime best-effort update deduplication and fallback notices."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.redis = None
        self._processed: dict[int, float] = {}
        self._locks: dict[int, tuple[str, float]] = {}
        self._notices: dict[int, float] = {}

    async def startup(self) -> None:
        if self.config.redis_url and redis_from_url is not None:
            self.redis = redis_from_url(self.config.redis_url, decode_responses=True)

    async def shutdown(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None

    def health_payload(self) -> dict[str, str]:
        return {
            "status": "ok",
            "bot": self.config.bot_name,
            "runtimeOrigin": self.config.runtime_origin,
            "backendRole": self.config.backend_role,
            "runtimeInstanceId": self.config.runtime_instance_id,
        }

    async def claim_update(self, update_id: int) -> bool:
        if self.redis is not None:
            processed_key = self._processed_key(update_id)
            if await self.redis.exists(processed_key):
                return False
            lock_key = self._lock_key(update_id)
            return bool(
                await self.redis.set(
                    lock_key,
                    self.config.runtime_instance_id,
                    ex=self.config.lock_ttl_seconds,
                    nx=True,
                )
            )

        self._purge_local_state()
        if update_id in self._processed:
            return False
        owner = self._locks.get(update_id)
        if owner and owner[1] > time.time():
            return owner[0] == self.config.runtime_instance_id
        self._locks[update_id] = (
            self.config.runtime_instance_id,
            time.time() + self.config.lock_ttl_seconds,
        )
        return True

    async def mark_processed(self, update_id: int) -> None:
        if self.redis is not None:
            await self.redis.set(
                self._processed_key(update_id),
                self.config.runtime_instance_id,
                ex=self.config.processed_ttl_seconds,
            )
            await self.redis.delete(self._lock_key(update_id))
            return

        self._purge_local_state()
        self._processed[update_id] = time.time() + self.config.processed_ttl_seconds
        self._locks.pop(update_id, None)

    async def should_send_fallback_notice(self, chat_id: int) -> bool:
        if self.config.runtime_origin != "render" and self.config.backend_role != "fallback":
            return False

        if self.redis is not None:
            return bool(
                await self.redis.set(
                    self._notice_key(chat_id),
                    self.config.runtime_instance_id,
                    ex=self.config.notice_cooldown_seconds,
                    nx=True,
                )
            )

        self._purge_local_state()
        expires_at = self._notices.get(chat_id, 0)
        if expires_at > time.time():
            return False
        self._notices[chat_id] = time.time() + self.config.notice_cooldown_seconds
        return True

    def _processed_key(self, update_id: int) -> str:
        return f"bot:{self.config.bot_name}:update:{update_id}:processed"

    def _lock_key(self, update_id: int) -> str:
        return f"bot:{self.config.bot_name}:update:{update_id}:lock"

    def _notice_key(self, chat_id: int) -> str:
        return f"bot:{self.config.bot_name}:chat:{chat_id}:fallback-notice"

    def _purge_local_state(self) -> None:
        now = time.time()
        self._processed = {key: value for key, value in self._processed.items() if value > now}
        self._locks = {key: value for key, value in self._locks.items() if value[1] > now}
        self._notices = {key: value for key, value in self._notices.items() if value > now}


async def install_failover(application, bot_name: str, bot_label: str) -> None:
    config = build_runtime_config(bot_name, bot_label)
    store = DeliveryStateStore(config)
    await store.startup()
    application.bot_data["runtime_config"] = config
    application.bot_data["delivery_state_store"] = store
    application.bot_data["claimed_update_ids"] = set()


async def shutdown_failover(application) -> None:
    store: DeliveryStateStore | None = application.bot_data.get("delivery_state_store")
    if store is not None:
        await store.shutdown()


def runtime_health_payload(bot_name: str, bot_label: str) -> dict[str, str]:
    config = build_runtime_config(bot_name, bot_label)
    return {
        "status": "ok",
        "bot": config.bot_name,
        "botLabel": config.bot_label,
        "runtimeOrigin": config.runtime_origin,
        "backendRole": config.backend_role,
        "runtimeInstanceId": config.runtime_instance_id,
    }


async def duplicate_guard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not isinstance(update, Update):
        return
    store: DeliveryStateStore | None = context.application.bot_data.get("delivery_state_store")
    if store is None:
        return
    if not await store.claim_update(update.update_id):
        logger.info("Skipping duplicate update for %s update_id=%s", store.config.bot_name, update.update_id)
        raise ApplicationHandlerStop
    context.application.bot_data["claimed_update_ids"].add(update.update_id)


async def degraded_runtime_notice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not isinstance(update, Update):
        return

    store: DeliveryStateStore | None = context.application.bot_data.get("delivery_state_store")
    if store is None or update.effective_chat is None:
        return
    target_message = update.effective_message
    if target_message is None and update.callback_query is not None:
        target_message = update.callback_query.message
    if target_message is None:
        return
    if await store.should_send_fallback_notice(update.effective_chat.id):
        await target_message.reply_text(store.config.fallback_notice_text)


async def finalize_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not isinstance(update, Update):
        return
    claimed_updates: set[int] = context.application.bot_data.get("claimed_update_ids", set())
    if update.update_id not in claimed_updates:
        return
    store: DeliveryStateStore | None = context.application.bot_data.get("delivery_state_store")
    if store is None:
        return
    await store.mark_processed(update.update_id)
    claimed_updates.discard(update.update_id)
