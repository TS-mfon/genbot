# GenBot - GenLayer Telegram Bot

A Telegram bot for deploying and interacting with GenLayer Intelligent Contracts.

## Features

- `/start` `/help` - Welcome and command list
- `/deploy` - Paste GenLayer Python contract code to deploy
- `/call` - Read methods on deployed contracts
- `/write` - Write transactions to contracts
- `/ask` - Natural language query routed to a contract
- `/contracts` - List your deployed contracts
- `/tx` - Transaction lookup by hash
- `/template` - Starter GenLayer contract templates
- `/audit` - AI-powered contract audit via Claude
- `/faucet` - Request testnet tokens
- `/validators` - Live validator count and consensus status

## Setup

1. Copy `.env.example` to `.env` and fill in values.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python -m bot.main`

## Docker

```bash
docker build -t genbot .
docker run --env-file .env genbot
```
