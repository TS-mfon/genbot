"""Prediction Market template contract for GenLayer."""

PREDICTION_MARKET_CODE = '''from genlayer import *
import json


@gl.contract
class PredictionMarket:
    """A prediction market where users bet on outcomes,
    resolved by AI-powered validator consensus."""

    markets: TreeMap[str, dict]
    market_count: u256
    balances: TreeMap[str, u256]

    def __init__(self):
        self.market_count = u256(0)
        self.markets = TreeMap[str, dict]()
        self.balances = TreeMap[str, u256]()

    @gl.public.write
    def create_market(self, question: str, options: list[str]) -> str:
        """Create a new prediction market."""
        market_id = str(self.market_count)
        self.market_count += u256(1)

        market = {
            "question": question,
            "options": options,
            "bets": {opt: [] for opt in options},
            "total_pool": 0,
            "resolved": False,
            "winner": None,
            "creator": gl.message.sender,
        }
        self.markets[market_id] = market
        return market_id

    @gl.public.write
    def place_bet(self, market_id: str, option: str, amount: int) -> str:
        """Place a bet on a market option."""
        market = self.markets[market_id]
        if market["resolved"]:
            return "Market already resolved"
        if option not in market["options"]:
            return "Invalid option"

        sender = str(gl.message.sender)
        market["bets"][option].append({"user": sender, "amount": amount})
        market["total_pool"] += amount
        self.markets[market_id] = market
        return f"Bet placed: {amount} on {option}"

    @gl.public.write
    def resolve_market(self, market_id: str, resolution_url: str) -> str:
        """Resolve a market using AI consensus on real-world data."""
        market = self.markets[market_id]
        if market["resolved"]:
            return "Already resolved"

        with EquivalencePrinciple(
            result=get_outcome(market["question"], market["options"], resolution_url),
            principle="The winning option must match the real-world outcome "
                      "as determined by the provided source URL.",
            comparative=True,
        ) as outcome:
            market["winner"] = outcome.result
            market["resolved"] = True
            self.markets[market_id] = market
            return f"Market resolved: {outcome.result}"

    @gl.public.view
    def get_market(self, market_id: str) -> dict:
        """Get market details."""
        return self.markets[market_id]

    @gl.public.view
    def get_market_count(self) -> int:
        """Get total number of markets."""
        return int(self.market_count)


def get_outcome(question: str, options: list[str], url: str) -> str:
    """Non-deterministic function to determine market outcome."""
    web_data = gl.get_webpage(url, mode="text")
    task = (
        f"Based on the following information, determine the answer to: {question}\\n"
        f"Options: {options}\\n"
        f"Source data: {web_data}\\n"
        f"Respond with ONLY the winning option, exactly as written."
    )
    result = gl.exec_prompt(task)
    return result.strip()
'''
