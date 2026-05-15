# GenBot — GenLayer Intelligent Contracts via Telegram

A production-grade Telegram bot for deploying and interacting with GenLayer Intelligent Contracts. Supports **StudioNet**, **Bradbury Testnet**, and **Asimov Testnet**.

## Features

### Contract Management
- `/deploy` — Upload a .py file or paste code; auto-prepends correct header; deploys via `genlayer` CLI
- `/call <address> <method(args)>` — Read from a contract
- `/write <address> <method(args)>` — Write a transaction
- `/schema <address>` — Inspect deployed methods before interacting
- `/ask <address> <question>` — Natural language query
- `/contracts` — List your deployed contracts
- `/doctor <address>` — Diagnose network/schema/finalization issues
- `/examples` — Copyable deploy/call/write examples with real values
- `/tx <hash>` — Look up a transaction
- `/template` — Get starter contract templates
- `/audit <address|code>` — AI audit via Claude API

### Network
- `/network` — Switch between StudioNet, Bradbury Testnet, and Asimov Testnet
- `/guide` — Show exact input formats and examples
- `/validators` — View current validators

### Wallet
- `/start` — Create wallet (shows private key once)

## Contract Headers

GenLayer contracts must start with a header:

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

GenBot **normalizes** the file before deployment so this exact magic comment is the first line. If a user sends a bare JSON dependency line or an older dependency line, the bot replaces it with the supported pinned dependency header.

## Contract Structure Guide

GenBot validates contract shape using the same rules as the internal `write-contract` guidance:

- Contract class must extend `gl.Contract`; do not use the old `@gl.contract` decorator.
- Storage fields should be class-level type annotations.
- Persisted collections should use GenLayer types such as `DynArray[T]` and `TreeMap[K, V]`, not Python `list` or `dict`.
- Public methods must use `@gl.public.view` or `@gl.public.write`.
- Expected contract failures should use `gl.vm.UserError`.
- LLM calls should request JSON with `response_format="json"` and validate returned fields.
- `strict_eq` should be reserved for deterministic or canonicalized outputs; LLM and variable web workflows need explicit validator logic.

## Starter Templates

The `/template` command returns lint-clean GenLayer examples that use the current SDK shape:

- `Storage Counter` — minimal `gl.Contract` with typed storage and owner-gated writes
- `Token Manager` — fungible-token style balances and flat allowance indexes
- `Voting DAO` — typed proposal, option, vote, and membership indexes
- `Prediction Market` — typed market storage with `gl.vm.run_nondet_unsafe` outcome validation
- `Escrow` — typed escrow state machine with validator-checked delivery evidence

Template quality checks:

```text
genvm-lint check storage_counter.py     # Contract: StorageCounter, 3 methods
genvm-lint check token_manager.py       # Contract: TokenManager, 7 methods
genvm-lint check voting_dao.py          # Contract: VotingDAO, 7 methods
genvm-lint check prediction_market.py   # Contract: PredictionMarket, 6 methods
genvm-lint check escrow.py              # Contract: Escrow, 6 methods
```

All included templates pass GenVM lint and validation against the pinned dependency header.

## Deployment Flow

`/deploy` uses the official `genlayer` CLI:

1. User uploads a `.py` file or pastes code
2. Bot validates Python syntax
3. Bot auto-prepends header if missing
4. Bot detects required constructor args such as `label`
5. Bot asks for constructor args when needed, for example `"Demo counter"`
6. Bot writes code to temp file
7. Bot runs `genlayer network set <network>` then `genlayer deploy --contract <path> --args ...`
8. Bot parses contract address from output
9. Bot checks schema readiness and stores address, tx, network, constructor args, and status

For contract interaction, the bot aligns with the installed CLI structure:

```bash
genlayer call <address> <method> --args ...
genlayer write <address> <method> --args ...
genlayer schema <address>
genlayer receipt <txHash>
```

Use `/guide` inside Telegram to see the supported argument formats and copyable examples.

## Error Handling

GenBot translates raw CLI failures into guided recovery steps. Examples:

- `Contract ... not found` becomes a network/finalization diagnosis with `/network`, `/contracts`, `/schema`, and `/doctor` next steps.
- `StorageCounter.__init__() missing ... label` becomes a constructor-argument guide with the exact value format to retry, e.g. `"Demo counter"`.
- Bad method names or args point users to `/schema` and show valid examples like `get_state()`, `increment()`, and `rename("Demo counter")`.
- Noisy CLI warnings such as deprecated `initializeConsensusSmartContract()` output are hidden from user replies but preserved in logs.

Use `/doctor <address>` when a contract is visible in an explorer but not callable from the selected network.

## Production Features

- Safe JSON arg parsing (no `ast.literal_eval`)
- File upload deployment (avoids Telegram message splitting)
- Rate limiting (10 commands/minute per user)
- Structured JSON logging
- Multi-stage Docker build with Node.js + genlayer CLI pre-installed
- Health endpoint on `/`
- Fernet-encrypted private keys
- Serialized GenLayer CLI commands to avoid global network/account race conditions
- Weekly GenLayer CLI update script and systemd timer examples in `deploy/systemd`

## Live Bot and Deployment Evidence

- Telegram bot username: `@Genlayertgbot`
- Telegram bot id: `8672625541`
- Telegram delivery mode: long polling, webhook URL empty
- Current production host: VPS systemd service `genbot.service`
- Deployment status checked on 2026-05-12: service active, Telegram `getWebhookInfo` returned `pending_update_count=0` and no last error
- GitHub repository: `https://github.com/TS-mfon/genbot`

## Setup

```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, WALLET_ENCRYPTION_KEY
npm install -g genlayer@0.39.0
pip install -e .
genbot --check
genbot
```

You can also run `python -m bot`, but `genbot` is the primary entrypoint now.

## Deploy to Render

Docker handles everything (Node, Python, genlayer CLI):

1. Create a Web Service from this repo
2. Select Docker runtime
3. Set env vars from `.env.example`
4. Deploy

## License

MIT
