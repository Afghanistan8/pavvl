# Review target

This is a guide for an independent steward: the exact things to check, and the
exact commands to check them with. Nothing here asks you to trust the authors.

## 0. One-minute orientation

- Contract: [`contracts/pavvl.py`](../contracts/pavvl.py) — one file, no runtime
  dependencies beyond the pinned GenVM std.
- Tests: [`tests/direct/`](../tests/direct) — Direct Mode against the real SDK.
- Deploy driver: [`scripts/deploy.mjs`](../scripts/deploy.mjs).
- Deployment of record: `0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234` on Studionet
  (chain 61999).

## 1. Does the running contract match this repository?

```bash
node scripts/deploy.mjs --verify
```

Expect `verified true` and a `source sha256` equal to `onchain sha256`. If they
disagree, the script exits non-zero. You can also check independently:

```bash
genlayer code 0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234 | sha256sum
```

The on-chain source is also stored verbatim at
`deployments/proofs/studionet-0x5F3fcc6….genlayer.py`.

## 2. Is it really Studionet-only?

```bash
grep -n "_guard_chain" contracts/pavvl.py
python -m pytest tests/direct/test_receipt.py -q -k chain
python -m pytest tests/direct/test_smoke.py   -q -k chain
```

`_guard_chain()` must be the first statement of every `@gl.public.write` method, and
the static test `test_every_write_guards_the_chain` asserts that from the source.

## 3. Is there really no owner, admin, or upgrade path?

```bash
genlayer call 0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234 get_governance
python -m pytest tests/direct/test_governance.py tests/direct/test_receipt.py -q
```

Expect the governance view to report empty owner/admin/operator, no pause, no
upgrade, no admin or upgrade key, and `deployer_has_power: false`. The tests assert
that no write consults a stored key (`test_every_write_gate_is_a_role_from_the_frozen_terms`)
and that the deployer cannot move held funds.

## 4. Can a party win on its own evidence alone?

```bash
python -m pytest tests/direct/test_assessment.py -q -k "floors or f2 or self"
python -m pytest tests/direct/test_invariants.py -q -k self_certification
python -m pytest tests/direct/test_hardening.py -q -k "reuse or injection"
```

The floors (**F3**, **F2**, **F6/F7**) must demote a finding to `CONFLICTING` /
`INSUFFICIENT` wherever a conclusive finding would rest only on the favoured side's
own evidence, or on reused or injection-flagged items.

## 4b. Does every voting validator see the images itself?

```bash
python -m pytest tests/direct/test_validators.py -q
```

A node proves it receives images by reading a calibration image. If it cannot, the
contract refuses to let it assess any case with image evidence: it cannot lead, and
as a validator it dissents. It never judges the leader's description of an image it
did not see, so a decision needs a majority that actually looked. The tests show a
sighted validator calibrating, examining, and agreeing; a blind validator dissenting
without ever examining; and a blind leader recording no decision.

## 4d. Is the seen set bound by the validators, not just claimed by the leader?

```bash
python -m pytest tests/direct/test_seen_binding.py -q
node tools/adversarial_review.mjs
```

The decision's `seen_ids` and `unseen_ids` decide who may ask for the assessment
again: the retry right is only granted when an image genuinely went unexamined. So
the set must be the one the validators examined, not the one the leader claimed.

A validator compares the counted seen set — its own images plus any copy of the same
bytes — in **both** directions, and dissents on any difference. It will not stand
behind a result that rests on less than it saw, and it will not certify one that
rests on an image it never saw. The panel therefore succeeds only when every voting
validator reproduced the same counted set, and the record carries a set the
validators themselves examined.

Without the second direction a leader could count an image no validator saw, and
take the retry right away from the side the decision went against. The tests show a
validator dissenting when the leader counts an image it did not see, dissenting when
the leader omits one it did see, agreeing when both saw the same images, agreeing on
a twin whose bytes were seen, and the record reporting an image the panel never saw
as unseen.

## 4c. Is there a live case to read?

```bash
genlayer call 0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234 get_case --args PR-0002
genlayer call 0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234 get_decision --args D-0002
genlayer call 0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234 get_receipt --args PR-0002
```

Two cases ran to completion on this deployment and are finalized, so the
property in 4b can be read off the chain rather than taken on trust:

- `PR-0002` — the claimant filed a photograph, a delivery note and the respondent
  a receipt. The decision carries `calibrated: true` and `seen_ids: ["E-0002"]`:
  the node proved it receives images, and the photograph it examined is the one
  the finding rests on. The finding is `SUPPORTED` with no floor applied, and the
  held sum moved to the claimant.
- `PR-0001` — the same flow with a photograph that did not establish the claim.
  The finding is `INSUFFICIENT` and the held sum was released to the respondent.

The machine-written copies are `deployments/demo-case-PR-0001.json` and
`deployments/demo-case-PR-0002.json`. To run the flow yourself from nothing:

```bash
node probe/pavvl_demo_case.mjs
node probe/pavvl_demo_case.mjs --finalize
```

## 5. Does anything but SUPPORTED pay the claimant?

```bash
python -m pytest tests/direct/test_hardening.py -q -k "pays or pay the claimant"
python -m pytest tests/direct/test_invariants.py -q -k "books or strands"
```

`finalize` pays only on a final `SUPPORTED`; every other outcome releases to the
funder; all movement is pull-based so nothing is stranded.

## 6. Does the published authority match the callable one?

```bash
python -m pytest tests/direct/test_actions.py -q
node tools/adversarial_review.mjs
```

`get_actions(cid, who)` publishes, on chain, what a wallet may do right now,
computed from the same state the writes check. The review script re-derives the
write → gate mapping from the source and fails if any write has no gate or any gate
has no write, so the published surface cannot drift from the callable one.
`test_actions.py` exercises the gate map for the draft, open, funding, and finalize
states and checks that a wallet the contract would refuse is told why.

## 6b. Does a client recompute the contract's digest byte for byte?

```bash
python -m pytest tests/direct/test_canonical.py tests/direct/test_receipt.py -q -k "canon or digest"
```

Every digest is a SHA-256 over the contract's `_canon`, which uses
`ensure_ascii=True` and Python's code-point key ordering, so the bytes are pure
ASCII and language-independent. The tests rebuild the terms, decision, and receipt
digests in Python and assert the on-chain values, and `test_canonical.py` does the
same over accented Latin, CJK, and an astral emoji (a UTF-16 surrogate pair in the
escaped form). A client that reproduces those bytes reaches the same digest; if the
contract ever switched to raw UTF-8, these tests would fail while the ASCII-only
ones still passed.

## 7. Are the toolchain pins real?

```bash
cat TOOLCHAIN.md
python -m pytest tests/direct/test_receipt.py -q -k "runner or source"
```

The header must be exactly `# v0.2.16` then the `py-genlayer:132536…` Depends line;
the source must be ASCII with LF line endings. Both are asserted statically.

## 8. Advisory automated review

```bash
node tools/adversarial_review.mjs
```

This script walks the repository and flags (a) any write not guarded by
`_guard_chain`, (b) any write with no `get_actions` gate or any gate with no write,
(c) any sign of a pause/upgrade/admin/owner surface, (d) a `_guard_chain` that does
not refuse a non-Studionet chain, (e) any model/assistant attribution in committed
text, and (f) any path where a node could judge another node's observations of the
evidence instead of the evidence itself. It prints findings and exits non-zero on a
hard failure. It is a convenience, not a substitute for the tests.

## 9. Design guarantees

The guarantees in [`README.md`](../README.md#design-guarantees) are each checkable
from this repository: the pinned GenVM header (`TOOLCHAIN.md`, and the static source
tests), the chain gate on every write (section 2), the `SUBJECT_KINDS`
generalization (`get_config` and `test_smoke.py`), the on-chain `get_actions`
authority map (section 6), the `get_governance` view (section 3), and the verified
deployment (section 1).

## 10. Reporting a finding

Open an issue with a minimal reproduction. The strongest report is a failing test
against `tests/direct/` plus the exact command that shows the divergence.
