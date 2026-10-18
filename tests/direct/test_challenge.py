"""Challenge, readjudication, bond settlement, finality with value."""

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
    same_addr,
    terms,
)
from .model import jpeg, look

BOND = GEN // 100  # default challenge bond (contract default 86400s windows)
CHEV = 86400  # default challenge_evidence_seconds


def opened(h, c, **over):
    base = {"allowed": ["PHOTO", "TEXT_DOCUMENT"],
            "criteria": [{"text": "100 widgets were delivered", "needs_independent": False}],
            "held_sum_wei": str(GEN // 10), "funder": "RESPONDENT"}
    base.update(over)
    cid = open_case(h, c, **{k: v for k, v in base.items()})["case_id"]
    t = terms(**base)
    accept_case(h, c, cid, by=t["respondent"])
    h.call(c, "fund_case", cid, by=t["respondent"], value=int(t["held_sum_wei"]))
    assert h.view(c, "get_case", cid)["state"] == "OPEN"
    return cid


def photo(h, c, cid, by=CLAIMANT, tag="a"):
    m = {"kind": "PHOTO", "criteria": ["C1"]}
    return h.call(c, "submit_image", cid, json.dumps(m), jpeg(tag), by=by)["evidence_id"]


def judged(h, c, cid, by, finding, supports=(), against=(), seen=()):
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "r", "supports": list(supports),
         "against": list(against), "evidence_adequate": True, "finding": finding, "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": list(seen)})
    return h.call(c, "request_assessment", cid, by=by)


def ready_all(h, c, cid):
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)


def test_challenge_needs_new_evidence_and_bond(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="delivery")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    r = judged(h, c, cid, CLAIMANT, "SUPPORTED", supports=[p1], seen=[p1])
    d = h.view(c, "get_decision", r["decision_id"])
    # wrong side cannot challenge: refusal returned, value credited back
    out = h.call(c, "challenge", cid, "i disagree", by=CLAIMANT, value=BOND)
    assert out["refused"] is True and "respondent" in out["reason"]
    # wrong bond refused and credited back (BOND-1 sits in the ledger)
    out = h.call(c, "challenge", cid, "the photo shows another depot", by=RESPONDENT,
                 value=BOND - 1)
    assert out["refused"] is True
    assert h.view(c, "get_credit", RESPONDENT)["owed"] == str(BOND - 1)
    ch = h.call(c, "challenge", cid, "the photo shows another depot", by=RESPONDENT,
                value=BOND)
    assert h.view(c, "get_case", cid)["state"] == "UNDER_CHALLENGE"
    assert h.view(c, "get_stats")["bonds_wei"] == str(BOND)
    # readjudication without new evidence refused (evidence window open)
    h.refused(c, "readjudicate", cid, by=STRANGER, match="may file new evidence until")
    h.refused(c, "close_challenge", cid, by=STRANGER, match="evidence period runs")
    h.later(CHEV // 2)
    # challenger files new evidence inside the evidence window
    p2 = photo(h, c, cid, by=RESPONDENT, tag="rebuttal")
    # readjudicate refused: evidence window still open, then reply window
    h.refused(c, "readjudicate", cid, by=STRANGER, match="may file new evidence until")
    h.later(CHEV // 2 + 1)
    h.refused(c, "readjudicate", cid, by=STRANGER, match="may answer")
    # close refused while readjudication is available
    h.refused(c, "close_challenge", cid, by=STRANGER, match="anyone can run the readjudication")
    h.later(CHEV)
    # other side answers, then readjudication reverses to NOT_ESTABLISHED
    h.mock_look(look())
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "rebuttal outweighs", "supports": [p1],
         "against": [p2], "evidence_adequate": True, "finding": "NOT_ESTABLISHED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p1, p2]})
    r2 = h.call(c, "readjudicate", cid, by=STRANGER)
    assert r2["changed"] is True and r2["reversed"] is True
    case = h.view(c, "get_case", cid)
    assert case["state"] == "DETERMINED"
    assert case["challenge"]["bond_to"] == "CHALLENGER"
    # bond back to challenger: withdraw works
    assert h.view(c, "get_actions", cid, RESPONDENT)["withdraw"]["ok"] is True
    before = len(h.transfers)
    out = h.call(c, "withdraw", by=RESPONDENT)
    assert out["wei"] == str(BOND + (BOND - 1)), "bond + the earlier wrong-bond credit"
    assert len(h.transfers) == before + 1
    assert h.transfers[-1]["to"].lower() == RESPONDENT.lower()
    # finalize: held sum goes to respondent (claim not established)
    h.at(h.view(c, "get_decision", case["standing"])["challenge_window_ends"])
    h.later(1)
    h.call(c, "finalize", cid, by=STRANGER)
    out = h.call(c, "withdraw", by=RESPONDENT)
    assert out["wei"] == str(GEN // 10), "held sum + nothing else (bond already withdrawn)"
    assert h.view(c, "get_stats")["held_wei"] == "0"


def test_failed_challenge_bond_goes_to_opponent(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="delivery")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    judged(h, c, cid, CLAIMANT, "SUPPORTED", supports=[p1], seen=[p1])
    h.call(c, "challenge", cid, "the photo shows another depot", by=RESPONDENT,
           value=BOND)
    h.later(CHEV // 2)
    photo(h, c, cid, by=RESPONDENT, tag="rebuttal-weak")
    h.later(CHEV // 2 + CHEV)
    h.mock_look(look())
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "still supported", "supports": [p1],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p1]})
    # readjudication keeps SUPPORTED: challenge fails, bond to claimant
    r = h.call(c, "readjudicate", cid, by=STRANGER)
    assert r["reversed"] is False
    assert h.view(c, "get_case", cid)["challenge"]["bond_to"] == "CLAIMANT"
    h.at(h.view(c, "get_decision", h.view(c, "get_case", cid)["standing"])["challenge_window_ends"])
    h.later(1)
    h.call(c, "finalize", cid, by=STRANGER)
    out = h.call(c, "withdraw", by=CLAIMANT)
    assert out["wei"] == str(GEN // 10 + BOND)


def test_close_without_new_evidence_returns_bond(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="delivery")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    judged(h, c, cid, CLAIMANT, "SUPPORTED", supports=[p1], seen=[p1])
    h.call(c, "challenge", cid, "the photo shows another depot", by=RESPONDENT,
           value=BOND)
    h.later(CHEV + 1)
    cl = h.call(c, "close_challenge", cid, by=STRANGER)
    assert cl["outcome"] and "no new evidence" in cl["outcome"]
    assert h.view(c, "get_case", cid)["challenge"]["bond_to"] == "CLAIMANT"


def test_single_challenge_only(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="delivery")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    judged(h, c, cid, CLAIMANT, "SUPPORTED", supports=[p1], seen=[p1])
    h.call(c, "challenge", cid, "the photo shows another depot", by=RESPONDENT,
           value=BOND)
    out = h.call(c, "challenge", cid, "again", by=RESPONDENT, value=BOND)
    assert out["refused"] is True and "UNDER_CHALLENGE" in out["reason"].upper() or "standing decision" in out["reason"] or "challenged" in out["reason"]


def test_double_finalize_and_double_withdraw_refused(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="delivery")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    judged(h, c, cid, RESPONDENT, "NOT_ESTABLISHED", against=[p1], seen=[p1])
    h.at(h.view(c, "get_decision", h.view(c, "get_case", cid)["standing"])["challenge_window_ends"])
    h.later(1)
    h.call(c, "finalize", cid, by=STRANGER)
    h.refused(c, "finalize", cid, by=STRANGER, match="standing decision")
    out = h.call(c, "withdraw", by=RESPONDENT)
    assert out["wei"] == str(GEN // 10)
    h.refused(c, "withdraw", by=RESPONDENT, match="nothing is owed")
