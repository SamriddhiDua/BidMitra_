"""
scripts/eval_nlquery.py – Evaluate NL query accuracy against the real local model.

Runs each sentence in docs/nl_examples.json through the actual model and compares
the output field-by-field against the expected JSON.
Never hardcodes results; prints live accuracy from the real model call.

Usage:
  # Ensure the model is running (Ollama or compatible endpoint)
  python scripts/eval_nlquery.py
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.data_loader import load_districts
from src.nlquery import parse_query

EXAMPLES_FILE = ROOT / "docs" / "nl_examples.json"
FIELDS = ["item_family", "max_emd_inr", "radius_km", "location_text"]


def load_examples() -> list[dict]:
    with open(EXAMPLES_FILE, encoding="utf-8") as f:
        return json.load(f)


def field_match(got: dict, expected: dict, field: str) -> bool:
    """
    Compare a single field. None == null. Numeric values compared as float.
    """
    g = got.get(field)
    e = expected.get(field)
    if e is None:
        return g is None
    if g is None:
        return False
    if isinstance(e, (int, float)):
        try:
            return abs(float(g) - float(e)) < 1.0
        except (TypeError, ValueError):
            return False
    return str(g).lower() == str(e).lower()


def main():
    examples = load_examples()
    dist_df, dist_err = load_districts(ROOT / "data" / "districts.csv")
    if dist_err:
        print(f"Error loading districts: {dist_err}")
        sys.exit(1)

    # Collect item families from the Panipat demo profile (or profile.yaml)
    import yaml
    profile_path = ROOT / "config" / "profile.yaml"
    try:
        with open(profile_path, encoding="utf-8") as f:
            profile = yaml.safe_load(f)
        item_families = list(profile.get("items", {}).keys())
    except Exception:
        item_families = ["timing_belts", "pulleys", "valves"]

    print(f"\nEvaluating {len(examples)} examples against the real model…")
    print(f"Item families in scope: {item_families}\n")
    print(f"{'#':>3}  {'Field':<15} {'Pass':>5}  Sentence")
    print("-" * 80)

    total_fields = 0
    passed_fields = 0

    for i, ex in enumerate(examples, 1):
        sentence = ex["sentence"]
        expected = ex["expected"]
        note = ex.get("note", "")

        result, raw, warns = parse_query(sentence, item_families, dist_df, timeout=30)

        if result is None:
            print(f"{i:>3}  (model unavailable – skipping)  [{sentence[:50]}]")
            continue

        row_pass = []
        for field in FIELDS:
            ok = field_match(result, expected, field)
            row_pass.append(ok)
            total_fields += 1
            if ok:
                passed_fields += 1

        status = "✅" if all(row_pass) else "❌"
        field_str = " ".join(
            f"{f[:3]}={'✓' if ok else '✗'}"
            for f, ok in zip(FIELDS, row_pass)
        )
        print(f"{i:>3}  {status}  {field_str}  [{sentence[:45]}]")
        if not all(row_pass):
            print(f"         Expected: {expected}")
            print(f"         Got:      {result}")
            if note:
                print(f"         Note:     {note}")

    print("\n" + "=" * 80)
    if total_fields > 0:
        accuracy = round((passed_fields / total_fields) * 100, 1)
        print(f"Field-level accuracy: {passed_fields}/{total_fields} = {accuracy}%")
        print(f"\nPaste this number in README.md section 4: eval accuracy = {accuracy}%")
    else:
        print("No fields evaluated (model may be unavailable).")


if __name__ == "__main__":
    main()
