# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 10b: catch transfer exceptions."""

import genlayer.gl as gl
from genlayer.py.types import Address, u256


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass


class Probe10b(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write.payable
    def deposit(self) -> str:
        return "deposited"

    @gl.public.write
    def p2(self, to: str, amount: int) -> str:
        try:
            _Payee(Address(to)).emit_transfer(value=u256(int(amount)))
            return "p2-sent"
        except Exception as e:
            return "p2-err: " + type(e).__name__ + ": " + str(e)[:200]

    @gl.public.write
    def p3(self, to: str, amount: int) -> str:
        try:
            _Payee(Address(to)).emit_transfer(value=u256(int(amount)), on="accepted")
            return "p3-sent"
        except Exception as e:
            return "p3-err: " + type(e).__name__ + ": " + str(e)[:200]
