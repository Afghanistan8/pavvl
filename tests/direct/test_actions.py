"""get_actions: on-chain action gates mirror the writes at every stage."""

import json

import pytest

from .conftest import (
    CLAIMANT,
    GEN,
    INSPECTOR,
    RESPONDENT,
    STRANGER,
    accept_case,
    open_case,
    terms,
)


def opened(h, c, **over):
    cid = open_case(h, c, **over)["case_id"]
    accept_case(h, c, cid, by=over.get("respondent", RESPONDENT))
    t = over
    if t.get("inspector"):
        d = h.view(c, "get_case", cid)
        h.call(c, "accept_inspector", cid, h.view(c, "get_terms", cid, 1)["digest"], by=t["inspector"])
    if int(terms(**over).get("held_sum_wei", "0")):
        t = terms(**over)
        funder = CLAIMANT if t["funder"] == "CLAIMANT" else t["respondent"]
        h.call(c, "fund_case", cid, by=funder, value=int(t["held_sum_wei"]))
    assert h.view(c, "get_case", cid)["state"] == "OPEN", h.view(c, "get_case", cid)
    return cid


def acts(h, c, cid, who):
    return h.view(c, "get_actions", cid, who)


def test_draft_gates(h, c):
    cid = open_case(h, c)["case_id"]
    a = acts(h, c, cid, RESPONDENT)
    assert a["role"] == "RESPONDENT"
    assert a["accept"]["ok"] is True
    assert a["fund"]["ok"] is False  # no held sum
    assert a["file"]["PHOTO"]["ok"] is False  # not open yet
    assert a["assess"]["ok"] is False
    assert a["finalize"]["ok"] is False
    s = acts(h, c, cid, STRANGER)
    assert s["role"] == ""
    assert s["accept"]["ok"] is False
    cl = acts(h, c, cid, CLAIMANT)
    assert cl["revise"]["ok"] is True
    assert cl["withdraw_case"]["ok"] is True


def test_open_gates(h, c):
    cid = opened(h, c)
    cl = acts(h, c, cid, CLAIMANT)
    assert cl["file"]["PHOTO"]["ok"] is True
    assert cl["file"]["TEXT_DOCUMENT"]["ok"] is True
    assert cl["ready"]["ok"] is True
    # assessment blocked until deadline or all ready
    assert cl["assess"]["ok"] is False
    assert "still running" in cl["assess"]["why"]
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    assert acts(h, c, cid, CLAIMANT)["assess"]["ok"] is True
    assert acts(h, c, cid, STRANGER)["assess"]["ok"] is False
    assert acts(h, c, cid, STRANGER)["file"]["PHOTO"]["ok"] is False


def test_fund_gates(h, c):
    cid = open_case(h, c, held_sum_wei=str(GEN // 10), funder="RESPONDENT")["case_id"]
    accept_case(h, c, cid)
    a = acts(h, c, cid, RESPONDENT)
    assert a["fund"]["ok"] is True
    assert acts(h, c, cid, CLAIMANT)["fund"]["ok"] is False
    h.call(c, "fund_case", cid, by=RESPONDENT, value=GEN // 10)
    assert acts(h, c, cid, RESPONDENT)["file"]["PHOTO"]["ok"] is True


def test_finalize_and_withdraw_gates(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    h.mock_judge({"criteria": [{"id": "C1", "rationale": "seen", "supports": [],
                                "against": [], "evidence_adequate": False,
                                "finding": "INSUFFICIENT", "missing": ["a photo"]}],
                  "limitations": [], "instructions_found": [], "seen_ids": []})
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "INSUFFICIENT"
    d = h.view(c, "get_decision", r["decision_id"])
    # challenge open for the respondent (decision went against claimant)
    assert acts(h, c, cid, CLAIMANT)["challenge"]["ok"] is True
    assert acts(h, c, cid, RESPONDENT)["challenge"]["ok"] is False
    assert acts(h, c, cid, CLAIMANT)["finalize"]["ok"] is False
    h.at(d["challenge_window_ends"])
    h.later(1)
    assert acts(h, c, cid, STRANGER)["finalize"]["ok"] is True
    h.call(c, "finalize", cid, by=STRANGER)
    # no held sum: nothing owed to anyone
    assert acts(h, c, cid, CLAIMANT)["withdraw"]["ok"] is False
    assert acts(h, c, cid, RESPONDENT)["withdraw"]["ok"] is False


def test_actions_refuse_off_chain(h, c):
    h.refused(c, "get_actions", "PR-9999", CLAIMANT, match="no case")
