"""
profiles.py – Profile model, validation, completeness, and I/O for BidMitra.

Profiles are stored in st.session_state only (no filesystem persistence).
Demo profiles are loaded from config/demo_profiles/*.yaml at startup.

HONESTY RULES enforced here:
  - Never use "Verified" or "Trusted" labels.
  - All declared fields are labelled "Self-declared" in the UI.
  - Win rate is only shown when applied_count >= 5.
  - No login, no identity numbers collected.
"""

from __future__ import annotations
import copy
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENTITY_TYPES = [
    "Sole Proprietorship", "Partnership", "LLP", "Pvt Ltd", "Public Ltd",
    "HUF", "Society / Trust", "Other",
]

# All fields that count toward completeness (exclude profile_id)
_COMPLETENESS_FIELDS = [
    "business_name", "base_location", "item_families", "delivery_radius_km",
    "max_emd_inr", "years_in_business", "entity_type",
    "mse_declared", "startup_declared", "certifications", "documents_declared",
]

MAX_STRING_LEN = 200
MAX_SYNONYMS = 50
MIN_RADIUS, MAX_RADIUS = 10, 3000
MIN_EMD, MAX_EMD = 0, 10_000_000
MIN_YEARS, MAX_YEARS = 0, 100


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SellerProfile:
    """Single seller profile – all user-declared, never verified."""

    profile_id: str                                # slug, auto-generated
    business_name: str = ""
    base_location: str = "Panipat, Haryana"        # "District, State"
    item_families: dict[str, list[str]] = field(default_factory=dict)
    adjacent_items: list[str] = field(default_factory=list)
    delivery_radius_km: float = 250.0
    max_emd_inr: float = 50000.0
    years_in_business: Optional[int] = None
    entity_type: str = ""
    mse_declared: bool = False
    startup_declared: bool = False
    certifications: list[str] = field(default_factory=list)   # ["ISO 9001", …]
    documents_declared: dict[str, bool] = field(default_factory=lambda: {
        "gst": False, "udyam": False, "iso": False, "other": False
    })

    def completeness_pct(self) -> int:
        """
        Percentage of profile fields that are meaningfully filled.
        Computed deterministically; used in the dashboard completeness bar.
        """
        filled = 0
        total = len(_COMPLETENESS_FIELDS)

        checks = {
            "business_name": bool(self.business_name.strip()),
            "base_location": bool(self.base_location.strip()),
            "item_families": bool(self.item_families),
            "delivery_radius_km": self.delivery_radius_km > 0,
            "max_emd_inr": self.max_emd_inr > 0,
            "years_in_business": self.years_in_business is not None,
            "entity_type": bool(self.entity_type.strip()),
            "mse_declared": self.mse_declared,
            "startup_declared": self.startup_declared,
            "certifications": bool(self.certifications),
            "documents_declared": any(self.documents_declared.values()),
        }
        # item_families counts as 2 sub-fields (has families + has synonyms)
        # to encourage completeness
        for f_name in _COMPLETENESS_FIELDS:
            if checks.get(f_name, False):
                filled += 1

        return round((filled / total) * 100)

    def completeness_suggestions(self) -> list[str]:
        """Return up to 3 friendly suggestions for improving the profile."""
        suggestions = []
        if not self.entity_type.strip():
            suggestions.append("Add your entity type (e.g. Sole Proprietorship)")
        if not self.certifications:
            suggestions.append("Add certifications (ISO, etc.) — may widen bid eligibility")
        if self.years_in_business is None:
            suggestions.append("Add years in business to complete your profile")
        if not any(self.documents_declared.values()):
            suggestions.append("Check the documents you have (GST, Udyam, etc.)")
        return suggestions[:3]

    def to_dict(self) -> dict:
        """Serialize to a plain dict (safe for JSON/YAML export)."""
        return asdict(self)

    def to_scorer_profile(self) -> dict:
        """Convert to the dict shape expected by scoring.score_bids()."""
        return {
            "seller": {
                "base_location": self.base_location,
                "delivery_radius_km": self.delivery_radius_km,
                "max_emd_inr": self.max_emd_inr,
            },
            "items": self.item_families,
            "adjacent_items": self.adjacent_items,
        }


def effective_profile(profile: SellerProfile, overrides: Optional[dict] = None) -> SellerProfile:
    """Return a copied profile with the supplied per-profile overrides applied."""
    effective = copy.deepcopy(profile)
    if not overrides:
        return effective

    if "delivery_radius_km" in overrides and overrides["delivery_radius_km"] is not None:
        effective.delivery_radius_km = float(overrides["delivery_radius_km"])
    if "max_emd_inr" in overrides and overrides["max_emd_inr"] is not None:
        effective.max_emd_inr = float(overrides["max_emd_inr"])

    active_families = overrides.get("active_families")
    if active_families is not None:
        allowed = [fam for fam in active_families if fam in profile.item_families]
        effective.item_families = {fam: profile.item_families.get(fam, []) for fam in allowed}
    return effective


def apply_profile_overrides(profile: SellerProfile, overrides: Optional[dict] = None) -> SellerProfile:
    """Backward-compatible alias for the effective profile helper."""
    return effective_profile(profile, overrides)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ProfileValidationError(ValueError):
    pass


def _str(val, field_name: str, max_len: int = MAX_STRING_LEN) -> str:
    if not isinstance(val, str):
        raise ProfileValidationError(f"'{field_name}' must be a string, got {type(val).__name__}")
    if len(val) > max_len:
        raise ProfileValidationError(f"'{field_name}' is too long (max {max_len} chars)")
    return val


def _float_in(val, field_name: str, lo: float, hi: float) -> float:
    try:
        v = float(val)
    except (TypeError, ValueError):
        raise ProfileValidationError(f"'{field_name}' must be a number")
    if not (lo <= v <= hi):
        raise ProfileValidationError(f"'{field_name}' must be between {lo} and {hi}, got {v}")
    return v


def validate_and_build(data: dict) -> tuple[SellerProfile, list[str]]:
    """
    Build a SellerProfile from a raw dict (from YAML or JSON import).
    Returns (profile, warnings). Raises ProfileValidationError on fatal errors.
    Unknown top-level keys are rejected.
    """
    KNOWN_KEYS = {
        "profile_id", "business_name", "base_location", "item_families",
        "adjacent_items", "delivery_radius_km", "max_emd_inr",
        "years_in_business", "entity_type", "mse_declared", "startup_declared",
        "certifications", "documents_declared",
    }
    unknown = set(data.keys()) - KNOWN_KEYS
    if unknown:
        raise ProfileValidationError(f"Unknown profile fields: {', '.join(sorted(unknown))}")

    warnings: list[str] = []

    profile_id = _str(data.get("profile_id", ""), "profile_id") or _make_id(data.get("business_name", ""))
    business_name = _str(data.get("business_name", ""), "business_name")
    base_location = _str(data.get("base_location", "Panipat, Haryana"), "base_location")

    # item_families
    raw_fams = data.get("item_families", {})
    if not isinstance(raw_fams, dict):
        raise ProfileValidationError("'item_families' must be a dict")
    item_families: dict[str, list[str]] = {}
    for fam, syns in raw_fams.items():
        _str(fam, f"item_families key '{fam}'")
        if not isinstance(syns, list):
            raise ProfileValidationError(f"Synonyms for '{fam}' must be a list")
        if len(syns) > MAX_SYNONYMS:
            warnings.append(f"Family '{fam}' has many synonyms (>{MAX_SYNONYMS}); truncated.")
            syns = syns[:MAX_SYNONYMS]
        item_families[fam] = [_str(s, f"synonym in '{fam}'") for s in syns]

    # adjacent_items
    raw_adj = data.get("adjacent_items", [])
    if not isinstance(raw_adj, list):
        raise ProfileValidationError("'adjacent_items' must be a list")
    adjacent_items = [_str(a, "adjacent_item") for a in raw_adj]

    radius   = _float_in(data.get("delivery_radius_km", 250), "delivery_radius_km", MIN_RADIUS, MAX_RADIUS)
    max_emd  = _float_in(data.get("max_emd_inr", 50000), "max_emd_inr", MIN_EMD, MAX_EMD)

    raw_years = data.get("years_in_business")
    years: Optional[int] = None
    if raw_years is not None:
        try:
            years = int(float(raw_years))
            if not (MIN_YEARS <= years <= MAX_YEARS):
                raise ProfileValidationError(f"'years_in_business' must be 0–{MAX_YEARS}")
        except (TypeError, ValueError):
            raise ProfileValidationError("'years_in_business' must be an integer")

    entity_type = _str(data.get("entity_type", ""), "entity_type")
    mse = bool(data.get("mse_declared", False))
    startup = bool(data.get("startup_declared", False))

    raw_certs = data.get("certifications", [])
    if not isinstance(raw_certs, list):
        raise ProfileValidationError("'certifications' must be a list")
    certifications = [_str(c, "certification") for c in raw_certs]

    raw_docs = data.get("documents_declared", {})
    if not isinstance(raw_docs, dict):
        raise ProfileValidationError("'documents_declared' must be a dict")
    docs_default = {"gst": False, "udyam": False, "iso": False, "other": False}
    docs: dict[str, bool] = {}
    for k in docs_default:
        docs[k] = bool(raw_docs.get(k, False))
    # Warn about unknown doc keys
    unknown_docs = set(raw_docs.keys()) - set(docs_default.keys())
    if unknown_docs:
        warnings.append(f"Unknown document keys ignored: {', '.join(sorted(unknown_docs))}")

    return SellerProfile(
        profile_id=profile_id,
        business_name=business_name,
        base_location=base_location,
        item_families=item_families,
        adjacent_items=adjacent_items,
        delivery_radius_km=radius,
        max_emd_inr=max_emd,
        years_in_business=years,
        entity_type=entity_type,
        mse_declared=mse,
        startup_declared=startup,
        certifications=certifications,
        documents_declared=docs,
    ), warnings


def _make_id(name: str) -> str:
    """Slug from business name, fallback to 'profile'."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower().strip())[:40]
    return slug or "profile"


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_profile_from_yaml(path: Path) -> tuple[SellerProfile, list[str]]:
    """Load a profile YAML file. Returns (profile, warnings). Raises on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ProfileValidationError(f"Profile file not found: {path}")
    except yaml.YAMLError as exc:
        raise ProfileValidationError(f"YAML parse error in {path.name}: {exc}")
    return validate_and_build(data)


def load_all_demo_profiles(demo_dir: Path) -> dict[str, SellerProfile]:
    """
    Load all *.yaml files from demo_dir.
    Returns {profile_id: SellerProfile}. Silently skips invalid files (prints warning).
    """
    profiles: dict[str, SellerProfile] = {}
    if not demo_dir.exists():
        return profiles
    for yaml_file in sorted(demo_dir.glob("*.yaml")):
        try:
            p, warns = load_profile_from_yaml(yaml_file)
            profiles[p.profile_id] = p
        except ProfileValidationError as exc:
            print(f"[BidMitra] Skipping demo profile {yaml_file.name}: {exc}")
    return profiles


# ---------------------------------------------------------------------------
# JSON import / export
# ---------------------------------------------------------------------------

def export_profile_json(profile: SellerProfile, diary: list[dict]) -> str:
    """Serialize profile + diary to JSON string for download."""
    data = profile.to_dict()
    data["bid_diary"] = diary
    return json.dumps(data, indent=2, default=str)


def import_profile_json(json_str: str) -> tuple[SellerProfile, list[dict], list[str]]:
    """
    Parse a JSON string exported by export_profile_json.
    Returns (profile, diary_rows, warnings). Raises ProfileValidationError on fatal errors.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ProfileValidationError(f"Invalid JSON: {exc}")

    diary = data.pop("bid_diary", [])
    if not isinstance(diary, list):
        diary = []

    profile, warnings = validate_and_build(data)
    return profile, diary, warnings
