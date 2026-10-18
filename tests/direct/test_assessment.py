"""Assessment: consensus path, code-decided floors, dissent, retries, finality."""

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
from .model import crit, jpeg, judge, look, look_by, png




def opened(h, c, **over):
    base = {"allowed": ["PHOTO", "TEXT_DOCUMENT", "DOCUMENT_PAGE", "VIDEO_FRAME"],
            "held_sum_wei": "0", "funder": "",
            "criteria": [{"text": "100 widgets were delivered", "needs_independent": False},
                         {"text": "delivery was on time", "needs_independent": False}]}
    base.update(over)
    cid = open_case(h, c, **{k: v for k, v in base.items()})["case_id"]
    t = terms(**base)
    accept_case(h, c, cid, by=t["respondent"])
    if t.get("inspector"):
        h.call(c, "accept_inspector", cid, h.view(c, "get_terms", cid, 1)["digest"], by=t["inspector"])
    assert h.view(c, "get_case", cid)["state"] == "OPEN", h.view(c, "get_case", cid)
    return cid


def photo(h, c, cid, by=CLAIMANT, tag="a", **meta):
    m = {"kind": "PHOTO", "file_name": f"{tag}.jpg", "description": "cartons on pallets",
         "criteria": ["C1"]}
    m.update(meta)
    return h.call(c, "submit_image", cid, json.dumps(m), jpeg(tag), by=by)["evidence_id"]


def doc(h, c, cid, by=RESPONDENT, text="The depot log shows delivery on 2026-10-09.", **meta):
    m = {"doc_type": "DELIVERY_NOTE", "title": "Depot log", "criteria": ["C2"]}
    m.update(meta)
    return h.call(c, "submit_text", cid, json.dumps(m), text, by=by)["evidence_id"]


def ready_all(h, c, cid, inspector=None):
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    if inspector:
        h.call(c, "mark_ready", cid, by=inspector)


def judge_for(*rows):
    return {"criteria": list(rows), "limitations": [], "instructions_found": [], "seen_ids": []}


def test_supported_assessment_end_to_end(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="good-delivery")
    ready_all(h, c, cid)
    h.mock_look(look())
    h.mock_judge(judge_for(
        {"id": "C1", "rationale": "photo shows stacked cartons", "supports": [p1],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []},
        {"id": "C2", "rationale": "no time evidence either way", "supports": [],
         "against": [], "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": ["a timestamp"]}))
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "INSUFFICIENT", r
    assert r["findings"] == {"C1": "SUPPORTED", "C2": "INSUFFICIENT"}
    d = h.view(c, "get_decision", r["decision_id"])
    assert d["status"] == "STANDING" and d["round"] == 1 and d["kind"] == "ASSESSMENT"
    assert d["terms_digest"] == h.view(c, "get_case", cid)["accepted_digest"]
    assert d["decision_digest"] and len(d["decision_digest"]) == 64
    # receipt digest recomputes from the core
    rcpt = h.view(c, "get_receipt", cid)
    import hashlib
    canon = json.dumps(rcpt["core"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canon.encode("ascii")).hexdigest() == rcpt["digest"]
    # not final until the challenge window passes
    h.refused(c, "finalize", cid, by=STRANGER, match="still be challenged")
    h.at(d["challenge_window_ends"])
    h.later(1)
    f = h.call(c, "finalize", cid, by=STRANGER)
    assert f["state"] == "FINAL" and f["overall"] == "INSUFFICIENT"
    fin = h.view(c, "get_decision", r["decision_id"])
    assert fin["status"] == "FINAL"


def test_code_decides_when_required_evidence_missing(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c, required=[{"type": "PHOTO", "min": 2}])
    photo(h, c, cid, tag="only-one")
    ready_all(h, c, cid)
    h.later(4 * 86400)
    # no model involved: required evidence missing decides INSUFFICIENT in code
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "INSUFFICIENT"
    d = h.view(c, "get_decision", r["decision_id"])
    assert all(x["floors"] == ["REQUIRED_MISSING"] for x in d["criteria"])
    assert h.prompts == [], "no model prompts when the code decides"


def test_code_decides_empty_file(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    ready_all(h, c, cid)
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=RESPONDENT)
    assert r["overall"] == "INSUFFICIENT"


def test_floors_demote_own_evidence_only(h, c):
    """F3: a SUPPORTED resting only on the claimant's own items with contrary
    evidence becomes CONFLICTING."""
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, by=CLAIMANT, tag="claimant-box")
    p2 = photo(h, c, cid, by=RESPONDENT, tag="respondent-empty")
    ready_all(h, c, cid)
    h.mock_look(look())
    h.mock_look(look())
    h.mock_judge(judge_for(
        {"id": "C1", "rationale": "claimant photo shows cartons but respondent shows empty bay",
         "supports": [p1], "against": [p2], "evidence_adequate": True,
         "finding": "SUPPORTED", "missing": []},
        {"id": "C2", "rationale": "nothing on timing", "supports": [],
         "against": [], "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []}))
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["findings"]["C1"] == "CONFLICTING", r
    d = h.view(c, "get_decision", r["decision_id"])
    c1 = [x for x in d["criteria"] if x["id"] == "C1"][0]
    assert "F3" in c1["floors"]


def test_f2_needs_independent_basis(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c, inspector=INSPECTOR, held_sum_wei="0", funder="",
                 criteria=[{"text": "the inspector confirms the count", "needs_independent": True},
                           {"text": "delivery was on time", "needs_independent": False}])
    assert h.view(c, "get_case", cid)["state"] == "OPEN", "opened() accepts inspector after respondent"
    p1 = photo(h, c, cid, by=CLAIMANT, tag="claimant-count")
    ready_all(h, c, cid, inspector=INSPECTOR)
    h.mock_look(look())
    h.mock_judge(judge_for(
        {"id": "C1", "rationale": "claimant photo", "supports": [p1],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []},
        {"id": "C2", "rationale": "nothing", "supports": [],
         "against": [], "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []}))
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["findings"]["C1"] == "INSUFFICIENT"
    d = h.view(c, "get_decision", r["decision_id"])
    assert "F2" in [x for x in d["criteria"] if x["id"] == "C1"][0]["floors"]


def test_retry_when_image_unseen(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    p1 = photo(h, c, cid, tag="unseen-box")
    ready_all(h, c, cid)
    # leader saw nothing: every image unseen -> NOT_ASSESSED overall.
    # look() with seen=False reports the image unseen.
    h.mock_look(look(seen=False, shows=""))
    h.mock_judge({"criteria": [
        {"id": "C1", "rationale": "could not examine", "supports": [],
         "against": [], "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []},
        {"id": "C2", "rationale": "could not examine", "supports": [],
         "against": [], "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": []})
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "NOT_ASSESSED", r
    # the side it went against retries free of bond
    assert h.view(c, "get_actions", cid, CLAIMANT)["assess"]["ok"] is True
    h.mock_look(look())
    h.mock_judge(judge_for(
        {"id": "C1", "rationale": "now seen", "supports": [p1],
         "against": [], "evidence_adequate": True, "finding": "SUPPORTED", "missing": []},
        {"id": "C2", "rationale": "nothing", "supports": [],
         "against": [], "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []},
        ))
    # judge must carry seen_ids through the harness queue
    h.answers[-1]["seen_ids"] = [p1]
    r2 = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r2["findings"]["C1"] == "SUPPORTED"
    # second retry refused
    h.refused(c, "request_assessment", cid, by=CLAIMANT, match="again")


def test_assessment_guards(h, c):
    h.at("2026-10-01T09:00:00Z")
    cid = opened(h, c)
    h.refused(c, "request_assessment", cid, by=STRANGER, match="claimant or the respondent")
    h.refused(c, "request_assessment", cid, by=CLAIMANT, match="unless every party")
    h.later(4 * 86400)
    # stranger with no role cannot file either
    h.refused(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), jpeg("x"),
              by=STRANGER, match="only the claimant")
