"""Binding the seen set across every validator.

The record's `seen_ids` and `unseen_ids` decide who may ask for the assessment
again: the retry right is only granted when an image genuinely went unexamined.
So the set must be the one the validators themselves examined, not the one the
leader claimed. A validator that cannot reproduce the leader's counted seen set
dissents, in both directions: it will not stand behind a result that rests on
less than it saw, and it will not certify one that rests on an image it never
saw.

Direct Mode runs only the leader, so each test replays the captured validator
closure with its own answers, which is what lets the leader and the validator
report different seen sets over the same evidence.
"""

import json

from .conftest import CLAIMANT, RESPONDENT, accept_case, open_case, terms
from .model import jpeg, look, look_by


def opened(h, c):
    cid = open_case(h, c)["case_id"]
    accept_case(h, c, cid, by=terms()["respondent"])
    return cid


def two_photos(h, c, cid):
    """Two photographs with distinct bytes, so each can be seen or missed alone."""
    p1 = h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}),
                jpeg("one"), by=CLAIMANT)["evidence_id"]
    p2 = h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}),
                jpeg("two"), by=CLAIMANT)["evidence_id"]
    return p1, p2


def ready_all(h, c, cid):
    h.call(c, "mark_ready", cid, by=CLAIMANT)
    h.call(c, "mark_ready", cid, by=RESPONDENT)


def judge(seen, supports=(), finding="SUPPORTED"):
    return {"criteria": [
        {"id": "C1", "rationale": "seen", "supports": list(supports), "against": [],
         "evidence_adequate": True, "finding": finding, "missing": []},
        {"id": "C2", "rationale": "nothing", "supports": [], "against": [],
         "evidence_adequate": False, "finding": "INSUFFICIENT", "missing": []}],
        "limitations": [], "instructions_found": [], "seen_ids": list(seen)}


def test_a_validator_dissents_when_the_leader_counts_an_image_it_did_not_see(h, c):
    """The leader claims a picture the panel never looked at. The record would
    then say the image was seen, and the side it went against would lose the
    retry it was owed."""
    cid = opened(h, c)
    p1, p2 = two_photos(h, c, cid)
    ready_all(h, c, cid)

    # the leader examined both and claims both
    h.mock_look(look())
    h.mock_judge(judge([p1, p2], supports=[p1]))
    h.later(4 * 86400)
    h.call(c, "request_assessment", cid, by=CLAIMANT)

    # the validator examined only the first
    assert h.run_validator(answers=[look_by({"one": {"seen": True, "shows": "cartons"},
                                              "two": {"seen": False, "shows": ""}}),
                                     judge([p1], supports=[p1])]) is False


def test_a_validator_dissents_when_the_leader_omits_an_image_it_saw(h, c):
    """The mirror of the rule: the record must not rest on less than this node
    saw, or the panel's own observation of an image is dropped silently."""
    cid = opened(h, c)
    p1, p2 = two_photos(h, c, cid)
    ready_all(h, c, cid)

    # the leader examined only the first and claims only the first
    h.mock_look(look_by({"one": {"seen": True, "shows": "cartons"},
                          "two": {"seen": False, "shows": ""}}))
    h.mock_judge(judge([p1], supports=[p1]))
    h.later(4 * 86400)
    h.call(c, "request_assessment", cid, by=CLAIMANT)

    # the validator examined both
    assert h.run_validator(answers=[look(), judge([p1, p2], supports=[p1])]) is False


def test_a_validator_agrees_when_both_saw_the_same_images(h, c):
    """The ordinary case is untouched: the same set on both sides agrees."""
    cid = opened(h, c)
    p1, p2 = two_photos(h, c, cid)
    ready_all(h, c, cid)

    h.mock_look(look())
    h.mock_judge(judge([p1, p2], supports=[p1]))
    h.later(4 * 86400)
    h.call(c, "request_assessment", cid, by=CLAIMANT)

    assert h.run_validator(answers=[look(), judge([p1, p2], supports=[p1])]) is True


def test_a_twin_counts_as_seen_on_both_sides(h, c):
    """The same bytes filed twice are one piece of evidence. A copy whose twin
    was seen counts as seen, so the leader naming one copy and the validator
    naming the other must still agree."""
    cid = opened(h, c)
    p1 = h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}),
                jpeg("same"), by=CLAIMANT)["evidence_id"]
    p2 = h.call(c, "submit_image", cid, json.dumps({"kind": "PHOTO"}),
                jpeg("same"), by=RESPONDENT)["evidence_id"]
    ready_all(h, c, cid)

    # The two copies were filed by different roles, so each is examined in its
    # own prompt: the leader needs a look answer for each, then its judgment.
    h.mock_look(look())
    h.mock_look(look())
    h.mock_judge(judge([p1], supports=[p1]))
    h.later(4 * 86400)
    h.call(c, "request_assessment", cid, by=CLAIMANT)

    # the validator saw the respondent's copy: the same bytes, counted as seen
    assert h.run_validator(answers=[look(), look(), judge([p2], supports=[p1])]) is True


def test_the_record_reports_an_image_the_panel_never_saw_as_unseen(h, c):
    """End to end: a leader that claims a picture nobody looked at leaves the
    record with an empty unseen set, and the side the decision went against
    cannot ask for the assessment again. The set the panel actually examined
    is what the record must carry."""
    cid = opened(h, c)
    p1, p2 = two_photos(h, c, cid)
    ready_all(h, c, cid)

    # the leader examined only the first, and claims only the first
    h.mock_look(look_by({"one": {"seen": True, "shows": "cartons"},
                          "two": {"seen": False, "shows": ""}}))
    h.mock_judge(judge([p1], supports=[p1]))
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)

    d = h.view(c, "get_decision", r["decision_id"])
    assert d["seen_ids"] == [p1], d["seen_ids"]
    assert d["unseen_ids"] == [p2], d["unseen_ids"]
    # and the side the finding went against may ask for it again
    assert h.view(c, "get_actions", cid, RESPONDENT)["assess"]["ok"] is True


def test_no_retry_when_the_panel_examined_every_image(h, c):
    """With every image seen, no side may ask for another assessment."""
    cid = opened(h, c)
    p1, p2 = two_photos(h, c, cid)
    ready_all(h, c, cid)

    h.mock_look(look())
    h.mock_judge(judge([p1, p2], supports=[p1]))
    h.later(4 * 86400)
    r = h.call(c, "request_assessment", cid, by=CLAIMANT)

    d = h.view(c, "get_decision", r["decision_id"])
    assert d["unseen_ids"] == [], d["unseen_ids"]
    assert h.view(c, "get_actions", cid, RESPONDENT)["assess"]["ok"] is False
