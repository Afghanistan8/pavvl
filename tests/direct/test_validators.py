"""Validator independence over image evidence.

Material image evidence can control settlement, so every voting validator must
verify it itself. A node whose model receives no images fails the calibration
image; the contract then refuses to let it assess a case that has images at all.
It may not lead, and it may not judge the leading validator's descriptions of
images it never saw -- it dissents instead, so a decision needs a majority that
actually looked.

Direct Mode runs only the leader, so these replay the captured validator closure
with the harness's `blind` switch.
"""

import json

from .conftest import CLAIMANT, RESPONDENT, accept_case, open_case, terms
from .model import jpeg, look


def judge(p):
    return {"criteria": [
        {"id": "C1", "rationale": "seen", "supports": [p], "against": [],
         "evidence_adequate": True, "finding": "SUPPORTED", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": [p]}


def determined(h, c):
    """Open, accept, file one photo, mark ready, and assess with a sighted leader."""
    cid = open_case(h, c)["case_id"]
    accept_case(h, c, cid, by=terms()["respondent"])
    p = h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}),
               jpeg("vd"), by=CLAIMANT)["evidence_id"]
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    h.mock_look(look())
    h.mock_judge(judge(p))
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)
    assert r["overall"] == "SUPPORTED"
    return cid, p


def test_a_sighted_validator_examines_the_image_and_agrees(h, c):
    cid, p = determined(h, c)
    before = len(h.prompts)

    assert h.run_validator(answers=[look(), judge(p)]) is True

    kinds = [x["kind"] if isinstance(x, dict) else "judge" for x in h.prompts[before:]]
    assert kinds == ["sight", "look", "judge"], "the validator looked for itself"


def test_a_blind_validator_dissents_instead_of_borrowing(h, c):
    cid, p = determined(h, c)
    h.blind()
    before = len(h.prompts)

    # No answers are queued: a blind node must refuse before it asks the model
    # anything, so consuming the judge queue would already be the bug.
    assert h.run_validator() is False

    replay = h.prompts[before:]
    assert replay == [{"kind": "sight", "images": 1, "blind": True}], (
        "the blind validator calibrated, saw it could not see, and refused; "
        "it never examined the image or judged the leader's description of it"
    )


def test_a_blind_leader_cannot_produce_a_decision(h, c):
    cid = open_case(h, c)["case_id"]
    accept_case(h, c, cid, by=terms()["respondent"])
    h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}), jpeg("bl"), by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)
    h.blind()
    h.later(4 * 86400)

    h.refused(c, "request_assessment", cid, by=CLAIMANT, match="cannot receive images")
    # Fails closed: the refusal reverted, so no decision was recorded.
    assert h.view(c, "get_case", cid)["state"] == "OPEN"
