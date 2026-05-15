"""Track deployed contracts per user via SQLite."""

import logging
import json
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
        network: str = "studionet",
        constructor_args: list | None = None,
        status: str = "unknown",
    ) -> None:
        """Register a newly deployed contract for a user."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO contracts (user_id, address, code_snippet, tx_hash, network, constructor_args, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                contract_address,
                code_snippet,
                tx_hash,
                network,
                json.dumps(constructor_args or []),
                status,
            ),
        )
        await db.commit()
        logger.info(f"Registered contract {contract_address} for user {user_id}")

    async def get_user_contracts(self, user_id: int) -> list[dict]:
        """Get all contracts deployed by a user."""
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT address, code_snippet, tx_hash, created_at, network, constructor_args, status
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
                "network": row[4] if len(row) > 4 else "studionet",
                "constructor_args": row[5] if len(row) > 5 else "[]",
                "status": row[6] if len(row) > 6 else "unknown",
            }
            for row in rows
        ]

    async def get_contract_by_address(self, address: str) -> Optional[dict]:
        """Look up a contract by address."""
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT user_id, address, code_snippet, tx_hash, created_at, network, constructor_args, status
            FROM contracts
            WHERE lower(address) = lower(?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
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
                "network": row[5] if len(row) > 5 else "studionet",
                "constructor_args": row[6] if len(row) > 6 else "[]",
                "status": row[7] if len(row) > 7 else "unknown",
            }
        return None

    async def update_status(self, address: str, status: str) -> None:
        """Update local readiness status for a contract."""
        db = await get_db()
        await db.execute(
            "UPDATE contracts SET status = ? WHERE lower(address) = lower(?)",
            (status, address),
        )
        await db.commit()


# Singleton
contract_registry = ContractRegistry()
