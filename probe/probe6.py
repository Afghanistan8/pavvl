# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
"""Pavvl probe 6: image prompt + dict-returning leader on Studionet."""

import json

import genlayer.gl as gl


class Probe6(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write
    def nd_img(self, prompt_text: str, img: bytes) -> str:
        def leader():
            return gl.nondet.exec_prompt(prompt_text, response_format="json", images=[img])

        def validator(result) -> bool:
            return True

        out = gl.vm.run_nondet(leader, validator)
        return json.dumps(out, sort_keys=True)

    @gl.public.write
    def nd_json_str(self, prompt_text: str) -> str:
        def leader():
            out = gl.nondet.exec_prompt(prompt_text, response_format="json")
            return json.dumps(out, sort_keys=True)

        def validator(result) -> bool:
            return True

        return gl.vm.run_nondet(leader, validator)
