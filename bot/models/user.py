"""User model."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """Represents a bot user."""
    user_id: int
    telegram_username: str = ""
    wallet_address: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
