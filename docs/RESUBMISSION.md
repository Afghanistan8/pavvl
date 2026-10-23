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
3. **Read a live case** — Call get_case PR-0002. It returns the terms digest the respondent accepted, the filed evidence with the SHA-256 the contract computed over the bytes it stored, and the standing decision id.
4. **Read what the validators decided** — Call get_decision D-0002. It returns the finding per criterion, the floors that were applied, which evidence each validator examined (seen_ids), and the rationale the agreeing validators reproduced.
5. **Settle and read the receipt** — The demo cases are already finalized: PR-0002's held sum moved to the claimant on a final SUPPORTED, PR-0001's to the respondent on INSUFFICIENT. get_receipt returns the receipt digest, which recomputes from chain state.

## 05 · Demo URL

Optional. A YouTube or X post link, if you record one.

## 06 · Review verification

Deployed on Studionet at 0x5F3fcc60…; its on-chain source SHA-256 equals this repository's, and `node scripts/deploy.mjs --verify` prints verified true. Live case PR-0002 is FINAL: the respondent accepted a frozen terms digest, the claimant filed a photograph and both sides a document, the validators examined that photograph themselves and agreed SUPPORTED with no floor, and the held sum moved to the claimant. PR-0001 is the same flow ending INSUFFICIENT, its held sum released to the respondent.

**Contract links**

- https://explorer-studio.genlayer.com/address/0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234

## 07 · Project links

- **Website:** https://explorer-studio.genlayer.com/address/0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234
- **GitHub:** https://github.com/Afghanistan8/pavvl

## 08 · Evidence & Supporting Information

One git/GitHub repository: https://github.com/Afghanistan8/pavvl
Deployer address: 0xeF18C89f28e4f1Aa2a7f180efcE01b423f7bDE0b (https://explorer-studio.genlayer.com/address/0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234)
Finalized deployment transaction: 0x9dec4f862550247051cb81c96461dc60d5dfe9134445de78c81c107133b496f9
On-chain source SHA-256: 730bc0c35cc6ae786e69bc5939895e757dfaa74b0b165cbac3f52d05ffe2e0b1
Reviewer guide: docs/REVIEW_TARGET.md - every property, with the exact command to check it.
Live finalized cases: PR-0002 (SUPPORTED - photographed evidence examined by the validators, held sum paid to the claimant) and PR-0001 (INSUFFICIENT - held sum released to the respondent).

## 09 · Appeal reason

Addressed the steward's finding: a node that cannot receive images no longer assesses a case by reading the leader's descriptions.

_borrow() and every borrowed marker are gone. _assess() refuses to assess when a case has image evidence and the node fails the calibration image: as leader it errors and no decision is recorded; as validator the refusal is a dissent. A decision needs a majority that examined every image itself. Nor a soft warning: a node that cannot open one image cannot cite it (F5), so a finding resting on it is floored to INSUFFICIENT (F1), not SUPPORTED (F3).

Redeployed: 0xAcBdea1B… becomes 0x5F3fcc60… (source sha256 730bc0c3…), FINALIZED / MAJORITY_AGREE; deploy.mjs --verify prints verified true.

Proof: 79 tests pass, including tests/direct/test_validators.py - a sighted validator examines the image itself and agrees; a blind validator dissents without examining; a blind leader records no decision. adversarial_review.mjs fails the build if borrowing returns.
