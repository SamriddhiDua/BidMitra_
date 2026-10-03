"""
tests/test_profiles.py – unit tests for profiles.py and diary.py.

Covers:
  - completeness % calculation
  - applied >= 5 rule for win rate
  - export/import round trip
  - switching profile changes diary view
  - validation rejects unknown keys and bad types
  - diary stats computation
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.profiles import (
    SellerProfile, validate_and_build, ProfileValidationError,
    export_profile_json, import_profile_json,
)
from src.diary import (
    compute_stats, get_diary, upsert_entry, remove_entry, get_entry,
    import_diary, export_diary, DiaryEntry, closing_soon, VALID_STATUSES,
)
from src.models import BidResult, Chip


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_full_profile_data(**overrides) -> dict:
    base = {
        "profile_id": "test_profile",
        "business_name": "Test Spares Co",
        "base_location": "Panipat, Haryana",
        "item_families": {"valves": ["gate valve", "ball valve"]},
        "adjacent_items": ["bearing"],
        "delivery_radius_km": 250,
        "max_emd_inr": 50000,
        "years_in_business": 10,
        "entity_type": "Sole Proprietorship",
        "mse_declared": True,
        "startup_declared": False,
        "certifications": ["ISO 9001:2015"],
        "documents_declared": {"gst": True, "udyam": True, "iso": False, "other": False},
    }
    base.update(overrides)
    return base


def make_minimal_profile_data() -> dict:
    """Profile with only required fields filled."""
    return {
        "profile_id": "minimal",
        "business_name": "",
        "base_location": "",
        "item_families": {},
        "adjacent_items": [],
        "delivery_radius_km": 250,
        "max_emd_inr": 50000,
    }


# ---------------------------------------------------------------------------
# validate_and_build tests
# ---------------------------------------------------------------------------

def test_validate_full_profile():
    data = make_full_profile_data()
    prof, warns = validate_and_build(data)
    assert prof.business_name == "Test Spares Co"
    assert prof.delivery_radius_km == 250
    assert prof.mse_declared is True
    assert not warns


def test_validate_unknown_key_rejected():
    data = make_full_profile_data(evil_key="hack")
    with pytest.raises(ProfileValidationError, match="Unknown profile fields"):
        validate_and_build(data)


def test_validate_wrong_type_radius():
    data = make_full_profile_data(delivery_radius_km="not a number")
    with pytest.raises(ProfileValidationError, match="must be a number"):
        validate_and_build(data)


def test_validate_out_of_range_radius():
    data = make_full_profile_data(delivery_radius_km=99999)
    with pytest.raises(ProfileValidationError, match="between"):
        validate_and_build(data)


def test_validate_string_too_long():
    data = make_full_profile_data(business_name="A" * 300)
    with pytest.raises(ProfileValidationError, match="too long"):
        validate_and_build(data)


def test_validate_bad_years():
    data = make_full_profile_data(years_in_business="abc")
    with pytest.raises(ProfileValidationError, match="integer"):
        validate_and_build(data)


def test_validate_item_families_must_be_dict():
    data = make_full_profile_data(item_families=["list", "not", "dict"])
    with pytest.raises(ProfileValidationError, match="must be a dict"):
        validate_and_build(data)


def test_validate_unknown_doc_keys_warned():
    data = make_full_profile_data(documents_declared={"gst": True, "secret_field": True})
    prof, warns = validate_and_build(data)
    assert any("secret_field" in w for w in warns)


# ---------------------------------------------------------------------------
# Completeness % tests
# ---------------------------------------------------------------------------

def test_completeness_full_profile():
    data = make_full_profile_data()
    prof, _ = validate_and_build(data)
    pct = prof.completeness_pct()
    assert 80 <= pct <= 100, f"Expected 80-100%, got {pct}%"


def test_completeness_minimal_profile():
    data = make_minimal_profile_data()
    prof, _ = validate_and_build(data)
    pct = prof.completeness_pct()
    # Only delivery_radius_km and max_emd_inr are filled → low completeness
    assert pct < 50, f"Expected < 50% for minimal profile, got {pct}%"


def test_completeness_increases_with_fields():
    """Adding fields should increase completeness."""
    min_prof, _ = validate_and_build(make_minimal_profile_data())
    full_prof, _ = validate_and_build(make_full_profile_data())
    assert full_prof.completeness_pct() > min_prof.completeness_pct()


def test_completeness_suggestions_provided_for_minimal():
    min_prof, _ = validate_and_build(make_minimal_profile_data())
    suggestions = min_prof.completeness_suggestions()
    assert len(suggestions) > 0


def test_completeness_pct_is_integer_0_to_100():
    data = make_full_profile_data()
    prof, _ = validate_and_build(data)
    pct = prof.completeness_pct()
    assert isinstance(pct, int)
    assert 0 <= pct <= 100


# ---------------------------------------------------------------------------
# Diary stats tests
# ---------------------------------------------------------------------------

def make_entry(bid_number: str, status: str, profile_id: str = "test") -> DiaryEntry:
    return DiaryEntry(bid_number=bid_number, title=f"Bid {bid_number}",
                      status=status, note="", date_recorded="2026-10-03", profile_id=profile_id)


def test_stats_empty_diary():
    stats = compute_stats([])
    assert stats.saved == 0
    assert stats.applied == 0
    assert stats.win_rate_pct is None
    assert "not enough data" in stats.win_rate_note


def test_stats_counts():
    entries = [
        make_entry("B1", "Saved"),
        make_entry("B2", "Applied"),
        make_entry("B3", "Applied"),
        make_entry("B4", "Won"),
        make_entry("B5", "Lost"),
        make_entry("B6", "Skipped"),
    ]
    stats = compute_stats(entries)
    assert stats.saved == 1
    assert stats.applied == 2
    assert stats.won == 1
    assert stats.lost == 1
    assert stats.skipped == 1


def test_win_rate_not_shown_below_5_applied():
    """Win rate must not be shown when applied < 5."""
    entries = [make_entry(f"B{i}", "Applied") for i in range(4)]
    entries += [make_entry("W1", "Won")]
    stats = compute_stats(entries)
    assert stats.applied == 4
    assert stats.win_rate_pct is None
    assert "not enough data" in stats.win_rate_note


def test_win_rate_shown_at_5_applied():
    """Win rate is shown when applied == 5."""
    entries = [make_entry(f"A{i}", "Applied") for i in range(5)]
    entries.append(make_entry("W1", "Won"))
    stats = compute_stats(entries)
    assert stats.applied == 5
    assert stats.win_rate_pct is not None
    # 1 won out of 5 applied = 20%
    assert stats.win_rate_pct == pytest.approx(20.0)


def test_win_rate_calculation():
    """3 won out of 6 applied = 50%."""
    entries = [make_entry(f"A{i}", "Applied") for i in range(6)]
    entries += [make_entry(f"W{i}", "Won") for i in range(3)]
    stats = compute_stats(entries)
    assert stats.applied == 6
    assert stats.win_rate_pct == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Diary session-state helpers
# ---------------------------------------------------------------------------

class FakeSession(dict):
    """Simple dict that acts as st.session_state."""
    pass


def test_upsert_and_get_entry():
    ss = FakeSession()
    upsert_entry(ss, "prof1", "BID001", "Test Bid", "Saved", "good one", "2026-10-03")
    entry = get_entry(ss, "prof1", "BID001")
    assert entry is not None
    assert entry.status == "Saved"
    assert entry.note == "good one"


def test_upsert_updates_existing():
    ss = FakeSession()
    upsert_entry(ss, "prof1", "BID001", "Test", "Saved", "", "2026-10-03")
    upsert_entry(ss, "prof1", "BID001", "Test", "Applied", "submitted", "2026-10-04")
    entries = get_diary(ss, "prof1")
    assert len(entries) == 1  # not duplicated
    assert entries[0].status == "Applied"
    assert entries[0].note == "submitted"


def test_remove_entry():
    ss = FakeSession()
    upsert_entry(ss, "prof1", "BID001", "Test", "Saved", "", "2026-10-03")
    remove_entry(ss, "prof1", "BID001")
    assert get_entry(ss, "prof1", "BID001") is None


def test_invalid_status_rejected():
    ss = FakeSession()
    with pytest.raises(ValueError, match="Invalid status"):
        upsert_entry(ss, "prof1", "BID001", "Test", "InvalidStatus")


def test_different_profiles_have_separate_diaries():
    ss = FakeSession()
    upsert_entry(ss, "prof1", "BID001", "Valve", "Saved", "", "2026-10-03")
    upsert_entry(ss, "prof2", "BID002", "Belt",  "Applied", "", "2026-10-03")
    assert get_entry(ss, "prof1", "BID002") is None  # not in prof1
    assert get_entry(ss, "prof2", "BID001") is None  # not in prof2
    assert get_entry(ss, "prof1", "BID001") is not None
    assert get_entry(ss, "prof2", "BID002") is not None


# ---------------------------------------------------------------------------
# Export / import round trip
# ---------------------------------------------------------------------------

def test_export_import_round_trip():
    data = make_full_profile_data()
    prof, _ = validate_and_build(data)
    diary = [
        DiaryEntry("B1", "My Bid", "Applied", "test note", "2026-10-03", prof.profile_id).to_dict()
    ]
    json_str = export_profile_json(prof, diary)
    imp_prof, imp_diary_raw, warns = import_profile_json(json_str)

    assert imp_prof.business_name == prof.business_name
    assert imp_prof.delivery_radius_km == prof.delivery_radius_km
    assert imp_prof.mse_declared == prof.mse_declared
    imp_diary = import_diary(imp_diary_raw, imp_prof.profile_id)
    assert len(imp_diary) == 1
    assert imp_diary[0].status == "Applied"
    assert imp_diary[0].note == "test note"


def test_import_rejects_invalid_json():
    with pytest.raises(ProfileValidationError, match="Invalid JSON"):
        import_profile_json("this is not json")


def test_import_diary_drops_invalid_status():
    bad_diary = [{"bid_number": "X", "title": "T", "status": "INVALID_STATUS"}]
    result = import_diary(bad_diary, "p1")
    assert len(result) == 0


def test_import_diary_accepts_valid_statuses():
    entries = [
        {"bid_number": f"B{i}", "title": f"T{i}", "status": s,
         "note": "", "date_recorded": "2026-10-03"}
        for i, s in enumerate(VALID_STATUSES)
    ]
    result = import_diary(entries, "p1")
    assert len(result) == len(VALID_STATUSES)


# ---------------------------------------------------------------------------
# closing_soon filter
# ---------------------------------------------------------------------------

def make_result(bid_number: str, days_left: float, verdict: str = "Bid") -> BidResult:
    return BidResult(
        bid_number=bid_number, title=f"Bid {bid_number}",
        score=80.0, verdict=verdict,
        chips=[], distance_km=50.0, days_left=days_left,
    )


def test_closing_soon_returns_within_threshold():
    results = [make_result("B1", 1.5), make_result("B2", 5.0), make_result("B3", 0.5)]
    soon = closing_soon(results, [], days_threshold=2.0)
    bid_nums = [r.bid_number for r in soon]
    assert "B1" in bid_nums
    assert "B3" in bid_nums
    assert "B2" not in bid_nums


def test_closing_soon_excludes_done_bids():
    ss = FakeSession()
    upsert_entry(ss, "p1", "B1", "Valve", "Won", "", "2026-10-03")
    results = [make_result("B1", 1.0), make_result("B2", 1.0)]
    diary = [DiaryEntry("B1", "Valve", "Won", "", "2026-10-03", "p1")]
    soon = closing_soon(results, diary, days_threshold=2.0)
    assert not any(r.bid_number == "B1" for r in soon)
    assert any(r.bid_number == "B2" for r in soon)


# ---------------------------------------------------------------------------
# to_scorer_profile conversion
# ---------------------------------------------------------------------------

def test_to_scorer_profile_shape():
    data = make_full_profile_data()
    prof, _ = validate_and_build(data)
    sp = prof.to_scorer_profile()
    assert "seller" in sp
    assert "items" in sp
    assert "adjacent_items" in sp
    assert sp["seller"]["delivery_radius_km"] == 250
    assert sp["seller"]["max_emd_inr"] == 50000
