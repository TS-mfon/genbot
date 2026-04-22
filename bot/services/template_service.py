"""Contract template service."""

from bot.templates.prediction_market import PREDICTION_MARKET_CODE
from bot.templates.voting_dao import VOTING_DAO_CODE
from bot.templates.escrow import ESCROW_CODE
from bot.templates.token_manager import TOKEN_MANAGER_CODE


TEMPLATES = [
    {
        "key": "prediction_market",
        "name": "Prediction Market",
        "description": "Create and resolve prediction markets with AI-powered outcome verification",
    },
    {
        "key": "voting_dao",
        "name": "Voting DAO",
        "description": "Decentralized voting system with proposal creation and tallying",
    },
    {
        "key": "escrow",
        "name": "Escrow",
        "description": "Trustless escrow with AI-verified delivery confirmation",
    },
    {
        "key": "token_manager",
        "name": "Token Manager",
        "description": "Simple token with mint, transfer, and balance tracking",
    },
]

TEMPLATE_CODE = {
    "prediction_market": PREDICTION_MARKET_CODE,
    "voting_dao": VOTING_DAO_CODE,
    "escrow": ESCROW_CODE,
    "token_manager": TOKEN_MANAGER_CODE,
}


class TemplateService:
    """Serve contract templates."""

    def list_templates(self) -> list[dict]:
        return TEMPLATES

    def get_template_code(self, key: str) -> str:
        return TEMPLATE_CODE.get(key, "# Template not found")


# Singleton
template_service = TemplateService()
