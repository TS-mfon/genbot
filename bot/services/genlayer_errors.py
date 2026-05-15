"""GenLayer CLI error translation for user-facing bot replies."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass


DEPRECATED_PATTERNS = (
    "initializeConsensusSmartContract() is deprecated",
)


@dataclass(frozen=True)
class CliErrorView:
    title: str
    what_happened: str
    likely_cause: str
    fix_steps: tuple[str, ...]
    example: str


def clean_cli_output(text: str, limit: int = 1800) -> str:
    """Remove noisy warnings and keep the useful tail of CLI output."""
    lines = []
    for line in (text or "").splitlines():
        if any(pattern in line for pattern in DEPRECATED_PATTERNS):
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    if len(cleaned) > limit:
        cleaned = "...\n" + cleaned[-limit:]
    return cleaned or "(empty)"


def _format_cli_args(args: list | None) -> str:
    if not args:
        return ""
    return " " + " ".join(repr(arg) if isinstance(arg, str) else str(arg) for arg in args)


def classify_cli_error(
    *,
    operation: str,
    stderr: str = "",
    stdout: str = "",
    returncode: int | None = None,
    address: str = "",
    method: str = "",
    network: str = "",
    tx_hash: str = "",
) -> CliErrorView:
    raw = f"{stdout}\n{stderr}"
    text = raw.lower()

    if "contract" in text and "not found" in text:
        return CliErrorView(
            title="Contract not found on the selected GenLayer network",
            what_happened=(
                f"GenLayer could not find {address or 'that contract'} while running "
                f"{operation} on {network or 'the selected network'}."
            ),
            likely_cause=(
                "The address may be on a different network, the deployment may still be finalizing, "
                "or the explorer may show the transaction before the CLI/RPC can serve calls for it."
            ),
            fix_steps=(
                "Open /network and select the same network you used for deployment.",
                "Run /contracts and confirm the saved network beside the address.",
                f"Run /schema {address or '<contract_address>'} before calling a method.",
                "If the deployment is new, wait 1-2 minutes and retry after finalization.",
                "Run /doctor <contract_address> for an automatic network/schema/receipt check.",
            ),
            example=(
                f"/schema {address or '0x25d3D67Ac4C5b3108355D7D72660E6Cd3140C3C6'}\n"
                f"/call -> {address or '0x25d3D67Ac4C5b3108355D7D72660E6Cd3140C3C6'} -> {method or 'get_state()'}"
            ),
        )

    missing_arg = re.search(r"__init__\(\) missing \d+ required positional argument: '([^']+)'", raw)
    if missing_arg:
        arg = missing_arg.group(1)
        return CliErrorView(
            title="Deployment constructor argument is missing",
            what_happened=f"The contract constructor requires a value named `{arg}`, but none was provided.",
            likely_cause="The source code defines `def __init__(self, ...):` with required parameters.",
            fix_steps=(
                "Deploy again with /deploy.",
                f"When GenBot asks for constructor args, enter a value for `{arg}`.",
                "Use JSON-style values: strings in quotes, numbers as numbers, booleans as true/false.",
                "For StorageCounter, the label is just a human-readable name.",
            ),
            example='Constructor args example:\n"Demo counter"\n\nAfter deploy:\n/call -> <address> -> get_state()',
        )

    if "missing" in text and "required positional argument" in text:
        return CliErrorView(
            title="Method argument is missing",
            what_happened="The method needs one or more arguments that were not provided.",
            likely_cause="The method signature and the values you entered do not match.",
            fix_steps=(
                f"Run /schema {address or '<contract_address>'} to see the exact method signature.",
                "Call the method with parentheses and values in order.",
                "Use quotes around text values.",
            ),
            example=f"{method or 'rename'}(\"Demo counter\")",
        )

    if "method" in text and ("not found" in text or "does not exist" in text):
        return CliErrorView(
            title="Method not found",
            what_happened=f"The contract does not expose a method named `{method}`.",
            likely_cause="The method name may be misspelled, private, or not decorated with @gl.public.view/write.",
            fix_steps=(
                f"Run /schema {address or '<contract_address>'}.",
                "Copy the method name exactly as shown.",
                "Use /call for view methods and /write for write methods.",
            ),
            example="get_state()\nincrement()\nrename(\"New label\")",
        )

    if "invalid argument" in text or "parse" in text or "json" in text or "syntax" in text:
        return CliErrorView(
            title="Argument format problem",
            what_happened="GenLayer could not parse one of the values sent to the method.",
            likely_cause="Strings may be missing quotes, arrays/objects may not be valid JSON, or the method expects a different type.",
            fix_steps=(
                "Use /schema to confirm the expected argument types.",
                "Put text in quotes: \"Demo counter\".",
                "Use true/false for booleans and [1, 2] for arrays.",
            ),
            example='rename("Demo counter")\nset_threshold(3)\nset_config({"enabled": true, "limit": 10})',
        )

    if "insufficient" in text or "balance" in text or "fund" in text:
        return CliErrorView(
            title="Wallet funding issue",
            what_happened="The wallet does not have enough GEN to pay for this deploy/write operation.",
            likely_cause="Deploy and write operations require funds on the selected GenLayer network.",
            fix_steps=(
                "Run /start to see your wallet address.",
                "Fund that wallet on the selected network.",
                "Run /network to confirm you are using the intended network.",
                "Retry the deploy/write after the balance is updated.",
            ),
            example="/network -> Bradbury Testnet\n/deploy",
        )

    if "timeout" in text or "timed out" in text:
        return CliErrorView(
            title="GenLayer command timed out",
            what_happened="The CLI did not finish before GenBot's timeout.",
            likely_cause="The network may be slow, validators may still be processing, or the contract may be complex.",
            fix_steps=(
                "Retry once after a minute.",
                "If you have a transaction hash, run /tx <tx_hash>.",
                "If deploying, try a smaller contract or use /template to start from a minimal example.",
            ),
            example="/tx 0xabc123...",
        )

    if "account" in text or "keystore" in text or "password" in text or "private key" in text:
        return CliErrorView(
            title="Wallet/account setup issue",
            what_happened="GenBot could not prepare the CLI account needed for this operation.",
            likely_cause="The encrypted wallet or CLI keystore setup failed.",
            fix_steps=(
                "Run /start to confirm your wallet exists.",
                "Retry the command once.",
                "If it repeats, report the support code from the bot logs.",
            ),
            example="/start\n/deploy",
        )

    if tx_hash:
        return CliErrorView(
            title="Transaction inspection failed",
            what_happened=f"GenLayer could not return a receipt for {tx_hash}.",
            likely_cause="The transaction may still be pending, on another network, or not indexed yet.",
            fix_steps=(
                "Run /network and choose the network where the transaction was sent.",
                "Retry /tx after 1-2 minutes.",
                "Use /doctor <contract_address> if you have the contract address.",
            ),
            example=f"/tx {tx_hash}",
        )

    return CliErrorView(
        title=f"GenLayer {operation} failed",
        what_happened="The GenLayer CLI returned an error that GenBot could not complete automatically.",
        likely_cause="This can happen from network mismatch, bad arguments, invalid contract code, or a temporary RPC/validator issue.",
        fix_steps=(
            "Run /network and confirm the selected network.",
            f"Run /schema {address or '<contract_address>'} if you are calling or writing.",
            "Use /template for a known-good contract and examples.",
            "Run /doctor <contract_address> for an automatic diagnosis.",
        ),
        example="/schema 0x25d3D67Ac4C5b3108355D7D72660E6Cd3140C3C6",
    )


def render_cli_error_html(
    *,
    operation: str,
    stderr: str = "",
    stdout: str = "",
    returncode: int | None = None,
    address: str = "",
    method: str = "",
    network: str = "",
    tx_hash: str = "",
    include_debug: bool = True,
) -> str:
    view = classify_cli_error(
        operation=operation,
        stderr=stderr,
        stdout=stdout,
        returncode=returncode,
        address=address,
        method=method,
        network=network,
        tx_hash=tx_hash,
    )
    lines = [
        f"❌ <b>{html.escape(view.title)}</b>",
        "",
        "<b>What happened</b>",
        html.escape(view.what_happened),
        "",
        "<b>Most likely cause</b>",
        html.escape(view.likely_cause),
        "",
        "<b>How to fix it</b>",
    ]
    lines.extend(f"{idx}. {html.escape(step)}" for idx, step in enumerate(view.fix_steps, 1))
    lines.extend(["", "<b>Try this example</b>", f"<pre>{html.escape(view.example)}</pre>"])

    if include_debug:
        lines.extend(
            [
                "",
                "<b>Debug details</b>",
                f"Result code: <code>{returncode if returncode is not None else 'unknown'}</code>",
                f"Stdout:\n<pre>{html.escape(clean_cli_output(stdout, 700))}</pre>",
                f"Stderr:\n<pre>{html.escape(clean_cli_output(stderr, 1000))}</pre>",
            ]
        )
    return "\n".join(lines)
