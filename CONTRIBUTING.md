# Contributing to BidMitra

Thank you for your interest! BidMitra is an open-source project and welcomes contributions.

> **Note:** This is a demo/hackathon project. All profile data is self-declared and not verified.
> Do not add any code that collects GSTIN, PAN, phone numbers, or identity data.

## Quick start

```bash
git clone https://github.com/your-org/bidmitra
cd bidmitra
pip install -r requirements.txt
python scripts/make_sample_data.py
streamlit run app.py           # open http://localhost:8501
python -m pytest tests/ -v     # all tests must pass
```

---

## How to add a district

1. Open `data/districts.csv`
2. Add a row: `DistrictName,StateName,lat,lon`
   - Coordinates are approximate district centroids (note this in your PR description)
   - States covered: Haryana, Punjab, Delhi, Uttar Pradesh, Rajasthan, Uttarakhand,
     Himachal Pradesh, Gujarat, Maharashtra
3. Run `python -m pytest tests/test_geo.py` to confirm no regressions
4. Submit a PR with a one-line description of why you added the district

---

## How to add an item family

1. Open `config/profile.yaml` (or a demo profile YAML in `config/demo_profiles/`)
2. Add a new family under `items:` with at least 2 synonyms:
   ```yaml
   items:
     new_family:
       - primary keyword
       - alternative keyword
   ```
3. Add matching titles to `scripts/make_sample_data.py` so the demo shows results
4. Run `python -m pytest tests/test_scoring.py`

---

## How to add a What-If scenario

1. Open `config/scenarios.yaml`
2. Add a new entry:
   ```yaml
   - id: my_scenario
     label: "Human-readable label"
     description: "One-line explanation"
     overrides:
       delivery_radius_km: "+50"   # relative: +N, *N, or absolute value
   ```
3. Run `python -m pytest tests/test_unlock.py`

---

## How to add a demo profile

1. Create `config/demo_profiles/my_profile.yaml` following the existing examples
2. All data must be clearly fictional (business name must start with "Demo:")
3. Extend `scripts/make_sample_data.py` to generate sample bids for the new profile
4. Run all tests: `python -m pytest tests/`

---

## Running tests

```bash
python -m pytest tests/ -v          # all tests
python -m pytest tests/test_geo.py  # specific module
```

## Running the submission check

```bash
python scripts/check_submission.py
```

---

## Code style

- Python 3.11, typed, short functions with docstrings
- No async, no database, no proprietary AI SDKs
- All new logic must have at least one unit test
- Deterministic code only — the AI model only converts text to JSON

## Honesty rules (non-negotiable)

- Never use "Verified" or "Trusted" as an active badge label
- All user-entered data is labelled "Self-declared"
- Win rate only shown when applied ≥ 5
- No collection of GSTIN, PAN, phone numbers, or identity data
- Profiles and diary stored in session_state only (no filesystem writes)
