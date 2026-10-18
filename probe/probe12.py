# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
import genlayer.gl as gl
from genlayer.gl._internal.eth import evm_contract_interface as eth_iface
from genlayer.py.types import Address, u256
@eth_iface
class _EthPayee:
    class View:
        pass
    class Write:
        pass
class Probe12(gl.Contract):
    def __init__(self):
        pass
    @gl.public.write
    def p(self, to: bytes, amount: int) -> str:
        try:
            _EthPayee(Address(to)).emit_transfer(value=u256(int(amount)))
            return "p-sent"
        except Exception as e:
            return "p-err: " + type(e).__name__ + ": " + str(e)[:200]
