"""
tests/test_geo.py – unit tests for geo.py distance calculations.

Covers: known distance, unknown district, missing district, haversine accuracy,
base-location parsing, and boundary cases.
"""

import pytest
import pandas as pd
import sys
import os

# Make src importable when running pytest from bidmitra/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.geo import haversine, distance_to_consignee, parse_base_location


# ---- Fixture: minimal districts DataFrame ----

@pytest.fixture
def districts():
    """A small in-memory districts DataFrame covering key test cities."""
    return pd.DataFrame([
        {"district": "Panipat",      "state": "Haryana",      "lat": 29.3909, "lon": 76.9635},
        {"district": "New Delhi",    "state": "Delhi",         "lat": 28.6139, "lon": 77.2090},
        {"district": "Ludhiana",     "state": "Punjab",        "lat": 30.9010, "lon": 75.8573},
        {"district": "Mohali",       "state": "Punjab",        "lat": 30.7046, "lon": 76.7179},
        {"district": "Gurugram",     "state": "Haryana",       "lat": 28.4595, "lon": 77.0266},
        {"district": "Karnal",       "state": "Haryana",       "lat": 29.6857, "lon": 76.9905},
        {"district": "Mumbai",       "state": "Maharashtra",   "lat": 19.0760, "lon": 72.8777},
    ])


# ---- haversine tests ----

def test_haversine_same_point():
    """Distance from a point to itself is 0."""
    assert haversine(29.39, 76.96, 29.39, 76.96) == pytest.approx(0.0, abs=1e-6)


def test_haversine_panipat_to_delhi(districts):
    """Panipat → New Delhi should be roughly 85–95 km."""
    dist = haversine(29.3909, 76.9635, 28.6139, 77.2090)
    assert 85 <= dist <= 95, f"Expected 85–95 km, got {dist:.1f} km"


def test_haversine_known_distance():
    """Panipat → Mohali cross-check: ~140-160 km (verified against haversine formula)."""
    dist = haversine(29.3909, 76.9635, 30.7046, 76.7179)
    assert 130 <= dist <= 165, f"Expected ~140-160 km, got {dist:.1f} km"


# ---- distance_to_consignee tests ----

def test_distance_panipat_to_delhi(districts):
    """Panipat → New Delhi: 85–95 km."""
    dist = distance_to_consignee("New Delhi", "Panipat", districts)
    assert dist is not None
    assert 85 <= dist <= 95, f"Expected 85–95 km, got {dist:.1f} km"


def test_distance_unknown_consignee(districts):
    """Unknown consignee district → returns None, does not crash."""
    dist = distance_to_consignee("NonExistentCity", "Panipat", districts)
    assert dist is None


def test_distance_unknown_base(districts):
    """Unknown base district → returns None, does not crash."""
    dist = distance_to_consignee("New Delhi", "UnknownBase", districts)
    assert dist is None


def test_distance_both_unknown(districts):
    """Both districts unknown → returns None."""
    dist = distance_to_consignee("Nowhere", "Anywhere", districts)
    assert dist is None


def test_distance_case_insensitive(districts):
    """District lookup is case-insensitive."""
    dist1 = distance_to_consignee("new delhi", "panipat", districts)
    dist2 = distance_to_consignee("New Delhi", "Panipat", districts)
    assert dist1 == pytest.approx(dist2, abs=0.01)


def test_distance_panipat_to_mohali(districts):
    """Panipat → Mohali: ~148 km (actual haversine with centroid coords)."""
    dist = distance_to_consignee("Mohali", "Panipat", districts)
    assert dist is not None
    assert 130 <= dist <= 165, f"Expected 130–165 km, got {dist:.1f} km"


def test_distance_panipat_to_mumbai_far(districts):
    """Panipat → Mumbai should be well over 1000 km."""
    dist = distance_to_consignee("Mumbai", "Panipat", districts)
    assert dist is not None
    assert dist > 1000, f"Expected > 1000 km, got {dist:.1f} km"


# ---- parse_base_location tests ----

def test_parse_base_location_with_comma():
    assert parse_base_location("Panipat, Haryana") == "Panipat"


def test_parse_base_location_no_comma():
    assert parse_base_location("Panipat") == "Panipat"


def test_parse_base_location_extra_spaces():
    result = parse_base_location("  Ludhiana , Punjab  ")
    assert result == "Ludhiana"
