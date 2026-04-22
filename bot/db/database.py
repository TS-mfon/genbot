"""SQLite database setup and access via aiosqlite."""

import aiosqlite
import logging

from bot.config import settings

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Initialize the database and create tables."""
    global _db
    _db = await aiosqlite.connect(settings.database_path)

    await _db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            telegram_username TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await _db.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            user_id INTEGER PRIMARY KEY,
            address TEXT NOT NULL,
            encrypted_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    await _db.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            code_snippet TEXT DEFAULT '',
            tx_hash TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_contracts_user_id ON contracts(user_id)
    """)

    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_contracts_address ON contracts(address)
    """)

    await _db.commit()
    logger.info(f"Database initialized at {settings.database_path}")


async def get_db() -> aiosqlite.Connection:
    """Get the database connection, initializing if needed."""
    global _db
    if _db is None:
        await init_db()
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None
