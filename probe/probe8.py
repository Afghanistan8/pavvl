# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 8: three transfer variants on Studionet."""

import genlayer.gl as gl
from genlayer.py.types import Address, u256


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass


class Probe8(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write.payable
    def deposit(self) -> str:
        return "deposited"

    @gl.public.write
    def p1(self, to: str, amount: int) -> str:
        gl.get_contract_at(Address(to)).emit_transfer(value=u256(int(amount)))
        return "p1-ok"

    @gl.public.write
    def p2(self, to: str, amount: int) -> str:
        _Payee(Address(to)).emit_transfer(value=u256(int(amount)))
        return "p2-ok"

    @gl.public.write
    def p3(self, to: str, amount: int) -> str:
        _Payee(Address(to)).emit_transfer(value=u256(int(amount)), on="accepted")
        return "p3-ok"
