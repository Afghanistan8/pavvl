"""Smoke: config, open/accept/fund lifecycle, chain gate, evidence validation."""

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


def test_config_rules_chain_subjects(h, c):
    cfg = h.view(c, "get_config")
    assert cfg["rules"] == "pavvl-rules-1"
    assert cfg["chain_id"] == 61999
    assert cfg["receipt_schema"] == "pavvl.receipt/1"
    for k in ("WORK_COMPLETED", "CONDITION_AT_TIME", "DELIVERY_MADE",
              "PAYMENT_MADE", "AGREEMENT_FOLLOWED", "OTHER"):
        assert k in cfg["subject_kinds"]
    assert cfg["limits"]["subject_ref"] == 80


def test_open_accept_flow(h, c):
    r = open_case(h, c)
    assert r["case_id"] == "PR-0001"
    assert r["version"] == 1
    assert len(r["digest"]) == 64
    case = h.view(c, "get_case", "PR-0001")
    assert case["state"] == "DRAFT"
    t = h.view(c, "get_terms", "PR-0001", 1)
    assert t["digest"] == r["digest"]
    # wrong digest refused
    h.refused(c, "accept_case", "PR-0001", "0" * 64, by=RESPONDENT, match="digest")
    # claimant cannot accept their own terms
    h.refused(c, "accept_case", "PR-0001", r["digest"], by=CLAIMANT, match="respondent")
    a = accept_case(h, c, "PR-0001")
    assert a["state"] == "OPEN"
    case = h.view(c, "get_case", "PR-0001")
    assert case["accepted_digest"] == r["digest"]
    assert case["evidence_deadline"] > case["opened_at"]


def test_case_id_sequence_and_index(h, c):
    open_case(h, c)
    open_case(h, c, subject_ref="order-43")
    assert h.view(c, "get_case", "PR-0002")["case_id"] == "PR-0002"
    lst = h.view(c, "list_cases", 0, 50)
    assert lst["total"] == 2
    assert len(lst["cases"]) == 2
    mine = h.view(c, "cases_of", CLAIMANT, 0, 50)
    assert mine["total"] == 2


def test_chain_gate_refuses_other_networks(h, c):
    h.vm._chain_id = 1
    try:
        h.refused(c, "open_case", json.dumps(terms()), by=CLAIMANT, match="Studionet")
    finally:
        h.vm._chain_id = 61999
    # views still work off-chain
    assert h.view(c, "get_stats")["case"] == "0"


def test_subject_kinds_validated(h, c):
    h.refused(c, "open_case", json.dumps(terms(subject_kind="REPAIR_COMPLETED")),
              by=CLAIMANT, match="subject kind")
    h.refused(c, "open_case", json.dumps(terms(subject_kind="OTHER", claim="x" * 9)),
              by=CLAIMANT, match="at least 10 characters")


def test_subject_ref_nickname_rules(h, c):
    h.refused(c, "open_case", json.dumps(terms(subject_ref="x@y.com")),
              by=CLAIMANT, match="nickname")
    h.refused(c, "open_case", json.dumps(terms(subject_ref="see http://e.com")),
              by=CLAIMANT, match="nickname")


def test_revise_terms_then_accept(h, c):
    r = open_case(h, c)
    r2 = h.call(c, "revise_terms", "PR-0001", json.dumps(terms(title="Delivery of 101 widgets")), by=CLAIMANT)
    assert r2["version"] == 2
    assert r2["digest"] != r["digest"]
    a = accept_case(h, c, "PR-0001", version=2)
    assert a["state"] == "OPEN"


def test_decline_and_withdraw(h, c):
    open_case(h, c)
    d = h.call(c, "decline_case", "PR-0001", "the claim is denied in full", by=RESPONDENT)
    assert d["state"] == "DECLINED"
    open_case(h, c, subject_ref="order-44")
    w = h.call(c, "withdraw_case", "PR-0002", by=CLAIMANT)
    assert w["state"] == "WITHDRAWN"
    h.refused(c, "withdraw_case", "PR-0002", by=CLAIMANT, match="before it opens")


def test_expire_draft(h, c):
    h.at("2026-10-01T09:00:00Z")
    open_case(h, c)
    h.later(8 * 86400)
    e = h.call(c, "expire_case", "PR-0001", by=STRANGER)
    assert e["state"] == "EXPIRED"


def test_inspector_flow(h, c):
    r = open_case(h, c, inspector=INSPECTOR,
                  criteria=[{"text": "100 widgets were delivered", "needs_independent": True}])
    a = accept_case(h, c, "PR-0001")
    assert a["state"] == "DRAFT", "case waits for the inspector"
    h.call(c, "accept_inspector", "PR-0001", r["digest"], by=INSPECTOR)
    assert h.view(c, "get_case", "PR-0001")["state"] == "OPEN"


def test_held_sum_funding(h, c):
    r = open_case(h, c, held_sum_wei=str(GEN // 10), funder="RESPONDENT")
    a = accept_case(h, c, "PR-0001")
    assert a["state"] == "DRAFT", "case waits for funding"
    # stranger cannot fund
    out = h.call(c, "fund_case", "PR-0001", by=STRANGER, value=GEN // 10)
    assert out["refused"] is True
    assert h.view(c, "get_credit", STRANGER)["owed"] == str(GEN // 10)
    # wrong amount refused
    out = h.call(c, "fund_case", "PR-0001", by=RESPONDENT, value=GEN // 10 - 1)
    assert out["refused"] is True
    f = h.call(c, "fund_case", "PR-0001", by=RESPONDENT, value=GEN // 10)
    assert f["state"] == "OPEN"
    assert h.view(c, "get_stats")["held_wei"] == str(GEN // 10)
    # double funding refused and credited back
    out = h.call(c, "fund_case", "PR-0001", by=RESPONDENT, value=GEN // 10)
    assert out["refused"] is True
