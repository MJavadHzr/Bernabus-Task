"""Part Four requirements 1, 2 and 6, demonstrated by construction.

  E4 cannot be treated as E0/E1/E2/E3
  E4 -> E5 raises without a valid, authorised confirmation event
  confirmation appends and never erases the original model output or history
  a claim edited after confirmation loses E5 (hash mismatch)

This is the construction evidence that 3.17's scope limitation refers to. It is
not measurement evidence and the report must not present it as such.
"""

from __future__ import annotations

import pytest

from barn_eval.authority.confirmation import sha256_text, validate_confirmation
from barn_eval.authority.levels import PRIMARY_TIERS, AuthorityLevel
from barn_eval.authority.state_machine import (
    AuthorityViolation,
    Claim,
    assert_producible,
    promote,
    revalidate,
)

CLAIM_TEXT = "Current eGFR is 41 mL/min/1.73m2."


def _claim():
    return Claim(claim_id="r1c1", text=CLAIM_TEXT)


def _confirmation(text=CLAIM_TEXT, authorised=True, cid="conf_1"):
    return {
        "confirmation_id": cid,
        "case_id": "clean_001",
        "claim_id": "r1c1",
        "confirmed_by": {"actor_id": "dr_smith", "role": "clinician", "authorised": authorised},
        "confirmed_at": "2026-08-01T00:00:00Z",
        "confirmed_text_hash": sha256_text(text),
    }


# --- E4 cannot be treated as E0/E1/E2/E3 -----------------------------------

@pytest.mark.parametrize("tier", ["E0", "E1", "E2", "E3"])
def test_model_cannot_assert_primary_tier(tier):
    with pytest.raises(AuthorityViolation):
        assert_producible(tier)


def test_none_and_e4_are_producible():
    assert assert_producible(None) is AuthorityLevel.E4
    assert assert_producible("E4") is AuthorityLevel.E4


def test_primary_tiers_are_exactly_e0_through_e3():
    assert PRIMARY_TIERS == {
        AuthorityLevel.E0,
        AuthorityLevel.E1,
        AuthorityLevel.E2,
        AuthorityLevel.E3,
    }


# --- E4 -> E5 requires a valid, authorised confirmation --------------------

def test_promote_without_event_raises():
    with pytest.raises(AuthorityViolation):
        promote(_claim(), None)


def test_promote_with_unauthorised_actor_raises():
    with pytest.raises(AuthorityViolation):
        promote(_claim(), _confirmation(authorised=False))


def test_promote_with_hash_mismatch_raises():
    bad = _confirmation(text="a different claim entirely")
    with pytest.raises(AuthorityViolation):
        promote(_claim(), bad)


def test_promote_with_valid_confirmation_reaches_e5():
    confirmed = promote(_claim(), _confirmation())
    assert confirmed.level is AuthorityLevel.E5


def test_cannot_promote_a_non_e4_claim():
    confirmed = promote(_claim(), _confirmation())
    # already E5; promoting again is not a permitted transition
    with pytest.raises(AuthorityViolation):
        promote(confirmed, _confirmation())


# --- confirmation appends, never erases (Part Four req 6) ------------------

def test_confirmation_appends_and_preserves_original_text():
    original = _claim()
    confirmed = promote(original, _confirmation())
    # original object is untouched
    assert original.level is AuthorityLevel.E4
    assert len(original.history) == 0
    # confirmed carries the original text and one appended history entry
    assert confirmed.original_text == CLAIM_TEXT
    assert confirmed.text == CLAIM_TEXT
    assert len(confirmed.history) == 1
    assert confirmed.history[0]["confirmation_id"] == "conf_1"


# --- edit after confirmation voids E5 (hash mismatch) ----------------------

def test_edit_after_confirmation_reverts_to_e4():
    event = _confirmation()
    confirmed = promote(_claim(), event)
    assert confirmed.level is AuthorityLevel.E5

    # claim text edited after confirmation -> hash no longer matches
    edited = Claim(
        claim_id=confirmed.claim_id,
        text="Current eGFR is 62 mL/min/1.73m2.",  # tampered
        level=AuthorityLevel.E5,
        original_text=confirmed.original_text,
        history=confirmed.history,
    )
    reverted = revalidate(edited, event)
    assert reverted.level is AuthorityLevel.E4
    # history is retained so the break is auditable
    assert len(reverted.history) == 1


def test_validate_confirmation_defect_reasons():
    assert validate_confirmation(_confirmation(), _claim()) is True
    assert validate_confirmation(_confirmation(authorised=False), _claim()).reason == "not_authorised"
    assert validate_confirmation(_confirmation(text="x"), _claim()).reason == "hash_mismatch"
    assert validate_confirmation(_confirmation(), None).reason == "claim_id_unresolved"
