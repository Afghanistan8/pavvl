# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 11: raw-bytes transfer + balance visibility."""

import genlayer.gl as gl
from genlayer.py.types import Address, u256


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass


class Probe11(gl.Contract):
    def __init__(self):
        pass

    @gl.public.view
    def bal(self) -> str:
        return str(int(gl.get_contract_at(gl.message.contract_address).balance))

    @gl.public.write.payable
    def deposit(self) -> str:
        return str(int(gl.message.value))

    @gl.public.write
    def p_raw(self, to: bytes, amount: int) -> str:
        try:
            _Payee(Address(to)).emit_transfer(value=u256(int(amount)))
            return "p_raw-sent"
        except Exception as e:
            return "p_raw-err: " + type(e).__name__ + ": " + str(e)[:200]

    @gl.public.write
    def p_hex(self, to: str, amount: int) -> str:
        try:
            raw = bytes.fromhex(to[2:] if to.startswith("0x") else to)
            _Payee(Address(raw)).emit_transfer(value=u256(int(amount)))
            return "p_hex-sent"
        except Exception as e:
            return "p_hex-err: " + type(e).__name__ + ": " + str(e)[:200]
