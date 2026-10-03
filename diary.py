"""
diary.py – Bid Diary for BidMitra.

Stores per-profile bid status entries in session_state only.
All data is self-reported; it is never presented as data from GeM.

Entry schema:
  bid_number, title, status, note, date_recorded, profile_id
Statuses: Saved | Applied | Won | Lost | Skipped
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional


VALID_STATUSES = ("Saved", "Applied", "Won", "Lost", "Skipped")


@dataclass
class DiaryEntry:
    """One bid diary record. All self-reported in BidMitra."""
    bid_number: str
    title: str
    status: str                     # one of VALID_STATUSES
    note: str = ""
    date_recorded: str = ""         # ISO date string
    profile_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Diary stats (used by the Dashboard)
# ---------------------------------------------------------------------------

@dataclass
class DiaryStats:
    saved: int = 0
    applied: int = 0
    won: int = 0
    lost: int = 0
    skipped: int = 0
    win_rate_pct: Optional[float] = None   # None when applied < 5
    win_rate_note: str = ""


def compute_stats(entries: list[DiaryEntry]) -> DiaryStats:
    """
    Compute diary stats for a single profile's entries.
    Win rate shown only when applied >= 5 (honesty rule).
    """
    stats = DiaryStats(
        saved=sum(1 for e in entries if e.status == "Saved"),
        applied=sum(1 for e in entries if e.status == "Applied"),
        won=sum(1 for e in entries if e.status == "Won"),
        lost=sum(1 for e in entries if e.status == "Lost"),
        skipped=sum(1 for e in entries if e.status == "Skipped"),
    )
    # Win rate requires at least 5 applied bids (spec requirement)
    if stats.applied >= 5:
        stats.win_rate_pct = round((stats.won / stats.applied) * 100, 1)
        stats.win_rate_note = "self-reported in BidMitra"
    else:
        stats.win_rate_pct = None
        stats.win_rate_note = f"not enough data (need 5 applied, have {stats.applied})"
    return stats


# ---------------------------------------------------------------------------
# Session-state helpers (called from app.py)
# ---------------------------------------------------------------------------

def diary_key(profile_id: str) -> str:
    """Session-state key for a profile's diary list."""
    return f"diary_{profile_id}"


def get_diary(session_state: dict, profile_id: str) -> list[DiaryEntry]:
    """Return the diary list for a profile, creating it if needed."""
    key = diary_key(profile_id)
    if key not in session_state:
        session_state[key] = []
    return session_state[key]


def upsert_entry(
    session_state: dict,
    profile_id: str,
    bid_number: str,
    title: str,
    status: str,
    note: str = "",
    recorded_date: Optional[str] = None,
) -> None:
    """Add or update a diary entry for a bid. Idempotent by bid_number."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status!r}. Must be one of {VALID_STATUSES}")
    entries = get_diary(session_state, profile_id)
    date_str = recorded_date or date.today().isoformat()
    # Update existing entry or append
    for entry in entries:
        if entry.bid_number == bid_number:
            entry.status = status
            entry.note = note
            entry.date_recorded = date_str
            return
    entries.append(DiaryEntry(
        bid_number=bid_number,
        title=title,
        status=status,
        note=note,
        date_recorded=date_str,
        profile_id=profile_id,
    ))


def remove_entry(session_state: dict, profile_id: str, bid_number: str) -> None:
    """Remove a diary entry if it exists."""
    entries = get_diary(session_state, profile_id)
    session_state[diary_key(profile_id)] = [
        e for e in entries if e.bid_number != bid_number
    ]


def get_entry(session_state: dict, profile_id: str, bid_number: str) -> Optional[DiaryEntry]:
    """Return an entry by bid_number, or None."""
    for e in get_diary(session_state, profile_id):
        if e.bid_number == bid_number:
            return e
    return None


def export_diary(entries: list[DiaryEntry]) -> list[dict]:
    """Serialize diary for JSON export."""
    return [e.to_dict() for e in entries]


def import_diary(raw: list[dict], profile_id: str) -> list[DiaryEntry]:
    """
    Deserialize diary from imported JSON.
    Silently drops entries with invalid status.
    """
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        status = item.get("status", "")
        if status not in VALID_STATUSES:
            continue
        result.append(DiaryEntry(
            bid_number=str(item.get("bid_number", "")),
            title=str(item.get("title", "")),
            status=status,
            note=str(item.get("note", "")),
            date_recorded=str(item.get("date_recorded", "")),
            profile_id=profile_id,
        ))
    return result


def closing_soon(
    results: list,          # list[BidResult] from scoring.py
    diary_entries: list[DiaryEntry],
    days_threshold: float = 2.0,
) -> list:
    """
    Return scored bids closing within `days_threshold` days,
    excluding bids the user has already marked as Won/Lost/Skipped.
    """
    done_ids = {e.bid_number for e in diary_entries if e.status in ("Won", "Lost", "Skipped")}
    return [
        r for r in results
        if r.days_left is not None
        and 0 <= r.days_left <= days_threshold
        and r.bid_number not in done_ids
    ]
