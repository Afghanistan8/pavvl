"""Ledger invariants: balance books, conservation, no self-certification."""

import json

import pytest

from .conftest import (
    CLAIMANT,
    GEN,
    RESPONDENT,
    STRANGER,
    accept_case,
    open_case,
    terms,
)
from .model import jpeg, look


def opened(h, c, **over):
    base = {"allowed": ["PHOTO", "TEXT_DOCUMENT"],
            "criteria": [{"text": "100 widgets were delivered", "needs_independent": False}],
            "held_sum_wei": str(GEN // 10), "funder": "RESPONDENT"}
    base.update(over)
    t = terms(**base)
    cid = open_case(h, c, **{k: v for k, v in base.items()})["case_id"]
    accept_case(h, c, cid, by=t["respondent"])
    if int(t.get("held_sum_wei", "0")):
        funder = CLAIMANT if t["funder"] == "CLAIMANT" else t["respondent"]
        h.call(c, "fund_case", cid, by=funder, value=int(t["held_sum_wei"]))
    assert h.view(c, "get_case", cid)["state"] == "OPEN", h.view(c, "get_case", cid)
    return cid


def books(h, c):
    st = h.view(c, "get_stats")
    return int(st["held_wei"]) + int(st["bonds_wei"]) + int(st["owed_wei"])


def test_balance_books_equality(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    assert books(h, c) == h.network_balance == GEN // 10
    m = {"kind": "PHOTO", "criteria": ["C1"]}
    h.call(c, "submit_image", cid, json.dumps(m), jpeg("a"), by=CLAIMANT)
    assert books(h, c) == h.network_balance
    # challenge posts bond
    p = h.view(c, "get_case_evidence", cid)[0]["evidence_id"]
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    h.later(4 * 86400)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "r", "supports": [p],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p]})
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "SUPPORTED"
    h.call(c, "challenge", cid, "the photo shows another depot", by=RESPONDENT, value=GEN // 100)
    assert books(h, c) == h.network_balance == GEN // 10 + GEN // 100


def test_failed_transfer_never_strands_value(h, c):
    # payable refusal returns value as credit, never raises it away
    cid = open_case(h, c)["case_id"]
    out = h.call(c, "fund_case", cid, by=STRANGER, value=GEN // 10)
    assert out["refused"] is True
    assert h.view(c, "get_credit", STRANGER)["owed"] == str(GEN // 10)
    out = h.call(c, "withdraw", by=STRANGER)
    assert out["wei"] == str(GEN // 10)
    assert h.transfers[-1]["to"].lower() == STRANGER.lower()
    assert books(h, c) == h.network_balance == 0


def test_no_self_certification_paths(h, c):
    """No single party — claimant, respondent, stranger — can force a
    SUPPORTED final finding alone. Every path to FINAL runs through the
    validator panel or explicit code floors."""
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c, held_sum_wei="0", funder="")
    # readiness can only be marked while the case is OPEN (funded first —
    # here there is no held sum so it opens on acceptance)
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "INSUFFICIENT"  # code floor, not a finding
    # respondent cannot finalize someone else's late window early
    h.refused(c, "finalize", cid, by=RESPONDENT, match="still be challenged")
    # stranger cannot challenge, readjudicate, or close
    h.refused(c, "readjudicate", cid, by=STRANGER, match="under challenge")
    h.refused(c, "close_challenge", cid, by=STRANGER, match="under challenge")


def test_lapse_returns_deposit_and_closes(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    h.later(4 * 86400 + 3 * 86400 + 1)
    out = h.call(c, "lapse_case", cid, by=STRANGER)
    assert out["state"] == "LAPSED"
    # deposit returns to the funder (respondent)
    assert h.view(c, "get_credit", RESPONDENT)["owed"] == str(GEN // 10)
    assert books(h, c) == h.network_balance == GEN // 10


def test_stats_counters_are_consistent(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    st = h.view(c, "get_stats")
    assert st["case"] == "1" and st["evidence"] == "0"
    m = {"kind": "PHOTO", "criteria": ["C1"]}
    h.call(c, "submit_image", cid, json.dumps(m), jpeg("a"), by=CLAIMANT)
    st = h.view(c, "get_stats")
    assert st["evidence"] == "1"
