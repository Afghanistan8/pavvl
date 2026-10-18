# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

"""Pavvl probe 3: legacy-idiom storage, chain gate, payable, nondet, transfer."""

import json

import genlayer as gl
from genlayer.types import Address, u256


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass


class Probe3(gl.Contract):
    counters: gl.storage.TreeMap[str, str]
    blobs: gl.storage.TreeMap[str, bytes]

    def __init__(self):
        self.counters["n"] = "0"

    def _bump(self) -> int:
        n = int(self.counters.get("n") or "0") + 1
        self.counters["n"] = str(n)
        return n

    @gl.public.view
    def get_chain(self) -> str:
        return json.dumps({"chain_id": int(gl.message.chain_id)})

    @gl.public.write.payable
    def deposit(self) -> str:
        n = self._bump()
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
                parsed = json.loads(result.calldata)
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
                parsed = json.loads(result.calldata)
            except Exception:
                return False
            return isinstance(parsed, dict) and "ok" in parsed

        return json.dumps(gl.vm.run_nondet(leader, validator), sort_keys=True)

    @gl.public.write
    def payout(self, to: str, amount: int) -> str:
        _Payee(Address(to)).emit_transfer(value=u256(int(amount)))
        return json.dumps({"to": to, "amount": str(int(amount))})
