"""Prediction Market template contract for GenLayer."""

PREDICTION_MARKET_CODE = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class PredictionMarket(gl.Contract):
    """Prediction market with typed storage and validator-checked resolution."""

    market_count: u256
    questions: TreeMap[str, str]
    creators: TreeMap[str, str]
    resolved: TreeMap[str, bool]
    winners: TreeMap[str, str]
    option_count: TreeMap[str, u256]
    options: TreeMap[str, str]
    option_stakes: TreeMap[str, u256]
    user_stakes: TreeMap[str, u256]

    def __init__(self):
        self.market_count = u256(0)

    def _option_key(self, market_id: str, option_index: int) -> str:
        return market_id + "|" + str(option_index)

    def _stake_key(self, market_id: str, option: str) -> str:
        return market_id + "|" + option

    def _user_stake_key(self, market_id: str, user: str, option: str) -> str:
        return market_id + "|" + user + "|" + option

    @gl.public.write
    def create_market(self, question: str, options_csv: str) -> str:
        options = [item.strip() for item in options_csv.split(",") if item.strip()]
        if len(options) < 2:
            raise gl.vm.UserError("[EXPECTED] Provide at least two comma-separated options")

        market_id = str(int(self.market_count))
        self.market_count += u256(1)
        self.questions[market_id] = question
        self.creators[market_id] = str(gl.message.sender_account)
        self.resolved[market_id] = False
        self.winners[market_id] = ""
        self.option_count[market_id] = u256(len(options))

        for index, option in enumerate(options):
            self.options[self._option_key(market_id, index)] = option
            self.option_stakes[self._stake_key(market_id, option)] = u256(0)

        return market_id

    @gl.public.write
    def place_bet(self, market_id: str, option: str, amount: int) -> None:
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Amount must be positive")
        if self.resolved.get(market_id, False):
            raise gl.vm.UserError("[EXPECTED] Market already resolved")
        if not self.option_exists(market_id, option):
            raise gl.vm.UserError("[EXPECTED] Invalid option")

        value = u256(amount)
        user = str(gl.message.sender_account)
        stake_key = self._stake_key(market_id, option)
        user_key = self._user_stake_key(market_id, user, option)
        self.option_stakes[stake_key] = self.option_stakes.get(stake_key, u256(0)) + value
        self.user_stakes[user_key] = self.user_stakes.get(user_key, u256(0)) + value

    @gl.public.write
    def resolve_market(self, market_id: str, resolution_url: str) -> str:
        if self.resolved.get(market_id, False):
            raise gl.vm.UserError("[EXPECTED] Market already resolved")

        winner = self._resolve_outcome(
            self.questions.get(market_id, ""),
            self.get_options_csv(market_id),
            resolution_url,
        )
        if not self.option_exists(market_id, winner):
            raise gl.vm.UserError("[LLM_ERROR] Resolver returned an unknown option")

        self.winners[market_id] = winner
        self.resolved[market_id] = True
        return winner

    def _resolve_outcome(self, question: str, options_csv: str, url: str) -> str:
        def leader_fn() -> str:
            page = gl.nondet.web.get(url).body.decode("utf-8")
            prompt = (
                "Resolve this prediction market using only the source text. "
                "Return exactly one option and no extra text.\\n"
                + "Question: " + question + "\\n"
                + "Options: " + options_csv + "\\n"
                + "Source: " + page[:6000]
            )
            return str(gl.nondet.exec_prompt(prompt)).strip()

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            validator_winner = leader_fn()
            leader_winner = str(leaders_res.calldata)
            return validator_winner == leader_winner

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    @gl.public.view
    def option_exists(self, market_id: str, option: str) -> bool:
        count = int(self.option_count.get(market_id, u256(0)))
        for index in range(count):
            if self.options.get(self._option_key(market_id, index), "") == option:
                return True
        return False

    @gl.public.view
    def get_options_csv(self, market_id: str) -> str:
        values = []
        count = int(self.option_count.get(market_id, u256(0)))
        for index in range(count):
            values.append(self.options.get(self._option_key(market_id, index), ""))
        return ", ".join(values)

    @gl.public.view
    def get_market(self, market_id: str) -> dict:
        return {
            "id": market_id,
            "question": self.questions.get(market_id, ""),
            "creator": self.creators.get(market_id, ""),
            "resolved": self.resolved.get(market_id, False),
            "winner": self.winners.get(market_id, ""),
            "options": self.get_options_csv(market_id),
        }
'''
