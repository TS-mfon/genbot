"""Voting DAO template contract for GenLayer."""

VOTING_DAO_CODE = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class VotingDAO(gl.Contract):
    """DAO voting with typed storage and flat indexes."""

    admin: Address
    proposal_count: u256
    members: TreeMap[str, bool]
    proposal_titles: TreeMap[str, str]
    proposal_descriptions: TreeMap[str, str]
    proposal_creators: TreeMap[str, str]
    proposal_open: TreeMap[str, bool]
    proposal_option_count: TreeMap[str, u256]
    proposal_options: TreeMap[str, str]
    vote_counts: TreeMap[str, u256]
    voter_choices: TreeMap[str, str]

    def __init__(self):
        self.admin = gl.message.sender_account
        self.proposal_count = u256(0)
        self.members[str(gl.message.sender_account)] = True

    def _option_key(self, proposal_id: str, option_index: int) -> str:
        return proposal_id + "|" + str(option_index)

    def _vote_count_key(self, proposal_id: str, option: str) -> str:
        return proposal_id + "|" + option

    def _voter_key(self, proposal_id: str, voter: str) -> str:
        return proposal_id + "|" + voter

    @gl.public.write
    def add_member(self, member_address: str) -> None:
        if gl.message.sender_account != self.admin:
            raise gl.vm.UserError("[EXPECTED] Only admin can add members")
        self.members[member_address] = True

    @gl.public.write
    def create_proposal(self, title: str, description: str, options_csv: str) -> str:
        sender = str(gl.message.sender_account)
        if not self.members.get(sender, False):
            raise gl.vm.UserError("[EXPECTED] Only members can create proposals")

        options = [item.strip() for item in options_csv.split(",") if item.strip()]
        if len(options) < 2:
            raise gl.vm.UserError("[EXPECTED] Provide at least two comma-separated options")

        proposal_id = str(int(self.proposal_count))
        self.proposal_count += u256(1)
        self.proposal_titles[proposal_id] = title
        self.proposal_descriptions[proposal_id] = description
        self.proposal_creators[proposal_id] = sender
        self.proposal_open[proposal_id] = True
        self.proposal_option_count[proposal_id] = u256(len(options))

        for index, option in enumerate(options):
            self.proposal_options[self._option_key(proposal_id, index)] = option
            self.vote_counts[self._vote_count_key(proposal_id, option)] = u256(0)

        return proposal_id

    @gl.public.write
    def vote(self, proposal_id: str, option: str) -> None:
        sender = str(gl.message.sender_account)
        if not self.members.get(sender, False):
            raise gl.vm.UserError("[EXPECTED] Only members can vote")
        if not self.proposal_open.get(proposal_id, False):
            raise gl.vm.UserError("[EXPECTED] Voting is closed")
        if self.voter_choices.get(self._voter_key(proposal_id, sender), "") != "":
            raise gl.vm.UserError("[EXPECTED] You have already voted")
        if not self.option_exists(proposal_id, option):
            raise gl.vm.UserError("[EXPECTED] Invalid option")

        self.voter_choices[self._voter_key(proposal_id, sender)] = option
        count_key = self._vote_count_key(proposal_id, option)
        self.vote_counts[count_key] = self.vote_counts.get(count_key, u256(0)) + u256(1)

    @gl.public.write
    def close_proposal(self, proposal_id: str) -> None:
        sender = str(gl.message.sender_account)
        creator = self.proposal_creators.get(proposal_id, "")
        if sender != creator and gl.message.sender_account != self.admin:
            raise gl.vm.UserError("[EXPECTED] Only creator or admin can close proposals")
        self.proposal_open[proposal_id] = False

    @gl.public.view
    def option_exists(self, proposal_id: str, option: str) -> bool:
        option_count = int(self.proposal_option_count.get(proposal_id, u256(0)))
        for index in range(option_count):
            if self.proposal_options.get(self._option_key(proposal_id, index), "") == option:
                return True
        return False

    @gl.public.view
    def get_proposal(self, proposal_id: str) -> dict:
        options = []
        counts = {}
        option_count = int(self.proposal_option_count.get(proposal_id, u256(0)))
        for index in range(option_count):
            option = self.proposal_options.get(self._option_key(proposal_id, index), "")
            options.append(option)
            counts[option] = int(self.vote_counts.get(self._vote_count_key(proposal_id, option), u256(0)))

        return {
            "id": proposal_id,
            "title": self.proposal_titles.get(proposal_id, ""),
            "description": self.proposal_descriptions.get(proposal_id, ""),
            "creator": self.proposal_creators.get(proposal_id, ""),
            "open": self.proposal_open.get(proposal_id, False),
            "options": options,
            "vote_counts": counts,
        }

    @gl.public.view
    def is_member(self, account: str) -> bool:
        return self.members.get(account, False)
'''
