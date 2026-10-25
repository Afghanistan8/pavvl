"""Character-check the GenLayer Project Explorer resubmission copy for Pavvl.

The portal enforces hard character limits on several fields, so the copy is
written here, measured here, and written out to docs/RESUBMISSION.md. Edit the
strings below and re-run:

    python probe/make_submission.py
"""

import pathlib

CONTRACT = "0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7"
EXPLORER = f"https://explorer-studio.genlayer.com/address/{CONTRACT}"
REPO = "https://github.com/Afghanistan8/pavvl"
DEPLOY_TX = "0xa523c2420f99a97ef7221e6038125d26a7f4b5ec8d2a058f4c6f439e54f90c80"
SOURCE_SHA = "8f449634455ae64371162237596024d9c78827c49b0af0a2364b01b0114379fd"
REJECTED_ADDR = "0x5F3fcc6094Fe68D2Db1D0F83e012Ad61E2Ffd234"
REJECTED_SHA = "730bc0c35cc6ae786e69bc5939895e757dfaa74b0b165cbac3f52d05ffe2e0b1"

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
    "Deployed on Studionet at 0x6173BD4F…; its on-chain source SHA-256 equals this "
    "repository's, and `node scripts/deploy.mjs --verify` prints verified true. Live case "
    "PR-0001 is FINAL: the respondent accepted a frozen terms digest, the claimant filed a "
    "photograph and both sides a document, the validators examined that photograph themselves "
    "and agreed SUPPORTED with no floor, and the held sum moved to the claimant."
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
        "Call get_case PR-0001. It returns the terms digest the respondent accepted, the filed "
        "evidence with the SHA-256 the contract computed over the bytes it stored, and the "
        "standing decision id.",
    ),
    (
        "Read what the validators decided",
        "Call get_decision D-0001. It returns the finding per criterion, the floors that were "
        "applied, which evidence each validator examined (seen_ids), and the rationale the "
        "agreeing validators reproduced.",
    ),
    (
        "Settle and read the receipt",
        "The demo case is already finalized: PR-0001's held sum moved to the claimant on a "
        "final SUPPORTED. get_receipt returns the "
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
    "Live finalized case: PR-0001 (SUPPORTED - photographed evidence examined by the "
    "validators, held sum paid to the claimant)."
    ""
)

APPEAL = (
    "Addressed the steward's second finding: the validators did not bind which images were seen. "
    "_dissent compared the leader's claimed seen_ids against a validator's own set in one direction "
    "only, so a leader could claim an image no validator saw, have it recorded as seen, and take "
    "the retry right away from the side the decision went against.\n\n"
    "The counted seen set - a node's own images plus any copy of the same bytes - is now compared in "
    "both directions, and a validator dissents on any difference: it will not stand behind a result "
    "resting on less than it saw, nor certify one resting on an image it never saw. The panel "
    "succeeds only when every validator reproduced that set.\n\n"
    f"Redeployed: 0x5F3fcc60… becomes 0x6173BD4F… (sha256 {SOURCE_SHA[:8]}…), FINALIZED / "
    "MAJORITY_AGREE; deploy.mjs --verify prints verified true.\n\n"
    "Proof: 85 tests pass, including tests/direct/test_seen_binding.py - a validator dissents when "
    "the leader counts an image it did not see, and when the leader omits one it did see."
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
