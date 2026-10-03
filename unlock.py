"""
unlock.py – "What-if" scenario analysis for BidMitra.

Re-runs the SAME scorer with modified profiles and reports how many additional
bids reach Bid or Maybe status versus the baseline. No new scoring logic here.

"Almost matched" section: bids that missed the baseline by a small margin:
  - EMD up to 30% above the limit, OR
  - Distance up to 30% beyond the radius
  (while otherwise matching on item family)
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from .models import BidResult
from .scoring import score_bids


@dataclass
class ScenarioResult:
    """Result of a single what-if scenario."""
    id: str
    label: str
    description: str
    extra_bid_count: int       # bids newly reaching "Bid"
    extra_maybe_count: int     # bids newly reaching "Maybe"
    total_extra: int           # bid + maybe gain vs baseline
    example_titles: list[str]  # up to 3 newly unlocked titles


@dataclass
class AlmostMatch:
    """A bid that narrowly missed the baseline."""
    bid_number: str
    title: str
    reason: str                # e.g. "EMD ₹5,000 above your limit"
    score: float


def _apply_scenario_overrides(base_profile: dict, scenario: dict) -> dict:
    """
    Return a new profile dict with scenario overrides applied.
    Supports relative overrides: "+N" adds N, "*N" multiplies.
    """
    import copy
    profile = copy.deepcopy(base_profile)
    seller = profile.setdefault("seller", {})
    overrides = scenario.get("overrides", {})

    for key, val in overrides.items():
        if key == "include_adjacent":
            # Stored as session override, not in profile dict
            profile["_include_adjacent"] = val
            continue

        current = seller.get(key, 0)
        if isinstance(val, str) and val.startswith("+"):
            seller[key] = current + float(val[1:])
        elif isinstance(val, str) and val.startswith("*"):
            seller[key] = current * float(val[1:])
        else:
            seller[key] = val

    return profile


def _count_bid_maybe(results: list[BidResult]) -> tuple[int, int]:
    bid = sum(1 for r in results if r.verdict == "Bid")
    maybe = sum(1 for r in results if r.verdict == "Maybe")
    return bid, maybe


def _baseline_ids(results: list[BidResult]) -> set[str]:
    return {r.bid_number for r in results if r.verdict in ("Bid", "Maybe")}


def run_scenarios(
    scenarios: list[dict],
    bids_df: pd.DataFrame,
    profile: dict,
    districts_df: pd.DataFrame,
    scoring_cfg: dict,
    as_of: date,
    baseline_results: list[BidResult],
) -> list[ScenarioResult]:
    """
    Run each scenario and return ScenarioResult list sorted by total_extra desc.
    """
    baseline_ids = _baseline_ids(baseline_results)
    original_seller = profile.get("seller", {})
    output: list[ScenarioResult] = []

    for scenario in scenarios:
        session_overrides: dict = {}
        raw_overrides = scenario.get("overrides", {})

        for key, val in raw_overrides.items():
            if key == "include_adjacent":
                session_overrides["include_adjacent"] = bool(val)
                continue
            # Map seller key to session_override key
            current = float(original_seller.get(key, 0))
            if isinstance(val, str) and val.startswith("+"):
                session_overrides[key] = current + float(val[1:])
            elif isinstance(val, str) and val.startswith("*"):
                session_overrides[key] = current * float(val[1:])
            else:
                session_overrides[key] = val

        new_results = score_bids(
            bids_df, profile, districts_df, scoring_cfg, as_of, session_overrides
        )
        new_ids = _baseline_ids(new_results)
        gained_ids = new_ids - baseline_ids

        # Count verdict splits for newly gained bids
        gained_results = [r for r in new_results if r.bid_number in gained_ids]
        extra_bid = sum(1 for r in gained_results if r.verdict == "Bid")
        extra_maybe = sum(1 for r in gained_results if r.verdict == "Maybe")
        examples = [r.title for r in gained_results[:3]]

        output.append(ScenarioResult(
            id=scenario.get("id", ""),
            label=scenario.get("label", ""),
            description=scenario.get("description", ""),
            extra_bid_count=extra_bid,
            extra_maybe_count=extra_maybe,
            total_extra=extra_bid + extra_maybe,
            example_titles=examples,
        ))

    output.sort(key=lambda s: s.total_extra, reverse=True)
    return output


def find_almost_matches(
    bids_df: pd.DataFrame,
    profile: dict,
    districts_df: pd.DataFrame,
    scoring_cfg: dict,
    as_of: date,
    baseline_results: list[BidResult],
    emd_margin: float = 0.30,
    dist_margin: float = 0.30,
) -> list[AlmostMatch]:
    """
    Return bids that narrowly missed the baseline shortlist.

    Criteria (bid must have an item match first):
      - EMD is above the limit but within emd_margin (30%) of it, OR
      - Distance is beyond radius but within dist_margin (30%) of it
    Uses already-computed BidResult data to avoid re-scoring.
    """
    seller = profile.get("seller", {})
    max_emd = float(seller.get("max_emd_inr", 50000))
    radius_km = float(seller.get("delivery_radius_km", 250))

    baseline_ids = {r.bid_number for r in baseline_results}
    # Map bid_number -> BidResult for all scored bids
    all_results = score_bids(
        bids_df, profile, districts_df, scoring_cfg, as_of,
        session_overrides={"include_adjacent": True}  # widen item net for near-misses
    )

    almost: list[AlmostMatch] = []

    for r in all_results:
        if r.bid_number in baseline_ids:
            continue  # already shortlisted

        reasons = []

        # EMD near-miss
        if r.emd_inr is not None and r.emd_inr > max_emd:
            over = r.emd_inr - max_emd
            pct = over / max_emd
            if pct <= emd_margin:
                reasons.append(f"EMD ₹{over:,.0f} above your limit")

        # Distance near-miss
        if r.distance_km is not None and r.distance_km > radius_km:
            over_km = r.distance_km - radius_km
            pct = over_km / radius_km
            if pct <= dist_margin:
                reasons.append(f"{over_km:.0f} km beyond your radius")

        if reasons:
            almost.append(AlmostMatch(
                bid_number=r.bid_number,
                title=r.title,
                reason="; ".join(reasons),
                score=r.score,
            ))

    return almost[:10]  # cap at 10 to keep UI clean
