"""
app.py – BidMitra Streamlit application (Feature P: Seller Profiles & Dashboard).

Tabs: Dashboard | Shortlist | What-If | About
Profile switcher in sidebar; all state in session_state (no DB, no auth).

HONESTY RULES enforced in UI:
  - Never show "Verified" or "Trusted" as an active label.
  - All user-entered data is labelled "Self-declared".
  - Win rate only shown when applied >= 5.
  - "Demo: no authentication" note always visible.
"""

from __future__ import annotations
import copy
import json
import os
import sys
from pathlib import Path
from datetime import date

import streamlit as st
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.data_loader import (
    load_bids, load_districts, load_snapshot_meta,
    load_scoring_config, load_scenarios,
)
from src.scoring import score_bids
from src.unlock import run_scenarios, find_almost_matches
from src import llm as llm_module
from src.nlquery import parse_query, filter_to_session_overrides
from src.models import BidResult
from src.profiles import (
    SellerProfile, apply_profile_overrides, effective_profile as compute_effective_profile,
    validate_and_build, load_all_demo_profiles, export_profile_json, import_profile_json,
    ProfileValidationError,
)
from src.diary import (
    get_diary, upsert_entry, remove_entry, get_entry,
    compute_stats, export_diary, import_diary, closing_soon,
    VALID_STATUSES,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR    = ROOT / "data"
CONFIG_DIR  = ROOT / "config"
BIDS_CSV    = DATA_DIR / "bids.csv"
DISTRICTS_CSV = DATA_DIR / "districts.csv"
META_YAML   = DATA_DIR / "snapshot_meta.yaml"
SCORING_YAML  = CONFIG_DIR / "scoring.yaml"
SCENARIOS_YAML = CONFIG_DIR / "scenarios.yaml"
DEMO_PROFILES_DIR = CONFIG_DIR / "demo_profiles"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BidMitra – GeM Bid Shortlister",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Target text elements only — avoid overriding Streamlit internals like expander arrows */
html, body, [class*="css"], .stMarkdown, .stTextInput, .stNumberInput,
.stSelectbox, .stSlider, .stButton, .stDataFrame, .stMetric,
.stExpander, .stTabs, .stSidebar, p, span, div, h1, h2, h3, h4, h5, h6, label {
    font-family: 'Inter', sans-serif;
}

.badge-bid   { background:#16a34a; color:#fff; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; }
.badge-maybe { background:#d97706; color:#fff; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; }
.badge-skip  { background:#6b7280; color:#fff; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; }

.chip-good { background:#dcfce7; color:#15803d; border:1px solid #86efac; padding:2px 8px; border-radius:999px; font-size:0.75rem; margin:2px; display:inline-block; }
.chip-warn { background:#fef9c3; color:#92400e; border:1px solid #fde047; padding:2px 8px; border-radius:999px; font-size:0.75rem; margin:2px; display:inline-block; }
.chip-bad  { background:#fee2e2; color:#991b1b; border:1px solid #fca5a5; padding:2px 8px; border-radius:999px; font-size:0.75rem; margin:2px; display:inline-block; }
.chip-neutral { background:#f3f4f6; color:#374151; border:1px solid #d1d5db; padding:2px 8px; border-radius:999px; font-size:0.75rem; margin:2px; display:inline-block; }

.bid-card { border:1px solid #e5e7eb; border-radius:10px; padding:14px 16px; margin-bottom:10px; background:#fff; }
.bid-card:hover { border-color:#6366f1; box-shadow: 0 2px 12px rgba(99,102,241,0.10); }

.banner-snapshot { background:#1e3a5f; color:#e0f0ff; padding:8px 14px; border-radius:8px; font-size:0.82rem; margin-bottom:8px; }
.banner-sample   { background:#7f1d1d; color:#fee2e2; padding:8px 14px; border-radius:8px; font-size:0.82rem; margin-bottom:8px; font-weight:600; }
.banner-demo-auth { background:#312e81; color:#e0e7ff; padding:6px 14px; border-radius:8px; font-size:0.78rem; margin-bottom:8px; }

.ai-badge { background:linear-gradient(135deg,#312e81,#4f46e5); color:#e0e7ff; padding:6px 14px; border-radius:8px; font-size:0.8rem; font-weight:500; }

.score-bar-outer { background:#e5e7eb; border-radius:999px; height:6px; width:100%; margin:4px 0; }
.score-bar-inner { border-radius:999px; height:6px; }

.completeness-bar-outer { background:#e5e7eb; border-radius:999px; height:12px; width:100%; }
.completeness-bar-inner { border-radius:999px; height:12px; transition: width 0.4s; }

.profile-card { border:2px solid #6366f1; border-radius:12px; padding:16px; background:linear-gradient(135deg,#f5f3ff,#ede9fe); margin-bottom:12px; }
.diary-strip  { background:#fafafa; border:1px solid #e5e7eb; border-radius:8px; padding:10px 14px; margin:4px 0; }
.closing-soon-card { background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:8px 12px; margin:4px 0; }
.metric-panel { background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; padding:16px 14px; height:100%; box-shadow:0 1px 2px rgba(15,23,42,0.04); }
.metric-title { color:#6b7280; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:10px; font-weight:700; }
.metric-number { font-size:2rem; font-weight:700; line-height:1.1; color:#111827; margin:0; }
.metric-subtext { color:#6b7280; font-size:0.78rem; margin-top:8px; }
.metric-split { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }
.metric-split-value { font-size:1.35rem; font-weight:700; color:#111827; }
.metric-split-label { font-size:0.74rem; color:#6b7280; text-transform:uppercase; letter-spacing:0.05em; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _load_static():
    bids_df, bids_err = load_bids(BIDS_CSV)
    dist_df, dist_err = load_districts(DISTRICTS_CSV)
    meta              = load_snapshot_meta(META_YAML)
    scoring_cfg       = load_scoring_config(SCORING_YAML)
    scenarios_cfg     = load_scenarios(SCENARIOS_YAML)
    demo_profiles     = load_all_demo_profiles(DEMO_PROFILES_DIR)
    return bids_df, bids_err, dist_df, dist_err, meta, scoring_cfg, scenarios_cfg, demo_profiles


bids_df, bids_err, dist_df, dist_err, meta, scoring_cfg, scenarios_cfg, demo_profiles = _load_static()

if bids_err or dist_err:
    st.error("### ⚠️ Data Error")
    for e in bids_err + dist_err:
        st.error(e)
    st.info("Run `python scripts/make_sample_data.py` to generate sample data, then reload.")
    st.stop()

# ---------------------------------------------------------------------------
# Snapshot date
# ---------------------------------------------------------------------------
as_of_raw = meta.get("as_of", "")
try:
    as_of: date = date.fromisoformat(str(as_of_raw))
except Exception:
    as_of = date.today()
as_of_str = str(as_of)

has_sample = (bids_df["data_source"] == "SAMPLE").any()

# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------

def _init_session():
    """One-time session initialisation."""
    if "profiles" not in st.session_state:
        # Load demo profiles into session_state
        st.session_state.profiles = dict(demo_profiles)
    if not st.session_state.profiles:
        # Fallback: create a blank default profile
        blank, _ = validate_and_build({
            "profile_id": "default",
            "business_name": "My Business",
            "base_location": "Panipat, Haryana",
            "delivery_radius_km": 250,
            "max_emd_inr": 50000,
        })
        st.session_state.profiles["default"] = blank

    if "active_profile_id" not in st.session_state:
        st.session_state.active_profile_id = next(iter(st.session_state.profiles))
    if "session_overrides" not in st.session_state:
        st.session_state.session_overrides = {}
    if "nl_filter" not in st.session_state:
        st.session_state.nl_filter = {}
    if "nl_raw_output" not in st.session_state:
        st.session_state.nl_raw_output = ""
    if "nl_warnings" not in st.session_state:
        st.session_state.nl_warnings = []
    if "nl_parsed" not in st.session_state:
        st.session_state.nl_parsed = {}
    # AI reachability – check once per session (cached in session_state)
    if "ai_status" not in st.session_state:
        st.session_state.ai_status = None  # (ok: bool, label: str) or None


_init_session()


def profile_override_key(profile_id: str) -> str:
    return f"profile_overrides_{profile_id}"


def get_profile_overrides(profile_id: str) -> dict:
    key = profile_override_key(profile_id)
    return dict(st.session_state.get(key, {}))


def set_profile_overrides(profile_id: str, overrides: dict) -> None:
    st.session_state[profile_override_key(profile_id)] = dict(overrides or {})


def clear_profile_overrides(profile_id: str) -> None:
    st.session_state[profile_override_key(profile_id)] = {}


def profile_nl_filter_key(profile_id: str) -> str:
    return f"nl_filter_{profile_id}"


def get_profile_nl_filter(profile_id: str) -> dict:
    key = profile_nl_filter_key(profile_id)
    return dict(st.session_state.get(key, {}))


def clear_profile_nl_filter(profile_id: str) -> None:
    st.session_state[profile_nl_filter_key(profile_id)] = {}


def active_profile() -> SellerProfile:
    pid = st.session_state.active_profile_id
    return st.session_state.profiles[pid]


def get_effective_profile(profile_id: str | None = None) -> SellerProfile:
    pid = profile_id or st.session_state.active_profile_id
    base = st.session_state.profiles[pid]
    return compute_effective_profile(base, get_profile_overrides(pid))


def active_diary() -> list:
    return get_diary(st.session_state, st.session_state.active_profile_id)


# ---------------------------------------------------------------------------
# Banners (always visible)
# ---------------------------------------------------------------------------
st.markdown(
    f'<div class="banner-snapshot">📅 Snapshot data as of {as_of_str}. '
    f'Verify everything on the official GeM bid document.</div>',
    unsafe_allow_html=True,
)
if has_sample:
    st.markdown(
        '<div class="banner-sample">🔴 SAMPLE DATA – Synthetic bids for demo only. '
        'Replace data/bids.csv with your real GeM snapshot.</div>',
        unsafe_allow_html=True,
    )
st.markdown(
    '<div class="banner-demo-auth">🔒 Demo: no authentication. '
    'Real accounts and persistent storage are on the roadmap.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar: Profile Switcher
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎯 BidMitra")
    st.caption("GeM bid shortlister for industrial suppliers")
    st.divider()

    # ---- Profile selector ----
    prof_ids = list(st.session_state.profiles.keys())
    prof_labels = {pid: st.session_state.profiles[pid].business_name or pid for pid in prof_ids}
    current_idx = prof_ids.index(st.session_state.active_profile_id) if st.session_state.active_profile_id in prof_ids else 0

    selected_id = st.selectbox(
        "Active Profile",
        options=prof_ids,
        format_func=lambda pid: prof_labels[pid],
        index=current_idx,
        key="profile_selector",
    )
    if selected_id != st.session_state.active_profile_id:
        st.session_state.active_profile_id = selected_id
        clear_profile_overrides(selected_id)
        clear_profile_nl_filter(selected_id)
        st.session_state.nl_parsed = {}
        st.rerun()

    prof = active_profile()
    current_overrides = get_profile_overrides(st.session_state.active_profile_id)

    # ---- Quick profile overrides ----
    st.markdown("### Profile Overrides")
    with st.form(key=f"override_form_{st.session_state.active_profile_id}"):
        radius = st.slider(
            "Delivery radius (km)", 50, 1000,
            value=int(current_overrides.get("delivery_radius_km", prof.delivery_radius_km)),
            step=50, key=f"sb_radius_{st.session_state.active_profile_id}",
        )
        max_emd = st.number_input(
            "Max EMD (₹)", 0, 10_000_000,
            value=int(current_overrides.get("max_emd_inr", prof.max_emd_inr)),
            step=5000, key=f"sb_emd_{st.session_state.active_profile_id}",
        )
        active_fams = current_overrides.get("active_families", list(prof.item_families.keys()))
        st.markdown("**Item families**")
        selected_fams = []
        for fam in prof.item_families:
            checked = st.checkbox(
                fam.replace("_", " ").title(),
                value=(fam in active_fams),
                key=f"fam_{st.session_state.active_profile_id}_{fam}",
            )
            if checked:
                selected_fams.append(fam)
        include_adj = st.checkbox(
            "Include adjacent items",
            value=bool(current_overrides.get("include_adjacent", False)),
            key=f"sb_adj_{st.session_state.active_profile_id}",
        )

        c1, c2 = st.columns(2)
        with c1:
            applied = st.form_submit_button("Apply", use_container_width=True, type="primary")
        with c2:
            reset = st.form_submit_button("Reset", use_container_width=True)

        if applied:
            set_profile_overrides(st.session_state.active_profile_id, {
                "delivery_radius_km": radius, "max_emd_inr": max_emd,
                "active_families": selected_fams or list(prof.item_families.keys()),
                "include_adjacent": include_adj,
            })
            clear_profile_nl_filter(st.session_state.active_profile_id)
            st.session_state.nl_parsed = {}
            st.rerun()
        if reset:
            clear_profile_overrides(st.session_state.active_profile_id)
            clear_profile_nl_filter(st.session_state.active_profile_id)
            st.session_state.nl_parsed = {}
            st.rerun()

    st.divider()

    # ---- Create new profile ----
    with st.expander("➕ Create new profile"):
        new_name = st.text_input("Business name", key="new_prof_name", max_chars=200)
        new_loc  = st.text_input("Base location (District, State)", value="Panipat, Haryana", key="new_prof_loc")
        new_rad  = st.number_input("Radius (km)", 50, 3000, value=250, step=50, key="new_prof_rad")
        new_emd  = st.number_input("Max EMD (₹)", 0, 10_000_000, value=50000, step=5000, key="new_prof_emd")
        if st.button("Create Profile", key="create_prof_btn"):
            if not new_name.strip():
                st.error("Business name is required.")
            else:
                try:
                    np, warns = validate_and_build({
                        "business_name": new_name.strip(),
                        "base_location": new_loc.strip() or "Panipat, Haryana",
                        "delivery_radius_km": new_rad,
                        "max_emd_inr": new_emd,
                    })
                    pid = np.profile_id
                    # Make unique if clash
                    if pid in st.session_state.profiles:
                        import time
                        pid = f"{pid}_{int(time.time()) % 10000}"
                        np.profile_id = pid
                    st.session_state.profiles[pid] = np
                    st.session_state.active_profile_id = pid
                    st.session_state.session_overrides = {}
                    for w in warns:
                        st.warning(w)
                    st.success(f"Profile '{new_name}' created!")
                    st.rerun()
                except ProfileValidationError as exc:
                    st.error(f"Validation error: {exc}")

    # ---- JSON Export / Import ----
    with st.expander("📤 Export / Import profile"):
        diary_entries = active_diary()
        export_str = export_profile_json(prof, export_diary(diary_entries))
        st.download_button(
            "Download profile JSON",
            data=export_str,
            file_name=f"{prof.profile_id}_bidmitra.json",
            mime="application/json",
            key="export_btn",
        )
        uploaded = st.file_uploader("Import profile JSON", type=["json"], key="import_upload")
        if uploaded is not None:
            try:
                raw_str = uploaded.read().decode("utf-8")
                imp_prof, imp_diary, imp_warns = import_profile_json(raw_str)
                pid = imp_prof.profile_id
                if pid in st.session_state.profiles:
                    import time
                    pid = f"{pid}_{int(time.time()) % 10000}"
                    imp_prof.profile_id = pid
                st.session_state.profiles[pid] = imp_prof
                # Import diary
                key = f"diary_{pid}"
                st.session_state[key] = import_diary(imp_diary, pid)
                st.session_state.active_profile_id = pid
                for w in imp_warns:
                    st.warning(w)
                st.success(f"Imported '{imp_prof.business_name}'")
                st.rerun()
            except ProfileValidationError as exc:
                st.error(f"Import failed: {exc}")
            except Exception as exc:
                st.error(f"Could not read file: {exc}")

    st.caption(f"📍 {prof.base_location}")
    st.caption(f"Profile completeness: {prof.completeness_pct()}%")


# ---------------------------------------------------------------------------
# Active scoring
# ---------------------------------------------------------------------------
profile_overrides = get_profile_overrides(st.session_state.active_profile_id)
merged_overrides: dict = dict(profile_overrides)
for k, v in get_profile_nl_filter(st.session_state.active_profile_id).items():
    merged_overrides[k] = v

# Lazy AI reachability check – runs once per session, non-blocking
if st.session_state.ai_status is None:
    st.session_state.ai_status = llm_module.check_reachable(timeout=2.5)
_ai_ok, _ai_label = st.session_state.ai_status

scorer_profile = get_effective_profile().to_scorer_profile()
results: list[BidResult] = score_bids(
    bids_df, scorer_profile, dist_df, scoring_cfg, as_of, merged_overrides
)

bid_count   = sum(1 for r in results if r.verdict == "Bid")
maybe_count = sum(1 for r in results if r.verdict == "Maybe")
diary_entries = active_diary()
diary_stats = compute_stats(diary_entries)
soon_bids   = closing_soon(results, diary_entries, days_threshold=2.0)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_dash, tab_short, tab_whatif, tab_about = st.tabs(
    ["🏠 Dashboard", "📋 Shortlist", "🔓 What-If", "ℹ️ About"]
)


# ============================================================
# TAB 1: DASHBOARD
# ============================================================
with tab_dash:
    prof = active_profile()
    effective = get_effective_profile()

    # ---- Profile card: shows active (possibly overridden) values ----
    pct = prof.completeness_pct()
    pct_color = "#16a34a" if pct >= 80 else "#d97706" if pct >= 50 else "#dc2626"

    active_radius = effective.delivery_radius_km
    active_emd    = effective.max_emd_inr
    radius_ovr = " <span style='color:#f59e0b;font-size:0.72rem'>(override)</span>" \
        if float(active_radius) != float(prof.delivery_radius_km) else ""
    emd_ovr = " <span style='color:#f59e0b;font-size:0.72rem'>(override)</span>" \
        if float(active_emd) != float(prof.max_emd_inr) else ""

    st.markdown(f"""
<div class="profile-card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
    <div>
      <h2 style="margin:0; font-size:1.4rem;">{prof.business_name or "Unnamed Business"}</h2>
      <span style="color:#6b7280; font-size:0.9rem;">📍 {prof.base_location} &nbsp;·&nbsp;
        Radius {float(active_radius):.0f} km{radius_ovr} &nbsp;·&nbsp; Max EMD ₹{float(active_emd):,.0f}{emd_ovr}</span>
    </div>
    <div style="text-align:right;">
      <span style="font-size:1.1rem; font-weight:700; color:{pct_color};">{pct}%</span><br>
      <span style="font-size:0.75rem; color:#6b7280;">Profile completeness</span>
    </div>
  </div>
  <div class="completeness-bar-outer" style="margin:10px 0 4px;">
    <div class="completeness-bar-inner" style="width:{pct}%; background:{pct_color};"></div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Self-declared chips row
    sdecl_chips = []
    if prof.mse_declared:
        sdecl_chips.append('<span class="chip-neutral">🏷️ MSE (Self-declared)</span>')
    if prof.startup_declared:
        sdecl_chips.append('<span class="chip-neutral">🚀 Startup (Self-declared)</span>')
    for cert in prof.certifications:
        sdecl_chips.append(f'<span class="chip-neutral">📜 {cert} (Self-declared)</span>')
    for doc, has_it in prof.documents_declared.items():
        if has_it:
            sdecl_chips.append(f'<span class="chip-good">✅ {doc.upper()} doc declared</span>')
    if sdecl_chips:
        st.markdown(" ".join(sdecl_chips), unsafe_allow_html=True)
    st.caption("⚠️ All badges above are self-declared. Verification against official sources (GSTIN, Udyam) is on the roadmap.")

    # Item families chips – human-friendly names
    fam_chips = " ".join(
        f'<span class="chip-good">🔧 {f.replace("_", " ").title()}</span>'
        for f in (effective.item_families.keys())
    )
    if fam_chips:
        st.markdown(fam_chips, unsafe_allow_html=True)

    # Completeness suggestions
    suggestions = prof.completeness_suggestions()
    if suggestions:
        st.markdown("**💡 Complete your profile:**")
        for s in suggestions:
            st.markdown(f"- {s}")

    if prof.years_in_business is not None:
        st.caption(f"🏢 {prof.entity_type or 'Entity'} · {prof.years_in_business} years in business")

    st.divider()

    # ---- Key metrics ----
    st.markdown("### 📊 At a Glance")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        with st.container(border=True):
            st.markdown('<div class="metric-title">Matching bids</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-split"><div><div class="metric-split-label">Bid</div><div class="metric-split-value">{bid_count}</div></div><div><div class="metric-split-label">Maybe</div><div class="metric-split-value">{maybe_count}</div></div></div>', unsafe_allow_html=True)

    with c2:
        with st.container(border=True):
            st.markdown('<div class="metric-title">Closing within 2 days</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-number">{len(soon_bids)}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-subtext">tender deadlines</div>', unsafe_allow_html=True)

    with c3:
        with st.container(border=True):
            st.markdown('<div class="metric-title">Saved</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-number">{diary_stats.saved}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-subtext">tracked for follow-up</div>', unsafe_allow_html=True)

    with c4:
        with st.container(border=True):
            st.markdown('<div class="metric-title">Applied</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-number">{diary_stats.applied}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-subtext">self-reported</div>', unsafe_allow_html=True)

    with st.expander("Track record (self-reported in BidMitra)", expanded=False):
        if not diary_entries:
            st.write("No entries yet")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("🏆 Won", diary_stats.won)
            c2.metric("❌ Lost", diary_stats.lost)
            if diary_stats.win_rate_pct is not None:
                c3.metric("Win Rate", f"{diary_stats.win_rate_pct}%",
                          help="Self-reported in BidMitra · not from GeM")
            else:
                c3.metric("Win Rate", "—", help=diary_stats.win_rate_note)
                c3.caption(diary_stats.win_rate_note)

    st.divider()

    # ---- Closing Soon strip ----
    if soon_bids:
        st.markdown("### ⏰ Closing Soon (within 2 days)")
        for r in soon_bids[:5]:
            if r.days_left is None:
                days_str = "?"
            elif r.days_left < 1:
                hours = max(1, round(r.days_left * 24))
                days_str = f"{hours} hours"
            else:
                days_str = f"{r.days_left:.1f} days"
            e = get_entry(st.session_state, prof.profile_id, r.bid_number)
            status_label = f" · {e.status}" if e else ""
            st.markdown(
                f'<div class="closing-soon-card">⚡ <strong>{r.title}</strong> '
                f'<span style="color:#b45309">({days_str} left{status_label})</span>'
                f' · #{r.bid_number}</div>',
                unsafe_allow_html=True,
            )

    # ---- Top 5 matches ----
    st.markdown("### 🎯 Top Matches")
    top5 = [r for r in results if r.verdict in ("Bid", "Maybe")][:5]
    if not top5:
        st.info("No matching bids with current profile. Adjust filters in the sidebar.")
    else:
        for r in top5:
            bc = "badge-bid" if r.verdict == "Bid" else "badge-maybe"
            sc = "#16a34a" if r.verdict == "Bid" else "#d97706"
            chip_html = " ".join(
                f'<span class="chip-{c.level}">{c.emoji} {c.text}</span>'
                for c in r.chips[:3]
            )
            st.markdown(f"""
<div class="bid-card">
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
    <div style="flex:1;"><strong>{r.title}</strong>
      <span style="font-size:0.78rem; color:#6b7280;"> · #{r.bid_number}</span></div>
    <div><span class="{bc}">{r.verdict}</span>
      <strong style="color:{sc}; margin-left:8px;">{r.score:.0f}</strong>/100</div>
  </div>
  <div style="margin-top:6px;">{chip_html}</div>
</div>
""", unsafe_allow_html=True)

    st.divider()

    # ---- Bid Diary table ----
    st.markdown("### 📒 Bid Diary")
    st.caption("Self-reported in BidMitra · not from GeM")
    if not diary_entries:
        st.info("No diary entries yet. Mark bids as Saved/Applied/Won from the Shortlist tab.")
    else:
        diary_rows = [
            {
                "Date": e.date_recorded,
                "Bid #": e.bid_number,
                "Title": e.title[:60] + ("…" if len(e.title) > 60 else ""),
                "Status": e.status,
                "Note": e.note,
            }
            for e in sorted(diary_entries, key=lambda x: x.date_recorded, reverse=True)
        ]
        st.dataframe(pd.DataFrame(diary_rows), use_container_width=True, hide_index=True)


# ============================================================
# TAB 2: SHORTLIST
# ============================================================
with tab_short:
    prof = active_profile()
    effective = get_effective_profile()

    # ---- Hinglish query ----
    st.markdown("### 🗣️ Apni requirement likho")
    col_nl, col_badge = st.columns([3, 1])

    with col_nl:
        nl_sentence = st.text_input(
            "Hindi / Hinglish / English",
            placeholder="Panipat ke paas valve, EMD 30 hazaar tak",
            label_visibility="collapsed",
            key="nl_input",
        )
    with col_badge:
        model_name = llm_module.model_display_name()
        _badge_ok, _badge_label = st.session_state.ai_status or (False, "not configured")
        badge_color = "#16a34a" if _badge_ok else "#dc2626"
        st.markdown(
            f'<div class="ai-badge">🤖 {model_name}<br>'
            f'<span style="font-size:0.7rem; color:{badge_color};">{_badge_label}</span></div>',
            unsafe_allow_html=True,
        )
        lic_url = llm_module.license_url()
        if lic_url:
            st.markdown(f"[Model license]({lic_url})")
        if not _badge_ok:
            st.caption("Search stays available with local rule-based parsing; install/configure a model for AI parsing.")

    if nl_sentence and st.button("🔍 Search", key="nl_search_btn"):
        item_families = list(prof.item_families.keys())
        with st.spinner("Understanding your request…"):
            filt, raw, warns = parse_query(nl_sentence, item_families, dist_df)
        if filt is None:
            st.warning("Search could not parse that request. Try naming an item, district, EMD, or radius.")
        else:
            st.session_state.nl_parsed = filt
            st.session_state.nl_raw_output = raw
            st.session_state.nl_warnings = warns
            st.session_state[profile_nl_filter_key(st.session_state.active_profile_id)] = filter_to_session_overrides(filt, effective.to_scorer_profile())
            st.rerun()

    # AI interpretation panel
    if st.session_state.nl_parsed:
        st.markdown("#### 🤖 Search ne ye samjha *(editable)*")
        parsed = st.session_state.nl_parsed
        ca, cb, cc = st.columns(3)
        with ca:
            fam_opts = ["(any)"] + list(prof.item_families.keys())
            fam_friendly = {k: k.replace("_", " ").title() for k in prof.item_families}
            fam_opts_display = ["(any)"] + [fam_friendly[k] for k in prof.item_families]
            cur_fam = parsed.get("item_family", "")
            cur_idx = (list(prof.item_families.keys()).index(cur_fam) + 1
                       if cur_fam in prof.item_families else 0)
            new_item_display = st.selectbox(
                "Item family", fam_opts_display, index=cur_idx, key="nl_edit_item"
            )
            # Map display name back to key
            new_item = (list(prof.item_families.keys())[fam_opts_display.index(new_item_display) - 1]
                        if new_item_display != "(any)" else "(any)")
        with cb:
            new_emd = st.number_input("Max EMD (₹)",
                value=float(parsed.get("max_emd_inr") or prof.max_emd_inr),
                step=1000.0, key="nl_edit_emd")
        with cc:
            new_radius = st.number_input("Radius (km)",
                value=float(parsed.get("radius_km") or prof.delivery_radius_km),
                step=10.0, key="nl_edit_radius")

        for w in st.session_state.nl_warnings:
            st.caption(f"ℹ️ {w}")

        ca2, cb2 = st.columns([1, 3])
        with ca2:
            if st.button("Apply AI filter", key="nl_apply_btn", type="primary"):
                nf: dict = {}
                if new_item != "(any)":
                    nf["active_families"] = [new_item]
                nf["max_emd_inr"] = new_emd
                nf["delivery_radius_km"] = new_radius
                st.session_state[profile_nl_filter_key(st.session_state.active_profile_id)] = nf
                st.rerun()
        with cb2:
            if st.button("Reset AI filter", key="nl_reset_btn"):
                clear_profile_nl_filter(st.session_state.active_profile_id)
                st.session_state.nl_parsed = {}
                st.session_state.nl_raw_output = ""
                st.session_state.nl_warnings = []
                st.rerun()

        with st.expander("Raw model output"):
            st.code(st.session_state.nl_raw_output or "(no output)", language="json")
            st.caption("*AI sirf aapki baat samajhta hai. Matching code karta hai.*")

    st.divider()

    # ---- Metrics ----
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Shortlisted", f"{len(results)} of {len(bids_df)}")
    m2.metric("✅ Bid", bid_count)
    m3.metric("⚠️ Maybe", maybe_count)
    m4.metric("⏰ Closing ≤2 days", len(soon_bids))

    # ---- Bid cards ----
    if not results:
        st.markdown("---")
        st.info(
            "**No matching bids found.**\n\n"
            "Try: widening the radius · raising EMD limit · enabling adjacent items."
        )
    else:
        BADGE = {"Bid": "badge-bid", "Maybe": "badge-maybe", "Skip": "badge-skip"}
        SC    = {"Bid": "#16a34a", "Maybe": "#d97706", "Skip": "#6b7280"}

        for r in results:
            bc = BADGE.get(r.verdict, "badge-skip")
            sc = SC.get(r.verdict, "#6b7280")
            bar_pct = int(r.score)
            chip_html = " ".join(
                f'<span class="chip-{c.level}">{c.emoji} {c.text}</span>' for c in r.chips
            )
            emd_str  = f"₹{r.emd_inr:,.0f}" if r.emd_inr is not None else "Check"
            days_str = f"{r.days_left:.0f} days" if r.days_left is not None else "Check"

            st.markdown(f"""
<div class="bid-card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
    <div style="flex:1; min-width:200px;">
      <strong style="font-size:1rem;">{r.title}</strong><br>
      <span style="font-size:0.78rem; color:#6b7280;">#{r.bid_number} · {r.buyer_org}</span>
    </div>
    <div style="text-align:right;">
      <span class="{bc}">{r.verdict}</span>
      <br><span style="font-size:1.1rem; font-weight:700; color:{sc};">{r.score:.0f}</span>
      <span style="font-size:0.72rem; color:#9ca3af;">/100</span>
    </div>
  </div>
  <div class="score-bar-outer"><div class="score-bar-inner" style="width:{bar_pct}%; background:{sc};"></div></div>
  <div style="margin:6px 0;">{chip_html}</div>
  <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:0.82rem; color:#374151; margin-top:4px;">
    <span>📍 {r.consignee_district}, {r.consignee_state}</span>
    <span>💰 EMD {emd_str}</span>
    <span>⏰ Closes {days_str}</span>
  </div>
</div>
""", unsafe_allow_html=True)

            # ---- Diary status buttons ----
            existing = get_entry(st.session_state, prof.profile_id, r.bid_number)
            cur_status = existing.status if existing else ""

            with st.expander(f"📌 Mark bid · {r.bid_number}" + (f" [{cur_status}]" if cur_status else "")):
                note_val = existing.note if existing else ""
                new_note = st.text_input("Note (optional)", value=note_val, key=f"note_{r.bid_number}", max_chars=300)
                btn_cols = st.columns(len(VALID_STATUSES) + 1)
                for i, status in enumerate(VALID_STATUSES):
                    btn_type = "primary" if cur_status == status else "secondary"
                    if btn_cols[i].button(status, key=f"diary_{status}_{r.bid_number}", type=btn_type):
                        upsert_entry(
                            st.session_state, prof.profile_id,
                            r.bid_number, r.title, status, new_note, as_of_str,
                        )
                        st.rerun()
                if cur_status and btn_cols[-1].button("Clear", key=f"diary_clear_{r.bid_number}"):
                    remove_entry(st.session_state, prof.profile_id, r.bid_number)
                    st.rerun()

                if r.data_source == "SAMPLE":
                    st.caption("🔴 Sample bid: no real document")
                elif r.doc_url:
                    st.markdown(f"[🔗 Open official bid document]({r.doc_url})")
                else:
                    st.caption("No document URL available.")
                with st.expander("Raw fields"):
                    st.json({
                        "bid_number": r.bid_number, "title": r.title,
                        "buyer_org": r.buyer_org,
                        "consignee_district": r.consignee_district,
                        "emd_inr": r.emd_inr,
                        "end_datetime": r.end_datetime,
                        "distance_km": round(r.distance_km, 1) if r.distance_km else None,
                        "days_left": round(r.days_left, 1) if r.days_left else None,
                        "score": r.score, "verdict": r.verdict,
                        "data_source": r.data_source,
                    })

    st.divider()

    # ---- Almost Matched ----
    st.markdown("### 🔍 Almost Matched")
    st.caption("Bids that narrowly missed your profile — small adjustments could unlock them.")
    almost = find_almost_matches(bids_df, scorer_profile, dist_df, scoring_cfg, as_of, results)
    if not almost:
        st.info("No near-miss bids found with the current profile.")
    else:
        for am in almost:
            st.markdown(f"**{am.title}** (`{am.bid_number}`)  \n🔶 Missed because: *{am.reason}*")


# ============================================================
# TAB 3: WHAT-IF
# ============================================================
with tab_whatif:
    st.markdown("### 🔓 What-If Scenarios")
    st.caption("How many more bids would you see if you changed one thing?")

    if not scenarios_cfg:
        st.warning("No scenarios configured. Check config/scenarios.yaml.")
    else:
        scenario_results = run_scenarios(
            scenarios_cfg, bids_df, scorer_profile, dist_df, scoring_cfg, as_of, results
        )

        if not any(s.total_extra > 0 for s in scenario_results):
            st.info("No scenario unlocks additional bids. Your profile may already be quite broad.")

        rows = [
            {
                "Scenario": s.label,
                "Extra Bid": s.extra_bid_count,
                "Extra Maybe": s.extra_maybe_count,
                "Total Unlocked": s.total_extra,
                "Example Bids": " · ".join(s.example_titles[:3]) or "—",
            }
            for s in scenario_results
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        chart_data = pd.DataFrame({
            "Scenario": [s.label for s in scenario_results],
            "Unlocked":  [s.total_extra for s in scenario_results],
        }).set_index("Scenario")
        if chart_data["Unlocked"].sum() > 0:
            st.bar_chart(chart_data)

        for s in scenario_results:
            if s.total_extra > 0:
                st.success(
                    f"**{s.label}** → unlocks **{s.total_extra}** more bid(s)  \n"
                    + (f"Examples: {', '.join(s.example_titles[:3])}" if s.example_titles else "")
                )


# ============================================================
# TAB 4: ABOUT
# ============================================================
with tab_about:
    st.markdown("### ℹ️ About BidMitra")
    st.markdown("""
**BidMitra** is a decision-support tool for small suppliers on India's
[GeM portal](https://gem.gov.in) (Government e-Marketplace).

---

#### 🤖 AI Model
- The AI's **only job** is converting a typed sentence (Hindi/Hinglish/English)
  to a JSON filter. It **never sees** bid data or the supplier profile.
- All matching, scoring, and ranking is **deterministic Python code**.
- Runs **locally via Ollama** — your query never leaves your machine.
- Set `OPEN_LLM_MODEL` env var to your model (e.g., `phi3:mini`).

#### 👤 Profiles & Data
- All profile data is **self-declared**. Nothing is verified against official sources.
- Verification against GSTIN, Udyam and other official sources is on the roadmap.
- No login, no passwords, no persistent storage in this demo.
- Profiles and bid diary are stored in browser session only.

#### ⚠️ Disclaimer
BidMitra is a **decision-support tool**, not legal or commercial advice.
Always verify on the **official GeM bid document** before bidding.
""")
    st.divider()
    st.markdown("**Built with:** Streamlit · pandas · PyYAML · requests · pytest · MIT License")
