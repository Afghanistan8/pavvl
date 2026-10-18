# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

"""Pavvl deploy probe: minimal storage + message contract on Studionet."""

import genlayer as gl
from genlayer.types import Address, u256


class Probe(gl.Contract):
    count: gl.TreeMap[Address, u256]

    def __init__(self):
        pass

    @gl.public.write
    def bump(self) -> None:
        s = gl.message.sender_address
        self.count[s] = self.count.get(s, 0) + 1

    @gl.public.view
    def get(self, who: str) -> int:
        return self.count.get(Address(who), 0)
