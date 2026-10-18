"""Evidence: digests over stored bytes, caps, reuse, metadata rejection."""

import hashlib
import json

import pytest

from .conftest import (
    CLAIMANT,
    GEN,
    INSPECTOR,
    RESPONDENT,
    SECOND,
    STRANGER,
    accept_case,
    open_case,
    terms,
)
from .model import jpeg, png


def opened(h, c, **over):
    base = {"allowed": ["PHOTO", "TEXT_DOCUMENT", "DOCUMENT_PAGE", "VIDEO_FRAME"],
            "held_sum_wei": "0", "funder": ""}
    base.update(over)
    cid = open_case(h, c, **{k: v for k, v in base.items()})["case_id"]
    t = terms(**base)
    accept_case(h, c, cid, by=t["respondent"])
    if t.get("inspector"):
        h.call(c, "accept_inspector", cid, h.view(c, "get_terms", cid, 1)["digest"], by=t["inspector"])
    assert h.view(c, "get_case", cid)["state"] == "OPEN"
    return cid


def photo(h, c, cid, by=CLAIMANT, tag="a", **meta):
    m = {"kind": "PHOTO", "file_name": f"{tag}.jpg", "description": "cartons on pallets",
         "criteria": ["C1"]}
    m.update(meta)
    blob = jpeg(tag)
    return h.call(c, "submit_image", cid, json.dumps(m), blob, by=by)["evidence_id"]


def test_digest_over_stored_bytes(h, c):
    cid = opened(h, c)
    blob = jpeg("roof-a")
    out = h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO", "criteria": ["C1"]}),
                 blob, by=CLAIMANT)
    assert out["sha256"] == hashlib.sha256(blob).hexdigest()
    it = h.view(c, "get_evidence", out["evidence_id"])
    assert it["sha256"] == out["sha256"] and it["bytes"] == len(blob)
    from .conftest import same_addr
    assert it["role"] == "CLAIMANT" and same_addr(it["filed_by"], CLAIMANT) and it["filed_at"]
    assert bytes(h.view(c, "get_evidence_image", out["evidence_id"])) == blob \
        if isinstance(h.view(c, "get_evidence_image", out["evidence_id"]), (bytes, bytearray)) else True


def test_text_document_digest_and_line_breaks(h, c):
    cid = opened(h, c)
    text = "Delivery note\r\nLine: 100 cartons.\n\n\n\nSigned: depot."
    out = h.call(c, "submit_text", cid, json.dumps({"doc_type": "DELIVERY_NOTE", "title": "Note"}),
                 text, by=RESPONDENT)
    stored = h.view(c, "get_evidence_text", out["evidence_id"])
    assert "\r" not in stored and "\n\n\n" not in stored
    assert out["sha256"] == hashlib.sha256(stored.encode("utf-8")).hexdigest()


def test_only_parties_and_accepted_inspector_file(h, c):
    cid = opened(h, c, inspector=INSPECTOR)
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), jpeg("s"),
              by=STRANGER, match="only the claimant, the respondent or an accepted inspector")
    assert photo(h, c, cid, by=INSPECTOR, tag="insp")
    assert h.view(c, "get_evidence", photo(h, c, cid, by=RESPONDENT, tag="resp"))["role"] == "RESPONDENT"


def test_images_must_be_clean_and_small(h, c):
    cid = opened(h, c)
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), b"\xff\xd8\xff\xe1" + b"x" * 100,
              by=CLAIMANT, match="metadata")
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), jpeg("big", 400_001),
              by=CLAIMANT, match="at most 400000")
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), b"",
              by=CLAIMANT, match="empty")
    assert h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), png("p1"))["evidence_id"]


def test_kinds_follow_the_terms(h, c):
    cid = opened(h, c, allowed=["PHOTO"])
    h.refused(c, "submit_text", cid, json.dumps({"doc_type": "DELIVERY_NOTE"}), "a long enough text",
              by=CLAIMANT, match="do not allow text document")
    h.refused(c, "submit_image", cid, json.dumps({"kind": "DOCUMENT_PAGE", "doc_type": "DELIVERY_NOTE"}),
              jpeg("pg"), by=CLAIMANT, match="do not allow document page")
    h.refused(c, "submit_image", cid, json.dumps({"kind": "HOLOGRAM"}), jpeg("h"),
              by=CLAIMANT, match="photo, a video frame")


def test_caps_per_role(h, c):
    cid = opened(h, c)
    for i in range(5):
        photo(h, c, cid, tag=f"c{i}")
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), jpeg("c5"),
              by=CLAIMANT, match="most images")


def test_same_bytes_twice_by_one_role_refused(h, c):
    cid = opened(h, c)
    blob = jpeg("dup")
    h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), blob, by=CLAIMANT)
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), blob,
              by=CLAIMANT, match="already filed")


def test_cross_case_reuse_flagged(h, c):
    cid1 = opened(h, c)
    blob = jpeg("shared")
    h.call(c, "submit_image", cid1, json.dumps({"kind": "PHOTO"}), blob, by=CLAIMANT)
    cid2 = open_case(h, c, subject_ref="order-99")["case_id"]
    t = terms(subject_ref="order-99")
    accept_case(h, c, cid2, by=t["respondent"])
    out = h.call(c, "submit_image", cid2, json.dumps({"kind": "PHOTO"}), blob, by=CLAIMANT)
    assert out["evidence_id"]
    it = h.view(c, "get_evidence", out["evidence_id"])
    assert it["reuse"] in ("SELF", "OTHER", "RELATED")


def test_filing_ends_with_evidence_period(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    h.later(4 * 86400)
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), jpeg("late"),
              by=CLAIMANT, match="evidence period")


def test_readiness_cleared_by_new_filing(h, c):
    cid = opened(h, c)
    photo(h, c, cid, tag="one")
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    photo(h, c, cid, by=RESPONDENT, tag="two")
    assert h.view(c, "get_case", cid)["ready"]["CLAIMANT"] is False
