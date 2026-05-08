"""Guide handler - explain the right input formats for users."""

from telegram import Update
from telegram.ext import ContextTypes

GUIDE_TEXT = """
<b>GenBot Input Guide</b>

<b>1. Pick a network first</b>
Use <code>/network</code> and choose:
- <b>StudioNet</b> for fast dev/testing
- <b>Bradbury Testnet</b> for public testnet work
- <b>Asimov Testnet</b> if you need that specific testnet

<b>2. Deploy contracts</b>
Use <code>/deploy</code>, then send either:
- a <code>.py</code> contract file
- the full Python source code as a message

Your contract must start with the GenLayer dependency magic comment. GenBot normalizes this before deploy:
<code># { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }</code>

Correct contract skeleton:
<code>from genlayer import *

class MyContract(gl.Contract):
    owner: Address
    count: u256

    def __init__(self):
        self.owner = gl.message.sender_account
        self.count = u256(0)

    @gl.public.view
    def get_count(self) -> u256:
        return self.count

    @gl.public.write
    def increment(self) -> None:
        self.count += u256(1)</code>

Contract rules:
- Extend <code>gl.Contract</code>; do not use old <code>@gl.contract</code>
- Declare storage as class-level type annotations
- Use <code>DynArray</code> / <code>TreeMap</code> for persisted collections
- Decorate public methods with <code>@gl.public.view</code> or <code>@gl.public.write</code>
- Use <code>gl.vm.UserError</code> for expected contract errors
- Use <code>response_format="json"</code> and explicit validators for LLM workflows

<b>3. Inspect methods before calling</b>
Use <code>/schema &lt;contract_address&gt;</code> to see available methods and argument shapes.

<b>4. Call and write format</b>
After <code>/call</code> or <code>/write</code>, enter:
<code>method_name(arg1, arg2, ...)</code>

Examples:
<code>get_count()</code>
<code>balance_of(0x1234abcd1234abcd1234abcd1234abcd1234abcd)</code>
<code>set_name("alice")</code>
<code>vote(2, true)</code>
<code>store_config({"threshold": 3, "members": ["a", "b"]})</code>
<code>set_payload(b#deadbeef)</code>

<b>5. Supported argument styles</b>
GenBot formats values for the GenLayer CLI, matching its accepted shapes:
- numbers: <code>42</code>, <code>-1</code>, <code>0x1a</code>
- booleans: <code>true</code>, <code>false</code>
- null: <code>null</code>
- strings: <code>hello</code> or <code>"multi word"</code>
- addresses: <code>0x...</code> or <code>addr#...</code>
- bytes: <code>b#deadbeef</code>
- arrays: <code>[1, 2, "three"]</code>
- objects: <code>{"key": "value"}</code>

<b>6. Transaction lookup</b>
Use <code>/tx &lt;tx_hash&gt;</code> to inspect the CLI receipt for a transaction.

<b>7. Common mistakes</b>
- Don't paste an address where a method is expected
- Don't omit quotes around multi-word strings
- Don't guess method names; check <code>/schema</code> first
- Use <code>/cancel</code> to exit any active flow
""".strip()


async def guide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /guide command."""
    await update.message.reply_text(GUIDE_TEXT, parse_mode="HTML")
