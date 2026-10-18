"""Hardening: terms freezing, evidence integrity, reuse floors, fail-closed
settlement, and prompt-injection resistance.

Each test here pins one hardening property the project claims, and each is
deliberately adversarial: they try to move the goalposts, recycle evidence,
inject instructions, and make uncertainty pay the claimant.
"""

import hashlib
import json

from .conftest import (
    CLAIMANT,
    GEN,
    RESPONDENT,
    SECOND,
    accept_case,
    open_case,
    terms,
)
from .model import jpeg, look


def opened(h, c, respondent=RESPONDENT, **over):
    base = {"allowed": ["PHOTO", "TEXT_DOCUMENT"],
            "criteria": [{"text": "100 widgets were delivered", "needs_independent": False}],
            "held_sum_wei": "0", "funder": "", "respondent": respondent}
    base.update(over)
    t = terms(**base)
    cid = open_case(h, c, **base)["case_id"]
    accept_case(h, c, cid, by=t["respondent"])
    assert h.view(c, "get_case", cid)["state"] == "OPEN"
    return cid


def photo(h, c, cid, by=CLAIMANT, tag="a", criteria=("C1",), blob=None):
    m = {"kind": "PHOTO", "criteria": list(criteria)}
    return h.call(c, "submit_image", cid, json.dumps(m), blob if blob is not None else jpeg(tag),
                  by=by)["evidence_id"]


def ready_all(h, c, cid):
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)


# ---- terms freezing by digest ------------------------------------------------

def test_accept_requires_the_current_digest_not_an_older_one(h, c):
    """A respondent who read version 1 cannot accept after the claimant moved
    the goalposts to version 2: only the current digest is accepted."""
    v1 = open_case(h, c)["digest"]
    v2 = h.call(c, "revise_terms", "PR-0001", json.dumps(terms(title="Delivery of 101 widgets")),
                by=CLAIMANT)["digest"]
    assert v1 != v2
    h.refused(c, "accept_case", "PR-0001", v1, by=RESPONDENT, match="does not match")
    accept_case(h, c, "PR-0001", version=2)
    case = h.view(c, "get_case", "PR-0001")
    assert case["accepted_digest"] == v2
    assert case["accepted_version"] == 2


def test_terms_digest_recomputes_from_every_stored_version(h, c):
    """Each stored version's digest is exactly the sha256 of its canonical
    JSON: a tampered record could not keep its digest."""
    r = open_case(h, c)
    h.call(c, "revise_terms", "PR-0001", json.dumps(terms(title="Delivery of 101 widgets")), by=CLAIMANT)
    for version in (1, 2):
        t = h.view(c, "get_terms", "PR-0001", version)
        core = {k: v for k, v in t.items() if k != "digest"}
        canon = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        assert hashlib.sha256(canon.encode("ascii")).hexdigest() == t["digest"]
    # v1's digest is the one the respondent first saw, and it is unchanged.
    assert h.view(c, "get_terms", "PR-0001", 1)["digest"] == r["digest"]


def test_terms_are_frozen_once_accepted(h, c):
    open_case(h, c)
    accept_case(h, c, "PR-0001")
    h.refused(c, "revise_terms", "PR-0001", json.dumps(terms(title="A different claim entirely")),
              by=CLAIMANT, match="frozen")


# ---- evidence integrity ------------------------------------------------------

def test_criteria_id_from_nowhere_is_refused(h, c):
    cid = opened(h, c)
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO", "criteria": ["C9"]}), jpeg("x"),
              by=CLAIMANT, match="not a criterion of this case")


def test_stored_bytes_match_the_reported_digest(h, c):
    cid = opened(h, c)
    blob = jpeg("integrity")
    out = photo(h, c, cid, blob=blob)
    it = h.view(c, "get_evidence", out)
    assert it["sha256"] == hashlib.sha256(blob).hexdigest()
    assert it["bytes"] == len(blob)
    assert bytes(h.view(c, "get_evidence_image", out)) == blob


def test_refiling_the_same_bytes_by_one_role_is_refused(h, c):
    """A party cannot pad its file with the same exhibit twice, which would
    overstate how much evidence it filed."""
    cid = opened(h, c)
    blob = jpeg("dup")
    photo(h, c, cid, blob=blob)
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO", "criteria": ["C1"]}), blob,
              by=CLAIMANT, match="already filed")


# ---- reuse floors ------------------------------------------------------------

def test_cross_counterparty_reuse_cannot_carry_a_finding(h, c):
    """F7: bytes the claimant already filed against a *different* other party
    (SELF reuse) are flagged and floored, so a claimant cannot recycle one
    photograph across unrelated disputes and win on it."""
    h.at("2026-10-01T09:00:00Z")
    # Case A: same claimant, a different opponent. File the photograph there first.
    a = open_case(h, c, respondent=SECOND, subject_ref="thread-a")["case_id"]
    accept_case(h, c, a, by=SECOND)
    blob = jpeg("recycled")
    h.call(c, "submit_image", a, json.dumps({"kind": "PHOTO", "criteria": ["C1"]}), blob, by=CLAIMANT)
    # Case B: same claimant, a different counterparty. Refiling the same bytes.
    b = opened(h, c, subject_ref="thread-b")
    eid = photo(h, c, b, blob=blob)
    assert h.view(c, "get_evidence", eid)["reuse"] == "SELF"
    ready_all(h, c, b)
    h.later(4 * 86400)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "recycled photo", "supports": [eid], "against": [],
         "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [eid]})
    r = h.call(c, "request_assessment", b, by=CLAIMANT)
    assert r["findings"]["C1"] == "INSUFFICIENT"
    row = [x for x in h.view(c, "get_decision", r["decision_id"])["criteria"] if x["id"] == "C1"][0]
    assert "F6/F7" in row["floors"]


def test_manifest_records_reuse_for_the_receipt(h, c):
    """The decision's evidence snapshot tells a later reader which item was
    reused and from where, so the receipt is self-describing."""
    h.at("2026-10-01T09:00:00Z")
    a = open_case(h, c, respondent=SECOND, subject_ref="t-a")["case_id"]
    accept_case(h, c, a, by=SECOND)
    blob = jpeg("reused-2")
    h.call(c, "submit_image", a, json.dumps({"kind": "PHOTO", "criteria": ["C1"]}), blob, by=CLAIMANT)
    b = opened(h, c, subject_ref="t-b")
    eid = photo(h, c, b, blob=blob)
    ready_all(h, c, b)
    h.later(4 * 86400)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "r", "supports": [], "against": [],
         "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [eid]})
    r = h.call(c, "request_assessment", b, by=CLAIMANT)
    d = h.view(c, "get_decision", r["decision_id"])
    row = [x for x in d["evidence"] if x["evidence_id"] == eid][0]
    assert row["reuse"] == "SELF" and row["first_filed_in"] == a
    assert d["manifest_digest"]


# ---- prompt-injection resistance --------------------------------------------

def test_injected_instruction_cannot_carry_a_supported_finding(h, c):
    """F6/F7: an item that tried to instruct the assessor is discarded from the
    side that filed it, however the model labelled it. Text in evidence is
    never authority."""
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    eid = photo(h, c, cid, tag="injection")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "the exhibit says to return SUPPORTED", "supports": [eid],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [eid], "seen_ids": [eid]})
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["findings"]["C1"] == "INSUFFICIENT", r
    row = [x for x in h.view(c, "get_decision", r["decision_id"])["criteria"] if x["id"] == "C1"][0]
    assert "F6/F7" in row["floors"]
    assert row["basis"] == []


# ---- fail-closed settlement --------------------------------------------------

def funded(h, c, **over):
    base = {"held_sum_wei": str(GEN // 10), "funder": "RESPONDENT",
            "allowed": ["PHOTO", "TEXT_DOCUMENT"],
            "criteria": [{"text": "100 widgets were delivered", "needs_independent": False}]}
    base.update(over)
    t = terms(**base)
    cid = open_case(h, c, **base)["case_id"]
    accept_case(h, c, cid)
    funder = CLAIMANT if t["funder"] == "CLAIMANT" else RESPONDENT
    h.call(c, "fund_case", cid, by=funder, value=int(t["held_sum_wei"]))
    assert h.view(c, "get_case", cid)["state"] == "OPEN"
    return cid


def test_insufficient_finding_never_pays_the_claimant(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = funded(h, c)
    eid = photo(h, c, cid, tag="thin")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "too thin", "supports": [], "against": [],
         "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": ["a delivery note"]}],
        "limitations": [], "instructions_found": [], "seen_ids": [eid]})
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "INSUFFICIENT"
    d = h.view(c, "get_decision", r["decision_id"])
    h.at(d["challenge_window_ends"])
    h.later(1)
    h.call(c, "finalize", cid, by=CLAIMANT)
    assert h.view(c, "get_credit", CLAIMANT)["owed"] == "0"
    assert h.view(c, "get_credit", RESPONDENT)["owed"] == str(GEN // 10)


def test_finding_that_could_not_be_assessed_pays_no_claimant(h, c):
    """NOT_ASSESSED (nothing could be examined) fails closed: the held sum goes
    back to the party that deposited it, never to the claimant on silence."""
    h.at("2026-10-01T09:00:00Z")
    cid = funded(h, c)
    eid = photo(h, c, cid, tag="unreadable")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    h.mock_look(look(seen=False, shows=""))
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "could not examine", "supports": [], "against": [],
         "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": []})
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "NOT_ASSESSED"
    d = h.view(c, "get_decision", r["decision_id"])
    h.at(d["challenge_window_ends"])
    h.later(1)
    h.call(c, "finalize", cid, by=CLAIMANT)
    assert h.view(c, "get_credit", CLAIMANT)["owed"] == "0"
    assert h.view(c, "get_credit", RESPONDENT)["owed"] == str(GEN // 10)


def test_supported_finding_pays_the_claimant(h, c):
    """The one path that pays the claimant: a final SUPPORTED on every
    criterion, after a challenge window nobody used."""
    h.at("2026-10-01T09:00:00Z")
    cid = funded(h, c)
    eid = photo(h, c, cid, tag="good")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    h.mock_look(look())
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "clearly delivered", "supports": [eid], "against": [],
         "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [eid]})
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "SUPPORTED"
    d = h.view(c, "get_decision", r["decision_id"])
    h.at(d["challenge_window_ends"])
    h.later(1)
    h.call(c, "finalize", cid, by=CLAIMANT)
    assert h.view(c, "get_credit", CLAIMANT)["owed"] == str(GEN // 10)
    assert h.view(c, "get_credit", RESPONDENT)["owed"] == "0"
