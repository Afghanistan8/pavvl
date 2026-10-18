# Pavvl architecture

Pavvl is one dependency-free Python contract. It is the system of record: it
stores evidence bytes, computes digests, runs the assessment under GenLayer
consensus, applies the floors, and settles any held sum. Any client is a view and
a signer — it can build a transaction but it can never invent authority the
contract would refuse, because the contract publishes its own authority through
`get_actions` and enforces every rule itself.

- Contract: [`contracts/pavvl.py`](../contracts/pavvl.py)
- Tests: [`tests/direct/`](../tests/direct) — Direct Mode, the real v0.2.16 SDK
- Deploy driver: [`scripts/deploy.mjs`](../scripts/deploy.mjs)

---

## 1. Case lifecycle

```
         open_case            accept_case            fund_case
   ───────────────────▶ DRAFT ───────────▶ DRAFT ──────────────▶  (held sum)
   (claim + criteria)     │  (respondent accepts by digest)        │
                          │                                        ▼
        revise_terms ◀────┘                                     OPEN
        (claimant only,                                       │    │
         before accept)                                       │    │ submit_image / submit_text
                                                              │    │ mark_ready
                                                              ▼    ▼
                                                    request_assessment
                                                              │
                              ┌───────────────────────────────┴──────────────┐
                              ▼                                              ▼
        missing required / nothing filed                      validators assess
              (decided in code)                              (consensus panel)
                              └───────────────┬──────────────────────────────┘
                                              ▼
                                          DETERMINED  ──────────────▶  finalize
                                          (standing                  (after the
                                           decision)                  challenge window)
                                              │
                                    challenge │ (the side it went against)
                                              ▼
                                     UNDER_CHALLENGE ──▶ readjudicate ──▶ close_challenge
                                              │
                                     (or withdraw/cancel paths)
```

Terminal states: `FINAL`, `DECLINED`, `WITHDRAWN`, `EXPIRED`, `LAPSED`.

### Write surface

| Method | Who | What it does |
|---|---|---|
| `open_case(terms_json)` | anyone (becomes claimant) | drafts a case with frozen criteria |
| `revise_terms(cid, terms_json)` | claimant, pre-acceptance | new terms version (≤ `MAX_VERSIONS`) |
| `accept_case(cid, terms_digest)` | named respondent | accepts an exact version by digest |
| `decline_case(cid, reason)` | named respondent | declines a draft |
| `withdraw_case(cid)` | claimant, pre-open | withdraws a draft |
| `accept_inspector(cid, terms_digest)` | named inspector | accepts the inspector role |
| `fund_case(cid)` | named funder | deposits the held sum (payable) |
| `expire_case(cid)` | anyone | closes an expired draft |
| `submit_image(cid, meta_json, data)` | party / accepted inspector | files image bytes (contract hashes them) |
| `submit_text(cid, meta_json, text)` | party / accepted inspector | files a text document |
| `mark_ready(cid)` | party / accepted inspector | declares your evidence complete |
| `lapse_case(cid)` | anyone | closes an open case nobody advanced |
| `request_assessment(cid)` | party | asks validators to assess |
| `challenge(cid, reason)` | side it went against | opens a challenge (payable bond) |
| `readjudicate(cid)` | anyone | re-runs the panel on new evidence |
| `close_challenge(cid)` | anyone | closes the challenge, settles the bond |
| `finalize(cid)` | anyone | settles the held sum after the window |
| `withdraw()` | any credit holder | pulls owed credit (no stranded value) |

### Read surface

`get_config`, `get_stats`, `get_governance`, `get_case`, `get_actions`,
`get_terms`, `list_cases`, `cases_of`, `get_evidence`, `get_evidence_text`,
`get_evidence_image`, `get_case_evidence`, `get_decision`, `get_events`,
`get_credit`, `get_receipt`.

---

## 2. Frozen terms

`open_case` parses and bounds a `terms_json` document (`_terms`). The respondent
accepts `terms_digest`, a SHA-256 over the canonical JSON of the accepted version.
Once accepted, the terms cannot change; `revise_terms` is refused after
acceptance. This is the anti-goalpost-moving guarantee: every later step — filing,
assessment, settlement — reads the *accepted* version (`_accepted_terms`), never
the latest.

Terms carry: `title`, `subject_kind` (one of `SUBJECT_KINDS`), `subject_ref`,
`time_zone`, `claim`, `criteria[]` (≤ `MAX_CRITERIA`, each optionally
`needs_independent`), `allowed` evidence kinds, `respondent`, an optional
`inspector`, an optional `held_sum_wei` with a `funder`, a `challenge_bond_wei`,
the evidence window, and the challenge window.

---

## 3. Evidence

Evidence is stored, not referenced. `submit_image` takes raw bytes and a metadata
JSON; the contract computes the SHA-256 itself, validates the image (PNG/JPEG
magic, side bounds, byte cap), and stores `evidence_bytes` keyed by evidence id.
`submit_text` stores bounded text. Filers do not supply a digest — the contract
derives it, so a filer cannot lie about what they filed.

Per-role caps apply (`CAPS`, and `CHALLENGE_CAPS` during a challenge). Identical
bytes filed by different roles are linked as `twins`: the same bytes are "seen
together" during assessment, so which copy a model cites does not decide whose
evidence it is.

---

## 4. Assessment under consensus

`request_assessment` (and `readjudicate`) call `_run_assessment`:

1. **Code first.** If required evidence is missing, or nothing was filed at all,
   no validator is asked. The result is `INSUFFICIENT` with floor
   `REQUIRED_MISSING` / `NOTHING_FILED`, recorded as a `CODE` decision. Missing
   evidence is never proof of anything.
2. **The panel.** Otherwise `_panel` runs `gl.vm.run_nondet(leader, validator)`.
   The leader examines each image (a sighted calibration step first), then judges
   each criterion. Every validator re-runs the *same* assessment itself.

### What consensus binds

`_dissent` decides whether a validator can stand behind the leader's result. It
compares only `_bound(settled, ids)` — for every criterion, whether it is
`SUPPORTED`, and whether the overall finding is `NOT_ASSESSED` (nothing assessable).
Wording, cited ids, and the finer labels (`NOT_ESTABLISHED`, `CONFLICTING`,
`INSUFFICIENT`) are **not** compared: they turn on which items a model cites, and
honest models differ. They are recorded as the leader's reading, and the decision
record says so in `bound`.

A validator also refuses the leader's result if:
- the leader's result does not judge every criterion (`_judged`), or is malformed;
- the leader claims to have seen images that are not on the case;
- the leader fails to count images this node saw (copies count together);
- the leader's flag list on evidence that tried to instruct the assessor
  (`instructions_found`) changes what the record binds.

### The floors (F0–F8)

After shaping, `_settle_criterion` applies fixed, deterministic floors to each
criterion. A floor can only move a finding *toward* `INSUFFICIENT` /
`CONFLICTING`, never toward `SUPPORTED`.

| Floor | Trigger | Effect |
|---|---|---|
| `F0` | label outside the vocabulary | → `INSUFFICIENT` |
| `F5` | cites an item this node did not see or read | dropped from the citation |
| `F6`/`F7` | cites an item that tried to instruct the assessor, or bytes reused across cases with a different counter-party | dropped for the side it would favour |
| `F4` | conclusive finding with `evidence_adequate != true` | → `INSUFFICIENT` |
| `F1` | conclusive finding with an empty basis | → `INSUFFICIENT` |
| `F8` | `CONFLICTING` with only one side present | → `INSUFFICIENT` |
| `F2` | criterion `needs_independent` and no inspector item in the basis | → `INSUFFICIENT` |
| `F3` | the favoured side's own evidence alone, with opposing evidence present | → `CONFLICTING` |

`NONE_SEEN` is recorded when nothing was visible to the node at all (`NOT_ASSESSED`).

### Overall finding

`_overall`: any `NOT_ASSESSED` ⇒ `NOT_ASSESSED`; all `SUPPORTED` ⇒ `SUPPORTED`;
else any `NOT_ESTABLISHED` ⇒ `NOT_ESTABLISHED`; else any `CONFLICTING` ⇒
`CONFLICTING`; else `INSUFFICIENT`.

---

## 5. Decisions and receipts

Each decision (`_record`) is immutable except for `status`, `supersedes`,
`superseded_by`, `challenge_window_ends`, and `decision_digest`. It carries:

- `manifest_digest` — over the frozen evidence snapshot (id, kind, role, sha256,
  filed_at, declared capture, reuse flags);
- per-criterion `finding`, `model_finding`, `floors`, `basis`, `contrary`,
  `missing`, `rationale`;
- `seen_ids` / `unseen_ids` (which images were examined — this drives the retry
  right);
- `observations`, `limitations`, `instructions_found`;
- `bound` — a plain-language statement of exactly what consensus bound;
- `decision_digest` — over the whole record, mirrored by the app's verifier.

`get_receipt(cid)` bundles the accepted terms, the evidence manifest, the
standing decision, and the settlement state into one recomputable object
(`pavvl.receipt/1`). The canonical JSON + SHA-256 reconstruction lives in the
contract's `_canon`: `json.dumps(core, sort_keys=True, separators=(",", ":"),
ensure_ascii=True)`, hashed with SHA-256. Because the bytes are pure ASCII and
key-sorted, a client in any language can rebuild the same digest;
`tests/direct/test_canonical.py` pins that over accented Latin, CJK, and an
astral emoji, and `tests/direct/test_receipt.py` recomputes the terms, decision,
and receipt digests end to end.

---

## 6. Challenge and settlement

- **Challenge.** Only the side the decision went against may `challenge`, within
  the challenge window, by posting the challenge bond. The challenger then files
  new evidence; the other side may answer; then anyone may `readjudicate` (≤
  `MAX_READJUDICATIONS`).
- **Bond.** `_settle_bond` returns the bond to the challenger if the readjudication
  reverses which side the decision favours, or if no readjudication was recorded in
  time; otherwise the bond goes to the other side.
- **Finalize.** `finalize` moves the held sum to the claimant **only** if the
  standing decision's overall finding is `SUPPORTED`. Any other outcome releases
  the held sum back to the funder. Settlement fails closed.
- **Credits.** All value movement is pull-based through `withdraw()`; the contract
  tracks `owed`/`paid` per address, so nothing is stranded.

---

## 7. No governance

`get_governance()` returns empty owner/admin/operator, `pausable: false`,
`upgradeable: false`, `has_admin_key: false`, `has_upgrade_key: false`,
`deployer_has_power: false`. The deployer is recorded for provenance and consulted
by nothing. The only global gate is `_guard_chain`, and it only pins the network to
Studionet. Every write authorises purely from the roles named in the frozen terms.

---

## 8. Client integration

There is no app in this repository: an intelligent contract is the unit of
submission, and the contract is complete without one. A client is expected to be
thin, because the contract already answers what a wallet may do.

- **Authority comes from the contract.** `get_actions(cid, who)` returns a JSON
  object: `role` plus one gate per write (`revise`, `accept`, `decline`,
  `withdraw_case`, `accept_inspector`, `fund`, `expire`, `file`, `ready`,
  `assess`, `lapse`, `challenge`, `readjudicate`, `close_challenge`, `finalize`,
  `withdraw`), each a `{ok, why}` pair computed on chain from the same state the
  writes check, in the same order. A client renders buttons from these rows: it
  cannot offer an act the contract would refuse, and it cannot hide a path the
  contract allows. `open_case` is the one ungated write, and it is gated by design
  (a wallet may hold at most `MAX_OPEN_PER_CLAIMANT` unfinished cases).

- **Every write has a gate, and every gate has a write.**
  `tools/adversarial_review.mjs` re-derives that mapping from the source and fails
  if the two drift, so no callable path can go missing from what the contract
  publishes.

- **Reads are canonical JSON strings.** Every view returns `json.dumps(...,
  sort_keys=True)`, so field order is stable. `get_receipt` returns
  `{core, digest}`; a client hashes `core` with `_canon` to check it.

- **Money is exact.** `held_sum_wei`, `challenge_bond_wei`, and the `owed`/`paid`
  credit rows are decimal atto-GEN strings. Clients must use integer arithmetic
  (BigInt, Python int) and never floating point.

- **Chain 61999 only.** A client should refuse to sign on any other chain before
  building a transaction; the contract refuses regardless (`_guard_chain`).
