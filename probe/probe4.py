# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 4: v0.2.16 idioms — full capability check on Studionet."""

import json

import genlayer.gl as gl
from genlayer.py.types import Address, u256
from genlayer.py.storage import TreeMap


class Probe4(gl.Contract):
    counters: TreeMap[str, str]

    def __init__(self):
        self.counters["n"] = "0"

    @gl.public.view
    def get_chain(self) -> str:
        return json.dumps({"chain_id": int(gl.message.chain_id)})

    @gl.public.write.payable
    def deposit(self) -> str:
        n = int(self.counters.get("n") or "0") + 1
        self.counters["n"] = str(n)
        return json.dumps({"n": n, "value": str(int(gl.message.value)),
                           "sender": str(gl.message.sender_address)})

    @gl.public.write
    def assess_text(self, prompt_text: str) -> str:
        def leader():
            return gl.nondet.exec_prompt(prompt_text, response_format="json")

        def validator(result) -> bool:
            if not isinstance(result, gl.vm.Return):
                return False
            try:
                parsed = json.loads(gl.vm.unpack_result(result))
            except Exception:
                return False
            return isinstance(parsed, dict) and "ok" in parsed

        return json.dumps(gl.vm.run_nondet(leader, validator), sort_keys=True)

    @gl.public.write
    def assess_image(self, prompt_text: str, img: bytes) -> str:
        def leader():
            return gl.nondet.exec_prompt(prompt_text, response_format="json", images=[img])

        def validator(result) -> bool:
            if not isinstance(result, gl.vm.Return):
                return False
            try:
                parsed = json.loads(gl.vm.unpack_result(result))
            except Exception:
                return False
            return isinstance(parsed, dict) and "ok" in parsed

        return json.dumps(gl.vm.run_nondet(leader, validator), sort_keys=True)

    @gl.public.write
    def payout(self, to: str, amount: int) -> str:
        gl.get_contract_at(Address(to)).emit_transfer(value=u256(int(amount)))
        return json.dumps({"to": to, "amount": str(int(amount))})
