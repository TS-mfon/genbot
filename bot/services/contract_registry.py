"""Track deployed contracts per user via SQLite."""

import logging
from typing import Optional

from bot.db.database import get_db

logger = logging.getLogger(__name__)


class ContractRegistry:
    """Registry for tracking user-deployed contracts."""

    async def register_contract(
        self,
        user_id: int,
        contract_address: str,
        code_snippet: str,
        tx_hash: str,
    ) -> None:
        """Register a newly deployed contract for a user."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO contracts (user_id, address, code_snippet, tx_hash)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, contract_address, code_snippet, tx_hash),
        )
        await db.commit()
        logger.info(f"Registered contract {contract_address} for user {user_id}")

    async def get_user_contracts(self, user_id: int) -> list[dict]:
        """Get all contracts deployed by a user."""
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT address, code_snippet, tx_hash, created_at
            FROM contracts
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "address": row[0],
                "code_snippet": row[1],
                "tx_hash": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    async def get_contract_by_address(self, address: str) -> Optional[dict]:
        """Look up a contract by address."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT user_id, address, code_snippet, tx_hash, created_at FROM contracts WHERE address = ?",
            (address,),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "user_id": row[0],
                "address": row[1],
                "code_snippet": row[2],
                "tx_hash": row[3],
                "created_at": row[4],
            }
        return None


# Singleton
contract_registry = ContractRegistry()
