# Pavvl

**Criteria first. Evidence on chain. Validators judge. Code settles.**

Pavvl is a standalone GenLayer intelligent contract for falsifiable disputes. Two
parties freeze the criteria that would settle a claim *before* any evidence is
filed. Evidence is stored on chain with its digest. Independent validators examine
it under consensus. Deterministic code — never a person — turns that consensus into
a finding and moves any held sum.

A finding is an assessment of evidence against agreed criteria. It is **not** a
legal determination, **not** proof that an event happened, and missing evidence is
never treated as proof of anything.

The contract is one dependency-free Python file. There is no companion app in this
repository: the contract publishes everything a client needs (`get_actions`,
`get_config`, `get_governance`, `get_receipt`), so any client can be thin and none
can invent authority the contract would refuse.

---

## Live deployment (Studionet, chain 61999)

| | |
|---|---|
| Contract | [`0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7`](https://explorer-studio.genlayer.com/address/0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7) |
| Deploy transaction | `0xa523c2420f99a97ef7221e6038125d26a7f4b5ec8d2a058f4c6f439e54f90c80` |
| Status / result | `FINALIZED` / `MAJORITY_AGREE` |
| Deployer | `0xeF18C89f28e4f1Aa2a7f180efcE01b423f7bDE0b` |
| Source SHA-256 | `8f449634455ae64371162237596024d9c78827c49b0af0a2364b01b0114379fd` |
| On-chain source SHA-256 | `8f449634455ae64371162237596024d9c78827c49b0af0a2364b01b0114379fd` |

The two hashes above are equal: the source stored on chain is byte-for-byte the
source in this repository. That is not a claim in a document — it is re-checkable:

```bash
node scripts/deploy.mjs --verify
```

The machine-written record is in [`deployments/studionet.json`](deployments/studionet.json),
with the raw on-chain source and receipt under [`deployments/proofs/`](deployments/proofs).

### Live cases

Two cases ran end to end on this deployment, both finalized, so a reviewer can
read real data rather than a description of it:

| Case | Evidence | Finding | Settlement |
|---|---|---|---|
| `PR-0001` | a photograph the validators examined themselves, a delivery note, a receipt | `SUPPORTED`, no floor applied | 1 GEN to the claimant |
| `PR-0002` | a photograph that did not establish the claim | `INSUFFICIENT` | 1 GEN released to the respondent |

```bash
genlayer call 0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7 get_case --args PR-0001
genlayer call 0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7 get_decision --args D-0001
genlayer call 0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7 get_receipt --args PR-0001
```

`get_decision` shows `calibrated: true` and the image ids the validators
examined, so the record itself says the finding came from nodes that looked at
the pictures themselves. The machine-written copies are in
[`deployments/demo-case-PR-0001.json`](deployments/demo-case-PR-0001.json) and
[`deployments/demo-case-PR-0002.json`](deployments/demo-case-PR-0002.json).

---

## The trust model in one screen

1. **Freeze.** The claimant publishes the claim and the criteria. The respondent
   accepts *that exact version* by its digest. No moving the goalposts.
2. **File.** Both parties, and an optional independent inspector, file photographs
   and documents. The contract stores the bytes and computes their digests itself.
3. **Judge.** GenLayer validators re-examine the stored evidence against the frozen
   criteria. Consensus binds only whether each criterion is *supported* and whether
   anything could be assessed at all. Every voting validator examines the images
   itself, and the set of images the panel saw is bound by all of them: a validator
   will not certify a result that rests on an image it never saw, so the record
   cannot claim an image was examined when it was not.
4. **Settle.** Deterministic code applies fixed floors to the result and derives the
   overall finding. The held sum moves to the claimant **only** on a final
   `SUPPORTED` finding.

Uncertainty fails closed. An assessment result is a standing decision, not
authority: funds move only after the challenge window closes and `finalize` runs.

There is no owner, no admin, no operator, and no upgrade key. That is readable
from the chain itself:

```
genlayer call 0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7 get_governance
```

---

## Design guarantees

Every property below is checkable against the source and the tests, not just
asserted here.

1. **It runs on today's Studionet.** The source carries the exact GenVM header and
   import idiom that Studionet's non-debug v0.2.16 GenVM accepts, and nothing else.
   See [`TOOLCHAIN.md`](TOOLCHAIN.md) for the proven pins.

2. **Every write is pinned to Studionet.** `_guard_chain()` runs first in every
   state-changing method and refuses any chain but 61999. Pavvl settles real value
   under one network's consensus, so it refuses to run anywhere else.

3. **It judges any falsifiable claim.** `SUBJECT_KINDS` covers work completed,
   condition at a time, delivery made, payment made, an agreed procedure followed,
   or other — each with its own validator guidance. The claim, not the domain, is
   the unit.

4. **The contract publishes its own authority.** `get_actions(case, wallet)`
   returns what that wallet may do *right now*, computed on chain from the same
   state the writes check, each rule mirroring its write's own check in the same
   order. Every write has a gate and every gate has a write, so a client that
   renders these rows can neither invent authority nor hide a path. That mapping
   is re-derived from the source by `tools/adversarial_review.mjs`.

5. **Governance is auditable on chain.** `get_governance()` returns the empty owner
   / admin / operator, `pausable: false`, `upgradeable: false`, `has_admin_key:
   false`, `has_upgrade_key: false`, and `deployer_has_power: false`, with the
   authority statement.

6. **Digests are reproducible anywhere.** Every digest is a SHA-256 over
   `json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`, so
   the bytes are pure ASCII and language-independent. A client in any language can
   rebuild the receipt digest from chain state and check it. Non-ASCII text — CJK,
   an astral emoji — is escaped exactly, and `tests/direct/test_canonical.py` pins
   it.

7. **A reproducible, verified deployment.** `scripts/deploy.mjs` refuses any chain
   but 61999, refuses a source without the pinned GenVM header, deploys, waits for
   finality, and proves the on-chain source matches the repository before writing a
   machine-readable manifest. No key is ever handled, printed, or stored.

8. **The seen set is bound, not claimed.** The decision's `seen_ids` and
   `unseen_ids` decide who may ask for the assessment again, so they must be the
   images the validators examined. Every voting validator compares the counted
   seen set in both directions and dissents on any difference: it will not stand
   behind a result resting on less than it saw, and it will not certify one
   resting on an image it never saw. A leader therefore cannot count an image the
   panel did not examine and take the retry right away. See
   [`docs/SECURITY.md`](docs/SECURITY.md) T14.

---

## Quickstart

### Contract tests (no network, no keys)

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The Direct Mode suite deploys the contract in-process against the real v0.2.16 SDK
and drives the full lifecycle: the floors, the challenge path, settlement,
governance isolation, digests over non-ASCII payloads, and the source-level
properties. See [`docs/TESTING.md`](docs/TESTING.md).

### Advisory review (no network)

```bash
node tools/adversarial_review.mjs
```

### Deploy / verify

```bash
node scripts/deploy.mjs --check     # validate source header + network only
node scripts/deploy.mjs             # deploy, wait for finality, verify, write manifest
node scripts/deploy.mjs --verify    # re-verify the recorded deployment
```

The deployer must be an unlocked GenLayer CLI account on Studionet. The script
never reads a private key.

---

## Repository layout

```
contracts/pavvl.py        the contract (single file, dependency-free)
tests/direct/             Direct Mode contract tests (gltest, real v0.2.16 SDK)
scripts/deploy.mjs        deployment driver + source-SHA verifier
tools/                    advisory review tooling for a steward
deployments/              verified deployment manifest + raw proofs
probe/                    toolchain probes that established the Studionet pins
docs/                     architecture, security, deployment, testing, review guide
TOOLCHAIN.md              pinned toolchain and proven Studionet patterns
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — states, data model, consensus, floors, receipts, client integration.
- [`docs/SECURITY.md`](docs/SECURITY.md) — threat model, invariants, governance guarantees.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — deploy, verify, and the manifest schema.
- [`docs/TESTING.md`](docs/TESTING.md) — the test suite and how to run it.
- [`docs/REVIEW_TARGET.md`](docs/REVIEW_TARGET.md) — what a reviewer should check, with exact commands.
- [`TOOLCHAIN.md`](TOOLCHAIN.md) — pinned versions and the proven Studionet idioms.

## License

ISC. See [`LICENSE`](LICENSE).

---

Studionet only (chain 61999). Everything written to Pavvl is public and permanent.
