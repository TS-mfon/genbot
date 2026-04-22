"""GenLayer JSON-RPC client."""

import httpx
import json
import logging
from typing import Any

from bot.config import settings

logger = logging.getLogger(__name__)


class GenLayerRPC:
    """Async JSON-RPC client for GenLayer network."""

    def __init__(self):
        self.url = settings.genlayer_rpc_url
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _rpc_call(self, method: str, params: list | dict | None = None) -> dict:
        """Make a JSON-RPC 2.0 call to GenLayer."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or [],
        }

        logger.info(f"RPC call: {method} -> {self.url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e}")
                return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                return {"error": f"Connection error: {str(e)}"}
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response from RPC"}

    async def deploy_contract(self, from_address: str, code: str, args: list | None = None) -> dict:
        """Deploy an Intelligent Contract."""
        params = {
            "from": from_address,
            "code": code,
            "args": args or [],
        }
        return await self._rpc_call("gen_deployContract", [params])

    async def call_contract(self, contract_address: str, method: str, args: list | None = None) -> dict:
        """Read from a contract (no state change)."""
        params = {
            "to": contract_address,
            "method": method,
            "args": args or [],
        }
        return await self._rpc_call("gen_call", [params])

    async def write_contract(
        self, from_address: str, contract_address: str, method: str, args: list | None = None
    ) -> dict:
        """Write transaction to a contract (state change)."""
        params = {
            "from": from_address,
            "to": contract_address,
            "method": method,
            "args": args or [],
        }
        return await self._rpc_call("gen_sendTransaction", [params])

    async def get_transaction(self, tx_hash: str) -> dict:
        """Look up a transaction by hash."""
        return await self._rpc_call("gen_getTransactionByHash", [tx_hash])

    async def get_validators(self) -> dict:
        """Get current validator information."""
        return await self._rpc_call("gen_getValidators", [])

    async def request_faucet(self, address: str) -> dict:
        """Request testnet tokens from the faucet."""
        return await self._rpc_call("gen_fundAccount", [address])

    async def get_balance(self, address: str) -> dict:
        """Get account balance."""
        return await self._rpc_call("gen_getBalance", [address])

    async def get_contract_state(self, contract_address: str) -> dict:
        """Get the full state of a contract."""
        return await self._rpc_call("gen_getContractState", [contract_address])


# Singleton
genlayer_rpc = GenLayerRPC()
