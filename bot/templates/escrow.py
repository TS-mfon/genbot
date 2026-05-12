"""Escrow template contract for GenLayer."""

ESCROW_CODE = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class Escrow(gl.Contract):
    """Escrow state machine with optional validator-checked delivery evidence."""

    escrow_count: u256
    buyers: TreeMap[str, str]
    sellers: TreeMap[str, str]
    amounts: TreeMap[str, u256]
    descriptions: TreeMap[str, str]
    verification_urls: TreeMap[str, str]
    statuses: TreeMap[str, str]

    def __init__(self):
        self.escrow_count = u256(0)

    @gl.public.write
    def create_escrow(
        self, seller: str, amount: int, description: str, verification_url: str
    ) -> str:
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Amount must be positive")

        escrow_id = str(int(self.escrow_count))
        self.escrow_count += u256(1)
        self.buyers[escrow_id] = str(gl.message.sender_account)
        self.sellers[escrow_id] = seller
        self.amounts[escrow_id] = u256(amount)
        self.descriptions[escrow_id] = description
        self.verification_urls[escrow_id] = verification_url
        self.statuses[escrow_id] = "active"
        return escrow_id

    @gl.public.write
    def confirm_delivery(self, escrow_id: str) -> None:
        if str(gl.message.sender_account) != self.buyers.get(escrow_id, ""):
            raise gl.vm.UserError("[EXPECTED] Only buyer can confirm delivery")
        if self.statuses.get(escrow_id, "") != "active":
            raise gl.vm.UserError("[EXPECTED] Escrow is not active")
        self.statuses[escrow_id] = "completed"

    @gl.public.write
    def dispute(self, escrow_id: str) -> None:
        sender = str(gl.message.sender_account)
        buyer = self.buyers.get(escrow_id, "")
        seller = self.sellers.get(escrow_id, "")
        if sender != buyer and sender != seller:
            raise gl.vm.UserError("[EXPECTED] Only buyer or seller can dispute")
        if self.statuses.get(escrow_id, "") != "active":
            raise gl.vm.UserError("[EXPECTED] Escrow is not active")
        self.statuses[escrow_id] = "disputed"

    @gl.public.write
    def verify_and_release(self, escrow_id: str) -> bool:
        if self.statuses.get(escrow_id, "") != "active":
            raise gl.vm.UserError("[EXPECTED] Escrow is not active")

        delivered = self._check_delivery(
            self.descriptions.get(escrow_id, ""),
            self.verification_urls.get(escrow_id, ""),
        )
        if delivered:
            self.statuses[escrow_id] = "completed"
        return delivered

    def _check_delivery(self, description: str, url: str) -> bool:
        def leader_fn() -> bool:
            page = gl.nondet.web.get(url).body.decode("utf-8")
            prompt = (
                "Check whether delivery is clearly confirmed by the source text. "
                "Return exactly delivered or not_delivered.\\n"
                + "Item: " + description + "\\n"
                + "Source: " + page[:6000]
            )
            result = str(gl.nondet.exec_prompt(prompt)).strip().lower()
            if result == "delivered":
                return True
            if result == "not_delivered":
                return False
            raise gl.vm.UserError("[LLM_ERROR] Resolver returned invalid status")

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            return bool(leaders_res.calldata) == leader_fn()

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    @gl.public.view
    def get_escrow(self, escrow_id: str) -> dict:
        return {
            "id": escrow_id,
            "buyer": self.buyers.get(escrow_id, ""),
            "seller": self.sellers.get(escrow_id, ""),
            "amount": int(self.amounts.get(escrow_id, u256(0))),
            "description": self.descriptions.get(escrow_id, ""),
            "verification_url": self.verification_urls.get(escrow_id, ""),
            "status": self.statuses.get(escrow_id, ""),
        }

    @gl.public.view
    def get_status(self, escrow_id: str) -> str:
        return self.statuses.get(escrow_id, "")
'''
