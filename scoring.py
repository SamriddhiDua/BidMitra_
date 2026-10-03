"""
scoring.py – deterministic bid scorer for BidMitra.

The scorer is purely functional: given a profile dict and a bids DataFrame,
it returns a list of BidResult objects. No AI, no randomness, no I/O.

Scoring dimensions (weights from scoring.yaml):
  item     35 – keyword match against item families and adjacent items
  location 30 – haversine distance vs delivery radius
  emd      20 – EMD vs max_emd_inr
  time     15 – days until closing vs snapshot as_of date

Verdicts: Bid >= 70, Maybe 40-69, Skip < 40.
Hidden bids (wrong item family, already closed) are excluded from results.
"""

from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional
import re

import pandas as pd

from .models import BidResult, Chip
from .geo import distance_to_consignee, parse_base_location


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _words_in(text: str) -> set[str]:
    """Return lower-cased tokens from text for whole-phrase matching."""
    return set(re.findall(r"[a-z0-9 ]+", text.lower()))


def _phrase_in_title(phrase: str, title_lower: str) -> bool:
    """Return True if the phrase appears as a whole word/phrase in title."""
    escaped = re.escape(phrase.lower())
    return bool(re.search(r"\b" + escaped + r"\b", title_lower))


# ---------------------------------------------------------------------------
# Per-dimension scorers (each returns (raw_score 0-1, list[Chip]))
# ---------------------------------------------------------------------------

def _score_item(
    title: str,
    families: dict[str, list[str]],
    adjacent_items: list[str],
    include_adjacent: bool,
) -> tuple[Optional[float], list[Chip]]:
    """
    Returns (score, chips).
    Returns (None, chips) when the bid should be HIDDEN (no item match at all).
    Score 1.0 for family match, 0.5 for adjacent-only match.
    """
    title_lower = title.lower()
    chips: list[Chip] = []

    # Check primary families
    for family_name, synonyms in families.items():
        for syn in synonyms:
            if _phrase_in_title(syn, title_lower):
                chips.append(Chip(f"Matched: {family_name}", "good"))
                return 1.0, chips

    # Check adjacent items
    for adj in adjacent_items:
        if _phrase_in_title(adj, title_lower):
            if include_adjacent:
                chips.append(Chip("Adjacent item", "warn"))
                return 0.5, chips
            else:
                # Adjacent match but not enabled: hide the bid
                return None, [Chip("Adjacent item (disabled)", "bad")]

    # No match at all → hide
    return None, []


def _score_location(
    consignee_district: str,
    base_district: str,
    radius_km: float,
    districts_df: pd.DataFrame,
) -> tuple[float, list[Chip], Optional[float]]:
    """Returns (score, chips, distance_km)."""
    chips: list[Chip] = []
    dist = distance_to_consignee(consignee_district, base_district, districts_df)

    if dist is None:
        chips.append(Chip("Check location", "warn"))
        return 0.5, chips, None

    dist_rounded = round(dist, 1)
    if dist <= radius_km:
        score = 1.0 - 0.5 * (dist / radius_km)
        chips.append(Chip(f"Consignee {consignee_district}, {dist_rounded:.0f} km", "good"))
    else:
        score = 0.0
        chips.append(Chip(f"Far ({dist_rounded:.0f} km, limit {radius_km:.0f} km)", "bad"))

    return score, chips, dist


def _score_emd(
    emd_inr: Optional[float],
    max_emd_inr: float,
) -> tuple[float, list[Chip]]:
    """Returns (score, chips)."""
    chips: list[Chip] = []
    if emd_inr is None or pd.isna(emd_inr):
        chips.append(Chip("Check EMD", "warn"))
        return 0.5, chips
    if emd_inr <= max_emd_inr:
        chips.append(Chip(f"EMD ₹{emd_inr:,.0f} (within limit)", "good"))
        return 1.0, chips
    else:
        over = emd_inr - max_emd_inr
        chips.append(Chip(f"EMD ₹{emd_inr:,.0f} (₹{over:,.0f} over limit)", "bad"))
        return 0.0, chips


def _score_time(
    end_datetime: pd.Timestamp,
    as_of: date,
    time_cfg: dict,
) -> tuple[Optional[float], list[Chip], Optional[float]]:
    """
    Returns (score, chips, days_left).
    Returns (None, chips, days_left) when bid is already closed → HIDDEN.
    """
    chips: list[Chip] = []

    if pd.isna(end_datetime):
        chips.append(Chip("Check closing date", "warn"))
        return 0.5, chips, None

    as_of_dt = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)
    delta = end_datetime - as_of_dt
    days_left = delta.total_seconds() / 86400

    if days_left < 0:
        # Already closed
        chips.append(Chip("Bid closed", "bad"))
        return None, chips, days_left

    closing_soon = time_cfg.get("closing_soon_max", 1)
    urgent = time_cfg.get("urgent_max", 2)
    ideal = time_cfg.get("ideal_max", 6)

    if days_left < closing_soon:
        score = 0.0
        chips.append(Chip(f"Closing very soon ({days_left:.1f} days)", "bad"))
    elif days_left <= urgent:
        score = 0.4
        chips.append(Chip(f"Urgent ({days_left:.1f} days)", "warn"))
    elif days_left <= ideal:
        score = 1.0
        chips.append(Chip(f"{days_left:.0f} days left", "good"))
    else:
        score = 0.8
        chips.append(Chip(f"{days_left:.0f} days left", "good"))

    return score, chips, days_left


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def score_bids(
    bids_df: pd.DataFrame,
    profile: dict,
    districts_df: pd.DataFrame,
    scoring_cfg: dict,
    as_of: date,
    session_overrides: Optional[dict] = None,
) -> list[BidResult]:
    """
    Score all bids and return BidResult list (Hidden bids excluded).

    session_overrides keys (all optional):
      delivery_radius_km, max_emd_inr, include_adjacent,
      item_families (dict), active_families (list[str])
    """
    overrides = session_overrides or {}

    # ---- Profile extraction ----
    seller = profile.get("seller", {})
    base_location = overrides.get("base_location", seller.get("base_location", "Panipat, Haryana"))
    base_district = parse_base_location(base_location)

    radius_km = float(overrides.get("delivery_radius_km", seller.get("delivery_radius_km", 250)))
    max_emd = float(overrides.get("max_emd_inr", seller.get("max_emd_inr", 50000)))
    include_adjacent = bool(overrides.get("include_adjacent", False))

    # Item families from profile, possibly filtered by session
    all_families: dict[str, list[str]] = profile.get("items", {})
    active_families_override: Optional[list[str]] = overrides.get("active_families")
    if active_families_override is not None:
        families = {k: v for k, v in all_families.items() if k in active_families_override}
    else:
        families = all_families

    adjacent_items: list[str] = profile.get("adjacent_items", [])

    # Scoring config
    weights = scoring_cfg.get("weights", {"item": 35, "location": 30, "emd": 20, "time": 15})
    time_cfg = scoring_cfg.get("time_scoring", {})
    thresholds = scoring_cfg.get("thresholds", {"bid": 70, "maybe": 40})

    results: list[BidResult] = []

    for _, row in bids_df.iterrows():
        title = str(row.get("title", ""))

        # --- Item scoring ---
        item_score, item_chips = _score_item(title, families, adjacent_items, include_adjacent)
        if item_score is None:
            continue  # Hidden: no item match

        # --- Location scoring ---
        loc_score, loc_chips, dist_km = _score_location(
            str(row.get("consignee_district", "")),
            base_district,
            radius_km,
            districts_df,
        )

        # --- EMD scoring ---
        emd_val = row.get("emd_inr")
        emd_inr_float = float(emd_val) if pd.notna(emd_val) else None
        emd_score, emd_chips = _score_emd(emd_inr_float, max_emd)

        # --- Time scoring ---
        time_score, time_chips, days_left = _score_time(
            row.get("end_datetime"),
            as_of,
            time_cfg,
        )
        if time_score is None:
            continue  # Hidden: already closed

        # --- Weighted total ---
        w_item = weights.get("item", 35)
        w_loc = weights.get("location", 30)
        w_emd = weights.get("emd", 20)
        w_time = weights.get("time", 15)
        total_w = w_item + w_loc + w_emd + w_time

        raw = (item_score * w_item + loc_score * w_loc + emd_score * w_emd + time_score * w_time)
        score = round((raw / total_w) * 100, 1)

        # --- Verdict ---
        if score >= thresholds.get("bid", 70):
            verdict = "Bid"
        elif score >= thresholds.get("maybe", 40):
            verdict = "Maybe"
        else:
            verdict = "Skip"

        all_chips = item_chips + loc_chips + emd_chips + time_chips

        results.append(BidResult(
            bid_number=str(row.get("bid_number", "")),
            title=title,
            score=score,
            verdict=verdict,
            chips=all_chips,
            distance_km=dist_km,
            days_left=days_left,
            buyer_org=str(row.get("buyer_org", "")),
            consignee_state=str(row.get("consignee_state", "")),
            consignee_district=str(row.get("consignee_district", "")),
            emd_inr=emd_inr_float,
            end_datetime=str(row.get("end_datetime", "")),
            doc_url=str(row.get("doc_url", "")),
            data_source=str(row.get("data_source", "")),
        ))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    return results
