# Good First Issues – BidMitra

These are beginner-friendly improvements to BidMitra. Each one is self-contained and comes with clear acceptance criteria.

---

## Issue 1: Add a new district to districts.csv

**Difficulty:** ⭐ Easy
**File:** `data/districts.csv`

Pick any district in Haryana, Punjab, Delhi, UP, Rajasthan, Uttarakhand, HP, Gujarat, or Maharashtra that is missing. Add a row with approximate centroid coordinates (lat/lon). Verify with `python -m pytest tests/test_geo.py`.

**Acceptance criteria:** At least one new district row, tests pass.

---

## Issue 2: Add a demo profile for a new business type

**Difficulty:** ⭐⭐ Easy
**Files:** `config/demo_profiles/`, `scripts/make_sample_data.py`

Create a YAML profile for a fictional supplier of a product type not yet covered (e.g., electrical cables, plumbing fittings). Business name must start with "Demo:". Add at least 10 sample bid titles in `make_sample_data.py`.

**Acceptance criteria:** Profile loads without errors, sample bids appear in Shortlist tab when profile is selected.

---

## Issue 3: Improve the completeness scoring rules

**Difficulty:** ⭐⭐ Medium
**File:** `src/profiles.py`

The current completeness function counts each field as filled/empty. Improve it to give partial credit (e.g., having 3+ item families scores higher than 1), or add a new field to the completeness calculation. Add a unit test for the new rule.

**Acceptance criteria:** `test_completeness_full_profile` still passes, at least one new test added.

---

## Issue 4: Add a new What-If scenario

**Difficulty:** ⭐⭐ Medium
**File:** `config/scenarios.yaml`

Add a scenario that isn't already there — for example "Accept MSE-only bids" or "Extend radius by 50 km". Verify it appears in the What-If tab and shows a meaningful gain on the sample data.

**Acceptance criteria:** Scenario shows in the table, `python -m pytest tests/test_unlock.py` passes.

---

## Issue 5: Add nl_examples.json evaluation sentences

**Difficulty:** ⭐⭐ Medium
**File:** `docs/nl_examples.json`

Add 5 new test sentences to `docs/nl_examples.json` covering edge cases not yet tested (e.g., a number written in words like "pachees hazaar", a state name instead of a district, a multi-word item family). Run `python scripts/eval_nlquery.py` to check the model handles them.

**Acceptance criteria:** Valid JSON with `sentence` and `expected` fields, no duplicate sentences.

---

## Issue 6: Improve closing-soon UI in the Dashboard

**Difficulty:** ⭐⭐⭐ Medium
**File:** `app.py` (Dashboard tab)

The closing-soon strip currently shows a plain HTML div. Replace it with a Streamlit-native component (e.g., `st.columns` with a progress bar showing time left as a percentage of a 14-day window). Keep the same data source (`diary.closing_soon()`).

**Acceptance criteria:** Closing-soon section looks visually distinct, no regression in tests.
