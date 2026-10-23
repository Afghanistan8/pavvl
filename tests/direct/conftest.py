"""Pavvl Direct Mode harness: the real contract against the real v0.2.16 SDK.

Studionet runs GenVM v0.2.16 (non-debug). The contract header pins
runner 132536jbnx... which maps to v0.2.16's bundle, so Direct Mode tests run
the SAME std the network runs: `import genlayer.gl as gl`, `gl.vm.run_nondet`,
`gl.nondet.exec_prompt`, `gl.message.chain_id`, EthSend transfers.

MONEY. The WASI mock has no EthSend support and vm.value never reaches the
contract balance. This harness installs a `_gl_call_hook` implementing the
network's money semantics:
- payable value: credited to the harness contract balance BEFORE the method
  runs. A _PayableRefusal-style return (not raise) keeps it credited.
- EthSend: debited from the harness balance, recorded in h.transfers.
  Unfunded sends raise SystemError("7: inbalance") exactly like Studionet.
- Each write snapshots the VM; a raise restores everything.

TIME. `h.at(iso)` / `h.later(seconds)` drive vm.warp(). datetime.now() is
patched by the VM context, so contract time follows.

ADDRESSES. Pass wallets as 0x-hex strings (`by=CLAIMANT`). The harness
converts to the SDK Address type the runner expects.

MODEL. `h.mock_judge(answer)` queues exec_prompt answers in order. Each
assessment consumes one. Unmocked prompts raise NoAnswer (a BaseException, so
the contract can never swallow a harness mistake).

VALIDATORS. Direct Mode runs only the leader. `h.run_validator()` replays the
captured validator closure for dissent/adversarial tests.
"""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gltest.direct.loader import deploy_contract
from gltest.direct.vm import VMContext

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "pavvl.py"
SDK_VERSION = "v0.2.16"
STUDIONET_CHAIN_ID = 61999
GEN = 10 ** 18

def same_addr(a: str, b: str) -> bool:
    """Address equality the way the contract means it: 20 bytes, any case.
    str(Address) on chain is EIP-55 checksummed (keccak); the harness keeps
    lowercase constants and compares case-insensitively."""
    return a.lower() == b.lower() if isinstance(a, str) and isinstance(b, str) else a == b


CLAIMANT = "0x3f2536fd5c1ad0f1e8ea5591f36d731a6d51d911"
RESPONDENT = "0x993ba6cae307feb5400b02083062e874f5fe6839"
INSPECTOR = "0x54782bd558865f9c9b6dafc2660f5ea877220ed2"
STRANGER = "0x4d25429512bdc4e2a1c3ec899705b369bfbdc29c"
SECOND = "0x9c965e50e5f25f2660e9a8a1fd7e89a06655a3dd"
DEPLOYER_ADDR = "0x74328d4024fe926ee79a8b86311f986843777ace"


class NoAnswer(BaseException):
    """A test ran a prompt with no queued answer. BaseException so nothing in
    the contract can swallow a harness mistake."""


class Harness:
    def __init__(self, vm: VMContext):
        self.vm = vm
        self.answers = []
        self.prompts = []
        self.transfers = []
        self.network_balance = 0  # GEN the network holds for the contract
        self._Address = None
        self._blind = False  # when True, the model receives no images at all
        vm._chain_id = STUDIONET_CHAIN_ID
        vm._gl_call_hook = self._hook
        # The contract gates writes on gl.message.chain_id (Studionet only).
        # The loader injects the message at import time; refresh it now that
        # the harness set the chain id.
        vm._refresh_gl_message()

    def _addr(self, hexstr: str):
        if self._Address is None:
            import genlayer.py.types as t

            self._Address = t.Address
        return self._Address(bytes.fromhex(hexstr[2:]))

    # -- gl_call hook: network money semantics -------------------------------
    def _hook(self, vmref, request):
        if not isinstance(request, dict):
            return None
        if "EthSend" in request:
            d = request["EthSend"]
            wei = int(d.get("value", 0))
            if wei > self.network_balance:
                raise SystemError("7: inbalance")
            self.network_balance -= wei
            addr = d.get("address")
            try:
                to = "0x" + bytes(addr).hex()
            except Exception:
                to = str(addr)
            self.transfers.append({"to": to, "wei": wei})
            return {"ok": None}
        return None

    # -- time -----------------------------------------------------------------
    def at(self, iso: str):
        self.vm.warp(iso)

    def later(self, seconds: int):
        cur = datetime.fromisoformat(self.vm._datetime.replace("Z", "+00:00"))
        self.vm.warp((cur + timedelta(seconds=int(seconds))).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def now_iso(self) -> str:
        return self.vm._datetime

    # -- model ------------------------------------------------------------------
    def mock_judge(self, answer: dict):
        """Queue one exec_prompt answer (consumed in order)."""
        self.answers.append(copy.deepcopy(answer))

    def mock_look(self, answer):
        """Queue one examination answer: a look() callable or a raw dict.
        Queued BEFORE the judge answer; consumed by the image prompt."""
        self.answers.append(answer)

    def _install_llm(self):
        # gltest matches prompts against vm._llm_mocks regexes in order.
        # Install one catch-all mock whose response is served from the queue
        # by a patched matcher (see call()).
        self.vm.mock_llm("(?s).*", "__PAVVL_QUEUE__")

    # -- model Prompts ------------------------------------------------------
    def auto_sight(self):
        """Patch the SDK's exec_prompt (eager form) so the harness sees the
        images the wasi mock never forwards. The calibration prompt is
        answered truthfully by decoding the attached canary PNG (validating
        CRCs + zlib like a sighted model); examination prompts are answered
        from the queued look function called with (prompt, images); judge
        prompts fall through to the queued dict answers via the normal
        prompt-text matcher.

        genlayer.gl reads the message from fd 0 at import time, so the SDK
        can only be imported while the VM context (with its message on fd 0)
        is active. The loader imports it during deploy_contract — patch then.
        """
        harness = self
        harness._sight_patched = False
        orig = {}

        def ensure_patch():
            if harness._sight_patched:
                return
            import genlayer.gl as _gl

            _ = _gl.nondet  # force lazy load through the proxy
            import genlayer.gl.nondet as _nd
            from genlayer.py.types import Lazy
            from .model import read_canary

            orig_eager = _nd.exec_prompt

            def patched(prompt, **config):
                # NOTE: this replaces the EAGER wrapper (which unwraps .get()
                # itself), so return plain values, not Lazy.
                images = config.get("images") or []
                if "calibration image" in prompt and images:
                    harness.prompts.append({"kind": "sight", "images": len(images),
                                            "blind": harness._blind})
                    if harness._blind:
                        # A model that receives no image cannot read the digits.
                        raw = {"digits": ""}
                    else:
                        try:
                            code = read_canary(bytes(images[0]))
                        except Exception as e:
                            raise NoAnswer(f"canary PNG did not decode: {e}")
                        raw = {"digits": code}
                    if config.get("response_format") == "json":
                        return raw
                    import json as _j

                    return _j.dumps(raw)
                if images and "For each image answer" in prompt:
                    harness.prompts.append({"kind": "look", "images": len(images)})
                    if not harness.answers:
                        raise NoAnswer(f"no queued look answer for a {len(images)}-image prompt")
                    ans = harness.answers.pop(0)
                    if callable(ans):
                        ans = ans(prompt, [bytes(x) for x in images])
                    if isinstance(ans, BaseException):
                        raise ans
                    return ans
                return orig_eager(prompt, **config)

            _nd.exec_prompt = patched
            orig["eager"] = orig_eager
            harness._sight_patched = True
            harness._sight_orig = orig

        harness._ensure_sight_patch = ensure_patch
        # Patch at first call() (VM active + SDK importable); the contract
        # import during deploy happens before any call, and calibration only
        # runs inside request_assessment — always after a call started.
        harness._sight_patched = False

    def restore_llm(self):
        if getattr(self, "_sight_patched", False) and hasattr(self, "_sight_orig"):
            import genlayer.gl.nondet as _nd

            _nd.exec_prompt = self._sight_orig["eager"]

    # -- calls ------------------------------------------------------------------
    def call(self, contract, method, *args, by=CLAIMANT, value=0):
        if getattr(self, "_ensure_sight_patch", None) and not self._sight_patched:
            self._ensure_sight_patch()
        if not self.vm._llm_mocks:
            self._install_llm()
        # Swap the queue sentinel each call so _match returns next answer.
        fn = getattr(contract, method)
        self.vm.sender = self._addr(by)
        self.vm.value = int(value)
        if value:
            self.network_balance += int(value)
        snap = self.vm.snapshot()
        # Monkey-patch _match_llm_mock for this call to serve the queue.
        orig = self.vm._match_llm_mock
        answers = self.answers

        def queued(prompt):
            if not answers:
                raise NoAnswer(f"no queued model answer for prompt: {prompt[:120]}")
            self.prompts.append(prompt)
            return answers.pop(0)

        self.vm._match_llm_mock = queued
        try:
            out = fn(*args)
        except BaseException:
            self.vm.revert(snap)
            raise
        finally:
            self.vm._match_llm_mock = orig
            self.vm.value = 0
        return json.loads(out) if isinstance(out, str) and out[:1] in "{[" else out

    def view(self, contract, method, *args):
        out = getattr(contract, method)(*args)
        return json.loads(out) if isinstance(out, str) and out[:1] in "{[" else out

    def refused(self, contract, method, *args, by=CLAIMANT, value=0, match=""):
        with pytest.raises(Exception) as e:
            self.call(contract, method, *args, by=by, value=value)
        text = str(e.value)
        assert match in text, f"refusal was: {text}"
        return text

    def blind(self, on: bool = True):
        """Make this node's model receive no images, so its calibration fails
        and it must refuse to assess a case that has image evidence."""
        self._blind = bool(on)
        return self

    def run_validator(self, index=-1, answers=None):
        """Replay the captured validator closure.

        `answers` re-arms the model queue for the replay (examination answers
        first, then the judge answer), because a sighted validator re-runs the
        whole assessment itself. With no answers the replay uses whatever this
        node's calibration decides, which is enough to show that a blind node
        refuses before it asks anything."""
        if answers is None:
            return self.vm.run_validator(index=index)
        saved = self.answers
        queue = list(answers)
        self.answers = queue
        orig = self.vm._match_llm_mock

        def queued(prompt):
            if not queue:
                raise NoAnswer(f"no queued model answer for prompt: {prompt[:120]}")
            self.prompts.append(prompt)
            return queue.pop(0)

        self.vm._match_llm_mock = queued
        try:
            return self.vm.run_validator(index=index)
        finally:
            self.vm._match_llm_mock = orig
            self.answers = saved


@pytest.fixture
def h():
    from gltest.direct.sdk_loader import setup_sdk_paths

    setup_sdk_paths(CONTRACT_PATH, SDK_VERSION)
    vm = VMContext()
    with vm.activate():
        harness = Harness(vm)
        harness.auto_sight()
        try:
            yield harness
        finally:
            harness.restore_llm()


@pytest.fixture
def c(h):
    contract = deploy_contract(CONTRACT_PATH, h.vm, sdk_version=SDK_VERSION)
    return contract


def terms(**over):
    t = {
        "title": "Delivery of 100 widgets",
        "subject_kind": "DELIVERY_MADE",
        "subject_ref": "order-42",
        "time_zone": "UTC",
        "claim": "The supplier delivered 100 widgets by 2026-10-10",
        "criteria": [{"text": "100 widgets were delivered", "needs_independent": False}],
        "allowed": ["PHOTO", "TEXT_DOCUMENT"],
        "respondent": RESPONDENT,
        "held_sum_wei": "0",
        "challenge_bond_wei": str(GEN // 100),
    }
    t.update(over)
    return t


def open_case(h, c, by=CLAIMANT, **over):
    return h.call(c, "open_case", json.dumps(terms(**over)), by=by)


def accept_case(h, c, cid, by=RESPONDENT, version=1):
    t = h.view(c, "get_terms", cid, version)
    return h.call(c, "accept_case", cid, t["digest"], by=by)
