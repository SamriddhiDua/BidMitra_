"""
data_loader.py – CSV loading with validation for BidMitra.

All I/O goes through this module. Returns a (DataFrame, errors) tuple so the UI
can show friendly errors instead of stack traces.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import pandas as pd
import yaml

# Columns that MUST exist in bids.csv
REQUIRED_COLUMNS = {
    "bid_number",
    "title",
    "quantity",
    "consignee_state",
    "consignee_district",
    "buyer_org",
    "emd_inr",
    "end_datetime",
    "doc_url",
    "data_source",
}


def load_bids(csv_path: str | Path) -> tuple[Optional[pd.DataFrame], list[str]]:
    """
    Load bids.csv and validate required columns.

    Returns (DataFrame, []) on success, or (None, [error_message]) on failure.
    Never raises.
    """
    errors: list[str] = []
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        errors.append(f"bids.csv not found at {csv_path}. Run scripts/make_sample_data.py to generate sample data.")
        return None, errors
    except Exception as exc:
        errors.append(f"Could not read bids.csv: {exc}")
        return None, errors

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"bids.csv is missing required columns: {', '.join(sorted(missing))}")
        return None, errors

    # Normalise types quietly
    df["emd_inr"] = pd.to_numeric(df["emd_inr"], errors="coerce")
    df["end_datetime"] = pd.to_datetime(df["end_datetime"], errors="coerce", utc=True)
    df["title"] = df["title"].fillna("").astype(str)
    df["bid_number"] = df["bid_number"].fillna("").astype(str)
    df["consignee_district"] = df["consignee_district"].fillna("").astype(str)
    df["consignee_state"] = df["consignee_state"].fillna("").astype(str)
    df["buyer_org"] = df["buyer_org"].fillna("").astype(str)
    df["doc_url"] = df["doc_url"].fillna("").astype(str)
    df["data_source"] = df["data_source"].fillna("").astype(str)

    return df, []


def load_districts(csv_path: str | Path) -> tuple[Optional[pd.DataFrame], list[str]]:
    """Load districts.csv, ignoring comment lines. Returns (df, errors)."""
    errors: list[str] = []
    try:
        df = pd.read_csv(csv_path, comment="#")
        needed = {"district", "state", "lat", "lon"}
        missing = needed - set(df.columns)
        if missing:
            errors.append(f"districts.csv missing columns: {', '.join(sorted(missing))}")
            return None, errors
        return df, []
    except FileNotFoundError:
        errors.append(f"districts.csv not found at {csv_path}.")
        return None, errors
    except Exception as exc:
        errors.append(f"Could not read districts.csv: {exc}")
        return None, errors


def load_snapshot_meta(yaml_path: str | Path) -> dict:
    """Load snapshot_meta.yaml; returns {} on any error."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_profile(yaml_path: str | Path) -> dict:
    """Load profile.yaml; returns {} on any error."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_scoring_config(yaml_path: str | Path) -> dict:
    """Load scoring.yaml; returns {} on any error."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_scenarios(yaml_path: str | Path) -> list[dict]:
    """Load scenarios.yaml; returns [] on any error."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data.get("scenarios", [])
    except Exception:
        return []
