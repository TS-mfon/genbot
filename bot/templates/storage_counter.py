"""Minimal production-style GenLayer storage counter template."""

STORAGE_COUNTER_CODE = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class StorageCounter(gl.Contract):
    owner: Address
    label: str
    count: u256

    def __init__(self, label: str):
        self.owner = gl.message.sender_account
        self.label = label
        self.count = u256(0)

    @gl.public.view
    def get_state(self) -> dict:
        return {
            "owner": str(self.owner),
            "label": self.label,
            "count": int(self.count),
        }

    @gl.public.write
    def increment(self) -> None:
        self.count += u256(1)

    @gl.public.write
    def rename(self, new_label: str) -> None:
        if gl.message.sender_account != self.owner:
            raise gl.vm.UserError("[EXPECTED] Only owner can rename")
        self.label = new_label
'''
