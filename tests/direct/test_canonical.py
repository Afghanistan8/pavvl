"""Canonical digests over non-ASCII payloads.

Every digest Pavvl publishes covers exactly

    json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

which is the form `contracts/pavvl.py` builds in `_canon`. Because the bytes are
pure ASCII and language-independent, any client can recompute a Pavvl digest
without agreeing on a JSON encoder first.

The ordinary tests exercise ASCII text. These drive the boundary that an
ASCII-only happy path never touches: accented Latin, CJK, and an astral emoji,
which `ensure_ascii` escapes as a UTF-16 surrogate pair. If the contract ever
switched to raw UTF-8 bytes, these tests fail while the ASCII ones still pass.
"""

import hashlib
import json

from .conftest import CLAIMANT, RESPONDENT, open_case


def canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_of(core: dict) -> str:
    return hashlib.sha256(canon(core).encode("ascii")).hexdigest()


NON_ASCII_TITLE = "Café — naïve façade 日本語テスト"
NON_ASCII_CLAIM = "The supplier delivered 100 widgets — no ifs, ands, or buts. 🚚📦"
NON_ASCII_CRITERIA = [
    {"text": "Los 100 widgets llegaron · acción completada ✓", "needs_independent": False},
    {"text": "数量が一致する (100 個)", "needs_independent": False},
]


def test_terms_digest_matches_python_ensure_ascii(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = open_case(h, c, title=NON_ASCII_TITLE, claim=NON_ASCII_CLAIM,
                    criteria=NON_ASCII_CRITERIA)["case_id"]

    t = h.view(c, "get_terms", cid, 1)
    assert t["title"] == NON_ASCII_TITLE  # stored verbatim
    core = {k: v for k, v in t.items() if k != "digest"}
    assert t["digest"] == digest_of(core)


def test_ascii_escaping_is_what_makes_the_digest(h, c):
    """The recomputation above only proves anything if the contract really
    hashes the escaped form: a raw UTF-8 canonicalization must disagree."""
    h.at("2026-10-01T09:00:00Z")
    cid = open_case(h, c, title=NON_ASCII_TITLE, claim=NON_ASCII_CLAIM,
                    criteria=NON_ASCII_CRITERIA)["case_id"]

    t = h.view(c, "get_terms", cid, 1)
    core = {k: v for k, v in t.items() if k != "digest"}
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() != t["digest"]


def test_astral_character_is_a_surrogate_pair(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = open_case(h, c, title="Emoji only 🚚", claim="Emoji in the claim 🚚")["case_id"]

    t = h.view(c, "get_terms", cid, 1)
    core = {k: v for k, v in t.items() if k != "digest"}
    text = canon(core)

    assert "\\ud83d\\ude9a" in text              # the truck, escaped
    assert all(ord(ch) < 128 for ch in text)     # nothing above ASCII survives
    assert hashlib.sha256(text.encode("ascii")).hexdigest() == t["digest"]


def test_receipt_digest_covers_non_ascii_terms(h, c):
    """Non-ASCII travels all the way into the receipt core an outside verifier
    hashes, so the two recomputations must agree on the same escaped bytes."""
    from .model import jpeg

    h.at("2026-10-01T09:00:00Z")
    cid = open_case(h, c, title=NON_ASCII_TITLE, claim=NON_ASCII_CLAIM,
                    criteria=NON_ASCII_CRITERIA,
                    allowed=["PHOTO"])["case_id"]
    h.call(c, "accept_case", cid, h.view(c, "get_terms", cid, 1)["digest"], by=RESPONDENT)

    m = {"kind": "PHOTO", "criteria": ["C1"]}
    p = h.call(c, "submit_image", cid, json.dumps(m), jpeg("na"), by=CLAIMANT)["evidence_id"]
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)

    from .model import look

    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "seen", "supports": [p], "against": [],
         "evidence_adequate": True, "finding": "SUPPORTED", "missing": []},
        {"id": "C2", "rationale": "seen", "supports": [p], "against": [],
         "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p]})
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "SUPPORTED"

    rcpt = h.view(c, "get_receipt", cid)
    assert rcpt["core"]["terms"]["title"] == NON_ASCII_TITLE
    assert rcpt["digest"] == digest_of(rcpt["core"])
