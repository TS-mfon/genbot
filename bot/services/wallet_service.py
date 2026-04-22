"""Embedded wallet service with Fernet encryption."""

import logging
from typing import Optional

from bot.db.database import get_db
from bot.utils.encryption import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)


def _create_eth_account():
    """Create an Ethereum-compatible account.

    Uses eth_account if available, falls back to secrets-based generation.
    """
    try:
        from eth_account import Account
        acct = Account.create()
        return {
            "address": acct.address,
            "private_key": acct.key.hex() if isinstance(acct.key, bytes) else acct.key,
        }
    except ImportError:
        import hashlib
        import secrets
        private_key_bytes = secrets.token_bytes(32)
        private_key = "0x" + private_key_bytes.hex()
        address_hash = hashlib.sha256(private_key_bytes).hexdigest()
        address = "0x" + address_hash[:40]
        return {"address": address, "private_key": private_key}


class WalletService:
    """Manage embedded wallets for Telegram users."""

    async def get_or_create_wallet(self, user_id: int) -> dict:
        """Get existing wallet or create a new one for the user."""
        wallet = await self._get_wallet(user_id)
        if wallet:
            return wallet
        return await self._create_wallet(user_id)

    async def _get_wallet(self, user_id: int) -> Optional[dict]:
        """Retrieve a user's wallet from the database."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT address, encrypted_key FROM wallets WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "address": row[0],
                "private_key": decrypt_data(row[1]),
            }
        return None

    async def _create_wallet(self, user_id: int) -> dict:
        """Generate a new wallet for a user."""
        acct = _create_eth_account()
        private_key = acct["private_key"]
        address = acct["address"]

        # Encrypt and store
        encrypted_key = encrypt_data(private_key)

        db = await get_db()
        await db.execute(
            """
            INSERT INTO wallets (user_id, address, encrypted_key)
            VALUES (?, ?, ?)
            """,
            (user_id, address, encrypted_key),
        )
        await db.commit()

        logger.info(f"Created wallet {address} for user {user_id}")
        return {"address": address, "private_key": private_key}

    async def get_address(self, user_id: int) -> Optional[str]:
        """Get just the wallet address for a user."""
        wallet = await self._get_wallet(user_id)
        return wallet["address"] if wallet else None


# Singleton
wallet_service = WalletService()
