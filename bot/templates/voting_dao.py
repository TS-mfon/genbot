"""Voting DAO template contract for GenLayer."""

VOTING_DAO_CODE = '''from genlayer import *


@gl.contract
class VotingDAO:
    """A decentralized voting system with proposal creation,
    voting, and automatic tallying."""

    proposals: TreeMap[str, dict]
    proposal_count: u256
    members: TreeMap[str, bool]
    admin: Address

    def __init__(self):
        self.admin = gl.message.sender
        self.proposal_count = u256(0)
        self.proposals = TreeMap[str, dict]()
        self.members = TreeMap[str, bool]()
        self.members[str(gl.message.sender)] = True

    @gl.public.write
    def add_member(self, member_address: str) -> str:
        """Add a new DAO member (admin only)."""
        if gl.message.sender != self.admin:
            return "Only admin can add members"
        self.members[member_address] = True
        return f"Member {member_address} added"

    @gl.public.write
    def create_proposal(self, title: str, description: str, options: list[str]) -> str:
        """Create a new proposal for voting."""
        sender = str(gl.message.sender)
        if not self.members.get(sender, False):
            return "Only members can create proposals"

        proposal_id = str(self.proposal_count)
        self.proposal_count += u256(1)

        self.proposals[proposal_id] = {
            "title": title,
            "description": description,
            "options": options,
            "votes": {},
            "vote_counts": {opt: 0 for opt in options},
            "creator": sender,
            "open": True,
        }
        return f"Proposal {proposal_id} created: {title}"

    @gl.public.write
    def vote(self, proposal_id: str, option: str) -> str:
        """Cast a vote on a proposal."""
        sender = str(gl.message.sender)
        if not self.members.get(sender, False):
            return "Only members can vote"

        proposal = self.proposals[proposal_id]
        if not proposal["open"]:
            return "Voting is closed"
        if option not in proposal["options"]:
            return f"Invalid option. Choose from: {proposal['options']}"
        if sender in proposal["votes"]:
            return "You have already voted"

        proposal["votes"][sender] = option
        proposal["vote_counts"][option] += 1
        self.proposals[proposal_id] = proposal
        return f"Vote recorded: {option}"

    @gl.public.write
    def close_proposal(self, proposal_id: str) -> str:
        """Close voting on a proposal and tally results."""
        proposal = self.proposals[proposal_id]
        if str(gl.message.sender) != proposal["creator"] and gl.message.sender != self.admin:
            return "Only creator or admin can close proposals"

        proposal["open"] = False
        self.proposals[proposal_id] = proposal

        counts = proposal["vote_counts"]
        winner = max(counts, key=counts.get) if counts else "No votes"
        return f"Proposal closed. Winner: {winner} ({counts.get(winner, 0)} votes)"

    @gl.public.view
    def get_proposal(self, proposal_id: str) -> dict:
        """Get proposal details and current vote counts."""
        return self.proposals[proposal_id]

    @gl.public.view
    def get_results(self, proposal_id: str) -> dict:
        """Get voting results for a proposal."""
        proposal = self.proposals[proposal_id]
        return {
            "title": proposal["title"],
            "vote_counts": proposal["vote_counts"],
            "total_votes": len(proposal["votes"]),
            "open": proposal["open"],
        }

    @gl.public.view
    def is_member(self, address: str) -> bool:
        """Check if an address is a DAO member."""
        return self.members.get(address, False)
'''
