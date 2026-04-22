"""Contract model."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Contract:
    """Represents a deployed intelligent contract."""
    address: str
    user_id: int
    code_snippet: str = ""
    tx_hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
