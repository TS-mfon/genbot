# GenBot — GenLayer Intelligent Contracts via Telegram

A production-grade Telegram bot for deploying and interacting with GenLayer Intelligent Contracts. Supports **StudioNet** and **Bradbury Testnet**.

## Features

### Contract Management
- `/deploy` — Upload a .py file or paste code; auto-prepends correct header; deploys via `genlayer` CLI
- `/call <address> <method(args)>` — Read from a contract
- `/write <address> <method(args)>` — Write a transaction
- `/ask <address> <question>` — Natural language query
- `/contracts` — List your deployed contracts
- `/tx <hash>` — Look up a transaction
- `/template` — Get starter contract templates
- `/audit <address|code>` — AI audit via Claude API

### Network
- `/network` — Switch between StudioNet and Bradbury Testnet
- `/validators` — View current validators

### Wallet
- `/start` — Create wallet (shows private key once)
- `/export_key` — Re-export your private key
- `/import_wallet <private_key>` — Import a wallet
- `/faucet` — Request testnet tokens

## Contract Headers

GenLayer contracts must start with a header:

```python
# { "Depends": "py-genlayer:test" }
```

For Bradbury testnet, use the pinned hash:

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

GenBot **auto-prepends** the default header if your code doesn't start with one.

## Deployment Flow

`/deploy` uses the official `genlayer` CLI:

1. User uploads a `.py` file or pastes code
2. Bot validates Python syntax
3. Bot auto-prepends header if missing
4. Bot writes code to temp file
5. Bot runs `genlayer network set <network>` then `genlayer deploy --contract <path>`
6. Bot parses contract address from output
7. Bot stores contract in user's registry

## Production Features

- Safe JSON arg parsing (no `ast.literal_eval`)
- File upload deployment (avoids Telegram message splitting)
- Rate limiting (10 commands/minute per user)
- Structured JSON logging
- Multi-stage Docker build with Node.js + genlayer CLI pre-installed
- Health endpoint on `/`
- Fernet-encrypted private keys

## Setup

```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, WALLET_ENCRYPTION_KEY
npm install -g genlayer@0.37.1
pip install -r requirements.txt
python -m bot.main
```

## Deploy to Render

Docker handles everything (Node, Python, genlayer CLI):

1. Create a Web Service from this repo
2. Select Docker runtime
3. Set env vars from `.env.example`
4. Deploy

## License

MIT
