# Testing

Pavvl is a single contract, so its tests are a single layer: **Direct Mode**,
which runs the real contract against the real v0.2.16 SDK that Studionet runs.
No network and no keys are needed. Two more commands check the source statically
and verify the live deployment.

```bash
# Contract tests: from the repository root
python -m pip install -r requirements-dev.txt
python -m pytest -q

# Advisory review of the source (no network)
node tools/adversarial_review.mjs

# Verify the recorded deployment against the source (read-only, needs network)
node scripts/deploy.mjs --verify
```

> Note: `python -m pytest` prints a `gltest` warning on stderr, which PowerShell
> reports as `Exited with code 1`. The suite result line (`79 passed`) is the
> authoritative outcome.

## 1. Direct Mode contract tests (`tests/direct/`)

These deploy the **real** contract against the **real** v0.2.16 SDK the network
runs. The harness (`conftest.py`) reproduces the network's money semantics
(payable credit, `EthSend` debits, `inbalance` on unfunded sends), drives time with
`vm.warp`, and serves model answers from a queue. Identical bytes are matched by
the harness exactly as the contract links twins.

| File | Focus |
|---|---|
| `test_smoke.py` | config, chain gate, open/accept/decline/withdraw, expire, inspector, funding |
| `test_evidence.py` | digests over stored bytes, text line breaks, who may file, image rules, caps, duplicates, cross-case reuse, deadlines, readiness |
| `test_assessment.py` | supported end to end, code-decided missing/empty, floor demotion, F2 independent basis, retry when unseen, guards |
| `test_actions.py` | the `get_actions` gate map for draft/open/fund/finalize, and off-chain refusal |
| `test_challenge.py` | challenge needs new evidence + bond, failed bond → opponent, close without evidence returns the bond, single challenge, double finalize/withdraw refused |
| `test_canonical.py` | the digest over non-ASCII payloads: accented Latin, CJK, and an astral emoji (escaped as a UTF-16 surrogate pair), proving the contract hashes `ensure_ascii=True` bytes a client in any language can rebuild |
| `test_receipt.py` | receipt digest recomputes (terms, decision, receipt), receipt before decision refused, canary PNG, PNG metadata refused, source is ASCII+LF, runner pin header, storage/method name disjointness, every write guards the chain, payable writes refuse by returning, no operator backdoor, chain constant |
| `test_invariants.py` | balance books equality, failed transfer never strands value, no self-certification paths, lapse returns the deposit, counter consistency |
| `test_governance.py` | governance view reports no authority, deployer recorded but powerless, no pause/upgrade/admin methods, every write gate is a frozen-terms role, deployer cannot move held funds, stats/config agree |
| `test_hardening.py` | digest freeze/recompute, criteria-id injection, stored-bytes digest, duplicate filing, cross-counterparty reuse, manifest reuse, prompt injection, settlement fail-closed, supported pays claimant |
| `test_validators.py` | validator independence over image evidence: a sighted validator calibrates, examines the image, and agrees; a blind validator dissents without looking or judging the leader's descriptions; a blind leader records no decision |

`model.py` holds harness helpers (canary PNG codec, queued-answer helpers).

### Digest reproducibility

Every digest the contract publishes covers exactly
`json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`
(`_canon`). `test_receipt.py` recomputes the terms, decision, and receipt digests
in Python and asserts the on-chain values; `test_canonical.py` does the same over
non-ASCII payloads, so a client that rebuilds the escaped ASCII bytes in any
language reaches the same digest. Both fail if the contract switches to raw UTF-8.

## 2. Source-level checks

Several cheap, high-signal tests read the contract as text and assert properties
no single run can: the pinned header is exactly two lines, the source is pure
ASCII with LF-only endings (so its SHA-256 is stable everywhere), no storage field
shares a name with a method, every `@gl.public.write` calls `_guard_chain()` first,
every payable write refuses by returning a `_PayableRefusal` (never raising, which
would strand the credited value), and there is no operator backdoor. These live in
`test_receipt.py` and run with the rest.

## 3. Advisory review (`tools/adversarial_review.mjs`)

Not a substitute for the suite — a fast re-derivation of the headline guarantees
straight from the source, so a reviewer can spot drift in one command:

1. the exact pinned Studionet header;
2. every write guards the chain first;
3. every write has a `get_actions` gate and every gate has a write (so no callable
   path is missing from what the contract publishes, and no published button is
   unbacked);
4. no pause / upgrade / owner / admin / operator method or stored key;
5. `_guard_chain` refuses every chain but Studionet;
6. no node judges another node's observations of the evidence: a node whose model
   cannot receive images refuses, and every voting validator examines the evidence
   itself;
7. no model or assistant attribution in committed text.

Hard failures exit non-zero; advisories are printed and do not fail the run.

## 4. Deployment verification (`scripts/deploy.mjs`)

`node scripts/deploy.mjs --verify` re-fetches the on-chain source and proves its
SHA-256 equals the repository's, using the recorded manifest. It is the check that
the address in the README is the code in this repository. `--check` validates the
header and the configured network without sending a transaction.

## 5. What is deliberately not tested here

- **Live consensus.** Direct Mode runs only the leader; `h.run_validator()` replays
  the captured validator closure for dissent tests, including the blind validator
  that refuses to assess image evidence. Real validator voting, quorum, and
  finality are properties of Studionet, exercised by the live deployment's
  `FINALIZED` / `MAJORITY_AGREE` receipt.
- **Network availability.** The chain gate is asserted statically and behaviourally,
  but a live outage is not simulated.
- **Client code.** This repository ships the contract, not a client; a client's
  conformance to `get_actions` and to `_canon` is the client's own test.

## 6. Reproducing the counts

```bash
python -m pytest -q                 # 79 passed
node tools/adversarial_review.mjs   # 11 passed, 0 advisory, 0 failed
node scripts/deploy.mjs --verify    # verified: on-chain source == repository source
```
