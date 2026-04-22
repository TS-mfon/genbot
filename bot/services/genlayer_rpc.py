"""GenLayer CLI + JSON-RPC client."""

import httpx
import json
import logging
import os
import subprocess
import tempfile
from typing import Any

from bot.config import settings

logger = logging.getLogger(__name__)


class GenLayerRPC:
    """Client for GenLayer network - uses CLI for deploy, RPC for queries."""

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

    # ------------------------------------------------------------------ #
    #  Deploy via genlayer CLI (fixes "Method not found: gen_deployContract")
    # ------------------------------------------------------------------ #

    async def deploy_contract(
        self,
        code: str,
        user_private_key: str,
        password: str,
        network: str = "studionet",
    ) -> dict:
        """Deploy contract using the genlayer CLI."""
        # Write code to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            # 1. Set network
            subprocess.run(
                ["genlayer", "network", "set", network],
                capture_output=True,
                text=True,
            )

            # 2. Import user's private key (idempotent - will warn if exists)
            subprocess.run(
                ["genlayer", "account", "import"],
                capture_output=True,
                text=True,
                input=f"{user_private_key}\n{password}\n{password}\n",
                timeout=30,
            )

            # 3. Unlock the account
            subprocess.run(
                ["genlayer", "account", "unlock"],
                capture_output=True,
                text=True,
                input=f"{password}\n",
                timeout=30,
            )

            # 4. Deploy
            result = subprocess.run(
                ["genlayer", "deploy", "--contract", temp_path],
                capture_output=True,
                text=True,
                input=f"{password}\n",
                timeout=120,
            )

            output = result.stdout
            logger.info(f"genlayer deploy stdout: {output}")
            logger.info(f"genlayer deploy stderr: {result.stderr}")

            # Parse contract address from output
            for line in output.split("\n"):
                if "Contract Address" in line or "contract_address" in line:
                    # Handle formats like:  Contract Address: '0xabc...'
                    #                    or Contract Address: 0xabc...
                    if "'" in line:
                        addr = line.split("'")[-2]
                    elif ":" in line:
                        addr = line.split(":")[-1].strip().strip("'\"")
                    else:
                        addr = line.split()[-1]
                    return {"address": addr, "success": True, "output": output}

            # Also check for 0x addresses in the output as fallback
            import re
            addr_match = re.search(r"(0x[0-9a-fA-F]{40})", output)
            if addr_match:
                return {
                    "address": addr_match.group(1),
                    "success": True,
                    "output": output,
                }

            return {
                "error": result.stderr or output or "No contract address in output",
                "success": False,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Deployment timed out (120s)", "success": False}
        except FileNotFoundError:
            return {
                "error": "genlayer CLI not found. Install with: pip install genlayer",
                "success": False,
            }
        except Exception as e:
            return {"error": str(e), "success": False}
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    #  RPC-based read/write operations (unchanged)
    # ------------------------------------------------------------------ #

    async def call_contract(
        self, contract_address: str, method: str, args: list | None = None
    ) -> dict:
        """Read from a contract (no state change)."""
        params = {
            "to": contract_address,
            "method": method,
            "args": args or [],
        }
        return await self._rpc_call("gen_call", [params])

    async def write_contract(
        self,
        from_address: str,
        contract_address: str,
        method: str,
        args: list | None = None,
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
