"""GenLayer client: uses the `genlayer` CLI with per-user imported accounts.

The CLI is the officially-supported deployment path. For each deploy, we
import the user's private key as a named genlayer account, unlock it, run
the deploy, then clean up.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

NETWORK_ALIASES = {
    "studionet": "studionet",
    "testnet": "testnet-bradbury",
    "bradbury": "testnet-bradbury",
    "testnet-bradbury": "testnet-bradbury",
    "asimov": "testnet-asimov",
    "testnet-asimov": "testnet-asimov",
    "localnet": "localnet",
}

# Shared password for keystore entries the bot creates. These accounts
# are ephemeral (removed after each deploy) and the private key material
# is separately encrypted in SQLite, so the password is a formality.
# IMPORTANT: Keep this plain alphanumeric — special chars can misbehave
# when piped through stdin on minimal containers (no OS keychain).
_KEYSTORE_PASSWORD = "genbotephemeralpassword1234"


def _account_name_for_user(user_id: int) -> str:
    """Derive a unique genlayer account name from the telegram user_id."""
    digest = hashlib.sha256(str(user_id).encode()).hexdigest()[:12]
    return f"tg-{digest}"


async def _run(cmd: list[str], timeout: int = 120, stdin_input: str | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess off the event loop."""
    logger.debug("Running: %s", " ".join(cmd))
    return await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=stdin_input,
    )


class GenLayerClient:
    """Wraps the genlayer CLI + minimal JSON-RPC fallback."""

    def __init__(self):
        self.rpc_url = settings.genlayer_rpc_url

    def resolve_network(self, name: str) -> str:
        return NETWORK_ALIASES.get(name, "studionet")

    async def get_cli_version(self) -> str:
        """Return the installed genlayer CLI version."""
        if shutil.which("genlayer") is None:
            raise FileNotFoundError("genlayer CLI not found in PATH")

        proc = await _run(["genlayer", "--version"], timeout=15)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "genlayer --version failed").strip())
        return (proc.stdout or proc.stderr).strip()

    async def set_network(self, name: str) -> bool:
        alias = self.resolve_network(name)
        proc = await _run(["genlayer", "network", "set", alias], timeout=30)
        if proc.returncode != 0:
            logger.warning("network set failed: %s", proc.stderr[:300])
        return proc.returncode == 0

    async def ensure_account(self, user_id: int, private_key: str) -> str:
        """Import + unlock the user's private key as a genlayer account.

        Idempotent: remove any prior keystore with the same name first,
        then freshly import with our known password.
        Returns the account name.
        """
        name = _account_name_for_user(user_id)

        # 1. Nuke any prior keystore for this name so the password can't drift.
        await _run(
            ["genlayer", "account", "remove", "--force", name],
            timeout=15,
        )

        # 2. Fresh import with --overwrite defensively
        proc = await _run(
            [
                "genlayer", "account", "import",
                "--name", name,
                "--private-key", private_key,
                "--password", _KEYSTORE_PASSWORD,
                "--overwrite",
            ],
            timeout=30,
        )
        logger.info(
            "account import rc=%s stdout=%s stderr=%s",
            proc.returncode,
            (proc.stdout or "")[-200:],
            (proc.stderr or "")[-200:],
        )
        if proc.returncode != 0:
            raise RuntimeError(f"account import failed: {proc.stderr or proc.stdout}")

        # 3. Use this account as active
        await _run(["genlayer", "account", "use", name], timeout=15)

        # 4. Unlock (no-op on Render because no OS keychain, but harmless)
        unlock_proc = await _run(
            [
                "genlayer", "account", "unlock",
                "--account", name,
                "--password", _KEYSTORE_PASSWORD,
            ],
            timeout=30,
        )
        if unlock_proc.returncode != 0:
            logger.warning("unlock rc=%s stderr=%s", unlock_proc.returncode, (unlock_proc.stderr or "")[:300])

        return name

    async def deploy_contract(
        self,
        code: str,
        user_id: int,
        private_key: str,
        network: str = "studionet",
        args: list | None = None,
    ) -> dict[str, Any]:
        """Deploy via the genlayer CLI using the user's private key.

        Returns:
            {"success": True, "address": "0x...", "tx_hash": "0x...", "output": "..."}
            {"success": False, "error": "..."}
        """
        # Auto-prepend valid header if missing
        code_stripped = code.strip()
        if not code_stripped.startswith("#"):
            code = '# { "Depends": "py-genlayer:test" }\n' + code

        # 1. Select network
        await self.set_network(network)

        # 2. Import + unlock the user's account
        try:
            await self.ensure_account(user_id, private_key)
        except Exception as e:
            return {"success": False, "error": f"Failed to prepare account: {e}"}

        # 3. Write code to temp file and deploy
        fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="contract_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(code)

            cmd = ["genlayer", "deploy", "--contract", temp_path]
            if args:
                cmd.append("--args")
                cmd.extend(str(a) for a in args)

            logger.info("Deploying user=%s via CLI", user_id)
            # Pipe the keystore password to stdin in case the CLI prompts
            # (happens on fresh containers without an OS keychain, e.g. Render).
            # Feed it 3 times because the CLI allows 3 password attempts.
            pw_stdin = (_KEYSTORE_PASSWORD + "\n") * 3
            proc = await _run(cmd, timeout=180, stdin_input=pw_stdin)

            output = proc.stdout or ""
            stderr = proc.stderr or ""
            combined = output + "\n" + stderr

            logger.info("deploy rc=%s out_bytes=%s err_bytes=%s", proc.returncode, len(output), len(stderr))

            # Parse address/tx hash
            addr_match = re.search(r"Contract Address['\":]*\s*['\"]?(0x[a-fA-F0-9]{40})", combined)
            tx_match = re.search(
                r"(?:Deployment Transaction Hash|Transaction Hash|tx_hash)['\":]*\s*['\"]?(0x[a-fA-F0-9]+)",
                combined,
                re.IGNORECASE,
            )

            if addr_match:
                return {
                    "success": True,
                    "address": addr_match.group(1),
                    "tx_hash": tx_match.group(1) if tx_match else "",
                    "output": combined[-500:],
                }

            # Fallback: any 0x40 hex in output when the output clearly indicates success
            any_addr = re.search(r"(0x[a-fA-F0-9]{40})", combined)
            if any_addr and ("deployed" in combined.lower() or "success" in combined.lower()):
                return {
                    "success": True,
                    "address": any_addr.group(1),
                    "tx_hash": tx_match.group(1) if tx_match else "",
                    "output": combined[-500:],
                }

            # Non-zero exit code or no address = failure
            err_body = stderr or output or "No contract address in CLI output"
            return {"success": False, "error": err_body[-1500:]}

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

    # ---------------- Call / Write (per-user signing) ----------------

    async def call_contract(
        self,
        contract_address: str,
        method: str,
        args: list | None = None,
        network: str = "studionet",
    ) -> dict[str, Any]:
        """Read from a contract via `genlayer call` (no signing needed)."""
        await self.set_network(network)

        cmd = ["genlayer", "call", contract_address, method]
        if args:
            cmd.append("--args")
            cmd.extend(self._format_cli_arg(a) for a in args)

        proc = await _run(cmd, timeout=60)
        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout)[-800:]}

        output = proc.stdout or ""
        m = re.search(r"Result:\s*(\{.*\}|\[.*\]|\".*\"|\d+|true|false|null)", output, re.DOTALL)
        if m:
            try:
                return {"result": json.loads(m.group(1))}
            except json.JSONDecodeError:
                return {"result": m.group(1).strip()}
        return {"result": output.strip()}

    async def write_contract(
        self,
        user_id: int,
        private_key: str,
        contract_address: str,
        method: str,
        args: list | None = None,
        network: str = "studionet",
    ) -> dict[str, Any]:
        """Write tx via `genlayer write`. Requires per-user account setup."""
        await self.set_network(network)
        try:
            await self.ensure_account(user_id, private_key)
        except Exception as e:
            return {"error": f"Account setup failed: {e}"}

        cmd = ["genlayer", "write", contract_address, method]
        if args:
            cmd.append("--args")
            cmd.extend(self._format_cli_arg(a) for a in args)

        # Pipe password on stdin in case CLI prompts (Render has no OS keychain)
        pw_stdin = (_KEYSTORE_PASSWORD + "\n") * 3
        proc = await _run(cmd, timeout=120, stdin_input=pw_stdin)
        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout)[-800:]}

        tx_match = re.search(r"(?:Transaction Hash|tx_hash)['\":]*\s*['\"]?(0x[a-fA-F0-9]+)", proc.stdout or "", re.IGNORECASE)
        return {
            "result": (proc.stdout or "")[-500:],
            "tx_hash": tx_match.group(1) if tx_match else "",
        }

    async def get_code(self, contract_address: str, network: str = "studionet") -> str:
        await self.set_network(network)
        proc = await _run(["genlayer", "code", contract_address], timeout=30)
        return proc.stdout if proc.returncode == 0 else ""

    async def get_schema(self, contract_address: str, network: str = "studionet") -> dict[str, Any]:
        """Read deployed contract schema via the CLI."""
        await self.set_network(network)
        proc = await _run(["genlayer", "schema", contract_address], timeout=30)
        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout or "schema failed")[-1000:]}
        return {"result": (proc.stdout or "").strip()}

    async def get_transaction(self, tx_hash: str, network: str = "studionet") -> dict[str, Any]:
        """Inspect a transaction via `genlayer receipt`."""
        await self.set_network(network)
        proc = await _run(["genlayer", "receipt", tx_hash], timeout=90)
        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout or "receipt failed")[-1500:]}
        return {"result": (proc.stdout or "").strip()}

    # ---------------- RPC fallback ----------------

    @staticmethod
    def _format_cli_arg(value: Any) -> str:
        """Format Python values for `genlayer --args`."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    async def _rpc(self, method: str, params: list | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.post(self.rpc_url, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_validators(self) -> dict:
        return await self._rpc("gen_getValidators", [])

    async def request_faucet(self, address: str) -> dict:
        return await self._rpc("gen_fundAccount", [address])

    async def get_balance(self, address: str) -> dict:
        return await self._rpc("eth_getBalance", [address, "latest"])


# Singletons
genlayer_rpc = GenLayerClient()
genlayer_client = genlayer_rpc
