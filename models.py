"""
models.py – shared dataclasses used across scoring, unlock, and the UI.
Keep this file free of business logic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chip:
    """A reason chip shown on a bid card."""
    text: str                  # human-readable label
    level: str                 # "good" | "warn" | "bad"

    @property
    def emoji(self) -> str:
        return {"good": "✅", "warn": "⚠️", "bad": "❌"}.get(self.level, "ℹ️")

    def __str__(self) -> str:
        return f"{self.emoji} {self.text}"


@dataclass
class BidResult:
    """Scoring result for a single bid row."""
    bid_number: str
    title: str
    score: float               # 0–100
    verdict: str               # "Bid" | "Maybe" | "Skip" | "Hidden"
    chips: list[Chip] = field(default_factory=list)
    distance_km: Optional[float] = None
    days_left: Optional[float] = None

    # Pass-through display fields (raw from DataFrame)
    buyer_org: str = ""
    consignee_state: str = ""
    consignee_district: str = ""
    emd_inr: Optional[float] = None
    end_datetime: str = ""
    doc_url: str = ""
    data_source: str = ""
