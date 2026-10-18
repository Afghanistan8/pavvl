"""Governance isolation: there is no owner, admin, operator, pause or upgrade.

These tests read the chain and the source. They exist so the claim "no
operator key" is checkable, not merely asserted in a document. The deployer is
recorded for provenance and is consulted by nothing.
"""

import json
import re
from pathlib import Path

from .conftest import (
    CLAIMANT,
    DEPLOYER_ADDR,
    GEN,
    RESPONDENT,
    STRANGER,
    accept_case,
    open_case,
    terms,
)

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "pavvl.py"


def test_governance_view_reports_no_authority(h, c):
    g = h.view(c, "get_governance")
    assert g["owner"] == "" and g["admin"] == "" and g["operator"] == ""
    assert g["pausable"] is False
    assert g["upgradeable"] is False
    assert g["has_admin_key"] is False and g["has_upgrade_key"] is False
    assert g["deployer_has_power"] is False
    assert g["chain_id"] == 61999


def test_deployer_is_recorded_but_powerless(h, c):
    """The deployer gets no role, no bypass and no early finality."""
    cfg = h.view(c, "get_config")
    # The deployer is recorded for provenance (its exact value is the network's
    # deploy sender; on Studionet that is the deployment wallet).
    assert isinstance(cfg["deployer"], str) and cfg["deployer"] != ""
    assert h.view(c, "get_governance")["deployer_has_power"] is False
    cid = open_case(h, c)["case_id"]
    # The deployer is not the respondent: it cannot accept someone else's terms.
    h.refused(c, "accept_case", cid, h.view(c, "get_terms", cid, 1)["digest"],
              by=DEPLOYER_ADDR, match="respondent")
    # Nor can it withdraw the claimant's draft.
    h.refused(c, "withdraw_case", cid, by=DEPLOYER_ADDR, match="claimant")
    # A stranger's acts read false for the deployer too.
    acts = h.view(c, "get_actions", cid, DEPLOYER_ADDR)
    assert acts["role"] == ""
    assert acts["accept"]["ok"] is False
    assert acts["finalize"]["ok"] is False


def test_no_pause_upgrade_or_admin_methods_exist():
    """No write method can pause, upgrade, seize, mint or reassign authority."""
    s = CONTRACT.read_text(encoding="ascii")
    banned = re.compile(
        r"def (pause|unpause|upgrade|upgrade_to|set_owner|set_admin|set_operator|"
        r"transfer_ownership|renounce|rescue|sweep|seize|mint|burn|withdraw_all|set_fee)\b")
    hits = banned.findall(s)
    assert not hits, f"a privileged method exists: {hits}"


def test_every_write_gate_is_a_role_from_the_frozen_terms():
    """Authority comes only from the terms: the roles the contract recognises
    are CLAIMANT, RESPONDENT and an accepted INSPECTOR, and nothing else."""
    s = CONTRACT.read_text(encoding="ascii")
    m = re.search(r"def _role\(self.*?return \"\"\n", s, re.S)
    assert m, "_role not found"
    body = m.group(0)
    for role in ("CLAIMANT", "RESPONDENT", "INSPECTOR"):
        assert role in body
    # The only address compared against is one stored from the frozen terms.
    assert "c[\"claimant\"]" in body and "c[\"respondent\"]" in body and "c[\"inspector\"]" in body


def test_deployer_cannot_move_held_funds(h, c):
    """Only the roles named in the terms can drive a case to settlement."""
    h.at("2026-10-01T09:00:00Z")
    t = terms(held_sum_wei=str(GEN // 10), funder="RESPONDENT")
    cid = open_case(h, c, **t)["case_id"]
    accept_case(h, c, cid)
    funder = RESPONDENT if t["funder"] == "RESPONDENT" else CLAIMANT
    h.call(c, "fund_case", cid, by=funder, value=GEN // 10)
    # The deployer can never ask for an assessment it has no role in.
    h.refused(c, "request_assessment", cid, by=DEPLOYER_ADDR, match="claimant or the respondent")
    # And never finalize a case that is not decided.
    h.refused(c, "finalize", cid, by=DEPLOYER_ADDR, match="standing decision")
    # Nothing is owed to it, and it cannot withdraw the held sum.
    assert h.view(c, "get_credit", DEPLOYER_ADDR)["owed"] == "0"
    h.refused(c, "withdraw", by=DEPLOYER_ADDR, match="nothing is owed")


def test_stats_and_config_agree_on_zero_governance(h, c):
    # A fresh deployment has no cases and no privileged counters.
    st = h.view(c, "get_stats")
    assert st["case"] == "0"
    g = h.view(c, "get_governance")
    assert g["authority"].startswith("none")
    assert STRANGER.lower() != g["owner"]
