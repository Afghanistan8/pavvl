# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 7: transfer via _Payee evm interface."""

import json

import genlayer.gl as gl
from genlayer.py.types import Address, u256


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass


class Probe7(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write.payable
    def deposit(self) -> str:
        return json.dumps({"value": str(int(gl.message.value))})

    @gl.public.write
    def payout(self, to: str, amount: int) -> str:
        _Payee(Address(to)).emit_transfer(value=u256(int(amount)))
        return json.dumps({"to": to, "amount": str(int(amount))})
