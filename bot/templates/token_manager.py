"""Token Manager template contract for GenLayer."""

TOKEN_MANAGER_CODE = '''from genlayer import *


@gl.contract
class TokenManager:
    """Simple fungible token with mint, transfer, and balance tracking.
    Includes an admin role for minting new tokens."""

    name: str
    symbol: str
    total_supply: u256
    admin: Address
    balances: TreeMap[str, u256]
    allowances: TreeMap[str, dict]

    def __init__(self, name: str, symbol: str, initial_supply: int):
        self.name = name
        self.symbol = symbol
        self.admin = gl.message.sender
        self.total_supply = u256(initial_supply)
        self.balances = TreeMap[str, u256]()
        self.allowances = TreeMap[str, dict]()
        self.balances[str(gl.message.sender)] = u256(initial_supply)

    @gl.public.write
    def mint(self, to: str, amount: int) -> str:
        """Mint new tokens (admin only)."""
        if gl.message.sender != self.admin:
            return "Only admin can mint"
        if amount <= 0:
            return "Amount must be positive"

        current = self.balances.get(to, u256(0))
        self.balances[to] = current + u256(amount)
        self.total_supply += u256(amount)
        return f"Minted {amount} {self.symbol} to {to}"

    @gl.public.write
    def transfer(self, to: str, amount: int) -> str:
        """Transfer tokens to another address."""
        sender = str(gl.message.sender)
        if amount <= 0:
            return "Amount must be positive"

        sender_balance = self.balances.get(sender, u256(0))
        if sender_balance < u256(amount):
            return f"Insufficient balance: {sender_balance}"

        self.balances[sender] = sender_balance - u256(amount)
        recipient_balance = self.balances.get(to, u256(0))
        self.balances[to] = recipient_balance + u256(amount)
        return f"Transferred {amount} {self.symbol} to {to}"

    @gl.public.write
    def approve(self, spender: str, amount: int) -> str:
        """Approve another address to spend tokens on your behalf."""
        sender = str(gl.message.sender)
        user_allowances = self.allowances.get(sender, {})
        user_allowances[spender] = amount
        self.allowances[sender] = user_allowances
        return f"Approved {spender} to spend {amount} {self.symbol}"

    @gl.public.write
    def transfer_from(self, owner: str, to: str, amount: int) -> str:
        """Transfer tokens from an approved allowance."""
        spender = str(gl.message.sender)
        user_allowances = self.allowances.get(owner, {})
        allowed = user_allowances.get(spender, 0)

        if allowed < amount:
            return f"Allowance exceeded: {allowed}"

        owner_balance = self.balances.get(owner, u256(0))
        if owner_balance < u256(amount):
            return f"Owner insufficient balance: {owner_balance}"

        self.balances[owner] = owner_balance - u256(amount)
        recipient_balance = self.balances.get(to, u256(0))
        self.balances[to] = recipient_balance + u256(amount)

        user_allowances[spender] = allowed - amount
        self.allowances[owner] = user_allowances
        return f"Transferred {amount} {self.symbol} from {owner} to {to}"

    @gl.public.view
    def balance_of(self, address: str) -> int:
        """Get the token balance of an address."""
        return int(self.balances.get(address, u256(0)))

    @gl.public.view
    def get_total_supply(self) -> int:
        """Get the total token supply."""
        return int(self.total_supply)

    @gl.public.view
    def get_info(self) -> dict:
        """Get token metadata."""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "total_supply": int(self.total_supply),
            "admin": str(self.admin),
        }

    @gl.public.view
    def allowance(self, owner: str, spender: str) -> int:
        """Get the remaining allowance for a spender."""
        user_allowances = self.allowances.get(owner, {})
        return user_allowances.get(spender, 0)
'''
