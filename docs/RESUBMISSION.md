# Resubmission copy — Pavvl

What to paste into the GenLayer Project Explorer form. Write it with `python probe/make_submission.py`; edit the strings there, not here.

## 01 · Identity

- **Project name:** Pavvl
- **Primary tag:** Dispute Resolution
- **Tag 1:** Evidence Verification
- **Tag 2:** Arbitration
- **Logo:** `probe/pavvl-logo.png` (512x512 PNG, 32 KB)

## 02 · One-liner

Pavvl freezes the criteria that settle a dispute before any evidence is filed, stores that evidence on chain with its digest, and lets independent validators judge it.

## 03 · Description

Pavvl is dispute resolution where the rules are frozen before the evidence exists. A claimant opens a case naming a respondent and a few precise criteria; the respondent accepts that version by its digest, so nothing can be reworded later. Either side may deposit a held sum that moves only on a final decision, and both file evidence the contract hashes itself.

Independent GenLayer validators examine the stored evidence against the frozen criteria. Every validator that votes has examined every image itself: a node whose model cannot receive images refuses to assess rather than judge another's description. Deterministic code applies fixed floors that decide the outcome; a challenge posts a bond and a fresh round.

It suits two parties who disagree about a fact: the standard is set first, evidence is immutable, and every digest recomputes from chain state. It runs on GenLayer Studionet only (chain 61999) as one dependency-free file, so no client can invent authority.

## 04 · How-to — "Write the exact path"

1. **Open the deployed contract** — Go to the Studio Explorer address page for the contract and read its source and its finalized deployment transaction. The source on chain is byte-for-byte this repository's contracts/pavvl.py.
2. **Check who holds authority** — Call get_governance. It reports an empty owner, admin and operator, pausable false, upgradeable false, has_admin_key false, has_upgrade_key false and deployer_has_power false, so the deployer cannot move anything.
3. **Read a live case** — Call get_case PR-0001. It returns the terms digest the respondent accepted, the filed evidence with the SHA-256 the contract computed over the bytes it stored, and the standing decision id.
4. **Read what the validators decided** — Call get_decision D-0001. It returns the finding per criterion, the floors that were applied, which evidence each validator examined (seen_ids), and the rationale the agreeing validators reproduced.
5. **Settle and read the receipt** — The demo case is already finalized: PR-0001's held sum moved to the claimant on a final SUPPORTED. get_receipt returns the receipt digest, which recomputes from chain state.

## 05 · Demo URL

Optional. A YouTube or X post link, if you record one.

## 06 · Review verification

Deployed on Studionet at 0x6173BD4F…; its on-chain source SHA-256 equals this repository's, and `node scripts/deploy.mjs --verify` prints verified true. Live case PR-0001 is FINAL: the respondent accepted a frozen terms digest, the claimant filed a photograph and both sides a document, the validators examined that photograph themselves and agreed SUPPORTED with no floor, and the held sum moved to the claimant.

**Contract links**

- https://explorer-studio.genlayer.com/address/0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7

## 07 · Project links

- **Website:** https://explorer-studio.genlayer.com/address/0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7
- **GitHub:** https://github.com/Afghanistan8/pavvl

## 08 · Evidence & Supporting Information

One git/GitHub repository: https://github.com/Afghanistan8/pavvl
Deployer address: 0xeF18C89f28e4f1Aa2a7f180efcE01b423f7bDE0b (https://explorer-studio.genlayer.com/address/0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7)
Finalized deployment transaction: 0xa523c2420f99a97ef7221e6038125d26a7f4b5ec8d2a058f4c6f439e54f90c80
On-chain source SHA-256: 8f449634455ae64371162237596024d9c78827c49b0af0a2364b01b0114379fd
Reviewer guide: docs/REVIEW_TARGET.md - every property, with the exact command to check it.
Live finalized case: PR-0001 (SUPPORTED - photographed evidence examined by the validators, held sum paid to the claimant).

## 09 · Appeal reason

Addressed the steward's second finding: the validators did not bind which images were seen. _dissent compared the leader's claimed seen_ids against a validator's own set in one direction only, so a leader could claim an image no validator saw, have it recorded as seen, and take the retry right away from the side the decision went against.

The counted seen set - a node's own images plus any copy of the same bytes - is now compared in both directions, and a validator dissents on any difference: it will not stand behind a result resting on less than it saw, nor certify one resting on an image it never saw. The panel succeeds only when every validator reproduced that set.

Redeployed: 0x5F3fcc60… becomes 0x6173BD4F… (sha256 8f449634…), FINALIZED / MAJORITY_AGREE; deploy.mjs --verify prints verified true.

Proof: 85 tests pass, including tests/direct/test_seen_binding.py - a validator dissents when the leader counts an image it did not see, and when the leader omits one it did see.
