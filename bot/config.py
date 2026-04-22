from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., description="Telegram Bot API token")
    genlayer_rpc_url: str = Field(
        default="https://studio.genlayer.com/api",
        description="GenLayer JSON-RPC endpoint",
    )
    anthropic_api_key: str = Field(default="", description="Anthropic API key for audits")
    wallet_encryption_key: str = Field(..., description="Fernet key for wallet encryption")
    database_path: str = Field(default="genbot.db", description="SQLite database path")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
