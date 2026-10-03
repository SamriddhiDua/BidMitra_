"""
geo.py – Haversine distance helper for BidMitra.

Assumption: we compute distance from the seller's base district (looked up in
districts.csv) to the bid's consignee_district. If either district is unknown,
we return None and never crash.
"""

from __future__ import annotations
import math
import functools
from typing import Optional
import pandas as pd


# Earth radius in km
_EARTH_R_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in km between two lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_R_KM * math.asin(math.sqrt(a))


def _build_lookup(districts_df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Build a lower-cased district -> (lat, lon) lookup from the districts DataFrame."""
    lookup: dict[str, tuple[float, float]] = {}
    for _, row in districts_df.iterrows():
        key = str(row["district"]).strip().lower()
        lookup[key] = (float(row["lat"]), float(row["lon"]))
    return lookup


@functools.lru_cache(maxsize=1)
def _base_coords(base_district: str, districts_csv_path: str) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for the seller's base district, cached."""
    df = pd.read_csv(districts_csv_path, comment="#")
    lookup = _build_lookup(df)
    return lookup.get(base_district.strip().lower())


def distance_to_consignee(
    consignee_district: str,
    base_district: str,
    districts_df: pd.DataFrame,
) -> Optional[float]:
    """
    Return distance in km from base_district to consignee_district.
    Returns None if either district is not found in the lookup.
    Never raises.
    """
    try:
        lookup = _build_lookup(districts_df)
        base_key = base_district.strip().lower()
        dest_key = consignee_district.strip().lower()
        base = lookup.get(base_key)
        dest = lookup.get(dest_key)
        if base is None or dest is None:
            return None
        return haversine(base[0], base[1], dest[0], dest[1])
    except Exception:
        return None


def parse_base_location(base_location: str) -> str:
    """
    Extract the district name from 'District, State' format.
    Falls back to the full string if no comma is present.
    """
    parts = base_location.split(",", 1)
    return parts[0].strip()
