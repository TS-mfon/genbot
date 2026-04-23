"""GenLayer client: uses the `genlayer` CLI for deploy/call/write.

The CLI is the officially-supported path. JSON-RPC is used as a thin
fallback for read-only queries (e.g., transaction lookup).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Any

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

# Network aliases the genlayer CLI accepts
NETWORK_ALIASES = {
    "studionet": "studionet",
    "testnet": "testnet-asimov",
    "bradbury": "testnet-asimov",
    "testnet-bradbury": "testnet-asimov",
    "testnet-asimov": "testnet-asimov",
    "localnet": "localnet",
}

# Valid contract header prefixes
VALID_HEADERS = [
    '# { "Depends": "py-genlayer:test" }',
    '# {"Depends": "py-genlayer:test"}',
]


class GenLayerClient:
    """Wraps the genlayer CLI + minimal JSON-RPC fallback."""

    def __init__(self):
        self.rpc_url = settings.genlayer_rpc_url
        self._current_network: str | None = None

    # ---------------- Network handling ----------------

    def resolve_network(self, name: str) -> str:
        return NETWORK_ALIASES.get(name, "studionet")

    async def set_network(self, name: str) -> bool:
        """Run `genlayer network set <alias>`."""
        alias = self.resolve_network(name)
        proc = await asyncio.to_thread(
            subprocess.run,
            ["genlayer", "network", "set", alias],
            capture_output=True,
            text=True,
            timeout=30,
        )
        ok = proc.returncode == 0
        if ok:
            self._current_network = alias
        else:
            logger.warning("network set failed: %s", proc.stderr)
        return ok

    # ---------------- Deploy ----------------

    async def deploy_contract(
        self,
        code: str,
        network: str = "studionet",
        args: list | None = None,
    ) -> dict[str, Any]:
        """Deploy via the genlayer CLI.

        Returns:
            {"success": True, "address": "0x...", "tx_hash": "0x...", "output": "..."}
            {"success": False, "error": "..."}
        """
        # Auto-prepend valid header if missing
        code_stripped = code.strip()
        if not code_stripped.startswith("#"):
            code = '# { "Depends": "py-genlayer:test" }\n' + code

        # Set network
        await self.set_network(network)

        # Write code to temp file
        fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="contract_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(code)

            cmd = ["genlayer", "deploy", "--contract", temp_path]
            if args:
                cmd.append("--args")
                cmd.extend(str(a) for a in args)

            logger.info("Deploying contract via CLI: %s", " ".join(cmd))

            proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )

            output = proc.stdout
            stderr = proc.stderr

            # Parse contract address
            addr_match = re.search(r"Contract Address:\s*['\"]?(0x[a-fA-F0-9]{40})", output)
            tx_match = re.search(r"(?:Transaction Hash|tx_hash):\s*['\"]?(0x[a-fA-F0-9]+)", output, re.IGNORECASE)

            if addr_match:
                return {
                    "success": True,
                    "address": addr_match.group(1),
                    "tx_hash": tx_match.group(1) if tx_match else "",
                    "output": output[-500:],
                }

            # Fallback: any 0x40 hex in output
            any_addr = re.search(r"(0x[a-fA-F0-9]{40})", output)
            if any_addr and "deployed" in output.lower():
                return {
                    "success": True,
                    "address": any_addr.group(1),
                    "tx_hash": tx_match.group(1) if tx_match else "",
                    "output": output[-500:],
                }

            return {
                "success": False,
                "error": (stderr or output or "No contract address in CLI output")[-1000:],
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Deploy timed out after 180s"}
        except FileNotFoundError:
            return {
                "success": False,
                "error": "genlayer CLI not found. Install with: npm install -g genlayer",
            }
        except Exception as e:
            logger.exception("Deploy error")
            return {"success": False, "error": str(e)}
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    # ---------------- Call / Write ----------------

    async def call_contract(
        self,
        contract_address: str,
        method: str,
        args: list | None = None,
        network: str = "studionet",
    ) -> dict[str, Any]:
        """Read from a contract via `genlayer call`."""
        await self.set_network(network)

        cmd = ["genlayer", "call", contract_address, method]
        if args:
            cmd.append("--args")
            cmd.extend(json.dumps(a) if not isinstance(a, str) else a for a in args)

        proc = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=60
        )

        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout)[-800:]}

        # Try to parse a JSON result from output
        output = proc.stdout
        json_match = re.search(r"Result:\s*(\{.*\}|\[.*\]|\".*\"|\d+|true|false|null)", output, re.DOTALL)
        if json_match:
            try:
                return {"result": json.loads(json_match.group(1))}
            except json.JSONDecodeError:
                return {"result": json_match.group(1).strip()}
        return {"result": output.strip()}

    async def write_contract(
        self,
        from_address: str,
        contract_address: str,
        method: str,
        args: list | None = None,
        network: str = "studionet",
    ) -> dict[str, Any]:
        """Write transaction via `genlayer write`."""
        await self.set_network(network)

        cmd = ["genlayer", "write", contract_address, method]
        if args:
            cmd.append("--args")
            cmd.extend(json.dumps(a) if not isinstance(a, str) else a for a in args)

        proc = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=120
        )

        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout)[-800:]}

        tx_match = re.search(r"(?:Transaction Hash|tx_hash):\s*['\"]?(0x[a-fA-F0-9]+)", proc.stdout, re.IGNORECASE)
        return {
            "result": proc.stdout.strip()[-500:],
            "tx_hash": tx_match.group(1) if tx_match else "",
        }

    # ---------------- Code / schema ----------------

    async def get_code(self, contract_address: str, network: str = "studionet") -> str:
        """Fetch deployed contract source via `genlayer code`."""
        await self.set_network(network)
        proc = await asyncio.to_thread(
            subprocess.run,
            ["genlayer", "code", contract_address],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return ""
        return proc.stdout

    # ---------------- RPC fallback ----------------

    async def _rpc(self, method: str, params: list | None = None) -> dict:
        """Raw JSON-RPC call."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.post(self.rpc_url, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_transaction(self, tx_hash: str) -> dict:
        return await self._rpc("eth_getTransactionByHash", [tx_hash])

    async def get_validators(self) -> dict:
        return await self._rpc("gen_getValidators", [])

    async def request_faucet(self, address: str) -> dict:
        return await self._rpc("gen_fundAccount", [address])

    async def get_balance(self, address: str) -> dict:
        return await self._rpc("eth_getBalance", [address, "latest"])


# Singletons expected by existing imports
genlayer_rpc = GenLayerClient()
genlayer_client = genlayer_rpc
