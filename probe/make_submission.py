"""Character-check the GenLayer Project Explorer resubmission copy for Pavvl.

The portal enforces hard character limits on several fields, so the copy is
written here, measured here, and written out to docs/RESUBMISSION.md. Edit the
strings below and re-run:

    python probe/make_submission.py
"""

import pathlib

CONTRACT = "0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234"
EXPLORER = f"https://explorer-studio.genlayer.com/address/{CONTRACT}"
REPO = "https://github.com/Afghanistan8/pavvl"
DEPLOY_TX = "0x9dec4f862550247051cb81c96461dc60d5dfe9134445de78c81c107133b496f9"
SOURCE_SHA = "730bc0c35cc6ae786e69bc5939895e757dfaa74b0b165cbac3f52d05ffe2e0b1"
REJECTED_ADDR = "0xAcBdea1B9CA3863355C1081Dd3c302b1aaDc2144"
REJECTED_SHA = "8fc10d6f8c62b3a62c02fa449e0ee5ec2ce56cf9cb0db73959767d3276d4e019"

PROJECT_NAME = "Pavvl"
PRIMARY_TAG = "Dispute Resolution"
TAG_1 = "Evidence Verification"
TAG_2 = "Arbitration"

ONE_LINER = (
    "Pavvl freezes the criteria that settle a dispute before any evidence is filed, stores "
    "that evidence on chain with its digest, and lets independent validators judge it."
)

DESCRIPTION = (
    "Pavvl is dispute resolution where the rules are frozen before the evidence exists. A "
    "claimant opens a case naming a respondent and a few precise criteria; the respondent "
    "accepts that version by its digest, so nothing can be reworded later. Either side may "
    "deposit a held sum that moves only on a final decision, and both file evidence the "
    "contract hashes itself.\n\n"
    "Independent GenLayer validators examine the stored evidence against the frozen criteria. "
    "Every validator that votes has examined every image itself: a node whose model cannot "
    "receive images refuses to assess rather than judge another's description. Deterministic "
    "code applies fixed floors that decide the outcome; a challenge posts a bond and a fresh "
    "round.\n\n"
    "It suits two parties who disagree about a fact: the standard is set first, evidence is "
    "immutable, and every digest recomputes from chain state. It runs on GenLayer Studionet "
    "only (chain 61999) as one dependency-free file, so no client can invent authority."
)

PROVE = (
    "Deployed on Studionet at 0x5F3fcc60…; its on-chain source SHA-256 equals this "
    "repository's, and `node scripts/deploy.mjs --verify` prints verified true. Live case "
    "PR-0002 is FINAL: the respondent accepted a frozen terms digest, the claimant filed a "
    "photograph and both sides a document, the validators examined that photograph themselves "
    "and agreed SUPPORTED with no floor, and the held sum moved to the claimant. "
    "PR-0001 is the same flow ending INSUFFICIENT, its held sum released to the respondent."
)

STEPS = [
    (
        "Open the deployed contract",
        "Go to the Studio Explorer address page for the contract and read its source and its "
        "finalized deployment transaction. The source on chain is byte-for-byte this "
        "repository's contracts/pavvl.py.",
    ),
    (
        "Check who holds authority",
        "Call get_governance. It reports an empty owner, admin and operator, pausable false, "
        "upgradeable false, has_admin_key false, has_upgrade_key false and deployer_has_power "
        "false, so the deployer cannot move anything.",
    ),
    (
        "Read a live case",
        "Call get_case PR-0002. It returns the terms digest the respondent accepted, the filed "
        "evidence with the SHA-256 the contract computed over the bytes it stored, and the "
        "standing decision id.",
    ),
    (
        "Read what the validators decided",
        "Call get_decision D-0002. It returns the finding per criterion, the floors that were "
        "applied, which evidence each validator examined (seen_ids), and the rationale the "
        "agreeing validators reproduced.",
    ),
    (
        "Settle and read the receipt",
        "The demo cases are already finalized: PR-0002's held sum moved to the claimant on a "
        "final SUPPORTED, PR-0001's to the respondent on INSUFFICIENT. get_receipt returns the "
        "receipt digest, which recomputes from chain state.",
    ),
]

EVIDENCE = (
    f"One git/GitHub repository: {REPO}\n"
    f"Deployer address: 0xeF18C89f28e4f1Aa2a7f180efcE01b423f7bDE0b ({EXPLORER})\n"
    f"Finalized deployment transaction: {DEPLOY_TX}\n"
    f"On-chain source SHA-256: {SOURCE_SHA}\n"
    "Reviewer guide: docs/REVIEW_TARGET.md - every property, with the exact command to check "
    "it.\n"
    "Live finalized cases: PR-0002 (SUPPORTED - photographed evidence examined by the "
    "validators, held sum paid to the claimant) and PR-0001 (INSUFFICIENT - held sum released "
    "to the respondent)."
)

APPEAL = (
    "Addressed the steward's finding: a node that cannot receive images no longer assesses a "
    "case by reading the leader's descriptions.\n\n"
    "_borrow() and every borrowed marker are gone. _assess() refuses to assess when a case has "
    "image evidence and the node fails the calibration image: as leader it errors and no "
    "decision is recorded; as validator the refusal is a dissent. A decision needs a majority "
    "that examined every image itself. Nor a soft warning: a node that cannot open one image "
    "cannot cite it (F5), so a finding resting on it is floored to INSUFFICIENT (F1), not "
    "SUPPORTED (F3).\n\n"
    f"Redeployed: 0xAcBdea1B… becomes 0x5F3fcc60… (source sha256 {SOURCE_SHA[:8]}…), "
    "FINALIZED / MAJORITY_AGREE; deploy.mjs --verify prints verified true.\n\n"
    "Proof: 79 tests pass, including tests/direct/test_validators.py - a sighted validator "
    "examines the image itself and agrees; a blind validator dissents without examining; a "
    "blind leader records no decision. adversarial_review.mjs fails the build if borrowing "
    "returns."
)

LIMITS = [
    ("one-liner", ONE_LINER, 180),
    ("description", DESCRIPTION, 1000),
    ("prove the path works", PROVE, 500),
    ("appeal reason", APPEAL, 1000),
]

ok = True
for name, text, cap in LIMITS:
    n = len(text)
    ok = ok and n <= cap
    print(f"{'OK  ' if n <= cap else 'OVER'} {name}: {n}/{cap}")
for action, instruction in STEPS:
    over = len(action) > 48
    ok = ok and not over
    print(f"{'OK  ' if not over else 'OVER'} step heading: {len(action)}/48  {action}")

out = []
out.append("# Resubmission copy — Pavvl\n")
out.append(
    "What to paste into the GenLayer Project Explorer form. Write it with "
    "`python probe/make_submission.py`; edit the strings there, not here.\n"
)
out.append("## 01 · Identity\n")
out.append(f"- **Project name:** {PROJECT_NAME}")
out.append(f"- **Primary tag:** {PRIMARY_TAG}")
out.append(f"- **Tag 1:** {TAG_1}")
out.append(f"- **Tag 2:** {TAG_2}")
out.append("- **Logo:** `probe/pavvl-logo.png` (512x512 PNG, 32 KB)\n")
out.append("## 02 · One-liner\n")
out.append(f"{ONE_LINER}\n")
out.append("## 03 · Description\n")
out.append(f"{DESCRIPTION}\n")
out.append('## 04 · How-to — "Write the exact path"\n')
for i, (action, instruction) in enumerate(STEPS, 1):
    out.append(f"{i}. **{action}** — {instruction}")
out.append("")
out.append("## 05 · Demo URL\n")
out.append("Optional. A YouTube or X post link, if you record one.\n")
out.append("## 06 · Review verification\n")
out.append(f"{PROVE}\n")
out.append("**Contract links**\n")
out.append(f"- {EXPLORER}")
out.append("")
out.append("## 07 · Project links\n")
out.append(f"- **Website:** {EXPLORER}")
out.append(f"- **GitHub:** {REPO}\n")
out.append("## 08 · Evidence & Supporting Information\n")
out.append(f"{EVIDENCE}\n")
out.append("## 09 · Appeal reason\n")
out.append(f"{APPEAL}\n")

path = pathlib.Path(__file__).resolve().parent.parent / "docs" / "RESUBMISSION.md"
path.write_text("\n".join(out), encoding="utf-8", newline="\n")
print()
print("ALL WITHIN LIMITS" if ok else "SOME OVER LIMIT")
print("written:", path)
