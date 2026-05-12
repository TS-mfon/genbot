"""Token Manager template contract for GenLayer."""

TOKEN_MANAGER_CODE = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class TokenManager(gl.Contract):
    """Simple fungible token with admin-controlled minting."""

    name: str
    symbol: str
    total_supply: u256
    admin: Address
    balances: TreeMap[str, u256]
    allowances: TreeMap[str, u256]

    def __init__(self, name: str, symbol: str, initial_supply: int):
        if initial_supply < 0:
            raise gl.vm.UserError("[EXPECTED] Initial supply cannot be negative")

        self.name = name
        self.symbol = symbol
        self.admin = gl.message.sender_account
        self.total_supply = u256(initial_supply)
        self.balances[str(gl.message.sender_account)] = u256(initial_supply)

    def _allowance_key(self, owner: str, spender: str) -> str:
        return owner + "|" + spender

    @gl.public.write
    def mint(self, to: str, amount: int) -> None:
        if gl.message.sender_account != self.admin:
            raise gl.vm.UserError("[EXPECTED] Only admin can mint")
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Amount must be positive")

        current = self.balances.get(to, u256(0))
        self.balances[to] = current + u256(amount)
        self.total_supply += u256(amount)

    @gl.public.write
    def transfer(self, to: str, amount: int) -> None:
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Amount must be positive")

        sender = str(gl.message.sender_account)
        sender_balance = self.balances.get(sender, u256(0))
        value = u256(amount)
        if sender_balance < value:
            raise gl.vm.UserError("[EXPECTED] Insufficient balance")

        self.balances[sender] = sender_balance - value
        self.balances[to] = self.balances.get(to, u256(0)) + value

    @gl.public.write
    def approve(self, spender: str, amount: int) -> None:
        if amount < 0:
            raise gl.vm.UserError("[EXPECTED] Amount cannot be negative")

        owner = str(gl.message.sender_account)
        self.allowances[self._allowance_key(owner, spender)] = u256(amount)

    @gl.public.write
    def transfer_from(self, owner: str, to: str, amount: int) -> None:
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Amount must be positive")

        spender = str(gl.message.sender_account)
        key = self._allowance_key(owner, spender)
        value = u256(amount)
        allowed = self.allowances.get(key, u256(0))
        if allowed < value:
            raise gl.vm.UserError("[EXPECTED] Allowance exceeded")

        owner_balance = self.balances.get(owner, u256(0))
        if owner_balance < value:
            raise gl.vm.UserError("[EXPECTED] Owner has insufficient balance")

        self.allowances[key] = allowed - value
        self.balances[owner] = owner_balance - value
        self.balances[to] = self.balances.get(to, u256(0)) + value

    @gl.public.view
    def balance_of(self, account: str) -> int:
        return int(self.balances.get(account, u256(0)))

    @gl.public.view
    def allowance(self, owner: str, spender: str) -> int:
        return int(self.allowances.get(self._allowance_key(owner, spender), u256(0)))

    @gl.public.view
    def get_info(self) -> dict:
        return {
            "name": self.name,
            "symbol": self.symbol,
            "total_supply": int(self.total_supply),
            "admin": str(self.admin),
        }
'''
