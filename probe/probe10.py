# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
import genlayer.gl as gl
from genlayer.py.types import Address, u256
class Probe10(gl.Contract):
    def __init__(self):
        pass
    @gl.public.write
    def p1(self, to: str, amount: int) -> str:
        try:
            gl.get_contract_at(Address(to)).emit_transfer(value=u256(int(amount)))
            return "p1-sent"
        except Exception as e:
            return "p1-err: " + type(e).__name__ + ": " + str(e)[:200]
