"""Copyable examples for zero-knowledge GenBot users."""

from telegram import Update
from telegram.ext import ContextTypes


EXAMPLES_TEXT = """
<b>GenBot Copyable Examples</b>

<b>Example 1: StorageCounter</b>
1. Run <code>/template</code>
2. Choose <b>Storage Counter</b>
3. Run <code>/deploy</code> and upload/paste the template
4. When asked for constructor args, send:
<code>"Demo counter"</code>
5. After deployment, run:
<code>/schema 0xYourContractAddress</code>
6. Use <code>/call</code>, paste the address, then send:
<code>get_state()</code>
7. Use <code>/write</code>, paste the address, then send:
<code>increment()</code>
8. Use <code>/call</code> again:
<code>get_state()</code>

<b>Example 2: Rename StorageCounter</b>
Use <code>/write</code>, paste the address, then send:
<code>rename("Main demo counter")</code>

<b>Example 3: TokenManager deploy args</b>
When deploying TokenManager, constructor args look like:
<code>"Demo Token", "DMT", 1000</code>

Then call:
<code>get_info()</code>
<code>balance_of("0xYourWalletAddress")</code>

<b>If anything fails</b>
Run:
<code>/doctor 0xYourContractAddress</code>

The doctor checks network mismatch, schema availability, saved tx, deploy args, and likely next steps.
""".strip()


async def examples_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /examples."""
    await update.message.reply_text(EXAMPLES_TEXT, parse_mode="HTML")
