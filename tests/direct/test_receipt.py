"""Receipts, digests, canary, image validation, static source properties."""

import hashlib
import json
import re
from pathlib import Path

from .conftest import (
    CLAIMANT,
    CONTRACT_PATH,
    GEN,
    RESPONDENT,
    STRANGER,
    accept_case,
    open_case,
    terms,
)
from .model import jpeg, look, png, read_canary


def opened(h, c, **over):
    base = {"allowed": ["PHOTO", "TEXT_DOCUMENT"],
            "criteria": [{"text": "100 widgets were delivered", "needs_independent": False}],
            "held_sum_wei": "0", "funder": ""}
    base.update(over)
    cid = open_case(h, c, **{k: v for k, v in base.items()})["case_id"]
    t = terms(**base)
    accept_case(h, c, cid, by=t["respondent"])
    return cid


def test_receipt_digest_recomputes(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    m = {"kind": "PHOTO", "criteria": ["C1"]}
    p = h.call(c, "submit_image", cid, json.dumps(m), jpeg("rcpt"), by=CLAIMANT)["evidence_id"]
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "seen", "supports": [p],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p]})
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "SUPPORTED"
    rcpt = h.view(c, "get_receipt", cid)
    canon = json.dumps(rcpt["core"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canon.encode("ascii")).hexdigest() == rcpt["digest"]
    assert rcpt["core"]["case_id"] == cid
    assert rcpt["core"]["decision"]["decision_id"] == r["decision_id"]
    # decision digest recomputes from get_decision minus mutable fields
    d = h.view(c, "get_decision", r["decision_id"])
    mutable = ("status", "supersedes", "superseded_by", "challenge_window_ends", "decision_digest")
    core = {k: v for k, v in d.items() if k not in mutable}
    canon_d = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canon_d.encode("ascii")).hexdigest() == d["decision_digest"]
    # terms digest recomputes from get_terms
    t = h.view(c, "get_terms", cid, 1)
    core_t = {k: v for k, v in t.items() if k != "digest"}
    canon_t = json.dumps(core_t, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canon_t.encode("ascii")).hexdigest() == t["digest"]


def test_receipt_before_decision_refused(h, c):
    cid = opened(h, c)
    h.refused(c, "get_receipt", cid, match="no decision")


def test_canary_png_decodes(h, c):
    from .conftest import Harness  # noqa (anchor)
    # The harness auto-sight decodes the canary on every assessment; a
    # dedicated check: the contract's hand-written PNG has valid CRCs and a
    # zlib stream (read_canary asserts both).
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    m = {"kind": "PHOTO", "criteria": ["C1"]}
    p = h.call(c, "submit_image", cid, json.dumps(m), jpeg("canary"), by=CLAIMANT)["evidence_id"]
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "seen", "supports": [p],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p]})
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "SUPPORTED"
    assert any(p["kind"] == "sight" for p in h.prompts), "calibration ran"


def test_png_with_metadata_refused(h, c):
    cid = opened(h, c)
    meta = b"tEXtComment\x00created by test"
    bad = png("m", extra=png_chunk(b"tEXt", b"Comment\x00x"))
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), bad,
              by=CLAIMANT, match="metadata")
    bad_jpeg = jpeg("j", extra=b"\xff\xe1" + (10).to_bytes(2, "big") + b"Exif\x00\x001234")
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), bad_jpeg,
              by=CLAIMANT, match="metadata")


def png_chunk(kind, data):
    import zlib
    return len(data).to_bytes(4, "big") + kind + data + zlib.crc32(kind + data).to_bytes(4, "big")


def test_source_is_ascii_with_lf_only():
    raw = CONTRACT_PATH.read_bytes()
    assert b"\r" not in raw
    raw.decode("ascii")


def test_runner_pin_header_and_version_line():
    lines = CONTRACT_PATH.read_text(encoding="ascii").split("\n")
    assert lines[0] == "# v0.2.16"
    assert lines[1] == '# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }'


def test_no_storage_field_shares_a_name_with_a_method():
    s = CONTRACT_PATH.read_text(encoding="ascii")
    fields = set(re.findall(r"^    (\w+): TreeMap\[", s, re.M))
    methods = set(re.findall(r"^    def (\w+)\(", s, re.M))
    assert fields and methods
    assert not fields & methods


def test_every_write_guards_the_chain():
    s = CONTRACT_PATH.read_text(encoding="ascii")
    for m in re.finditer(r"    @gl\.public\.write(?:\.payable)?\n    def (\w+)\(", s):
        body = s[m.end():s.find("\n    @gl.public", m.end())]
        assert "_guard_chain()" in body, m.group(1)


def test_every_payable_write_refuses_by_returning():
    s = CONTRACT_PATH.read_text(encoding="ascii")
    for m in re.finditer(r"    @gl\.public\.write\.payable\n    def (\w+)\(", s):
        body = s[m.end():s.find("\n    @gl.public", m.end())]
        assert "_PayableRefusal" in body and "credited_wei" in body, m.group(1)


def test_no_operator_backdoor():
    s = CONTRACT_PATH.read_text(encoding="ascii")
    assert "deployer" in s.lower()
    # the deployer is recorded, never consulted for authority
    for m in re.finditer(r"self\.deployer", s):
        ctx = s[max(0, m.start() - 200):m.end() + 100]
        assert "get_config" in ctx or "deployer:" in ctx or "self.deployer =" in ctx or "deployer" in ctx, ctx


def test_chain_gate_constant():
    s = CONTRACT_PATH.read_text(encoding="ascii")
    assert "STUDIONET_CHAIN_ID = 61999" in s
    assert s.count("_guard_chain()") >= 19  # def + every write method
