"""GenLayer JSON-RPC client for deploying and interacting with contracts."""

import httpx
import json
import logging
from typing import Any

from bot.config import settings

logger = logging.getLogger(__name__)

# GenLayer studionet RPC endpoints
STUDIONET_RPC = "https://studio.genlayer.com/api"
# Bradbury testnet - update when available
BRADBURY_RPC = "https://rpc.genlayer.com"

NETWORK_RPCS = {
    "studionet": STUDIONET_RPC,
    "testnet": BRADBURY_RPC,
}


class GenLayerRPC:
    """Client for GenLayer network using JSON-RPC."""

    def __init__(self):
        self.default_url = settings.genlayer_rpc_url
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _get_rpc_url(self, network: str = "studionet") -> str:
        return NETWORK_RPCS.get(network, self.default_url)

    async def _rpc_call(self, method: str, params: list | dict | None = None, network: str = "studionet") -> dict:
        """Make a JSON-RPC 2.0 call to GenLayer."""
        url = self._get_rpc_url(network)
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or [],
        }

        logger.info(f"RPC call: {method} -> {url}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    return {"error": data["error"].get("message", str(data["error"]))}
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e}")
                return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                return {"error": f"Connection error: {str(e)}"}
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response from RPC"}

    # ------------------------------------------------------------------ #
    #  Deploy contract via RPC
    # ------------------------------------------------------------------ #

    async def deploy_contract(
        self,
        code: str,
        from_address: str,
        args: list | None = None,
        network: str = "studionet",
    ) -> dict:
        """Deploy contract using JSON-RPC.

        GenLayer contracts are deployed by sending the Python source code
        as a transaction. The contract header must start with:
        # {"Depends": "py-genlayer:test"} or similar.
        """
        # Ensure the contract has a valid header
        if not code.strip().startswith("#"):
            code = '# {"Depends": "py-genlayer:test"}\n' + code

        params = [{
            "from": from_address,
            "data": code,
            "args": args or [],
            "type": "deploy",
        }]

        result = await self._rpc_call("eth_sendTransaction", params, network=network)

        if "error" in result:
            # Try alternate method names
            for method in ["gen_deployIntelligentContract", "gen_sendTransaction"]:
                result = await self._rpc_call(method, params, network=network)
                if "error" not in result:
                    break

        if "result" in result:
            tx_hash = result["result"]
            # Wait for receipt to get contract address
            receipt = await self._wait_for_receipt(tx_hash, network=network)
            if receipt and receipt.get("result"):
                contract_addr = receipt["result"].get("contract_address", "")
                return {
                    "success": True,
                    "address": contract_addr,
                    "tx_hash": tx_hash,
                }

            return {
                "success": True,
                "tx_hash": tx_hash,
                "address": "",
                "note": "Contract deployed. Use /tx to check status."
            }

        return {
            "success": False,
            "error": result.get("error", "Unknown deployment error"),
        }

    async def _wait_for_receipt(self, tx_hash: str, network: str = "studionet", retries: int = 30) -> dict | None:
        """Poll for transaction receipt."""
        import asyncio
        for _ in range(retries):
            result = await self._rpc_call("eth_getTransactionReceipt", [tx_hash], network=network)
            if result.get("result"):
                return result
            await asyncio.sleep(2)
        return None

    # ------------------------------------------------------------------ #
    #  Read/write operations
    # ------------------------------------------------------------------ #

    async def call_contract(
        self, contract_address: str, method: str, args: list | None = None, network: str = "studionet"
    ) -> dict:
        """Read from a contract (no state change)."""
        params = [{
            "to": contract_address,
            "data": json.dumps({"method": method, "args": args or []}),
        }]
        return await self._rpc_call("eth_call", params, network=network)

    async def write_contract(
        self,
        from_address: str,
        contract_address: str,
        method: str,
        args: list | None = None,
        network: str = "studionet",
    ) -> dict:
        """Write transaction to a contract (state change)."""
        params = [{
            "from": from_address,
            "to": contract_address,
            "data": json.dumps({"method": method, "args": args or []}),
        }]
        return await self._rpc_call("eth_sendTransaction", params, network=network)

    async def get_transaction(self, tx_hash: str, network: str = "studionet") -> dict:
        """Look up a transaction by hash."""
        return await self._rpc_call("eth_getTransactionByHash", [tx_hash], network=network)

    async def get_validators(self, network: str = "studionet") -> dict:
        """Get current validator information."""
        return await self._rpc_call("gen_getValidators", [], network=network)

    async def request_faucet(self, address: str, network: str = "studionet") -> dict:
        """Request testnet tokens from the faucet."""
        return await self._rpc_call("gen_fundAccount", [address], network=network)

    async def get_balance(self, address: str, network: str = "studionet") -> dict:
        """Get account balance."""
        return await self._rpc_call("eth_getBalance", [address, "latest"], network=network)

    async def get_contract_state(self, contract_address: str, network: str = "studionet") -> dict:
        """Get the full state of a contract."""
        return await self._rpc_call("gen_getContractState", [contract_address], network=network)


# Singleton
genlayer_rpc = GenLayerRPC()
