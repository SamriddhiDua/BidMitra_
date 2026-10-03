"""
scripts/check_submission.py – pre-submission checklist for BidMitra.

Prints pass/fail for each check and exits non-zero if any fail.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 encoding errors)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent   # bidmitra/ package directory

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results: list[tuple[str, str, str]] = []  # (status, check_name, detail)


def check(name: str, passed: bool, detail: str = "", warn_only: bool = False) -> None:
    if passed:
        results.append((PASS, name, detail))
    elif warn_only:
        results.append((WARN, name, detail))
    else:
        results.append((FAIL, name, detail))


# ---- LICENSE ----
license_path = ROOT / "LICENSE"
if license_path.exists():
    first_line = license_path.read_text(encoding="utf-8").strip().splitlines()[0]
    check("LICENSE file exists", True)
    check("LICENSE starts with 'MIT License'", first_line.startswith("MIT License"),
          f"Got: {first_line[:60]}")
else:
    check("LICENSE file exists", False, "Create LICENSE at repo root")

# ---- README headings ----
readme_path = ROOT / "README.md"
REQUIRED_HEADINGS = [
    "What it does", "Demo", "How to run", "AI model",
    "Key dependencies", "How it works", "How we built it",
    "Limits", "Roadmap", "Contributing",
]
if readme_path.exists():
    readme_text = readme_path.read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        check(f"README has heading: {heading}", heading.lower() in readme_text.lower(),
              f"Missing section: {heading}")
else:
    check("README.md exists", False)

# ---- No <FILL_ placeholders ----
FILL_FILES = ["README.md", "THIRD_PARTY.md", "LICENSE"]
for fname in FILL_FILES:
    fpath = ROOT / fname
    if fpath.exists():
        text = fpath.read_text(encoding="utf-8")
        has_fill = "<FILL_" in text
        check(f"No <FILL_ placeholders in {fname}", not has_fill,
              "Replace all <FILL_...> placeholders before submitting", warn_only=True)

# ---- No proprietary AI SDKs ----
req_path = ROOT / "requirements.txt"
BANNED = ["openai", "anthropic", "google-generativeai", "google-genai", "cohere", "mistralai"]
if req_path.exists():
    req_text = req_path.read_text(encoding="utf-8").lower()
    for pkg in BANNED:
        check(f"requirements.txt does not contain '{pkg}'", pkg not in req_text)
else:
    check("requirements.txt exists", False)

# ---- .env not tracked by git ----
try:
    result = subprocess.run(
        ["git", "ls-files", ".env"],
        capture_output=True, text=True, cwd=ROOT, timeout=5
    )
    env_tracked = bool(result.stdout.strip())
    check(".env is not tracked by git", not env_tracked,
          ".env is in git history — add it to .gitignore")
except Exception:
    check(".env git check", True, "(git not available, skipped)", warn_only=True)

# ---- bids.csv ----
bids_path = ROOT / "data" / "bids.csv"
check("data/bids.csv exists", bids_path.exists(),
      "Run: python scripts/make_sample_data.py")
if bids_path.exists():
    text = bids_path.read_text(encoding="utf-8")
    if "SAMPLE" in text:
        results.append((WARN, "data/bids.csv contains SAMPLE rows",
                        "Replace with real GeM snapshot for final submission"))

# ---- THIRD_PARTY.md ----
check("THIRD_PARTY.md exists", (ROOT / "THIRD_PARTY.md").exists())

# ---- CONTRIBUTING.md ----
check("CONTRIBUTING.md exists", (ROOT / "CONTRIBUTING.md").exists())

# ---- Honesty: no "Verified" badge label in app.py ----
import re
# Try both ROOT/app.py and ROOT/../app.py (handles running from different cwd)
for candidate in [ROOT / "app.py", ROOT.parent / "app.py"]:
    if candidate.exists():
        app_text = candidate.read_text(encoding="utf-8")
        bad = re.search(r'"(Verified|Trusted)"', app_text)
        check("app.py has no hard-coded 'Verified'/'Trusted' badge",
              bad is None, "Remove standalone Verified/Trusted badge labels",
              warn_only=True)
        break
else:
    check("app.py found for honesty check", False, "app.py not found", warn_only=True)

# ---- Run tests ----
print("\nRunning pytest…")
test_result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
    cwd=ROOT, capture_output=False
)
check("All tests pass", test_result.returncode == 0)

# ---- Print summary ----
print("\n" + "=" * 60)
print("SUBMISSION CHECKLIST RESULTS")
print("=" * 60)
failures = 0
for status, name, detail in results:
    line = f"  {status}  {name}"
    if detail:
        line += f"\n         → {detail}"
    print(line)
    if status == FAIL:
        failures += 1

print("=" * 60)
if failures == 0:
    print(f"All checks passed ({len(results)} total). Ready to submit!")
else:
    print(f"{failures} check(s) FAILED. Fix before submitting.")
    sys.exit(1)
