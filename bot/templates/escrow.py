"""Escrow template contract for GenLayer."""

ESCROW_CODE = '''from genlayer import *


@gl.contract
class Escrow:
    """Trustless escrow with AI-verified delivery confirmation.
    Funds are held until validators confirm delivery via web evidence."""

    escrows: TreeMap[str, dict]
    escrow_count: u256

    def __init__(self):
        self.escrow_count = u256(0)
        self.escrows = TreeMap[str, dict]()

    @gl.public.write
    def create_escrow(
        self, seller: str, amount: int, description: str, verification_url: str
    ) -> str:
        """Create a new escrow agreement."""
        escrow_id = str(self.escrow_count)
        self.escrow_count += u256(1)

        self.escrows[escrow_id] = {
            "buyer": str(gl.message.sender),
            "seller": seller,
            "amount": amount,
            "description": description,
            "verification_url": verification_url,
            "status": "active",
            "created_at": str(gl.message.sender),
        }
        return f"Escrow {escrow_id} created for {amount} tokens"

    @gl.public.write
    def confirm_delivery(self, escrow_id: str) -> str:
        """Buyer manually confirms delivery, releasing funds."""
        escrow = self.escrows[escrow_id]
        if str(gl.message.sender) != escrow["buyer"]:
            return "Only buyer can confirm delivery"
        if escrow["status"] != "active":
            return f"Escrow is {escrow['status']}"

        escrow["status"] = "completed"
        self.escrows[escrow_id] = escrow
        return f"Delivery confirmed. {escrow['amount']} released to seller."

    @gl.public.write
    def verify_and_release(self, escrow_id: str) -> str:
        """AI-verified delivery confirmation using web evidence."""
        escrow = self.escrows[escrow_id]
        if escrow["status"] != "active":
            return f"Escrow is {escrow['status']}"

        with EquivalencePrinciple(
            result=check_delivery(
                escrow["description"],
                escrow["verification_url"],
            ),
            principle="Delivery must be verifiably confirmed based on the "
                      "tracking or proof URL provided. Return 'delivered' only "
                      "if clear evidence of delivery exists.",
            comparative=True,
        ) as verification:
            if verification.result == "delivered":
                escrow["status"] = "completed"
                self.escrows[escrow_id] = escrow
                return f"Delivery verified! {escrow['amount']} released to seller."
            else:
                return "Delivery could not be verified yet."

    @gl.public.write
    def dispute(self, escrow_id: str) -> str:
        """Open a dispute on an escrow."""
        escrow = self.escrows[escrow_id]
        sender = str(gl.message.sender)
        if sender != escrow["buyer"] and sender != escrow["seller"]:
            return "Only buyer or seller can dispute"
        if escrow["status"] != "active":
            return f"Escrow is {escrow['status']}"

        escrow["status"] = "disputed"
        self.escrows[escrow_id] = escrow
        return "Escrow disputed. Awaiting resolution."

    @gl.public.view
    def get_escrow(self, escrow_id: str) -> dict:
        """Get escrow details."""
        return self.escrows[escrow_id]

    @gl.public.view
    def get_status(self, escrow_id: str) -> str:
        """Get escrow status."""
        return self.escrows[escrow_id]["status"]


def check_delivery(description: str, url: str) -> str:
    """Non-deterministic: check delivery status from a URL."""
    web_data = gl.get_webpage(url, mode="text")
    task = (
        f"Check if the following item has been delivered:\\n"
        f"Item: {description}\\n"
        f"Tracking/proof page content: {web_data}\\n"
        f"Respond with ONLY \\'delivered\\' or \\'not_delivered\\'."
    )
    result = gl.exec_prompt(task)
    return result.strip().lower()
'''
