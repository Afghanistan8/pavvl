# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

"""Pavvl capability probe: chain gate, payable, nondet+images, transfer."""

import json

import genlayer as gl
from genlayer.types import Address, u256
from genlayer.chain import Account


class Probe2(gl.Contract):
    total: u256

    def __init__(self):
        self.total = u256(0)

    @gl.public.view
    def get_chain(self) -> int:
        return int(gl.message.chain_id)

    @gl.public.write.payable
    def deposit(self) -> str:
        self.total = u256(int(self.total) + int(gl.message.value))
        return json.dumps({"chain": int(gl.message.chain_id), "value": str(int(gl.message.value)),
                           "total": str(int(self.total))})

    @gl.public.write
    def assess(self, prompt_text: str, img: bytes) -> str:
        def leader() -> str:
            out = gl.nondet.exec_prompt(prompt_text, response_format="json", images=[img])
            return json.dumps(out, sort_keys=True)

        def validator(result) -> bool:
            from genlayer.vm import unpack_result
            got = unpack_result(result)
            try:
                parsed = json.loads(got)
            except Exception:
                return False
            return isinstance(parsed, dict) and "ok" in parsed

        return gl.vm.run_nondet(leader, validator)

    @gl.public.write
    def payout(self, to: str, amount: int) -> str:
        Account(Address(to)).emit_transfer(u256(int(amount)))
        return json.dumps({"to": to, "amount": str(int(amount))})
