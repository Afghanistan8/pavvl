# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 5: isolate the run_nondet failure on Studionet."""

import genlayer.gl as gl


class Probe5(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write
    def nd_const(self) -> str:
        def leader():
            return "hello"

        def validator(result) -> bool:
            return True

        return gl.vm.run_nondet(leader, validator)

    @gl.public.write
    def nd_prompt(self, prompt_text: str) -> str:
        def leader():
            return gl.nondet.exec_prompt(prompt_text, response_format="json")

        def validator(result) -> bool:
            return True

        out = gl.vm.run_nondet(leader, validator)
        return str(type(out))
