"""
tests/test_scoring.py – unit tests for scoring.py.

Covers: item match/hidden, adjacent items, location scoring, EMD scoring,
time scoring, verdict thresholds, unknown values, and boundary conditions.
"""

import pytest
import pandas as pd
from datetime import date, datetime, timezone, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scoring import (
    _score_item, _score_location, _score_emd, _score_time, score_bids
)


# ---- Fixtures ----

@pytest.fixture
def districts():
    return pd.DataFrame([
        {"district": "Panipat",   "state": "Haryana",    "lat": 29.3909, "lon": 76.9635},
        {"district": "New Delhi", "state": "Delhi",      "lat": 28.6139, "lon": 77.2090},
        {"district": "Ludhiana", "state": "Punjab",      "lat": 30.9010, "lon": 75.8573},
        {"district": "Mumbai",    "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
        {"district": "Karnal",    "state": "Haryana",    "lat": 29.6857, "lon": 76.9905},
    ])


@pytest.fixture
def profile():
    return {
        "seller": {
            "base_location": "Panipat, Haryana",
            "delivery_radius_km": 250,
            "max_emd_inr": 50000,
        },
        "items": {
            "timing_belts": ["timing belt", "synchronous belt"],
            "valves": ["gate valve", "ball valve", "check valve"],
        },
        "adjacent_items": ["bearing", "gasket"],
    }


@pytest.fixture
def scoring_cfg():
    return {
        "weights": {"item": 35, "location": 30, "emd": 20, "time": 15},
        "thresholds": {"bid": 70, "maybe": 40},
        "time_scoring": {"closing_soon_max": 1, "urgent_max": 2, "ideal_max": 6},
    }


AS_OF = date(2026, 10, 3)


def make_dt(days_from_now: float) -> pd.Timestamp:
    """Create a UTC timestamp N days from AS_OF."""
    base = datetime(2026, 10, 3, tzinfo=timezone.utc)
    return pd.Timestamp(base + timedelta(days=days_from_now))


def make_bid_df(**kwargs) -> pd.DataFrame:
    """Build a single-row bids DataFrame with sensible defaults."""
    defaults = {
        "bid_number": "BID001",
        "title": "Supply of timing belt",
        "quantity": "10",
        "consignee_state": "Haryana",
        "consignee_district": "Karnal",
        "buyer_org": "Test Org",
        "emd_inr": 30000.0,
        "end_datetime": make_dt(5),
        "doc_url": "https://gem.gov.in/test",
        "data_source": "SAMPLE",
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


# ---- _score_item tests ----

def test_item_primary_match():
    """Exact family match → score 1.0."""
    families = {"valves": ["gate valve", "ball valve"]}
    score, chips = _score_item("Supply of gate valve", families, [], False)
    assert score == 1.0
    assert any("Matched" in c.text for c in chips)


def test_item_no_match_hidden():
    """No match → hidden (None)."""
    families = {"valves": ["gate valve"]}
    score, chips = _score_item("Supply of chairs", families, [], False)
    assert score is None


def test_item_adjacent_enabled():
    """Adjacent match with include_adjacent=True → 0.5."""
    families = {"valves": ["gate valve"]}
    score, chips = _score_item("Supply of bearing", families, ["bearing"], True)
    assert score == 0.5
    assert any("Adjacent" in c.text for c in chips)


def test_item_adjacent_disabled_hidden():
    """Adjacent match with include_adjacent=False → hidden."""
    families = {"valves": ["gate valve"]}
    score, chips = _score_item("Supply of bearing", families, ["bearing"], False)
    assert score is None


def test_item_case_insensitive():
    """Matching is case-insensitive."""
    families = {"belts": ["timing belt"]}
    score, _ = _score_item("TIMING BELT supply", families, [], False)
    assert score == 1.0


# ---- _score_location tests ----

def test_location_within_radius(districts):
    """Karnal is ~30 km from Panipat → within 250 km, score > 0.5."""
    score, chips, dist = _score_location("Karnal", "Panipat", 250, districts)
    assert 0.5 < score <= 1.0
    assert dist is not None and dist < 250
    assert any(c.level == "good" for c in chips)


def test_location_beyond_radius(districts):
    """Mumbai is ~1400 km → beyond 250 km, score 0."""
    score, chips, dist = _score_location("Mumbai", "Panipat", 250, districts)
    assert score == 0.0
    assert dist is not None and dist > 250
    assert any(c.level == "bad" for c in chips)


def test_location_unknown_district(districts):
    """Unknown district → score 0.5, 'Check location' chip."""
    score, chips, dist = _score_location("UnknownTown", "Panipat", 250, districts)
    assert score == 0.5
    assert dist is None
    assert any("Check location" in c.text for c in chips)


def test_location_score_decreases_with_distance(districts):
    """Farther (but in-radius) consignee → lower score than nearer."""
    score_near, _, _ = _score_location("Karnal", "Panipat", 250, districts)
    score_far, _, _ = _score_location("Ludhiana", "Panipat", 500, districts)
    # Ludhiana is ~180 km, Karnal is ~30 km; both in radius but Ludhiana gets lower
    score_ludhiana_250, _, _ = _score_location("Ludhiana", "Panipat", 250, districts)
    assert score_near > score_ludhiana_250


# ---- _score_emd tests ----

def test_emd_within_limit():
    """EMD under max → score 1.0."""
    score, chips = _score_emd(30000, 50000)
    assert score == 1.0
    assert any(c.level == "good" for c in chips)


def test_emd_exactly_at_limit():
    """EMD exactly at max → score 1.0."""
    score, _ = _score_emd(50000, 50000)
    assert score == 1.0


def test_emd_above_limit():
    """EMD above max → score 0."""
    score, chips = _score_emd(60000, 50000)
    assert score == 0.0
    assert any(c.level == "bad" for c in chips)


def test_emd_missing():
    """Missing EMD → score 0.5, 'Check EMD' chip."""
    score, chips = _score_emd(None, 50000)
    assert score == 0.5
    assert any("Check EMD" in c.text for c in chips)


# ---- _score_time tests ----

TIME_CFG = {"closing_soon_max": 1, "urgent_max": 2, "ideal_max": 6}


def test_time_already_closed():
    """Bid already closed → hidden (None)."""
    score, _, _ = _score_time(make_dt(-1), AS_OF, TIME_CFG)
    assert score is None


def test_time_closing_very_soon():
    """0.5 days left → score 0, 'Closing very soon'."""
    score, chips, _ = _score_time(make_dt(0.5), AS_OF, TIME_CFG)
    assert score == 0.0
    assert any("Closing very soon" in c.text for c in chips)


def test_time_urgent():
    """1.5 days left → score 0.4."""
    score, _, _ = _score_time(make_dt(1.5), AS_OF, TIME_CFG)
    assert score == pytest.approx(0.4)


def test_time_ideal():
    """5 days left → score 1.0."""
    score, _, _ = _score_time(make_dt(5), AS_OF, TIME_CFG)
    assert score == pytest.approx(1.0)


def test_time_plenty():
    """10 days left → score 0.8."""
    score, _, _ = _score_time(make_dt(10), AS_OF, TIME_CFG)
    assert score == pytest.approx(0.8)


def test_time_missing():
    """Missing datetime → score 0.5, 'Check closing date'."""
    score, chips, _ = _score_time(pd.NaT, AS_OF, TIME_CFG)
    assert score == pytest.approx(0.5)
    assert any("Check closing date" in c.text for c in chips)


# ---- Integration: score_bids ----

def test_score_bids_bid_verdict(profile, districts, scoring_cfg):
    """A well-matching bid should get 'Bid' verdict."""
    df = make_bid_df(title="Supply of timing belt", consignee_district="Karnal",
                     emd_inr=30000, end_datetime=make_dt(5))
    results = score_bids(df, profile, districts, scoring_cfg, AS_OF)
    assert len(results) == 1
    assert results[0].verdict == "Bid"


def test_score_bids_hidden_wrong_item(profile, districts, scoring_cfg):
    """Wrong item family → bid is hidden, not returned."""
    df = make_bid_df(title="Supply of office chairs")
    results = score_bids(df, profile, districts, scoring_cfg, AS_OF)
    assert len(results) == 0


def test_score_bids_hidden_closed(profile, districts, scoring_cfg):
    """Closed bid → hidden, not returned."""
    df = make_bid_df(title="Supply of timing belt", end_datetime=make_dt(-2))
    results = score_bids(df, profile, districts, scoring_cfg, AS_OF)
    assert len(results) == 0


def test_score_bids_sorted_by_score(profile, districts, scoring_cfg):
    """Results are sorted highest score first."""
    df = pd.concat([
        make_bid_df(bid_number="B1", title="Supply of timing belt",
                    consignee_district="Karnal", emd_inr=20000, end_datetime=make_dt(5)),
        make_bid_df(bid_number="B2", title="Supply of ball valve",
                    consignee_district="Mumbai", emd_inr=80000, end_datetime=make_dt(5)),
    ], ignore_index=True)
    df["end_datetime"] = pd.to_datetime(df["end_datetime"], utc=True)
    results = score_bids(df, profile, districts, scoring_cfg, AS_OF)
    if len(results) >= 2:
        assert results[0].score >= results[1].score


def test_score_bids_unknown_district_neutral(profile, districts, scoring_cfg):
    """Unknown district → not hidden, gets a neutral 0.5 location score."""
    df = make_bid_df(title="Supply of timing belt",
                     consignee_district="UnknownTown", emd_inr=30000, end_datetime=make_dt(5))
    results = score_bids(df, profile, districts, scoring_cfg, AS_OF)
    assert len(results) == 1
    assert any("Check location" in c.text for c in results[0].chips)
